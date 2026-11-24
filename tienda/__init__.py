"""Tienda: caja, inventario que se descuenta con cada venta y ganancia neta.

Vive en su propia carpeta y usa su propio usuario de Oracle (esquema aparte del CEA).
Se registra en app.py con:   from tienda import bp as tienda_bp
"""
from flask import Blueprint

bp = Blueprint(
    "tienda", __name__,
    url_prefix="/tienda",
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",     # queda en /tienda/static/...
)

from . import datos, rutas, usuarios  # noqa: E402,F401  (registra las rutas)

bp.teardown_app_request(datos.cerrar_conexion)
