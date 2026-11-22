"""Mis cuentas: lo que entró y lo que salió del CEA en un mes del calendario.

Las cuentas fijas (arriendo, luz, agua, nómina…) se anotan aquí una vez y cuentan en cada mes.
Lo demás sale solo de la caja: pagos de alumnos, ingresos y salidas de caja.
"""
from datetime import date
from functools import wraps

from flask import Blueprint, current_app, jsonify, render_template, request

import db
from auth import login_required, permiso_requerido
from utils import hoy

bp = Blueprint("cuentas", __name__, url_prefix="/cuentas")

CATEGORIAS = ("Arriendo", "Luz", "Agua", "Gas", "Internet y teléfono", "Nómina",
              "Combustible y vehículos", "Mantenimiento y arreglos", "Impuestos y trámites",
              "Papelería y aseo", "Otros")
MAX_VALOR = 999_999_999_999


class CuentaError(Exception):
    """Mensaje claro para mostrar a la persona."""


def api(fn):
    """Protege la ruta y convierte los errores en respuestas JSON claras."""
    @wraps(fn)
    @login_required
    @permiso_requerido("ver_cuentas")
    def envoltura(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except CuentaError as e:
            return jsonify(ok=False, error=str(e)), 400
        except Exception:
            current_app.logger.exception("Error en Mis cuentas (%s)", request.path)
            return jsonify(ok=False, error="No se pudo completar la operación. Intenta de nuevo."), 500
    return envoltura


def _json() -> dict:
    return request.get_json(silent=True) or {}


def _rango_mes(mes) -> tuple[str, date, date]:
    try:
        y, m = (int(x) for x in str(mes).split("-"))
        desde = date(y, m, 1)
    except (TypeError, ValueError):
        raise CuentaError("Mes no válido.")
    if not 2000 <= y <= 2100:
        raise CuentaError("Mes no válido.")
    hasta = date(y + (m == 12), m % 12 + 1, 1)
    return f"{y}-{m:02d}", desde, hasta


def _entero(valor, nombre: str) -> int:
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise CuentaError(f"{nombre} debe ser un número.")
    if not 1 <= n <= MAX_VALOR:
        raise CuentaError(f"{nombre} debe ser mayor que cero.")
    return n


def resumen_mes(mes) -> dict:
    mes, desde, hasta = _rango_mes(mes)
    p = (desde, hasta)

    pagos = db.fetchone(
        "SELECT NVL(SUM(valor), 0) AS v FROM pagos "
        "WHERE anulado = 0 AND concepto <> 'Abono histórico previo' "
        "AND fecha_pago >= %s AND fecha_pago < %s", p)
    otros = db.fetchone(
        "SELECT NVL(SUM(valor), 0) AS v FROM ingresos_caja "
        "WHERE anulado = 0 AND fecha_ingreso >= %s AND fecha_ingreso < %s", p)
    salidas = db.fetchall(
        "SELECT NVL(categoria, 'Sin categoría') AS categoria, SUM(valor) AS v FROM salidas_caja "
        "WHERE anulado = 0 AND fecha_salida >= %s AND fecha_salida < %s "
        "GROUP BY NVL(categoria, 'Sin categoría') ORDER BY SUM(valor) DESC", p)
    # Una cuenta fija cuenta desde el mes en que se anotó, para no cambiar los meses ya pasados.
    fijas = db.fetchall(
        "SELECT id, nombre, categoria, valor FROM cuentas_cea "
        "WHERE activa = 1 AND creado < %s ORDER BY categoria, nombre", (hasta,))

    entradas = [{"nombre": "Pagos de alumnos", "sub": "Cursos, matrículas y demás pagos", "valor": int(pagos["v"])},
                {"nombre": "Otros ingresos de la caja", "sub": "Plata que entró a la caja por otros motivos",
                 "valor": int(otros["v"])}]
    entradas = [f for f in entradas if f["valor"]]

    gastos = [{"id": int(c["id"]), "nombre": c["nombre"], "sub": c["categoria"], "categoria": c["categoria"],
               "valor": int(c["valor"])} for c in fijas]
    gastos += [{"nombre": f"Salidas de la caja: {s['categoria']}", "sub": "Plata que salió de la caja para pagar cosas",
                "valor": int(s["v"])} for s in salidas if int(s["v"])]

    entro = sum(f["valor"] for f in entradas)
    salio = sum(f["valor"] for f in gastos)
    return {"mes": mes, "entro": entro, "salio": salio, "quedo": entro - salio,
            "entradas": entradas, "gastos": gastos}


# ───────── Página ─────────
@bp.route("")
@login_required
@permiso_requerido("ver_cuentas")
def inicio():
    return render_template("cuentas.html", nav="cuentas", categorias=CATEGORIAS)


# ───────── API ─────────
@bp.route("/api/mes")
@api
def api_mes():
    return jsonify(ok=True, **resumen_mes(request.args.get("mes") or hoy().strftime("%Y-%m")))


@bp.route("/api/cuentas", methods=["POST"])
@api
def api_guardar():
    d = _json()
    nombre = " ".join(str(d.get("nombre", "")).split())
    categoria = str(d.get("categoria", "")).strip()
    if not nombre or len(nombre) > 80:
        raise CuentaError("El nombre de la cuenta es obligatorio (máximo 80 caracteres).")
    if categoria not in CATEGORIAS:
        raise CuentaError("Elige un tipo de la lista.")
    valor = _entero(d.get("valor"), "El valor al mes")
    cid = d.get("id")
    with db.transaccion() as cur:
        if cid not in (None, "", 0):
            cur.execute("UPDATE cuentas_cea SET nombre = %s, categoria = %s, valor = %s WHERE id = %s",
                        (nombre, categoria, valor, _entero(cid, "La cuenta")))
            if not cur.rowcount:
                raise CuentaError("Esa cuenta ya no existe.")
        else:
            cur.execute("INSERT INTO cuentas_cea (nombre, categoria, valor) VALUES (%s, %s, %s)",
                        (nombre, categoria, valor))
    return jsonify(ok=True)


@bp.route("/api/cuentas/<int:cid>/borrar", methods=["POST"])
@api
def api_borrar(cid):
    if not db.execute("DELETE FROM cuentas_cea WHERE id = %s", (cid,)):
        raise CuentaError("Esa cuenta ya no existe.")
    return jsonify(ok=True)
