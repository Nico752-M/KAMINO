"""Páginas y API JSON de la tienda. Todo exige iniciar sesión y el permiso «ver_tienda»."""
from functools import wraps

from flask import current_app, jsonify, render_template, request, session, url_for

from auth import login_required, permiso_requerido, permisos_actuales

from . import bp, servicios
from .datos import TiendaNoConfigurada
from .servicios import TiendaError

_PANTALLAS_CEA = (
    ("ver_caja", "caja.resumen"),
    ("ver_dashboard", "dashboard.index"),
    ("ver_alumnos", "alumnos.lista"),
    ("ver_tramites", "tramites.lista"),
    ("gestionar_usuarios", "usuarios.lista"),
)


def _usuario():
    return {"id": session["uid"], "nombre": session.get("nombre", "Usuario")}


def api(fn):
    """Protege la ruta y convierte errores en respuestas JSON claras."""
    @wraps(fn)
    @login_required
    @permiso_requerido("ver_tienda")
    def envoltura(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except TiendaError as e:
            return jsonify(ok=False, error=str(e)), 400
        except TiendaNoConfigurada as e:
            return jsonify(ok=False, error=str(e)), 503
        except Exception:
            current_app.logger.exception("Error en la API de la tienda (%s)", request.path)
            return jsonify(ok=False, error="No se pudo completar la operación. Intenta de nuevo."), 500
    return envoltura


def _json():
    return request.get_json(silent=True) or {}


# ───────── Página ─────────
@bp.route("")
@login_required
@permiso_requerido("ver_tienda")
def inicio():
    permisos = permisos_actuales()
    volver = next((url_for(ep) for codigo, ep in _PANTALLAS_CEA if codigo in permisos), None)
    return render_template("tienda/tienda.html", nav="tienda", volver=volver)


# ───────── API ─────────
@bp.route("/api/estado")
@api
def api_estado():
    return jsonify(ok=True, productos=servicios.listar_productos(), ajustes=servicios.leer_ajustes())


@bp.route("/api/productos", methods=["POST"])
@api
def api_guardar_producto():
    servicios.guardar_producto(_json(), _usuario())
    return jsonify(ok=True, productos=servicios.listar_productos())


@bp.route("/api/productos/<int:pid>/entrada", methods=["POST"])
@api
def api_entrada(pid):
    d = _json()
    servicios.entrada_stock(pid, d.get("cantidad"), d.get("nota"), _usuario())
    return jsonify(ok=True, productos=servicios.listar_productos())


@bp.route("/api/productos/<int:pid>/quitar", methods=["POST"])
@api
def api_quitar(pid):
    servicios.quitar_producto(pid)
    return jsonify(ok=True, productos=servicios.listar_productos())


@bp.route("/api/ventas", methods=["POST"])
@api
def api_vender():
    d = _json()
    r = servicios.registrar_venta(d.get("items"), d.get("metodo"), d.get("recibido"), _usuario())
    return jsonify(ok=True, **r)


@bp.route("/api/ventas")
@api
def api_ventas():
    return jsonify(ok=True, ventas=servicios.listar_ventas())


@bp.route("/api/ventas/<int:vid>/anular", methods=["POST"])
@api
def api_anular(vid):
    servicios.anular_venta(vid, _json().get("motivo"), _usuario())
    return jsonify(ok=True, productos=servicios.listar_productos(), ventas=servicios.listar_ventas())


@bp.route("/api/ganancias")
@api
def api_ganancias():
    return jsonify(ok=True, **servicios.ganancias(request.args.get("periodo", "30")))


@bp.route("/api/ajustes", methods=["POST"])
@api
def api_ajustes():
    return jsonify(ok=True, ajustes=servicios.guardar_ajustes(_json()))
