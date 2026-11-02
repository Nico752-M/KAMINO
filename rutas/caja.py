"""Apertura, cierre y consulta de cajas individuales."""
from datetime import date, timedelta
import re

import oracledb
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

import db
from auth import login_required, permiso_requerido, permisos_actuales, usuario_actual
from servicios.recibos import numero_recibo
from utils import cop, entero, hoy

bp = Blueprint("caja", __name__)
MAX_CAJA = 999_999_999_999


def _fecha_param() -> date:
    try:
        return date.fromisoformat(request.args.get("fecha", ""))
    except ValueError:
        return hoy()


def caja_abierta(cur, usuario_id):
    """Obtiene y bloquea la caja del usuario para evitar movimientos durante el cierre."""
    return cur.execute(
        "SELECT id, monto_apertura FROM cajas "
        "WHERE usuario_id = %s AND estado = 'ABIERTA' FOR UPDATE",
        (usuario_id,),
    ).fetchone()


def _entero_form(nombre: str, defecto: str = "") -> int | None:
    valor = request.form.get(nombre, defecto).strip()
    if not valor.isascii() or not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)", valor):
        return None
    return entero(valor, -1)


@bp.route("/caja")
@login_required
@permiso_requerido("ver_caja")
def resumen():
    dia = _fecha_param()
    sig = dia + timedelta(days=1)
    uid = session["uid"]
    admin = usuario_actual()["rol"] == "admin"
    cajero_filtro = request.args.get("cajero", "").strip()
    if not admin or not cajero_filtro.isdecimal():
        cajero_filtro = ""
    filtro_usuario = int(cajero_filtro) if cajero_filtro else (None if admin else uid)
    error = None
    movs, cajas = [], []
    recibo_q = request.args.get("recibo", "").strip()[:50]
    recibo_nuevo = request.args.get("recibo_nuevo", "").strip()[:50]
    historial_modo = request.args.get("historial", "dia")
    if historial_modo not in ("dia", "todos"):
        historial_modo = "dia"
    try:
        pagina_historial = max(1, min(int(request.args.get("pagina", "1")), 1_000_000))
    except ValueError:
        pagina_historial = 1
    historial_anterior = pagina_historial > 1
    historial_siguiente = False
    busqueda_recibos = []
    totales = {"efectivo": 0.0, "otros": 0.0, "ingresos": 0.0, "salidas": 0.0,
               "apertura": 0.0, "esperado": 0.0, "contado": 0.0, "diferencia": 0.0}
    try:
        filtro_pago = " AND p.usuario_id = %s" if filtro_usuario is not None else ""
        filtro_ingreso = " AND i.usuario_id = %s" if filtro_usuario is not None else ""
        filtro_salida = " AND s.usuario_id = %s" if filtro_usuario is not None else ""
        params_movimientos = (dia, sig)
        if filtro_usuario is not None:
            params_movimientos += (filtro_usuario,)
        params_movimientos += (dia, sig)
        if filtro_usuario is not None:
            params_movimientos += (filtro_usuario,)
        params_movimientos += (dia, sig)
        if filtro_usuario is not None:
            params_movimientos += (filtro_usuario,)
        movimientos = db.fetchall(f"""
            SELECT 'pago' AS tipo, p.numero_recibo AS recibo, p.fecha_pago AS momento,
                   COALESCE(TRIM(a.nombres || ' ' || a.apellidos), 'Sin alumno')
                       || ' — ' || p.concepto AS detalle,
                   p.metodo_pago AS metodo, p.valor, u.nombre AS cajero,
                   p.anulado, p.motivo_anulacion
            FROM pagos p
            LEFT JOIN matriculas m ON m.id = p.id_matricula
            LEFT JOIN alumnos a ON a.numero_documento = m.numero_documento
            LEFT JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.fecha_pago >= %s AND p.fecha_pago < %s
              AND p.concepto <> 'Abono histórico previo'{filtro_pago}
            UNION ALL
            SELECT 'ingreso', i.numero_recibo, i.fecha_ingreso, i.concepto,
                   'Efectivo', i.valor, u.nombre, i.anulado, i.motivo_anulacion
            FROM ingresos_caja i
            LEFT JOIN usuarios u ON u.id = i.usuario_id
            WHERE i.fecha_ingreso >= %s AND i.fecha_ingreso < %s{filtro_ingreso}
            UNION ALL
            SELECT 'salida', s.numero_recibo, s.fecha_salida, s.concepto,
                   'Efectivo', s.valor, u.nombre, s.anulado, s.motivo_anulacion
            FROM salidas_caja s
            LEFT JOIN usuarios u ON u.id = s.usuario_id
            WHERE s.fecha_salida >= %s AND s.fecha_salida < %s{filtro_salida}
        """, params_movimientos)

        for movimiento in movimientos:
            tipo = movimiento["tipo"]
            valor = float(movimiento["valor"])
            anulado = bool(movimiento["anulado"])
            if not anulado:
                if tipo == "pago":
                    totales["efectivo" if movimiento["metodo"] == "Efectivo" else "otros"] += valor
                else:
                    totales["ingresos" if tipo == "ingreso" else "salidas"] += valor
            movs.append({
                "tipo": tipo, "recibo": movimiento["recibo"], "momento": movimiento["momento"],
                "detalle": movimiento["detalle"] or "Sin alumno", "metodo": movimiento["metodo"],
                "valor": -valor if tipo == "salida" else valor,
                "cajero": movimiento["cajero"] or "—", "anulado": anulado,
                "motivo_anulacion": movimiento["motivo_anulacion"],
            })
        movs.sort(key=lambda mov: mov["momento"])

        filtro_caja = " AND c.usuario_id = %s" if filtro_usuario is not None else ""
        filtro_cajas_estado = """
            WHERE ((c.estado = 'CERRADA' AND c.fecha_cierre >= %s AND c.fecha_cierre < %s)
                OR (c.estado = 'ABIERTA' AND c.fecha_apertura >= %s AND c.fecha_apertura < %s)"""
        params_caja = (dia, sig, dia, sig)
        if dia == hoy():
            filtro_cajas_estado += " OR (c.estado = 'ABIERTA' AND c.fecha_apertura < %s)"
            params_caja += (sig,)
        filtro_cajas_estado += ")"
        if filtro_usuario is not None:
            params_caja += (filtro_usuario,)
        cajas = db.fetchall(f"""
            SELECT c.id, c.usuario_id, u.nombre AS cajero, c.estado, c.fecha_apertura,
                   c.fecha_cierre, c.monto_apertura, c.monto_cierre,
                   c.efectivo_esperado, c.diferencia, c.observaciones_cierre,
                   NVL((SELECT SUM(p.valor) FROM pagos p
                        WHERE p.caja_id = c.id AND p.metodo_pago = 'Efectivo'
                          AND p.concepto <> 'Abono histórico previo' AND p.anulado = 0), 0) AS pagos_efectivo,
                   NVL((SELECT SUM(p.valor) FROM pagos p
                        WHERE p.caja_id = c.id AND p.metodo_pago <> 'Efectivo'
                          AND p.concepto <> 'Abono histórico previo' AND p.anulado = 0), 0) AS pagos_otros,
                   NVL((SELECT SUM(i.valor) FROM ingresos_caja i
                        WHERE i.caja_id = c.id AND i.anulado = 0), 0) AS ingresos,
                   NVL((SELECT SUM(s.valor) FROM salidas_caja s
                        WHERE s.caja_id = c.id AND s.anulado = 0), 0) AS salidas
            FROM cajas c
            JOIN usuarios u ON u.id = c.usuario_id
            {filtro_cajas_estado}{filtro_caja}
            ORDER BY c.fecha_apertura DESC
        """, params_caja)
        for caja in cajas:
            apertura = float(caja["monto_apertura"])
            esperado = apertura + float(caja["pagos_efectivo"]) \
                + float(caja["ingresos"]) - float(caja["salidas"])
            contado = float(caja["monto_cierre"]) if caja["monto_cierre"] is not None else 0
            diferencia = float(caja["diferencia"]) if caja["diferencia"] is not None else 0
            caja.update({"efectivo_calculado": esperado, "contado_calculado": contado,
                         "diferencia_calculada": diferencia})
            totales["apertura"] += apertura
            totales["esperado"] += esperado
            totales["contado"] += contado
            totales["diferencia"] += diferencia
    except Exception:
        error = "No se pudo consultar la caja del día."
        current_app.logger.exception("No se pudo consultar la caja del día")

    if historial_modo == "todos":
        try:
            filtro_pago_todos = " AND p.usuario_id = %s" if filtro_usuario is not None else ""
            filtro_ingreso_todos = " AND i.usuario_id = %s" if filtro_usuario is not None else ""
            filtro_salida_todos = " AND s.usuario_id = %s" if filtro_usuario is not None else ""
            params_todos = ()
            if filtro_usuario is not None:
                params_todos += (filtro_usuario,)
            if filtro_usuario is not None:
                params_todos += (filtro_usuario,)
            if filtro_usuario is not None:
                params_todos += (filtro_usuario,)
            params_todos += ((pagina_historial - 1) * 50, 51)
            filas_historial = db.fetchall(f"""
                SELECT * FROM (
                    SELECT 'pago' AS tipo, p.numero_recibo AS recibo, p.fecha_pago AS momento,
                           COALESCE(TRIM(a.nombres || ' ' || a.apellidos), 'Sin alumno')
                               || ' — ' || p.concepto AS detalle,
                           p.metodo_pago AS metodo, p.valor, u.nombre AS cajero,
                           p.anulado, p.motivo_anulacion
                    FROM pagos p
                    LEFT JOIN matriculas m ON m.id = p.id_matricula
                    LEFT JOIN alumnos a ON a.numero_documento = m.numero_documento
                    LEFT JOIN usuarios u ON u.id = p.usuario_id
                    WHERE p.concepto <> 'Abono histórico previo'{filtro_pago_todos}
                    UNION ALL
                    SELECT 'ingreso', i.numero_recibo, i.fecha_ingreso, i.concepto,
                           'Efectivo', i.valor, u.nombre, i.anulado, i.motivo_anulacion
                    FROM ingresos_caja i
                    LEFT JOIN usuarios u ON u.id = i.usuario_id
                    WHERE 1 = 1{filtro_ingreso_todos}
                    UNION ALL
                    SELECT 'salida', s.numero_recibo, s.fecha_salida, s.concepto,
                           'Efectivo', s.valor, u.nombre, s.anulado, s.motivo_anulacion
                    FROM salidas_caja s
                    LEFT JOIN usuarios u ON u.id = s.usuario_id
                    WHERE 1 = 1{filtro_salida_todos}
                )
                ORDER BY momento DESC
                OFFSET %s ROWS FETCH NEXT %s ROWS ONLY
            """, params_todos)
            historial_siguiente = len(filas_historial) > 50
            movs = [{
                "tipo": fila["tipo"], "recibo": fila["recibo"], "momento": fila["momento"],
                "detalle": fila["detalle"] or "Sin alumno", "metodo": fila["metodo"],
                "valor": -float(fila["valor"]) if fila["tipo"] == "salida" else float(fila["valor"]),
                "cajero": fila["cajero"] or "—", "anulado": bool(fila["anulado"]),
                "motivo_anulacion": fila["motivo_anulacion"],
            } for fila in filas_historial[:50]]
        except Exception:
            current_app.logger.exception("No se pudo consultar el historial completo de caja")
            error = error or "No se pudo cargar el historial de caja."

    if recibo_q and "ver_recibos" in permisos_actuales():
        try:
            for tabla, tipo, fecha_col, usuario_col in (
                ("pagos", "PAGO", "fecha_pago", "usuario_id"),
                ("ingresos_caja", "INGRESO", "fecha_ingreso", "usuario_id"),
                ("salidas_caja", "EGRESO", "fecha_salida", "usuario_id"),
            ):
                filtro_recibo = f" AND {usuario_col} = %s" if filtro_usuario is not None else ""
                params_recibo = (recibo_q, filtro_usuario) if filtro_usuario is not None else (recibo_q,)
                fila = db.fetchone(
                    f"SELECT numero_recibo, concepto, valor, {fecha_col} AS momento, "
                    f"anulado FROM {tabla} WHERE numero_recibo = %s{filtro_recibo}",
                    params_recibo,
                )
                if fila:
                    busqueda_recibos.append({**fila, "tipo": tipo})
        except Exception:
            current_app.logger.exception("No se pudo buscar el recibo")
            error = error or "No se pudo buscar el recibo."

    totales["en_caja"] = totales["esperado"]
    admin_cajeros = []
    if admin:
        try:
            admin_cajeros = db.fetchall(
                "SELECT id, nombre FROM usuarios WHERE activo = 1 ORDER BY nombre"
            )
        except Exception:
            current_app.logger.exception("No se pudo consultar la lista de cajeros")

    caja_actual = None
    puede_cobrar = "registrar_pagos" in permisos_actuales()
    if puede_cobrar:
        try:
            caja_actual = db.fetchone(
                """SELECT c.id, c.fecha_apertura, c.monto_apertura,
                          c.monto_apertura
                          + NVL((SELECT SUM(p.valor) FROM pagos p
                                 WHERE p.caja_id = c.id AND p.metodo_pago = 'Efectivo'
                                   AND p.concepto <> 'Abono histórico previo'
                                   AND p.anulado = 0), 0)
                          + NVL((SELECT SUM(i.valor) FROM ingresos_caja i
                                 WHERE i.caja_id = c.id AND i.anulado = 0), 0)
                          - NVL((SELECT SUM(s.valor) FROM salidas_caja s
                                 WHERE s.caja_id = c.id AND s.anulado = 0), 0)
                          AS efectivo_esperado
                   FROM cajas c
                   WHERE c.usuario_id = %s AND c.estado = 'ABIERTA'""",
                (uid,)
            )
        except Exception:
            current_app.logger.exception("No se pudo consultar la caja abierta del usuario")
            error = error or "No se pudo consultar tu caja abierta."

    return render_template("tesoreria.html", dia=dia, movs=movs, cajas=cajas,
                           t=totales, error=error, admin=admin, cajeros=admin_cajeros,
                           cajero_filtro=cajero_filtro, caja_actual=caja_actual,
                           puede_cobrar=puede_cobrar, recibo_q=recibo_q,
                           busqueda_recibos=busqueda_recibos, recibo_nuevo=recibo_nuevo,
                           historial_modo=historial_modo, pagina_historial=pagina_historial,
                           historial_anterior=historial_anterior,
                           historial_siguiente=historial_siguiente)


