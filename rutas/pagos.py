"""Registro de pagos y recibo PDF (ticket 80 mm)."""
import re

from flask import Blueprint, Response, current_app, jsonify, request, session, url_for

import db
from auth import login_required, permiso_requerido, permisos_actuales
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


def _costos_con_asignado(cur, matricula_id):
    """Costos vigentes de la matrícula con lo ya asignado desde pagos no anulados."""
    filas = cur.execute("""
        SELECT c.id, c.concepto, c.valor,
               COALESCE((SELECT SUM(d.valor) FROM pago_distribucion d
                         JOIN pagos p ON p.id = d.id_pago
                         WHERE d.id_costo = c.id AND p.anulado = 0), 0) AS asignado
        FROM matricula_costos c
        WHERE c.id_matricula = %s AND c.anulado = 0
        ORDER BY c.fecha_registro, c.id
    """, (matricula_id,)).fetchall()
    return [{"id": f["id"], "concepto": f["concepto"], "valor": int(f["valor"]),
             "asignado": int(f["asignado"]),
             "restante": max(int(f["valor"]) - int(f["asignado"]), 0)} for f in filas]


def _leer_distribucion(d):
    """Normaliza [{costo_id, valor}] del navegador. costo_id nulo = ganancia."""
    crudo = d.get("distribucion")
    if not crudo:
        return []
    if not isinstance(crudo, list) or len(crudo) > 50:
        raise PagoInvalido("La distribución del pago no es válida.")
    partes, vistos = [], set()
    for fila in crudo:
        if not isinstance(fila, dict):
            raise PagoInvalido("La distribución del pago no es válida.")
        costo_id = fila.get("costo_id")
        costo_id = entero(costo_id) if costo_id not in (None, "", "ganancia") else None
        valor = entero(fila.get("valor"))
        if costo_id is not None and costo_id <= 0:
            raise PagoInvalido("La distribución del pago no es válida.")
        if valor < 0 or valor > MAX_PAGO:
            raise PagoInvalido("Los valores de la distribución no son válidos.")
        if valor == 0:
            continue
        if costo_id in vistos:
            raise PagoInvalido("Un costo aparece repetido en la distribución.")
        vistos.add(costo_id)
        partes.append((costo_id, valor))
    return partes


