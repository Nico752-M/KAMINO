"""Punto de entrada. Desarrollo:  flask --app app run --debug"""
from datetime import timedelta
from pathlib import Path
from time import perf_counter

from flask import Flask, abort, g, render_template, request, send_from_directory, session
from werkzeug.middleware.proxy_fix import ProxyFix

import auth
import db
from config import Config
from utils import cop, fecha_larga

STATIC_DIR = Path(__file__).resolve().parent / "public" / "static"


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=Config.SESSION_HOURS)
    app.teardown_appcontext(db.cerrar_conexion_request)

    @app.route("/static/<path:filename>", endpoint="static")
    def static_file(filename):
        response = send_from_directory(STATIC_DIR, filename)
        if filename == "sw.js":
            response.headers["Service-Worker-Allowed"] = "/"
        return response

    if Config.TRUST_PROXY:  # detrás del proxy de Vercel, Railway, Render o Nginx
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # ── Blueprints ──
    from rutas import alumnos, bancos, caja, costos, cuentas, dashboard, pagos, reportes_alumnos, tramites, usuarios
    from tienda import bp as tienda_bp
    app.register_blueprint(auth.bp)
    for modulo in (dashboard, alumnos, pagos, caja, bancos, costos, cuentas, tramites, usuarios, reportes_alumnos):
        app.register_blueprint(modulo.bp)
    app.register_blueprint(tienda_bp)   # carpeta propia: tienda/

    # ── Plantillas ──
    app.jinja_env.filters["cop"] = cop

    @app.context_processor
    def contexto_global():
        aceptada = request.cookies.get("cea_v", "")
        if not (aceptada.isalnum() and aceptada.isascii() and len(aceptada) <= 12):
            aceptada = ""
        datos = {"csrf_token": auth.token_csrf,
                 "asset_v": aceptada or Config.ASSET_V,   # versión que ese dispositivo aceptó
                 "version_actual": Config.ASSET_V,
                 "hay_version_nueva": bool(aceptada) and aceptada != Config.ASSET_V,
                 "fecha_hoy": fecha_larga(), "runt_pendientes": 0,
                 "permisos": auth.permisos_actuales() if "uid" in session else set(),
                 "aviso_login": session.pop("aviso_login", False)}
        if "uid" in session and "ver_tramites" in datos["permisos"]:
            from rutas.tramites import contar_pendientes_cacheado
            datos["runt_pendientes"] = contar_pendientes_cacheado()
        return datos

    # ── Seguridad ──
    @app.before_request
    def iniciar_medicion():
        g.request_started = perf_counter()
        g.db_query_count = 0
        g.db_query_ms = 0.0

    @app.before_request
    def proteger_post():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            auth.verificar_csrf()

    @app.after_request
    def cabeceras(resp):
        if hasattr(g, "request_started"):
            total_ms = (perf_counter() - g.request_started) * 1000
            db_ms = getattr(g, "db_query_ms", 0.0)
            db_count = getattr(g, "db_query_count", 0)
            resp.headers["Server-Timing"] = (
                f"app;dur={total_ms:.1f}, db;dur={db_ms:.1f};desc=\"{db_count} queries\""
            )
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        if not request.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-store"  # nunca guardar datos de dinero en caché
        return resp

    # ── PWA ──
    @app.route("/manifest.json")
    def manifest():
        return send_from_directory(STATIC_DIR, "manifest.json",
                                   mimetype="application/manifest+json")

    @app.route("/sw.js")
    def service_worker():
        # Se sirve desde la raíz para que controle todo el sitio
        resp = send_from_directory(STATIC_DIR, "sw.js", mimetype="application/javascript")
        resp.headers["Service-Worker-Allowed"] = "/"
        return resp

    @app.route("/offline")
    def offline():
        return render_template("offline.html")

    @app.route("/healthz")
    def healthz():
        return "ok"

    @app.route("/healthz/db")
    def healthz_db():
        db.fetchone("SELECT 1 AS ok FROM dual")   # mantiene viva la conexión a Oracle
        return "ok"

    # ── Errores ──
    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(500)
    def error(e):
        codigo = getattr(e, "code", 500)
        mensajes = {400: "Solicitud no válida.", 403: "No tienes permiso para ver esto.",
                    404: "No encontramos esa página.", 500: "Ocurrió un error en el servidor."}
        if request.path.startswith(("/pagos/registrar", "/tramites/runt/")):
            from flask import jsonify
            return jsonify(ok=False, error=getattr(e, "description", mensajes.get(codigo))), codigo
        return render_template("error.html", codigo=codigo,
                               mensaje=mensajes.get(codigo, "Error.")), codigo

    return app


app = create_app()