@bp.route("/caja/abrir", methods=["POST"])
@login_required
@permiso_requerido("registrar_pagos")
def abrir():
    monto = _entero_form("monto_apertura")
    if monto is None or monto < 0 or monto > MAX_CAJA:
        flash("El monto inicial debe ser un entero entre $0 y $999.999.999.999.", "error")
        return redirect(url_for("caja.resumen"))
    try:
        with db.transaccion() as cur:
            cur.execute(
                "INSERT INTO cajas (usuario_id, monto_apertura, estado) VALUES (%s, %s, 'ABIERTA')",
                (session["uid"], monto),
            )
    except oracledb.IntegrityError as error:
        causa = error.args[0] if error.args else None
        if getattr(causa, "code", None) == 1:
            flash("Ya tienes una caja abierta. Ciérrala antes de iniciar otra.", "error")
            return redirect(url_for("caja.resumen"))
        current_app.logger.exception("Error abriendo caja")
        flash("No se pudo abrir la caja. Intenta de nuevo.", "error")
        return redirect(url_for("caja.resumen"))
    except Exception:
        current_app.logger.exception("Error abriendo caja")
        flash("No se pudo abrir la caja. Intenta de nuevo.", "error")
        return redirect(url_for("caja.resumen"))

    flash("Caja abierta correctamente.", "ok")
    return redirect(url_for("caja.resumen"))


