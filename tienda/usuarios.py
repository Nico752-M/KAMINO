"""Usuarios de la tienda: los crea y edita quien tenga el permiso «tienda_usuarios».

Los usuarios y sus permisos viven en las mismas tablas del CEA (usuarios, perfiles, perfil_permisos),
pero esta pantalla solo ve y toca a los usuarios de la tienda:
  - Un usuario es «de la tienda» si su rol es de tienda y TODOS sus permisos son de la tienda.
  - Solo puede entregar permisos de la tienda, nunca permisos del CEA.
  - Nunca deja la tienda sin alguien que pueda administrar usuarios.
"""
import re

import oracledb
from flask import current_app, jsonify, request, session
from werkzeug.security import generate_password_hash

import auth
import db
from permisos import PERMISOS, PERMISOS_POR_ROL, PERMISOS_TIENDA, ROLES_DE_TIENDA, ROLES_TIENDA

from . import bp
from .rutas import api


class DatosInvalidos(Exception):
    pass


_ROL_TEXTO = {"tienda_admin": "Administrador", "tienda_cajero": "Cajero"}


def _json():
    return request.get_json(silent=True) or {}


def _permisos_enviados(d) -> set[str]:
    crudo = d.get("permisos")
    if not isinstance(crudo, list):
        raise DatosInvalidos("Marca los permisos del usuario.")
    permisos = {str(p) for p in crudo}
    if not permisos.issubset(PERMISOS_TIENDA):
        raise DatosInvalidos("Solo puedes dar permisos de la tienda.")
    if "ver_tienda" not in permisos:
        raise DatosInvalidos("Todo usuario necesita el permiso «entrar y cobrar».")
    return permisos


def _validar_nombre_rol(nombre: str, rol: str):
    if not nombre or len(nombre) > 100:
        raise DatosInvalidos("El nombre es obligatorio y admite hasta 100 caracteres.")
    if rol not in ROLES_TIENDA:
        raise DatosInvalidos("La plantilla de usuario no es válida.")


def _es_de_tienda(rol: str, permisos: set[str]) -> bool:
    return rol in ROLES_DE_TIENDA and permisos.issubset(PERMISOS_TIENDA)


def _lista_tienda() -> list[dict]:
    filas = db.fetchall("""
        SELECT u.id, u.nombre, u.usuario, u.rol, u.activo, u.ultimo_acceso, pp.codigo
        FROM usuarios u
        LEFT JOIN perfiles pf ON pf.usuario_id = u.id
        LEFT JOIN perfil_permisos pp ON pp.perfil_id = pf.id
        ORDER BY u.nombre, u.usuario
    """)
    por_id: dict[int, dict] = {}
    for f in filas:
        u = por_id.setdefault(f["id"], {
            "id": f["id"], "nombre": f["nombre"], "usuario": f["usuario"], "rol": f["rol"],
            "activo": int(f["activo"]) == 1,
            "ultimoAcceso": f["ultimo_acceso"].isoformat() if f["ultimo_acceso"] else None,
            "permisos": set(),
        })
        if f["codigo"]:
            u["permisos"].add(f["codigo"])
    lista = [u for u in por_id.values() if _es_de_tienda(u["rol"], u["permisos"])]
    for u in lista:
        u["permisos"] = sorted(u["permisos"])
    return lista


def _respuesta():
    return jsonify(
        ok=True,
        usuarios=_lista_tienda(),
        catalogo={c: PERMISOS[c] for c in PERMISOS_TIENDA},
        plantillas={r: sorted(PERMISOS_POR_ROL[r]) for r in ROLES_TIENDA},
        plantillaNombres=_ROL_TEXTO,
        yo=session.get("uid"),
    )


def _guardar_permisos(cur, perfil_id: int, permisos: set[str]):
    cur.execute("DELETE FROM perfil_permisos WHERE perfil_id = %s", (perfil_id,))
    for codigo in sorted(permisos):
        cur.execute("INSERT INTO perfil_permisos (perfil_id, codigo) VALUES (%s, %s)", (perfil_id, codigo))


def _hay_admin_de_usuarios(cur) -> bool:
    fila = cur.execute("""
        SELECT COUNT(DISTINCT u.id) AS total
        FROM usuarios u
        JOIN perfiles pf ON pf.usuario_id = u.id
        JOIN perfil_permisos pp ON pp.perfil_id = pf.id
        WHERE u.activo = 1 AND pp.codigo = 'tienda_usuarios'
    """).fetchone()
    return int(fila["total"]) > 0


def _bloquear_administracion(cur):
    # Mismo candado que usa el CEA: dos cambios de usuarios no se pisan.
    cur.execute("SELECT id FROM usuarios WHERE id = (SELECT MIN(id) FROM usuarios) FOR UPDATE")


@bp.route("/api/usuarios")
@api(permiso="tienda_usuarios")
def api_usuarios():
    return _respuesta()


