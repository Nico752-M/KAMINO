"""Administración de cuentas y perfiles de permisos individuales."""
import re

import oracledb
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

import db
from rutas.alumnos import _auditar
from auth import login_required, permiso_requerido
from permisos import GRUPOS_PERMISOS, PERMISOS, PERMISOS_POR_ROL, ROLES
from servicios.matriculas import TIPOS_TARIFA
from utils import invalidar_cache, parsear_pesos

bp = Blueprint("usuarios", __name__, url_prefix="/admin/usuarios")

# Cuentas principales: nunca se pueden eliminar (se comparan por usuario, sin importar mayúsculas).
USUARIOS_PROTEGIDOS = {"admin", "admin 2"}


class DatosInvalidos(Exception):
    pass


def _precio_tarifa(valor: str) -> int | None:
    return parsear_pesos(valor)


def _permisos_enviados() -> set[str]:
    seleccionados = set(request.form.getlist("permisos"))
    desconocidos = seleccionados - PERMISOS.keys()
    if desconocidos:
        raise DatosInvalidos("La selección contiene permisos no válidos.")
    return seleccionados


def _validar_usuario(nombre: str, rol: str, perfil: str, permisos: set[str]):
    if not nombre or len(nombre) > 100:
        raise DatosInvalidos("El nombre es obligatorio y admite hasta 100 caracteres.")
    if rol not in ROLES:
        raise DatosInvalidos("La categoría de usuario no es válida.")
    if not perfil or len(perfil) > 100:
        raise DatosInvalidos("El nombre del perfil personal es obligatorio (máximo 100 caracteres).")
    if not permisos.issubset(PERMISOS):
        raise DatosInvalidos("La selección contiene permisos no válidos.")
    if not permisos.intersection({"ver_dashboard", "ver_alumnos", "ver_caja", "ver_tramites", "ver_tienda", "ver_cuentas", "ver_bancos"}):
        raise DatosInvalidos("Asigna al menos permiso para consultar una pantalla.")
    dependencias = {
        "crear_matricula": "ver_alumnos",
        "editar_alumnos": "ver_alumnos",
        "eliminar_alumnos": "ver_alumnos",
        "ver_historial_pagos": "ver_alumnos",
        "gestionar_costos": "ver_ganancias",
        "ver_ganancias": "ver_alumnos",
        "registrar_pagos": "ver_alumnos",
        "anular_pagos": "ver_alumnos",
        "gestionar_caja": "ver_caja",
        "marcar_runt": "ver_tramites",
        "ver_todas_cajas": "ver_caja",
        "editar_cierres": "ver_caja",
        "gestionar_bancos": "ver_bancos",
        "tienda_anular": "ver_tienda",
        "tienda_inventario": "ver_tienda",
        "tienda_servicios": "ver_tienda",
        "tienda_caja": "ver_tienda",
        "tienda_ganancias": "ver_tienda",
        "tienda_cuentas": "ver_tienda",
        "tienda_usuarios": "ver_tienda",
    }
    for accion, pantalla in dependencias.items():
        if accion in permisos and pantalla not in permisos:
            raise DatosInvalidos(f"El permiso «{PERMISOS[accion]}» requiere «{PERMISOS[pantalla]}».")


def _guardar_permisos(cur, perfil_id: int, permisos: set[str]):
    cur.execute("DELETE FROM perfil_permisos WHERE perfil_id = %s", (perfil_id,))
    for codigo in sorted(permisos):
        cur.execute(
            "INSERT INTO perfil_permisos (perfil_id, codigo) VALUES (%s, %s)",
            (perfil_id, codigo),
        )


def _hay_administrador_activo(cur) -> bool:
    fila = cur.execute("""
        SELECT COUNT(DISTINCT u.id) AS total
        FROM usuarios u
        JOIN perfiles pf ON pf.usuario_id = u.id
        JOIN perfil_permisos pp ON pp.perfil_id = pf.id
        WHERE u.activo = 1 AND pp.codigo = 'gestionar_usuarios'
    """).fetchone()
    return int(fila["total"]) > 0


def _bloquear_administracion(cur):
    cur.execute(
        "SELECT id FROM usuarios WHERE id = (SELECT MIN(id) FROM usuarios) FOR UPDATE"
    )