@bp.route("/pagos/distribucion/<int:matricula_id>")
@login_required
@permiso_requerido("registrar_pagos")
def distribucion_matricula(matricula_id):
    """Costos de la matrícula y cuánto de cada uno ya está cubierto, para repartir un pago."""
    if "gestionar_costos" not in permisos_actuales():
        return jsonify(ok=False, error="Sin permiso para repartir pagos."), 403
    with db.transaccion() as cur:
        costos = _costos_con_asignado(cur, matricula_id)
    return jsonify(ok=True, costos=costos)


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
        distribucion = _leer_distribucion(d)
        if distribucion and "gestionar_costos" not in permisos_actuales():
            raise PagoInvalido("No tienes permiso para repartir el pago entre costos y ganancia.")
        if mid <= 0:
            raise PagoInvalido("Matrícula no válida.")
        if metodo not in METODOS:
            raise PagoInvalido("Método de pago no válido.")
        if concepto.casefold() == "abono histórico previo":
            raise PagoInvalido("Ese concepto está reservado para pagos históricos migrados.")
        if valor <= 0 or valor > MAX_PAGO:
            raise PagoInvalido("El valor a abonar debe ser mayor a $0.")

        with db.transaccion() as cur:
            cur.execute("""
                SELECT m.id, COALESCE(m.precio_total, 0) AS precio_total, m.estado, m.archivado,
                       (SELECT COALESCE(SUM(p.valor), 0) FROM pagos p
                         WHERE p.id_matricula = m.id AND p.anulado = 0) AS pagado
                FROM matriculas m WHERE m.id = %s FOR UPDATE OF m.id
            """, (mid,))
            mat = cur.fetchone()
            if not mat:
                raise PagoInvalido("No existe esa matrícula.")
            if mat["archivado"] or mat["estado"] == "Histórico":
                raise PagoInvalido("No se pueden registrar pagos a una matrícula histórica o archivada.")
            pagado = float(mat["pagado"])
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

            if distribucion:
                if sum(v for _, v in distribucion) != valor:
                    raise PagoInvalido("El reparto debe sumar exactamente el valor del pago.")
                costos = {c["id"]: c for c in _costos_con_asignado(cur, mid)}
                for costo_id, parte in distribucion:
                    if costo_id is None:
                        continue
                    costo = costos.get(costo_id)
                    if not costo:
                        raise PagoInvalido("Un costo del reparto no existe o fue anulado.")
                    if parte > costo["restante"]:
                        raise PagoInvalido(
                            f"«{costo['concepto']}» solo admite {cop(costo['restante'])} más.")
                filas = " UNION ALL ".join(
                    "SELECT CAST(%s AS NUMBER) AS c, CAST(%s AS NUMBER) AS v FROM dual"
                    for _ in distribucion)
                params = tuple(x for parte in distribucion for x in parte)
                cur.execute("INSERT INTO pago_distribucion (id_pago, id_costo, valor) "
                            "SELECT p.id, d.c, d.v FROM pagos p CROSS JOIN (" + filas + ") d "
                            "WHERE p.numero_recibo = %s", params + (numero,))

            nuevo_estado = estado_matricula(mat["estado"], precio, pagado + valor)
            if nuevo_estado != mat["estado"]:
                cur.execute("UPDATE matriculas SET estado = %s WHERE id = %s", (nuevo_estado, mid))

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

    ver_todas = "ver_todas_cajas" in permisos_actuales()
    solicitud_copia = request.args.get("copia") == "1"
    fila = None
    tipo = None
    tabla_movimiento = None
    with db.transaccion() as cur:
        for tabla, clase in (
            ("pagos", "PAGO"),
            ("ingresos_caja", "INGRESO"),
            ("salidas_caja", "EGRESO"),
        ):
            filtro_usuario = "" if ver_todas else " AND usuario_id = %s"
            parametros = (numero,) if ver_todas else (numero, session["uid"])
            movimiento = cur.execute(
                f"SELECT usuario_id, fecha_impresion_original FROM {tabla} "
                f"WHERE numero_recibo = %s{filtro_usuario} FOR UPDATE",
                parametros,
            ).fetchone()
            if not movimiento:
                continue
            tipo, tabla_movimiento = clase, tabla
            if clase == "PAGO":
                fila = cur.execute("""
                    SELECT p.numero_recibo, p.concepto, p.valor, p.metodo_pago,
                           p.observaciones, p.cambio, p.acompanante, p.fecha_pago,
                           a.nombres, a.apellidos, a.tipo_documento, a.numero_documento,
                           u.nombre AS cajero, p.anulado, p.motivo_anulacion
                    FROM pagos p
                    JOIN matriculas m ON m.id = p.id_matricula
                    JOIN alumnos a ON a.numero_documento = m.numero_documento
                    LEFT JOIN usuarios u ON u.id = p.usuario_id
                    WHERE p.numero_recibo = %s
                """, (numero,)).fetchone()
            else:
                fecha_col = "fecha_ingreso" if clase == "INGRESO" else "fecha_salida"
                fila = cur.execute(
                    f"SELECT numero_recibo, concepto, valor, {fecha_col} AS fecha, "
                    f"anulado, motivo_anulacion, usuario_id FROM {tabla} "
                    "WHERE numero_recibo = %s",
                    (numero,),
                ).fetchone()
                if fila:
                    cajero = cur.execute(
                        "SELECT nombre FROM usuarios WHERE id = %s",
                        (fila["usuario_id"],),
                    ).fetchone()
                    fila["cajero"] = cajero["nombre"] if cajero else None
            break
        if not fila or not tipo or not tabla_movimiento:
            return Response("Recibo no encontrado", status=404)

        copia = solicitud_copia or movimiento["fecha_impresion_original"] is not None
        if movimiento["fecha_impresion_original"] is None:
            cur.execute(
                f"UPDATE {tabla_movimiento} "
                "SET impreso_original_por = %s, fecha_impresion_original = CURRENT_TIMESTAMP "
                "WHERE numero_recibo = %s AND fecha_impresion_original IS NULL",
                (session["uid"], numero),
            )
        if copia:
            cur.execute(
                "INSERT INTO reimpresiones_recibos (tipo, numero_recibo, usuario_id) "
                "VALUES (%s, %s, %s)",
                (tipo, numero, session["uid"]),
            )

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
            "alumno_tipo_documento": fila["tipo_documento"],
            "metodo_pago": fila["metodo_pago"],
            "acompanante": fila["acompanante"] or "",
            "observaciones": fila["observaciones"] or "",
            "cambio": int(fila["cambio"] or 0),
        })
        pdf = generar_recibo_pago_pdf(detalles)
    else:
        detalles["tipo"] = tipo
        pdf = generar_recibo_movimiento_pdf(detalles)
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{numero}.pdf"'})
