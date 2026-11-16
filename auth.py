"""Login, sesiones, roles y protección CSRF."""
import hashlib
import hmac
import secrets
from functools import wraps

import oracledb
from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash

import db
from permisos import PERMISOS

bp = Blueprint("auth", __name__)

# Freno básico contra adivinar contraseñas (por IP + usuario, en memoria)
_MAX_INTENTOS = 5
_VENTANA_MIN = 5


# ───────────── CSRF ─────────────
def token_csrf() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def verificar_csrf():
    """Se llama antes de cada POST/PUT/PATCH/DELETE."""
    enviado = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token") or ""
    esperado = session.get("csrf", "")
    if not esperado or not hmac.compare_digest(enviado, esperado):
        abort(400, "Token de seguridad inválido. Recarga la página.")


# ───────────── Decorador de acceso ─────────────
def login_required(f=None, *, roles=None):
    """Uso:  @login_required        o        @login_required(roles=("admin",))"""
    def decorador(fn):
        @wraps(fn)
        def envoltura(*args, **kwargs):
            if "uid" not in session:
                if request.is_json or request.path.startswith("/pagos/registrar") \
                        or request.path.startswith("/tramites/runt/"):
                    return jsonify(ok=False, error="Sesión expirada. Vuelve a ingresar."), 401
                return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
            usuario = _usuario_actual()
            if not usuario or usuario["activo"] != 1:
                session.clear()
                if request.is_json:
                    return jsonify(ok=False, error="La cuenta está inactiva. Vuelve a ingresar."), 401
                return redirect(url_for("auth.login"))
            if roles and usuario["rol"] not in roles:
                if request.is_json:
                    return jsonify(ok=False, error="No tienes permiso para esta acción."), 403
                abort(403)
            return fn(*args, **kwargs)
        return envoltura
    return decorador(f) if f else decorador


def _cargar_sesion():
    if "usuario_actual" in g:
        return
    g.usuario_actual = None
    g.permisos_actuales = set()
    uid = session.get("uid")
    if not uid:
        return
    filas = db.fetchall("""
        SELECT u.id, u.nombre, u.rol, u.activo, pp.codigo
        FROM usuarios u
        LEFT JOIN perfiles pf ON pf.usuario_id = u.id
        LEFT JOIN perfil_permisos pp ON pp.perfil_id = pf.id
        WHERE u.id = %s
    """, (uid,))
    if filas:
        fila = filas[0]
        g.usuario_actual = {
            "id": fila["id"],
            "nombre": fila["nombre"],
            "rol": fila["rol"],
            "activo": fila["activo"],
        }
        g.permisos_actuales = {f["codigo"] for f in filas if f["codigo"]}


def _usuario_actual():
    return usuario_actual()


def usuario_actual():
    """Devuelve el usuario verificado y memorizado para la petición actual."""
    _cargar_sesion()
    return g.usuario_actual


def permisos_actuales() -> set[str]:
    """Carga usuario y permisos juntos en una sola consulta por petición."""
    _cargar_sesion()
    return g.permisos_actuales


def permiso_requerido(codigo: str):
    """Autoriza una acción usando el perfil individual del usuario."""
    if codigo not in PERMISOS:
        raise ValueError(f"Permiso desconocido: {codigo}")

    def decorador(fn):
        @wraps(fn)
        def envoltura(*args, **kwargs):
            if codigo not in permisos_actuales():
                if request.is_json or request.path.startswith(("/pagos/", "/tramites/runt/")):
                    return jsonify(ok=False, error="No tienes permiso para esta acción."), 403
                abort(403)
            return fn(*args, **kwargs)
        return envoltura
    return decorador


# ───────────── Rutas ─────────────
def _bloqueado(clave: str) -> bool:
    fila = db.fetchone("""
        SELECT CASE WHEN bloqueado_hasta > CURRENT_TIMESTAMP THEN 1 ELSE 0 END AS bloqueado
        FROM login_intentos WHERE clave = %s
    """, (clave,))
    return bool(fila and fila["bloqueado"])


def _actualizar_intento(cur, clave: str) -> None:
    ventana_vencida = f"""(inicio_ventana <= CURRENT_TIMESTAMP - INTERVAL '{_VENTANA_MIN}' MINUTE
        OR (bloqueado_hasta IS NOT NULL AND bloqueado_hasta <= CURRENT_TIMESTAMP))"""
    cur.execute(f"""
        UPDATE login_intentos
        SET intentos = CASE WHEN {ventana_vencida} THEN 1
                            ELSE LEAST(intentos + 1, {_MAX_INTENTOS}) END,
            inicio_ventana = CASE WHEN {ventana_vencida} THEN CURRENT_TIMESTAMP ELSE inicio_ventana END,
            bloqueado_hasta = CASE WHEN {ventana_vencida} THEN NULL
                                   WHEN intentos + 1 >= {_MAX_INTENTOS}
                                   THEN CURRENT_TIMESTAMP + INTERVAL '{_VENTANA_MIN}' MINUTE
                                   ELSE bloqueado_hasta END,
            actualizado_en = CURRENT_TIMESTAMP
        WHERE clave = %s
    """, (clave,))
    if cur.rowcount == 0:
        cur.execute(
            """INSERT INTO login_intentos (clave, intentos, inicio_ventana)
               VALUES (%s, 1, CURRENT_TIMESTAMP)""",
            (clave,),
        )