@bp.route("")
@bp.route("/")
@login_required
@permiso_requerido("gestionar_usuarios")
def lista():
    filas = db.fetchall("""
        SELECT u.id, u.nombre, u.usuario, u.rol, u.activo, u.ultimo_acceso,
               pf.id AS perfil_id, pf.nombre AS perfil, pp.codigo
        FROM usuarios u
        LEFT JOIN perfiles pf ON pf.usuario_id = u.id
        LEFT JOIN perfil_permisos pp ON pp.perfil_id = pf.id
        ORDER BY u.nombre, u.usuario
    """)
    usuarios_por_id = {}
    for f in filas:
        usuario = usuarios_por_id.setdefault(f["id"], {
            key: f[key] for key in
            ("id", "nombre", "usuario", "rol", "activo", "ultimo_acceso", "perfil_id", "perfil")
        } | {"permisos": set()})
        if f["codigo"]:
            usuario["permisos"].add(f["codigo"])
    usuarios = list(usuarios_por_id.values())
    tarifas = db.fetchall("""
        SELECT categoria, tipo, precio_base, activo, fecha_actualizacion
        FROM tarifas_categoria
        ORDER BY categoria, tipo
    """)
    categorias_caja = db.fetchall("""
        SELECT categoria, activo, fecha_actualizacion
        FROM categorias_caja
        ORDER BY categoria
    """)
    return render_template("admin_usuarios.html", usuarios=usuarios,
                           usuarios_protegidos=USUARIOS_PROTEGIDOS,
                           catalogo=PERMISOS, roles=ROLES, tarifas=tarifas,
                           categorias_caja=categorias_caja,
                           grupos_permisos=GRUPOS_PERMISOS,
                           permisos_por_rol={rol: sorted(permisos)
                                             for rol, permisos in PERMISOS_POR_ROL.items()})


@bp.route("/tarifas", methods=["POST"])
@login_required
@permiso_requerido("gestionar_usuarios")
def crear_tarifa():
    invalidar_cache("tarifas_activas")
    categoria = " ".join(request.form.get("categoria", "").upper().split())
    tipo = request.form.get("tipo", "")
    precio = _precio_tarifa(request.form.get("precio_base"))
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9 .-]{0,44}", categoria):
        flash("La categoría es obligatoria y solo admite letras, números, espacios, puntos y guiones.", "error")
        return redirect(url_for("usuarios.lista"))
    if tipo not in TIPOS_TARIFA:
        flash("Selecciona si la tarifa corresponde a un curso, una renovación o una recategorización.", "error")
        return redirect(url_for("usuarios.lista"))
    if precio is None or precio <= 0 or precio > 999_999_999_999:
        flash("El precio debe estar entre $1 y $999.999.999.999.", "error")
        return redirect(url_for("usuarios.lista"))
    try:
        db.execute(
            """INSERT INTO tarifas_categoria (categoria, tipo, precio_base, activo)
               VALUES (%s, %s, %s, 1)""",
            (categoria, tipo, precio),
        )
    except oracledb.IntegrityError as e:
        if getattr(e.args[0] if e.args else None, "code", None) == 1:
            flash("Ya existe una tarifa para esa categoría y tipo de matrícula.", "error")
        else:
            current_app.logger.exception("Error de integridad creando tarifa %s", categoria)
            flash("No se pudo guardar la tarifa.", "error")
    except Exception:
        current_app.logger.exception("Error creando tarifa %s", categoria)
        flash("No se pudo guardar la tarifa.", "error")
    else:
        flash(f"Tarifa de {categoria} ({tipo.lower()}) creada.", "ok")
    return redirect(url_for("usuarios.lista"))


