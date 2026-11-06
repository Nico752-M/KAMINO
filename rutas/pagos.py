"""Registro de pagos y recibo PDF (ticket 80 mm)."""
import re

from flask import Blueprint, Response, current_app, jsonify, request, session, url_for

import db
from auth import login_required, permiso_requerido
from rutas.caja import caja_abierta
from servicios.matriculas import estado_matricula
from servicios.recibos import (generar_recibo_movimiento_pdf, generar_recibo_pago_pdf,
                               numero_recibo)
from utils import ahora, cop, entero

bp = Blueprint("pagos", __name__)

METODOS = ("Efectivo", "Transferencia", "Nequi", "Daviplata", "Sistecredit", "Otro")
MAX_PAGO = 100_000_000


class PagoInvalido(Exception):
    """Error de negocio: se muestra tal cual al cajero."""


@bp.route("/pagos/registrar", methods=["POST"])
@login_required
@permiso_requerido("registrar_pagos")
def registrar():
    d = request.get_json(silent=True) or {}

    mid = entero(d.get("matricula_id"))
    valor = entero(d.get("valor"))
    recibido = entero(d.get("recibido"))
    metodo = str(d.get("metodo", ""))
    concepto = str(d.get("concepto") or "Pago curso de conducción").strip()[:200]
    observaciones = str(d.get("observaciones") or "").strip()[:1000] or None
    acompanante = str(d.get("acompanante") or "").strip()[:100] or None

    try:
        if mid <= 0:
            raise PagoInvalido("Matrícula no válida.")
        if metodo not in METODOS:
            raise PagoInvalido("Método de pago no válido.")
        if concepto.casefold() == "abono histórico previo":
            raise PagoInvalido("Ese concepto está reservado para pagos históricos migrados.")
        if valor <= 0 or valor > MAX_PAGO:
            raise PagoInvalido("El valor a abonar debe ser mayor a $0.")

        with db.transaccion() as cur:
            cur.execute("SELECT id, COALESCE(precio_total, 0) AS precio_total, estado, archivado "
                        "FROM matriculas WHERE id = %s FOR UPDATE", (mid,))
            mat = cur.fetchone()
            if not mat:
                raise PagoInvalido("No existe esa matrícula.")
            if mat["archivado"] or mat["estado"] == "Histórico":
                raise PagoInvalido("No se pueden registrar pagos a una matrícula histórica o archivada.")

            cur.execute("SELECT COALESCE(SUM(valor), 0) AS total FROM pagos "
                        "WHERE id_matricula = %s AND anulado = 0", (mid,))
            pagado = float(cur.fetchone()["total"])
            precio = int(mat["precio_total"])
            saldo = max(precio - pagado, 0)

            # El servidor decide, no el navegador: no se aceptan abonos mayores al saldo.
            if valor > saldo:
                raise PagoInvalido(f"El abono supera el saldo pendiente ({cop(saldo)}).")

            caja = caja_abierta(cur, session["uid"])
            if not caja:
                raise PagoInvalido("Abre tu caja antes de registrar un pago.")

            numero = numero_recibo(cur)
            cambio = max(recibido - valor, 0) if metodo == "Efectivo" else 0
            cur.execute("""
                INSERT INTO pagos (id_matricula, concepto, valor, metodo_pago,
                                   numero_recibo, usuario_id, observaciones, acompanante, caja_id, cambio)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (mid, concepto, valor, metodo, numero,
                  session["uid"], observaciones, acompanante, caja["id"], cambio))

            cur.execute("UPDATE matriculas SET estado = %s WHERE id = %s",
                        (estado_matricula(mat["estado"], precio, pagado + valor), mid))

    except PagoInvalido as e:
        return jsonify(ok=False, error=str(e)), 400
    except Exception:
        current_app.logger.exception("Error registrando pago")
        return jsonify(ok=False, error="No se pudo guardar el pago. Intenta de nuevo."), 500

    url = url_for("pagos.recibo", numero=numero)
    return jsonify(ok=True, numero_recibo=numero, saldo=max(saldo - valor, 0),
                   cambio=cambio, recibo_url=url)


@bp.route("/pagos/recibo/<numero>")
@login_required
@permiso_requerido("ver_recibos")
def recibo(numero):
    if not re.fullmatch(r"[A-Za-z0-9-]{6,50}", numero):
        return Response("Recibo no válido", status=404)

    copia = request.args.get("copia") == "1"
    fila = db.fetchone("""
        SELECT p.numero_recibo, p.concepto, p.valor, p.metodo_pago, p.observaciones, p.cambio,
               p.acompanante, p.fecha_pago,
               a.nombres, a.apellidos, a.numero_documento,
               u.nombre AS cajero, p.anulado, p.motivo_anulacion
        FROM pagos p
        JOIN matriculas m ON m.id = p.id_matricula
        JOIN alumnos a ON a.numero_documento = m.numero_documento
        LEFT JOIN usuarios u ON u.id = p.usuario_id
        WHERE p.numero_recibo = %s
    """, (numero,))
    tipo = "PAGO"
    if not fila:
        fila = db.fetchone("""
            SELECT i.numero_recibo, i.concepto, i.valor, i.fecha_ingreso AS fecha,
                   i.usuario_id, i.anulado, i.motivo_anulacion, u.nombre AS cajero
            FROM ingresos_caja i
            LEFT JOIN usuarios u ON u.id = i.usuario_id
            WHERE i.numero_recibo = %s
        """, (numero,))
        tipo = "INGRESO"
    if not fila:
        fila = db.fetchone("""
            SELECT s.numero_recibo, s.concepto, s.valor, s.fecha_salida AS fecha,
                   s.usuario_id, s.anulado, s.motivo_anulacion, u.nombre AS cajero
            FROM salidas_caja s
            LEFT JOIN usuarios u ON u.id = s.usuario_id
            WHERE s.numero_recibo = %s
        """, (numero,))
        tipo = "EGRESO"
    if not fila:
        return Response("Recibo no encontrado", status=404)

    fecha_reimpresion = ahora() if copia else None
    detalles = {
        "numero_recibo": fila["numero_recibo"],
        "concepto": fila["concepto"],
        "valor": float(fila["valor"]),
        "cajero": fila["cajero"] or "—",
        "fecha": fila.get("fecha_pago") or fila.get("fecha"),
        "anulado": fila["anulado"] == 1,
        "motivo_anulacion": fila["motivo_anulacion"],
        "copia": copia,
        "fecha_reimpresion": fecha_reimpresion,
        "usuario_reimpresion": session.get("nombre", ""),
    }
    if tipo == "PAGO":
        detalles.update({
            "alumno_nombre": f"{fila['nombres']} {fila['apellidos']}",
            "alumno_doc": fila["numero_documento"],
            "metodo_pago": fila["metodo_pago"],
            "acompanante": fila["acompanante"] or "",
            "observaciones": fila["observaciones"] or "",
            "cambio": int(fila["cambio"] or 0),
        })
        pdf = generar_recibo_pago_pdf(detalles)
    else:
        detalles["tipo"] = tipo
        pdf = generar_recibo_movimiento_pdf(detalles)
    if copia:
        db.execute(
            "INSERT INTO reimpresiones_recibos (tipo, numero_recibo, usuario_id) "
            "VALUES (%s, %s, %s)",
            (tipo, numero, session["uid"]),
        )
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{numero}.pdf"'})