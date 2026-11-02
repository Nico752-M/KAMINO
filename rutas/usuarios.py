"""Administración de cuentas y perfiles de permisos individuales."""
import re

import oracledb
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

import db
from auth import login_required, permiso_requerido
from permisos import PERMISOS, ROLES

bp = Blueprint("usuarios", __name__, url_prefix="/admin/usuarios")


class DatosInvalidos(Exception):
    pass


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
    if not permisos.intersection({"ver_dashboard", "ver_alumnos", "ver_caja", "ver_tramites"}):
        raise DatosInvalidos("Asigna al menos permiso para consultar una pantalla.")
    dependencias = {
        "crear_matricula": "ver_alumnos",
        "registrar_pagos": "ver_alumnos",
        "gestionar_caja": "ver_caja",
        "marcar_runt": "ver_tramites",
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
    return render_template("admin_usuarios.html", usuarios=usuarios,
                           catalogo=PERMISOS, roles=ROLES)


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