@bp.route("/caja/cerrar", methods=["POST"])
@login_required
@permiso_requerido("registrar_pagos")
def cerrar():
    monto = _entero_form("monto_cierre")
    observaciones = " ".join(request.form.get("observaciones", "").split()) or None
    if monto is None or monto < 0 or monto > MAX_CAJA:
        flash("El efectivo contado debe ser un entero entre $0 y $999.999.999.999.", "error")
        return redirect(url_for("caja.resumen"))
    if observaciones and len(observaciones) > 1000:
        flash("Las observaciones admiten hasta 1.000 caracteres.", "error")
        return redirect(url_for("caja.resumen"))

    try:
        with db.transaccion() as cur:
            caja = caja_abierta(cur, session["uid"])
            if not caja:
                flash("No tienes una caja abierta para cerrar.", "error")
                return redirect(url_for("caja.resumen"))
            pagos = cur.execute("""
                SELECT COALESCE(SUM(valor), 0) AS efectivo
                FROM pagos
                WHERE caja_id = %s AND metodo_pago = 'Efectivo'
                  AND concepto <> 'Abono histórico previo' AND anulado = 0
            """, (caja["id"],)).fetchone()["efectivo"]
            ingresos = cur.execute(
                "SELECT COALESCE(SUM(valor), 0) AS total FROM ingresos_caja "
                "WHERE caja_id = %s AND anulado = 0",
                (caja["id"],),
            ).fetchone()["total"]
            salidas = cur.execute(
                "SELECT COALESCE(SUM(valor), 0) AS total FROM salidas_caja "
                "WHERE caja_id = %s AND anulado = 0",
                (caja["id"],),
            ).fetchone()["total"]
            esperado = int(caja["monto_apertura"]) + int(pagos) + int(ingresos) - int(salidas)
            diferencia = monto - esperado
            cur.execute("""
                UPDATE cajas
                SET estado = 'CERRADA', fecha_cierre = CURRENT_TIMESTAMP,
                    monto_cierre = %s, efectivo_esperado = %s, diferencia = %s,
                    observaciones_cierre = %s
                WHERE id = %s AND usuario_id = %s AND estado = 'ABIERTA'
            """, (monto, esperado, diferencia, observaciones, caja["id"], session["uid"]))
    except Exception:
        current_app.logger.exception("Error cerrando caja")
        flash("No se pudo cerrar la caja. Intenta de nuevo.", "error")
        return redirect(url_for("caja.resumen"))

    flash(f"Caja cerrada. Efectivo esperado: {cop(esperado)}; diferencia: {cop(diferencia)}.", "ok")
    return redirect(url_for("caja.resumen"))