def _registrar_fallo(clave: str) -> None:
    try:
        with db.transaccion() as cur:
            cur.execute(
                "DELETE FROM login_intentos "
                "WHERE actualizado_en < CURRENT_TIMESTAMP - INTERVAL '1' DAY"
            )
            _actualizar_intento(cur, clave)
    except oracledb.IntegrityError as error:
        causa = error.args[0] if error.args else None
        if getattr(causa, "code", None) != 1:
            raise
        with db.transaccion() as cur:
            cur.execute("SELECT clave FROM login_intentos WHERE clave = %s FOR UPDATE", (clave,))
            if not cur.fetchone():
                raise
            _actualizar_intento(cur, clave)


def _destino_seguro(destino: str | None) -> str:
    # Solo rutas internas ("/algo"), nunca "//otro-sitio.com" ni "http://..."
    if (destino and destino.startswith("/") and not destino.startswith("//")
            and "\\" not in destino):
        path = destino.split("?", 1)[0]
        if (path == "/" and "registrar_pagos" in permisos_actuales()
                and "ver_caja" in permisos_actuales()):
            return url_for("caja.resumen")
        permisos_por_ruta = {
            "/": "ver_dashboard",
            "/alumnos": "ver_alumnos",
            "/caja": "ver_caja",
            "/tramites": "ver_tramites",
            "/admin/usuarios": "gestionar_usuarios",
        }
        for prefijo, codigo in permisos_por_ruta.items():
            if path == prefijo or (prefijo != "/" and path.startswith(prefijo + "/")):
                return destino if codigo in permisos_actuales() else _primer_destino_permitido()
        return destino
    return _primer_destino_permitido()


def _primer_destino_permitido() -> str:
    permisos = permisos_actuales()
    destinos = (
        ("ver_caja", "caja.resumen"),
        ("ver_dashboard", "dashboard.index"),
        ("ver_alumnos", "alumnos.lista"),
        ("ver_tramites", "tramites.lista"),
        ("gestionar_usuarios", "usuarios.lista"),
    )
    for codigo, endpoint in destinos:
        if codigo in permisos:
            return url_for(endpoint)
    return url_for("auth.sin_permisos")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if "uid" in session:
        usuario_actual = _usuario_actual()
        if usuario_actual and usuario_actual["activo"] == 1:
            return redirect(_primer_destino_permitido())
        session.clear()

    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip().lower()[:50]
        password = request.form.get("password", "")
        clave = hashlib.sha256(f"{request.remote_addr}|{usuario}".encode()).hexdigest()

        try:
            bloqueado = _bloqueado(clave)
        except Exception:
            current_app.logger.exception("No se pudo consultar el bloqueo de inicio de sesión")
            flash("No hay conexión con la base de datos. Intenta de nuevo.", "error")
            return render_template("login.html"), 503
        if bloqueado:
            flash("Demasiados intentos. Espera unos minutos e intenta de nuevo.", "error")
            return render_template("login.html"), 429

        fila = None
        try:
            fila = db.fetchone(
                "SELECT id, nombre, usuario, password_hash, rol "
                "FROM usuarios WHERE usuario = %s AND activo = 1", (usuario,))
        except Exception:
            flash("No hay conexión con la base de datos. Intenta de nuevo.", "error")
            return render_template("login.html"), 503

        if fila and check_password_hash(fila["password_hash"], password):
            try:
                db.execute("DELETE FROM login_intentos WHERE clave = %s", (clave,))
            except Exception:
                current_app.logger.exception("No se pudieron limpiar los intentos del inicio de sesión")
            destino = request.args.get("next")
            session.clear()
            session.permanent = True
            session["uid"] = fila["id"]
            session["nombre"] = fila["nombre"]
            session["rol"] = fila["rol"]
            session["aviso_login"] = True  # el aviso de actualización solo sale al ingresar
            token_csrf()
            try:
                db.execute("UPDATE usuarios SET ultimo_acceso = CURRENT_TIMESTAMP WHERE id = %s", (fila["id"],))
            except Exception:
                current_app.logger.exception("No se pudo actualizar el último acceso")
            return redirect(_destino_seguro(destino))

        try:
            _registrar_fallo(clave)
        except Exception:
            current_app.logger.exception("No se pudo registrar el intento de inicio de sesión")
            flash("No se pudo verificar el acceso. Intenta de nuevo.", "error")
            return render_template("login.html"), 503
        flash("Usuario o contraseña incorrectos.", "error")

    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/sin-permisos")
@login_required
def sin_permisos():
    return render_template("sin_permisos.html"), 403
