"""Caja y Tesorería: resumen del día (solo lectura por ahora)."""
from datetime import date

from flask import Blueprint, render_template, request

import db
from auth import login_required
from utils import hoy

bp = Blueprint("caja", __name__)


def _fecha_param() -> date:
    try:
        return date.fromisoformat(request.args.get("fecha", ""))
    except ValueError:
        return hoy()


@bp.route("/caja")
@login_required
def resumen():
    dia = _fecha_param()
    error = None
    movs, totales = [], {"efectivo": 0.0, "otros": 0.0, "ingresos": 0.0, "salidas": 0.0}
    try:
        pagos = db.fetchall("""
            SELECT p.numero_recibo, p.concepto, p.valor, p.metodo_pago, p.fecha_pago AS momento,
                   CONCAT(a.nombres, ' ', a.apellidos) AS detalle
            FROM pagos p
            LEFT JOIN matriculas m ON m.id = p.id_matricula
            LEFT JOIN alumnos a ON a.numero_documento = m.numero_documento
            WHERE DATE(p.fecha_pago) = %s AND p.concepto <> 'Abono histórico previo'
        """, (dia,))
        ingresos = db.fetchall("""
            SELECT numero_recibo, concepto, valor, fecha_ingreso AS momento
            FROM ingresos_caja WHERE DATE(fecha_ingreso) = %s
        """, (dia,))
        salidas = db.fetchall("""
            SELECT numero_recibo, concepto, valor, fecha_salida AS momento
            FROM salidas_caja WHERE DATE(fecha_salida) = %s
        """, (dia,))

        for p in pagos:
            v = float(p["valor"])
            totales["efectivo" if p["metodo_pago"] == "Efectivo" else "otros"] += v
            movs.append({"tipo": "pago", "recibo": p["numero_recibo"], "momento": p["momento"],
                         "detalle": f"{p['detalle'] or 'Sin alumno'} — {p['concepto']}",
                         "metodo": p["metodo_pago"], "valor": v})
        for i in ingresos:
            v = float(i["valor"]); totales["ingresos"] += v
            movs.append({"tipo": "ingreso", "recibo": i["numero_recibo"], "momento": i["momento"],
                         "detalle": i["concepto"], "metodo": "Efectivo", "valor": v})
        for s in salidas:
            v = float(s["valor"]); totales["salidas"] += v
            movs.append({"tipo": "salida", "recibo": s["numero_recibo"], "momento": s["momento"],
                         "detalle": s["concepto"], "metodo": "Efectivo", "valor": -v})
        movs.sort(key=lambda m: m["momento"])
    except Exception as e:
        error = "No se pudo consultar la caja del día."
        print(f"[caja] {e}")

    totales["en_caja"] = totales["efectivo"] + totales["ingresos"] - totales["salidas"]
    return render_template("tesoreria.html", dia=dia, movs=movs, t=totales, error=error)