@bp.route("/api/usuarios", methods=["POST"])
@api(permiso="tienda_usuarios")
def api_crear_usuario():
    d = _json()
    nombre = " ".join(str(d.get("nombre") or "").split())
    usuario = str(d.get("usuario") or "").strip().lower()
    rol = str(d.get("rol") or "")
    password = str(d.get("password") or "")
    try:
        permisos = _permisos_enviados(d)
        _validar_nombre_rol(nombre, rol)
        if not re.fullmatch(r"[a-z0-9._-]{3,50}", usuario):
            raise DatosInvalidos("El usuario debe tener de 3 a 50 caracteres: letras minúsculas, números, punto, guion o guion bajo.")
        if len(password) < 8 or len(password) > 128:
            raise DatosInvalidos("La contraseña debe tener entre 8 y 128 caracteres.")
        if password != str(d.get("confirmacion") or ""):
            raise DatosInvalidos("Las contraseñas no coinciden.")
        perfil = f"{nombre} - {_ROL_TEXTO[rol]}"[:100]

        with db.transaccion() as cur:
            _bloquear_administracion(cur)
            cur.execute(
                "INSERT INTO usuarios (nombre, usuario, password_hash, rol, activo) VALUES (%s, %s, %s, %s, 1)",
                (nombre, usuario, generate_password_hash(password), rol))
            user_id = cur.execute("SELECT id FROM usuarios WHERE usuario = %s", (usuario,)).fetchone()["id"]
            cur.execute("INSERT INTO perfiles (usuario_id, nombre) VALUES (%s, %s)", (user_id, perfil))
            perfil_id = cur.execute("SELECT id FROM perfiles WHERE usuario_id = %s", (user_id,)).fetchone()["id"]
            _guardar_permisos(cur, perfil_id, permisos)
            if not _hay_admin_de_usuarios(cur):
                raise DatosInvalidos("Debe quedar al menos un usuario activo que pueda administrar usuarios de la tienda.")
    except DatosInvalidos as e:
        return jsonify(ok=False, error=str(e)), 400
    except oracledb.IntegrityError as e:
        if getattr(e.args[0] if e.args else None, "code", None) == 1:
            return jsonify(ok=False, error="Ya existe una cuenta con ese usuario."), 400
        current_app.logger.exception("Error de integridad creando usuario de la tienda")
        return jsonify(ok=False, error="No se pudo crear el usuario. Revisa los datos."), 400
    return _respuesta()


@bp.route("/api/usuarios/<int:user_id>", methods=["POST"])
@api(permiso="tienda_usuarios")
def api_actualizar_usuario(user_id):
    d = _json()
    nombre = " ".join(str(d.get("nombre") or "").split())
    rol = str(d.get("rol") or "")
    activo = 1 if d.get("activo") else 0
    password = str(d.get("password") or "")
    try:
        permisos = _permisos_enviados(d)
        _validar_nombre_rol(nombre, rol)
        if password and (len(password) < 8 or len(password) > 128):
            raise DatosInvalidos("La nueva contraseña debe tener entre 8 y 128 caracteres.")
        if user_id == session.get("uid") and not activo:
            raise DatosInvalidos("No puedes desactivar tu propia cuenta.")

        with db.transaccion() as cur:
            _bloquear_administracion(cur)
            actual = cur.execute("SELECT id, rol FROM usuarios WHERE id = %s FOR UPDATE", (user_id,)).fetchone()
            if not actual:
                raise DatosInvalidos("La cuenta ya no existe.")
            perfil_actual = cur.execute(
                "SELECT id FROM perfiles WHERE usuario_id = %s FOR UPDATE", (user_id,)).fetchone()
            permisos_actuales = set()
            if perfil_actual:
                permisos_actuales = {f["codigo"] for f in cur.execute(
                    "SELECT codigo FROM perfil_permisos WHERE perfil_id = %s", (perfil_actual["id"],)).fetchall()}
            # Un usuario del CEA no se puede tocar desde aquí.
            if not _es_de_tienda(actual["rol"], permisos_actuales):
                raise DatosInvalidos("Esa cuenta no es de la tienda.")

            cur.execute("UPDATE usuarios SET nombre = %s, rol = %s, activo = %s WHERE id = %s",
                        (nombre, rol, activo, user_id))
            if password:
                cur.execute("UPDATE usuarios SET password_hash = %s WHERE id = %s",
                            (generate_password_hash(password), user_id))
            perfil = f"{nombre} - {_ROL_TEXTO[rol]}"[:100]
            if perfil_actual:
                perfil_id = perfil_actual["id"]
                cur.execute("UPDATE perfiles SET nombre = %s WHERE id = %s", (perfil, perfil_id))
            else:
                cur.execute("INSERT INTO perfiles (usuario_id, nombre) VALUES (%s, %s)", (user_id, perfil))
                perfil_id = cur.execute("SELECT id FROM perfiles WHERE usuario_id = %s", (user_id,)).fetchone()["id"]
            _guardar_permisos(cur, perfil_id, permisos)
            if not _hay_admin_de_usuarios(cur):
                raise DatosInvalidos("No puedes dejar la tienda sin un usuario activo que administre usuarios.")
    except DatosInvalidos as e:
        return jsonify(ok=False, error=str(e)), 400

    # Los permisos nuevos valen de inmediato (la sesión guarda una copia de 30 s).
    auth._CACHE_SESION.pop(user_id, None)
    if session.get("uid") == user_id:
        session["nombre"] = nombre
        session["rol"] = rol
    return _respuesta()