@bp.route("/tarifas/<tipo>/<path:categoria>", methods=["POST"])
@login_required
@permiso_requerido("gestionar_usuarios")
def actualizar_tarifa(tipo: str, categoria: str):
    invalidar_cache("tarifas_activas")
    if tipo not in TIPOS_TARIFA:
        flash("El tipo de tarifa no es válido.", "error")
        return redirect(url_for("usuarios.lista"))
    categoria_clave = " ".join(categoria.upper().split())
    accion = request.form.get("accion")
    if accion == "desactivar":
        try:
            afectadas = db.execute(
                """UPDATE tarifas_categoria SET activo = 0,
                          fecha_actualizacion = CURRENT_TIMESTAMP
                   WHERE categoria = %s AND tipo = %s AND activo = 1""",
                (categoria_clave, tipo),
            )
        except Exception:
            current_app.logger.exception("Error desactivando tarifa %s", categoria_clave)
            flash("No se pudo desactivar la categoría.", "error")
        else:
            flash("Categoría desactivada." if afectadas else "La categoría ya estaba desactivada.", "ok")
        return redirect(url_for("usuarios.lista"))

    if accion == "eliminar":
        # Las matrículas guardan la categoría como texto, así que borrar la tarifa no toca el historial.
        try:
            afectadas = db.execute(
                "DELETE FROM tarifas_categoria WHERE categoria = %s AND tipo = %s",
                (categoria_clave, tipo),
            )
        except Exception:
            current_app.logger.exception("Error eliminando tarifa %s", categoria_clave)
            flash("No se pudo eliminar la tarifa. ¿Ya se aplicó la migración 017?", "error")
        else:
            flash(f"Tarifa de {categoria_clave} ({tipo.lower()}) eliminada." if afectadas
                  else "La tarifa ya no existe.", "ok" if afectadas else "error")
        return redirect(url_for("usuarios.lista"))

    if accion != "actualizar":
        flash("La acción sobre la tarifa no es válida.", "error")
        return redirect(url_for("usuarios.lista"))

    precio = _precio_tarifa(request.form.get("precio_base"))
    activo = 1 if request.form.get("activo") == "1" else 0
    if precio is None or precio <= 0 or precio > 999_999_999_999:
        flash("El precio debe estar entre $1 y $999.999.999.999.", "error")
        return redirect(url_for("usuarios.lista"))
    try:
        afectadas = db.execute(
            """UPDATE tarifas_categoria SET precio_base = %s, activo = %s,
                      fecha_actualizacion = CURRENT_TIMESTAMP
               WHERE categoria = %s AND tipo = %s""",
            (precio, activo, categoria_clave, tipo),
        )
        if not afectadas:
            flash("La categoría ya no existe.", "error")
            return redirect(url_for("usuarios.lista"))
    except Exception:
        current_app.logger.exception("Error actualizando tarifa %s", categoria_clave)
        flash("No se pudo actualizar la tarifa.", "error")
    else:
        flash(f"Tarifa de {categoria_clave} ({tipo.lower()}) actualizada.", "ok")
    return redirect(url_for("usuarios.lista"))


@bp.route("/categorias-caja", methods=["POST"])
@login_required
@permiso_requerido("gestionar_usuarios")
def crear_categoria_caja():
    invalidar_cache("categorias_caja_activas")
    categoria = " ".join(request.form.get("categoria", "").upper().split())
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9 .-]{0,44}", categoria):
        flash("La categoría es obligatoria y solo admite letras, números, espacios, puntos y guiones.", "error")
        return redirect(url_for("usuarios.lista"))
    try:
        db.execute(
            "INSERT INTO categorias_caja (categoria, activo) VALUES (%s, 1)",
            (categoria,),
        )
    except oracledb.IntegrityError as e:
        if getattr(e.args[0] if e.args else None, "code", None) == 1:
            flash("Ya existe esa categoría de caja.", "error")
        else:
            current_app.logger.exception("Error de integridad creando categoría de caja")
            flash("No se pudo guardar la categoría.", "error")
    except Exception:
        current_app.logger.exception("Error creando categoría de caja")
        flash("No se pudo guardar la categoría.", "error")
    else:
        flash(f"Categoría de caja {categoria} creada.", "ok")
    return redirect(url_for("usuarios.lista"))


