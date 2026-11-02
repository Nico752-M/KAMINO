"""Login, sesiones, roles y protección CSRF."""
import hmac
import secrets
import time
from functools import wraps

from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash

import db
from permisos import PERMISOS

bp = Blueprint("auth", __name__)

# Freno básico contra adivinar contraseñas (por IP + usuario, en memoria)
_MAX_INTENTOS = 5
_VENTANA_SEG = 300
_intentos: dict[str, list[float]] = {}


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


def _usuario_actual():
    if "usuario_actual" not in g:
        uid = session.get("uid")
        g.usuario_actual = db.fetchone(
            "SELECT id, nombre, rol, activo FROM usuarios WHERE id = %s", (uid,)
        ) if uid else None
    return g.usuario_actual


def permisos_actuales() -> set[str]:
    """Carga los permisos actuales en cada petición autenticada."""
    if "permisos_actuales" in g:
        return g.permisos_actuales
    usuario = _usuario_actual()
    if not usuario:
        g.permisos_actuales = set()
        return g.permisos_actuales

    filas = db.fetchall("""
        SELECT pf.id AS perfil_id, pp.codigo
        FROM perfiles pf
        LEFT JOIN perfil_permisos pp ON pp.perfil_id = pf.id
        WHERE pf.usuario_id = %s
    """, (usuario["id"],))
    if filas and filas[0]["perfil_id"] is not None:
        g.permisos_actuales = {f["codigo"] for f in filas if f["codigo"]}
    else:
        g.permisos_actuales = set()
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
    ahora = time.time()
    recientes = [t for t in _intentos.get(clave, []) if ahora - t < _VENTANA_SEG]
    _intentos[clave] = recientes
    return len(recientes) >= _MAX_INTENTOS


def _destino_seguro(destino: str | None) -> str:
    # Solo rutas internas ("/algo"), nunca "//otro-sitio.com" ni "http://..."
    if (destino and destino.startswith("/") and not destino.startswith("//")
            and "\\" not in destino):
        path = destino.split("?", 1)[0]
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
        ("ver_dashboard", "dashboard.index"),
        ("ver_alumnos", "alumnos.lista"),
        ("ver_caja", "caja.resumen"),
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
        usuario = request.form.get("usuario", "").strip().lower()
        password = request.form.get("password", "")
        clave = f"{request.remote_addr}|{usuario}"

        if _bloqueado(clave):
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
            _intentos.pop(clave, None)
            destino = request.args.get("next")
            session.clear()
            session.permanent = True
            session["uid"] = fila["id"]
            session["nombre"] = fila["nombre"]
            session["rol"] = fila["rol"]
            token_csrf()
            try:
                db.execute("UPDATE usuarios SET ultimo_acceso = CURRENT_TIMESTAMP WHERE id = %s", (fila["id"],))
            except Exception:
                current_app.logger.exception("No se pudo actualizar el último acceso")
            return redirect(_destino_seguro(destino))

        _intentos.setdefault(clave, []).append(time.time())
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
