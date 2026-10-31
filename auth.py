"""Login, sesiones, roles y protección CSRF."""
import hmac
import secrets
import time
from functools import wraps

from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash

import db
from config import Config

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
            if roles and session.get("rol") not in roles:
                if request.is_json:
                    return jsonify(ok=False, error="No tienes permiso para esta acción."), 403
                abort(403)
            return fn(*args, **kwargs)
        return envoltura
    return decorador(f) if f else decorador


# ───────────── Rutas ─────────────
def _bloqueado(clave: str) -> bool:
    ahora = time.time()
    recientes = [t for t in _intentos.get(clave, []) if ahora - t < _VENTANA_SEG]
    _intentos[clave] = recientes
    return len(recientes) >= _MAX_INTENTOS


def _destino_seguro(destino: str | None) -> str:
    # Solo rutas internas ("/algo"), nunca "//otro-sitio.com" ni "http://..."
    if destino and destino.startswith("/") and not destino.startswith("//"):
        return destino
    return url_for("dashboard.index")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if "uid" in session:
        return redirect(url_for("dashboard.index"))

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
                db.execute("UPDATE usuarios SET ultimo_acceso = NOW() WHERE id = %s", (fila["id"],))
            except Exception:
                pass
            return redirect(_destino_seguro(destino))

        _intentos.setdefault(clave, []).append(time.time())
        flash("Usuario o contraseña incorrectos.", "error")

    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