@bp.route("/categorias-caja/<path:categoria>", methods=["POST"])
@login_required
@permiso_requerido("gestionar_usuarios")
def actualizar_categoria_caja(categoria: str):
    invalidar_cache("categorias_caja_activas")
    categoria_clave = " ".join(categoria.upper().split())
    accion = request.form.get("accion")
    if accion not in ("actualizar", "desactivar"):
        flash("La acción sobre la categoría no es válida.", "error")
        return redirect(url_for("usuarios.lista"))
    activo = 0 if accion == "desactivar" else (
        1 if request.form.get("activo") == "1" else 0
    )
    try:
        afectadas = db.execute(
            """UPDATE categorias_caja SET activo = %s,
                      fecha_actualizacion = CURRENT_TIMESTAMP
               WHERE categoria = %s""",
            (activo, categoria_clave),
        )
    except Exception:
        current_app.logger.exception("Error actualizando categoría de caja %s", categoria_clave)
        flash("No se pudo actualizar la categoría.", "error")
    else:
        if not afectadas:
            flash("La categoría ya no existe.", "error")
        elif activo:
            flash(f"Categoría {categoria_clave} activada.", "ok")
        else:
            flash(f"Categoría {categoria_clave} desactivada.", "ok")
    return redirect(url_for("usuarios.lista"))


@bp.route("", methods=["POST"])
@bp.route("/", methods=["POST"])
@login_required
@permiso_requerido("gestionar_usuarios")
def crear():
    nombre = " ".join(request.form.get("nombre", "").split())
    usuario = request.form.get("usuario", "").strip().lower()
    rol = request.form.get("rol", "")
    perfil = request.form.get("perfil", "").strip()
    password = request.form.get("password", "")
    confirmacion = request.form.get("confirmacion", "")
    try:
        permisos = _permisos_enviados()
        _validar_usuario(nombre, rol, perfil, permisos)
        if not re.fullmatch(r"[a-z0-9._-]{3,50}", usuario):
            raise DatosInvalidos("El usuario debe tener entre 3 y 50 caracteres: letras minúsculas, números, punto, guion o guion bajo.")
        if len(password) < 8 or len(password) > 128:
            raise DatosInvalidos("La contraseña debe tener entre 8 y 128 caracteres.")
        if password != confirmacion:
            raise DatosInvalidos("Las contraseñas no coinciden.")

        with db.transaccion() as cur:
            _bloquear_administracion(cur)
            cur.execute("""
                INSERT INTO usuarios (nombre, usuario, password_hash, rol, activo)
                VALUES (%s, %s, %s, %s, 1)
            """, (nombre, usuario, generate_password_hash(password), rol))
            user_id = cur.execute(
                "SELECT id FROM usuarios WHERE usuario = %s", (usuario,)
            ).fetchone()["id"]
            cur.execute(
                "INSERT INTO perfiles (usuario_id, nombre) VALUES (%s, %s)",
                (user_id, perfil),
            )
            profile_id = cur.execute(
                "SELECT id FROM perfiles WHERE usuario_id = %s", (user_id,)
            ).fetchone()["id"]
            _guardar_permisos(cur, profile_id, permisos)
            if not _hay_administrador_activo(cur):
                raise DatosInvalidos("Debe existir al menos un usuario activo con permiso para gestionar usuarios.")
    except DatosInvalidos as e:
        flash(str(e), "error")
    except oracledb.IntegrityError as e:
        if getattr(e.args[0] if e.args else None, "code", None) == 1:
            flash("Ya existe una cuenta con ese nombre de usuario.", "error")
        else:
            current_app.logger.exception("Error de integridad creando usuario")
            flash("No se pudo crear el usuario. Revisa los datos e intenta de nuevo.", "error")
    except Exception:
        current_app.logger.exception("Error creando usuario")
        flash("No se pudo crear el usuario. Intenta de nuevo.", "error")
    else:
        flash(f"Usuario «{usuario}» y perfil personal creados correctamente.", "ok")
    return redirect(url_for("usuarios.lista"))


