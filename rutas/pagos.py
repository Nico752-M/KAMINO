"""Registro de pagos y recibo PDF (ticket 80 mm)."""
import re
import uuid

import oracledb
from flask import Blueprint, Response, current_app, jsonify, request, session, url_for

import db
from auth import login_required
from config import Config
from servicios.recibos import generar_recibo_pago_pdf
from utils import entero

bp = Blueprint("pagos", __name__)

METODOS = ("Efectivo", "Transferencia", "Nequi", "Daviplata", "Sistecredit", "Otro")
MAX_PAGO = 100_000_000


class PagoInvalido(Exception):
    """Error de negocio: se muestra tal cual al cajero."""


def _numero_recibo() -> str:
    from utils import ahora
    return f"CEA-{ahora():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


def _estado_nuevo(estado_actual: str, precio: int, total_pagado: float) -> str:
    # Misma regla del sistema de escritorio. Las matrículas históricas no se tocan.
    if estado_actual == "Histórico":
        return estado_actual
    if precio > 0 and total_pagado >= precio:
        return "Cancelado"
    return "Pendiente Pago" if total_pagado > 0 else "Activo"


def _es_duplicado(e: Exception) -> bool:
    # ORA-00001: restricción única violada (número de recibo repetido)
    err = e.args[0] if e.args else None
    return getattr(err, "code", None) == 1


@bp.route("/pagos/registrar", methods=["POST"])
@login_required(roles=Config.ROLES_COBRO)
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
        if valor <= 0 or valor > MAX_PAGO:
            raise PagoInvalido("El valor a abonar debe ser mayor a $0.")

        with db.transaccion() as cur:
            cur.execute("SELECT id, COALESCE(precio_total, 0) AS precio_total, estado "
                        "FROM matriculas WHERE id = %s FOR UPDATE", (mid,))
            mat = cur.fetchone()
            if not mat:
                raise PagoInvalido("No existe esa matrícula.")

            cur.execute("SELECT COALESCE(SUM(valor), 0) AS total FROM pagos "
                        "WHERE id_matricula = %s", (mid,))
            pagado = float(cur.fetchone()["total"])
            precio = int(mat["precio_total"])
            saldo = max(precio - pagado, 0)

            # El servidor decide, no el navegador: no se aceptan abonos mayores al saldo.
            if precio > 0 and valor > saldo:
                raise PagoInvalido(f"El abono supera el saldo pendiente (${int(saldo):,}).".replace(",", "."))

            numero = None
            for _ in range(3):  # reintento si el número de recibo se repite
                candidato = _numero_recibo()
                try:
                    cur.execute("""
                        INSERT INTO pagos (id_matricula, concepto, valor, metodo_pago,
                                           numero_recibo, usuario_id, observaciones, acompanante)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (mid, concepto, valor, metodo, candidato,
                          session["uid"], observaciones, acompanante))
                    numero = candidato
                    break
                except oracledb.IntegrityError as e:
                    if not _es_duplicado(e):
                        raise
            if not numero:
                raise PagoInvalido("No se pudo generar el número de recibo. Intenta de nuevo.")

            cur.execute("UPDATE matriculas SET estado = %s WHERE id = %s",
                        (_estado_nuevo(mat["estado"], precio, pagado + valor), mid))

    except PagoInvalido as e:
        return jsonify(ok=False, error=str(e)), 400
    except Exception:
        current_app.logger.exception("Error registrando pago")
        return jsonify(ok=False, error="No se pudo guardar el pago. Intenta de nuevo."), 500

    cambio = max(recibido - valor, 0) if metodo == "Efectivo" and recibido else 0
    url = url_for("pagos.recibo", numero=numero) + (f"?cambio={cambio}" if cambio else "")
    return jsonify(ok=True, numero_recibo=numero, saldo=max(saldo - valor, 0),
                   cambio=cambio, recibo_url=url)


@bp.route("/pagos/recibo/<numero>")
@login_required
def recibo(numero):
    if not re.fullmatch(r"[A-Za-z0-9-]{6,50}", numero):
        return Response("Recibo no válido", status=404)

    fila = db.fetchone("""
        SELECT p.numero_recibo, p.concepto, p.valor, p.metodo_pago, p.observaciones,
               p.acompanante, p.fecha_pago,
               a.nombres, a.apellidos, a.numero_documento,
               u.nombre AS cajero
        FROM pagos p
        JOIN matriculas m ON m.id = p.id_matricula
        JOIN alumnos a ON a.numero_documento = m.numero_documento
        LEFT JOIN usuarios u ON u.id = p.usuario_id
        WHERE p.numero_recibo = %s
    """, (numero,))
    if not fila:
        return Response("Recibo no encontrado", status=404)

    pdf = generar_recibo_pago_pdf({
        "numero_recibo": fila["numero_recibo"],
        "alumno_nombre": f"{fila['nombres']} {fila['apellidos']}",
        "alumno_doc": fila["numero_documento"],
        "concepto": fila["concepto"],
        "valor": float(fila["valor"]),
        "metodo_pago": fila["metodo_pago"],
        "cajero": fila["cajero"] or "—",
        "acompanante": fila["acompanante"] or "",
        "observaciones": fila["observaciones"] or "",
        "cambio": max(entero(request.args.get("cambio")), 0),
        "fecha": fila["fecha_pago"],
    })
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{numero}.pdf"'})