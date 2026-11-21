"""Páginas y API JSON de la tienda. Todo exige iniciar sesión y el permiso «ver_tienda»."""
from functools import wraps

from flask import Response, current_app, jsonify, render_template, request, session, url_for

from auth import login_required, permiso_requerido, permisos_actuales

from . import bp, excel, pdf, servicios
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
    r = servicios.registrar_venta(d.get("items"), d.get("metodo"), d.get("recibido"), _usuario(),
                                  d.get("resto"), d.get("descuento"))
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

# ───────── PDFs ─────────
def _pdf(contenido, nombre):
    return Response(contenido, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@bp.route("/pdf/venta/<int:vid>")
@api
def pdf_venta(vid):
    v, items = servicios.obtener_venta(vid)
    return _pdf(pdf.ticket_venta(v, items), f"venta-{vid}.pdf")


@bp.route("/pdf/inventario")
@api
def pdf_inventario():
    return _pdf(pdf.inventario(servicios.listar_productos()), "inventario.pdf")


@bp.route("/pdf/ventas")
@api
def pdf_ventas():
    return _pdf(pdf.ventas(servicios.listar_ventas(200)), "ventas.pdf")


@bp.route("/pdf/ganancias")
@api
def pdf_ganancias():
    periodo = request.args.get("periodo", "30")
    return _pdf(pdf.ganancias(servicios.ganancias(periodo), servicios.leer_ajustes(), periodo),
                f"ganancias-{periodo}.pdf")

@bp.route("/pdf/reposicion")
@api
def pdf_reposicion():
    return _pdf(pdf.reposicion(servicios.listar_productos()), "pedido-reposicion.pdf")


@bp.route("/excel/<que>")
@api
def excel_descarga(que):
    if que == "inventario":
        hojas = [("Inventario", ["Producto", "Categoría", "Costo", "Precio", "Stock", "Mínimo"],
                  [(p["nombre"], p["cat"], p["costo"], p["precio"], p["stock"], p["minimo"])
                   for p in servicios.listar_productos()])]
    elif que == "ventas":
        hojas = [("Ventas", ["#", "Fecha", "Detalle", "Pago", "Total", "Atendió", "Estado"],
                  [(v["id"], (v["fecha"] or "")[:16].replace("T", " "),
                    ", ".join(f"{i['cant']} x {i['nombre']}" for i in v["items"]),
                    servicios.texto_pago(v), v["total"], v["cajero"],
                    "Anulada" if v["anulada"] else "Válida")
                   for v in servicios.listar_ventas(500)])]
    elif que == "ganancias":
        d = servicios.ganancias(request.args.get("periodo", "30"))
        hojas = [
            ("Por día", ["Fecha", "Ventas (n)", "Vendido", "Costo", "Ganancia bruta"],
             [(x["fecha"], x["n"], x["ventas"], x["costo"], x["ventas"] - x["costo"]) for x in d["porDia"]]),
            ("Más vendidos", ["Producto", "Unidades", "Ganancia"],
             [(t["nombre"], t["unidades"], t["ganancia"]) for t in d["top"]]),
            ("Por método", ["Método", "Valor"], [(m["metodo"], m["valor"]) for m in d["metodos"]]),
            ("Por hora", ["Hora", "Ventas (n)", "Vendido"], [(h["h"], h["n"], h["ventas"]) for h in d["horas"]]),
            ("Sin movimiento", ["Producto", "Stock", "Dinero parado"],
             [(q["nombre"], q["stock"], q["parado"]) for q in d["quietos"]]),
        ]
    elif que == "reporte":
        r = servicios.reporte(request.args.get("desde"), request.args.get("hasta"))
        hojas = [
            ("Por día", ["Fecha", "# Ventas", "Efectivo", "Nequi", "Tarjeta", "Total vendido", "Descuentos",
                         "Ganancia bruta", "Entradas", "Salidas", "Mermas", "Contado", "Diferencia"],
             [(f["fecha"], f["n"], f["Efectivo"], f["Nequi"], f["Tarjeta"], f["ventas"], f["desc"],
               f["ventas"] - f["costo"], f["ing"], f["egr"], f["mer"], f["contado"], f["dif"])
              for f in r["dias"]]),
            ("Caja", ["Fecha", "Hora", "Tipo", "Motivo", "Valor", "Cajero"], r["movs"]),
            ("Mermas", ["Fecha", "Producto", "Cantidad", "Costo unit.", "Perdido", "Motivo"], r["mermas"]),
            ("Productos", ["Producto", "Unidades", "Vendido", "Ganancia"], r["productos"]),
        ]
    else:
        return jsonify(ok=False, error="No existe ese reporte."), 404
    return Response(excel.libro(hojas),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{que}.xlsx"'})


@bp.route("/api/productos/<int:pid>/movimientos")
@api
def api_movimientos(pid):
    return jsonify(ok=True, movimientos=servicios.movimientos_producto(pid))


@bp.route("/api/cierre")
@api
def api_cierre():
    return jsonify(ok=True, **servicios.cierre_hoy())


@bp.route("/api/cierre", methods=["POST"])
@api
def api_cerrar():
    servicios.guardar_cierre(_json().get("contado"), _usuario())
    return jsonify(ok=True, **servicios.cierre_hoy())

@bp.route("/pdf/reporte")
@api
def pdf_reporte():
    r = servicios.reporte(request.args.get("desde"), request.args.get("hasta"))
    return _pdf(pdf.reporte(r), f"reporte-{r['desde']}_{r['hasta']}.pdf")


@bp.route("/api/caja/mov", methods=["POST"])
@api
def api_mov():
    servicios.registrar_mov(_json(), _usuario())
    return jsonify(ok=True, **servicios.cierre_hoy())


@bp.route("/api/caja/mov/<int:mid>/quitar", methods=["POST"])
@api
def api_quitar_mov(mid):
    servicios.quitar_mov(mid)
    return jsonify(ok=True, **servicios.cierre_hoy())


@bp.route("/api/productos/<int:pid>/baja", methods=["POST"])
@api
def api_baja(pid):
    d = _json()
    servicios.registrar_merma(pid, d.get("cantidad"), d.get("motivo"), d.get("nota"), _usuario())
    return jsonify(ok=True, productos=servicios.listar_productos(), mermas=servicios.listar_mermas())


@bp.route("/api/mermas")
@api
def api_mermas():
    return jsonify(ok=True, mermas=servicios.listar_mermas())


@bp.route("/api/mermas/<int:mid>/anular", methods=["POST"])
@api
def api_anular_merma(mid):
    servicios.anular_merma(mid, _usuario())
    return jsonify(ok=True, productos=servicios.listar_productos(), mermas=servicios.listar_mermas())