@bp.route("/<int:user_id>", methods=["POST"])
@login_required
@permiso_requerido("gestionar_usuarios")
def actualizar(user_id: int):
    nombre = " ".join(request.form.get("nombre", "").split())
    rol = request.form.get("rol", "")
    perfil = request.form.get("perfil", "").strip()
    activo = 1 if request.form.get("activo") == "1" else 0
    password = request.form.get("password", "")
    try:
        permisos = _permisos_enviados()
        _validar_usuario(nombre, rol, perfil, permisos)
        if password and (len(password) < 8 or len(password) > 128):
            raise DatosInvalidos("La nueva contraseña debe tener entre 8 y 128 caracteres.")

        with db.transaccion() as cur:
            _bloquear_administracion(cur)
            usuario = cur.execute(
                "SELECT id FROM usuarios WHERE id = %s FOR UPDATE", (user_id,)
            ).fetchone()
            if not usuario:
                raise DatosInvalidos("La cuenta ya no existe.")
            cur.execute(
                "UPDATE usuarios SET nombre = %s, rol = %s, activo = %s WHERE id = %s",
                (nombre, rol, activo, user_id),
            )
            if password:
                cur.execute(
                    "UPDATE usuarios SET password_hash = %s WHERE id = %s",
                    (generate_password_hash(password), user_id),
                )

            perfil_actual = cur.execute(
                "SELECT id FROM perfiles WHERE usuario_id = %s FOR UPDATE", (user_id,)
            ).fetchone()
            if perfil_actual:
                profile_id = perfil_actual["id"]
                cur.execute("UPDATE perfiles SET nombre = %s WHERE id = %s", (perfil, profile_id))
            else:
                cur.execute(
                    "INSERT INTO perfiles (usuario_id, nombre) VALUES (%s, %s)",
                    (user_id, perfil),
                )
                profile_id = cur.execute(
                    "SELECT id FROM perfiles WHERE usuario_id = %s", (user_id,)
                ).fetchone()["id"]
            _guardar_permisos(cur, profile_id, permisos)
            if not _hay_administrador_activo(cur):
                raise DatosInvalidos("No puedes quitar el último permiso activo para gestionar usuarios.")
    except DatosInvalidos as e:
        flash(str(e), "error")
    except Exception:
        current_app.logger.exception("Error actualizando usuario %s", user_id)
        flash("No se pudieron guardar los cambios. Intenta de nuevo.", "error")
    else:
        if session.get("uid") == user_id:
            session["nombre"] = nombre
            session["rol"] = rol
        flash("Cuenta y perfil personal actualizados correctamente.", "ok")
    return redirect(url_for("usuarios.lista"))



@bp.route("/<int:user_id>/eliminar", methods=["POST"])
@login_required
@permiso_requerido("gestionar_usuarios")
def eliminar(user_id: int):
    nombre = "La cuenta"
    try:
        if user_id == session.get("uid"):
            raise DatosInvalidos("No puedes eliminar tu propia cuenta.")
        with db.transaccion() as cur:
            _bloquear_administracion(cur)
            usuario = cur.execute(
                "SELECT id, nombre, usuario, rol FROM usuarios WHERE id = %s FOR UPDATE", (user_id,)
            ).fetchone()
            if not usuario:
                raise DatosInvalidos("La cuenta ya no existe.")
            nombre = f"«{usuario['nombre']}»"
            if str(usuario["usuario"]).strip().lower() in USUARIOS_PROTEGIDOS:
                raise DatosInvalidos(f"La cuenta {nombre} es una cuenta principal y no se puede eliminar.")
            cur.execute("DELETE FROM perfil_permisos WHERE perfil_id IN "
                        "(SELECT id FROM perfiles WHERE usuario_id = %s)", (user_id,))
            cur.execute("DELETE FROM perfiles WHERE usuario_id = %s", (user_id,))
            # Si la cuenta ya tiene historial (pagos, cajas, auditoría...), Oracle lo impide y se revierte todo.
            cur.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
            if not _hay_administrador_activo(cur):
                raise DatosInvalidos("No puedes eliminar la última cuenta que gestiona usuarios.")
            _auditar(cur, "USUARIO", user_id, "BORRADO", session["uid"],
                     {"nombre": usuario["nombre"], "usuario": usuario["usuario"], "rol": usuario["rol"]}, None)
    except DatosInvalidos as e:
        flash(str(e), "error")
    except oracledb.IntegrityError:
        flash(f"{nombre} ya tiene movimientos o historial y no se puede eliminar sin perderlo. "
              "Desmarca «Cuenta activa» y guarda para desactivarla.", "error")
    except Exception:
        current_app.logger.exception("Error eliminando usuario %s", user_id)
        flash("No se pudo eliminar la cuenta. ¿Ya se aplicó la migración 016?", "error")
    else:
        flash(f"{nombre} fue eliminada.", "ok")
    return redirect(url_for("usuarios.lista"))
