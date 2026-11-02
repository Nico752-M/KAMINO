"""Consulta de caja y registro de movimientos manuales."""
from datetime import date, timedelta
import uuid

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

import db
from auth import login_required, permiso_requerido
from utils import ahora, hoy

bp = Blueprint("caja", __name__)


def _fecha_param() -> date:
    try:
        return date.fromisoformat(request.args.get("fecha", ""))
    except ValueError:
        return hoy()


@bp.route("/caja")
@login_required
@permiso_requerido("ver_caja")
def resumen():
    dia = _fecha_param()
    sig = dia + timedelta(days=1)
    error = None
    movs, totales = [], {"efectivo": 0.0, "otros": 0.0, "ingresos": 0.0, "salidas": 0.0}
    try:
        pagos = db.fetchall("""
            SELECT p.numero_recibo, p.concepto, p.valor, p.metodo_pago, p.fecha_pago AS momento,
                   TRIM(a.nombres || ' ' || a.apellidos) AS detalle
            FROM pagos p
            LEFT JOIN matriculas m ON m.id = p.id_matricula
            LEFT JOIN alumnos a ON a.numero_documento = m.numero_documento
            WHERE p.fecha_pago >= %s AND p.fecha_pago < %s
              AND p.concepto <> 'Abono histórico previo'
        """, (dia, sig))
        ingresos = db.fetchall("""
            SELECT numero_recibo, concepto, valor, fecha_ingreso AS momento
            FROM ingresos_caja WHERE fecha_ingreso >= %s AND fecha_ingreso < %s
        """, (dia, sig))
        salidas = db.fetchall("""
            SELECT numero_recibo, concepto, valor, fecha_salida AS momento
            FROM salidas_caja WHERE fecha_salida >= %s AND fecha_salida < %s
        """, (dia, sig))

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
    except Exception:
        error = "No se pudo consultar la caja del día."
        current_app.logger.exception("No se pudo consultar la caja del día")

    totales["en_caja"] = totales["efectivo"] + totales["ingresos"] - totales["salidas"]
    return render_template("tesoreria.html", dia=dia, movs=movs, t=totales, error=error)


@bp.route("/caja/movimientos/<tipo>", methods=["POST"])
@login_required
@permiso_requerido("gestionar_caja")
def registrar_movimiento(tipo):
    tablas = {"ingreso": ("ingresos_caja", "Ingreso manual"),
              "salida": ("salidas_caja", "Salida de caja")}
    if tipo not in tablas:
        return "Tipo de movimiento no válido.", 404

    concepto = " ".join(request.form.get("concepto", "").split())
    valor_texto = request.form.get("valor", "").strip()
    if not concepto or len(concepto) > 200:
        flash("El concepto es obligatorio y admite hasta 200 caracteres.", "error")
        return redirect(url_for("caja.resumen"))
    if not valor_texto.isascii() or not valor_texto.isdecimal():
        flash("El valor debe ser un entero en pesos.", "error")
        return redirect(url_for("caja.resumen"))
    valor = int(valor_texto)
    if valor <= 0 or valor > 100_000_000:
        flash("El valor debe estar entre $1 y $100.000.000.", "error")
        return redirect(url_for("caja.resumen"))

    tabla, etiqueta = tablas[tipo]
    recibo = f"CEA-{ahora():%Y%m%d}-{uuid.uuid4().hex[:16].upper()}"
    try:
        with db.transaccion() as cur:
            cur.execute(
                f"INSERT INTO {tabla} (numero_recibo, concepto, valor, usuario_id) "
                "VALUES (%s, %s, %s, %s)",
                (recibo, concepto, valor, session["uid"]),
            )
    except Exception:
        current_app.logger.exception("Error registrando %s en caja", tipo)
        flash("No se pudo registrar el movimiento. Intenta de nuevo.", "error")
        return redirect(url_for("caja.resumen"))

    flash(f"{etiqueta} registrada. Recibo {recibo}.", "ok")
    return redirect(url_for("caja.resumen"))