@bp.route("/caja/movimientos/<tipo>", methods=["POST"])
@login_required
@permiso_requerido("gestionar_caja")
def registrar_movimiento(tipo):
    tablas = {"ingreso": ("ingresos_caja", "Ingreso manual"),
              "salida": ("salidas_caja", "Salida de caja")}
    if tipo not in tablas:
        return "Tipo de movimiento no válido.", 404

    concepto = " ".join(request.form.get("concepto", "").split())
    valor = _entero_form("valor")
    if not concepto or len(concepto) > 200:
        flash("El concepto es obligatorio y admite hasta 200 caracteres.", "error")
        return redirect(url_for("caja.resumen"))
    if valor is None or valor <= 0 or valor > 100_000_000:
        flash("El valor debe estar entre $1 y $100.000.000.", "error")
        return redirect(url_for("caja.resumen"))

    tabla, etiqueta = tablas[tipo]
    try:
        with db.transaccion() as cur:
            caja = caja_abierta(cur, session["uid"])
            if not caja:
                flash("Abre tu caja antes de registrar un movimiento.", "error")
                return redirect(url_for("caja.resumen"))
            recibo = numero_recibo(cur)
            cur.execute(
                f"INSERT INTO {tabla} (numero_recibo, concepto, valor, usuario_id, caja_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (recibo, concepto, valor, session["uid"], caja["id"]),
            )
    except Exception:
        current_app.logger.exception("Error registrando %s en caja", tipo)
        flash("No se pudo registrar el movimiento. Intenta de nuevo.", "error")
        return redirect(url_for("caja.resumen"))

    flash(f"{etiqueta} registrada. Recibo {recibo}.", "ok")
    return redirect(url_for("caja.resumen", recibo_nuevo=recibo))
