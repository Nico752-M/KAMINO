"""Apertura, cierre y consulta de cajas individuales."""
from datetime import date, timedelta
from io import BytesIO
import json
import re

import oracledb
from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, session, url_for

import db
from auth import login_required, permiso_requerido, permisos_actuales, usuario_actual
from servicios.bancos import BancoError, catalogo_destinos, movimiento_manual, parsear_destino
from servicios.cierres import caja_cerrada, recalcular_cierre, registrar_auditoria
from servicios.recibos import numero_recibo
from utils import cacheado, cop, hoy, parsear_pesos

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
    valor = request.form.get(nombre, defecto)
    return parsear_pesos(valor)


def _datos_cierre(caja_id: int) -> dict | None:
    ver_todas = "ver_todas_cajas" in permisos_actuales()
    filtro_usuario = "" if ver_todas else " AND c.usuario_id = %s"
    params = (caja_id,) if ver_todas else (caja_id, session["uid"])
    caja = db.fetchone(f"""
        SELECT c.id, c.usuario_id, u.nombre AS cajero, c.fecha_apertura, c.fecha_cierre,
               c.monto_apertura, c.monto_cierre, c.efectivo_esperado, c.diferencia,
               c.observaciones_cierre, c.modificada_despues, c.efectivo_esperado_original,
               c.fecha_ultima_modificacion,
               DBMS_LOB.SUBSTR(c.conteo_denominaciones, 4000, 1) AS conteo_denominaciones
        FROM cajas c
        JOIN usuarios u ON u.id = c.usuario_id
        WHERE c.id = %s AND c.estado = 'CERRADA'{filtro_usuario}
    """, params)
    if not caja:
        return None

    totales = db.fetchone("""
        SELECT
            NVL((SELECT SUM(p.valor) FROM pagos p WHERE p.caja_id = %s
                 AND p.metodo_pago = 'Efectivo' AND p.anulado = 0
                 AND p.concepto <> 'Abono histórico previo'), 0) AS pagos_efectivo,
            NVL((SELECT SUM(p.valor) FROM pagos p WHERE p.caja_id = %s
                 AND p.metodo_pago <> 'Efectivo' AND p.anulado = 0
                 AND p.concepto <> 'Abono histórico previo'), 0) AS pagos_otros,
            NVL((SELECT SUM(i.valor) FROM ingresos_caja i
                 WHERE i.caja_id = %s AND i.anulado = 0), 0) AS ingresos,
            NVL((SELECT SUM(s.valor) FROM salidas_caja s
                 WHERE s.caja_id = %s AND s.anulado = 0), 0) AS salidas
        FROM dual
    """, (caja_id, caja_id, caja_id, caja_id))
    pagos = db.fetchall("""
        SELECT p.fecha_pago AS momento, p.numero_recibo, p.concepto, m.categoria,
               TRIM(a.nombres || ' ' || a.apellidos) AS alumno,
               p.metodo_pago, p.valor, p.anulado, p.motivo_anulacion, p.confirmado
        FROM pagos p
        LEFT JOIN matriculas m ON m.id = p.id_matricula
        LEFT JOIN alumnos a ON a.numero_documento = m.numero_documento
        WHERE p.caja_id = %s AND p.concepto <> 'Abono histórico previo'
        ORDER BY p.fecha_pago, p.numero_recibo
    """, (caja_id,))
    ingresos = db.fetchall("""
        SELECT fecha_ingreso AS momento, numero_recibo, concepto, categoria, valor,
               anulado, motivo_anulacion
        FROM ingresos_caja WHERE caja_id = %s
        ORDER BY fecha_ingreso, numero_recibo
    """, (caja_id,))
    salidas = db.fetchall("""
        SELECT fecha_salida AS momento, numero_recibo, concepto, categoria, valor,
               anulado, motivo_anulacion
        FROM salidas_caja WHERE caja_id = %s
        ORDER BY fecha_salida, numero_recibo
    """, (caja_id,))
    return {"caja": caja, "totales": totales, "pagos": pagos,
            "ingresos": ingresos, "salidas": salidas}


@bp.route("/caja/cierres/<int:caja_id>/pdf")
@login_required
@permiso_requerido("ver_caja")
def exportar_cierre_pdf(caja_id: int):
    datos = _datos_cierre(caja_id)
    if not datos:
        abort(404)
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    caja, t = datos["caja"], datos["totales"]
    salida = BytesIO()
    pdf = SimpleDocTemplate(salida, pagesize=landscape(letter),
                            leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm)
    estilos = getSampleStyleSheet()
    estilos.add(ParagraphStyle(name="TituloCierre", parent=estilos["Title"],
                               alignment=TA_CENTER, fontSize=16, leading=20))
    estilos.add(ParagraphStyle(name="Celda", parent=estilos["BodyText"],
                               fontSize=7, leading=8))
    story = [
        Paragraph("CIERRE DE CAJA", estilos["TituloCierre"]),
        Paragraph(f"Cajero: {escape(str(caja['cajero']))} · "
                  f"Apertura: {caja['fecha_apertura'].strftime('%d/%m/%Y %H:%M')} · "
                  f"Cierre: {caja['fecha_cierre'].strftime('%d/%m/%Y %H:%M')}",
                  estilos["BodyText"]),
        Spacer(1, 8),
    ]
    resumen = [
        ["Resumen", "Valor"],
        ["Base inicial", cop(caja["monto_apertura"])],
        ["Pagos en efectivo", cop(t["pagos_efectivo"])],
        ["Pagos otros medios", cop(t["pagos_otros"])],
        ["Ingresos manuales", cop(t["ingresos"])],
        ["Salidas manuales", cop(t["salidas"])],
        ["Efectivo esperado", cop(caja["efectivo_esperado"])],
        ["Efectivo contado", cop(caja["monto_cierre"])],
        ["Diferencia", cop(caja["diferencia"])],
    ]
    if caja["modificada_despues"]:
        resumen.append(["Modificado después del cierre",
                        f"Esperado original {cop(caja['efectivo_esperado_original'])} · "
                        f"{caja['fecha_ultima_modificacion'].strftime('%d/%m/%Y %H:%M')}"])
    story.extend([Table(resumen, hAlign="LEFT", colWidths=[90 * mm, 42 * mm]),
                  Spacer(1, 10)])
    conteo = json.loads(caja["conteo_denominaciones"] or "{}")
    if conteo:
        story.append(Paragraph("Conteo de billetes y monedas", estilos["Heading2"]))
        story.append(Table(
            [["Denominación", "Cantidad", "Subtotal"]] + [
                [cop(int(denominacion)), cantidad,
                 cop(int(denominacion) * int(cantidad))]
                for denominacion, cantidad in sorted(
                    conteo.items(), key=lambda item: int(item[0]), reverse=True)
            ],
            hAlign="LEFT", colWidths=[45 * mm, 30 * mm, 45 * mm],
        ))
        story.append(Spacer(1, 10))

    def tabla_movimientos(titulo, encabezados, registros, filas):
        story.append(Paragraph(titulo, estilos["Heading2"]))
        contenido = [encabezados]
        for fila in registros:
            contenido.append([Paragraph(escape(str(valor or "—")), estilos["Celda"])
                              for valor in filas(fila)])
        if len(contenido) == 1:
            contenido.append([Paragraph("Sin movimientos", estilos["Celda"])]
                             + ["" for _ in encabezados[1:]])
        tabla = Table(contenido, repeatRows=1, hAlign="LEFT")
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#253449")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#ccd2da")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f3f5f7")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.extend([tabla, Spacer(1, 8)])

    fecha = lambda fila: fila["momento"].strftime("%d/%m/%Y %H:%M")
    estado = lambda fila: "ANULADO" if fila["anulado"] else "Válido"
    estado_pago = lambda fila: ("ANULADO" if fila["anulado"]
                                else "Confirmado" if fila["confirmado"] else "Pendiente")
    tabla_movimientos(
        "Pagos", ["Fecha", "Recibo", "Alumno", "Categoría", "Concepto", "Medio", "Valor", "Estado"],
        datos["pagos"],
        lambda r: (fecha(r), r["numero_recibo"], r["alumno"], r["categoria"], r["concepto"],
                   r["metodo_pago"], cop(r["valor"]), estado_pago(r)),
    )
    for titulo, registros in (("Ingresos", datos["ingresos"]), ("Salidas", datos["salidas"])):
        tabla_movimientos(
            titulo, ["Fecha", "Recibo", "Categoría", "Concepto", "Valor", "Estado", "Motivo de anulación"],
            registros,
            lambda r: (fecha(r), r["numero_recibo"], r["categoria"], r["concepto"], cop(r["valor"]),
                       estado(r), r["motivo_anulacion"]),
        )
    if caja["observaciones_cierre"]:
        story.append(Paragraph("Observaciones: " + escape(caja["observaciones_cierre"]),
                               estilos["BodyText"]))
    pdf.build(story)
    return Response(salida.getvalue(), mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="cierre-{caja_id}.pdf"'})


@bp.route("/caja/cierres/<int:caja_id>/excel")
@login_required
@permiso_requerido("ver_caja")
def exportar_cierre_excel(caja_id: int):
    datos = _datos_cierre(caja_id)
    if not datos:
        abort(404)
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    caja, t = datos["caja"], datos["totales"]
    libro = Workbook()
    resumen = libro.active
    resumen.title = "Resumen"
    resumen.append(["Cierre de caja", ""])
    resumen.append(["Cajero", caja["cajero"]])
    resumen.append(["Apertura", caja["fecha_apertura"]])
    resumen.append(["Cierre", caja["fecha_cierre"]])
    resumen.append(["Base inicial", caja["monto_apertura"]])
    resumen.append(["Pagos en efectivo", t["pagos_efectivo"]])
    resumen.append(["Pagos otros medios", t["pagos_otros"]])
    resumen.append(["Ingresos manuales", t["ingresos"]])
    resumen.append(["Salidas manuales", t["salidas"]])
    resumen.append(["Efectivo esperado", caja["efectivo_esperado"]])
    resumen.append(["Efectivo contado", caja["monto_cierre"]])
    resumen.append(["Diferencia", caja["diferencia"]])
    if caja["modificada_despues"]:
        resumen.append(["Modificado después del cierre",
                        f"Esperado original {caja['efectivo_esperado_original']} · "
                        f"{caja['fecha_ultima_modificacion'].strftime('%d/%m/%Y %H:%M')}"])
    resumen.append(["Observaciones", caja["observaciones_cierre"] or ""])
    conteo = json.loads(caja["conteo_denominaciones"] or "{}")
    if conteo:
        conteo_hoja = libro.create_sheet("Conteo")
        conteo_hoja.append(["Denominación", "Cantidad", "Subtotal"])
        for denominacion, cantidad in sorted(
                conteo.items(), key=lambda item: int(item[0]), reverse=True):
            conteo_hoja.append(
                [int(denominacion), int(cantidad), int(denominacion) * int(cantidad)])
        conteo_hoja.freeze_panes = "A2"
    for hoja in libro.worksheets:
        hoja.freeze_panes = "A2"

    definiciones = (
        ("Pagos", ["Fecha", "Recibo", "Alumno", "Categoría", "Concepto", "Medio", "Valor", "Estado", "Motivo"],
         datos["pagos"],
         lambda r: (r["momento"], r["numero_recibo"], r["alumno"], r["categoria"], r["concepto"],
                    r["metodo_pago"], r["valor"],
                    "Anulado" if r["anulado"] else "Confirmado" if r["confirmado"] else "Pendiente",
                    r["motivo_anulacion"])),
        ("Ingresos", ["Fecha", "Recibo", "Categoría", "Concepto", "Valor", "Estado", "Motivo"],
         datos["ingresos"],
         lambda r: (r["momento"], r["numero_recibo"], r["categoria"], r["concepto"], r["valor"],
                    "Anulado" if r["anulado"] else "Válido", r["motivo_anulacion"])),
        ("Salidas", ["Fecha", "Recibo", "Categoría", "Concepto", "Valor", "Estado", "Motivo"],
         datos["salidas"],
         lambda r: (r["momento"], r["numero_recibo"], r["categoria"], r["concepto"], r["valor"],
                    "Anulado" if r["anulado"] else "Válido", r["motivo_anulacion"])),
    )
    for nombre, encabezados, registros, convertir in definiciones:
        hoja = libro.create_sheet(nombre)
        hoja.append(encabezados)
        for fila in registros:
            hoja.append(list(convertir(fila)))
        hoja.freeze_panes = "A2"
        hoja.auto_filter.ref = hoja.dimensions

    for hoja in libro.worksheets:
        for fila in hoja.iter_rows():
            for celda in fila:
                if isinstance(celda.value, str):
                    celda.data_type = "s"
        for celda in hoja[1]:
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = PatternFill("solid", fgColor="253449")
            celda.alignment = Alignment(vertical="center")
        for columna in hoja.columns:
            letra = columna[0].column_letter
            ancho = min(max(max(len(str(c.value or "")) for c in columna) + 2, 12), 42)
            hoja.column_dimensions[letra].width = ancho
        if hoja.title == "Resumen":
            hoja.column_dimensions["A"].width = 28
            hoja.column_dimensions["B"].width = 34

    salida = BytesIO()
    libro.save(salida)
    return Response(
        salida.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="cierre-{caja_id}.xlsx"'},
    )


@bp.route("/caja")
@login_required
@permiso_requerido("ver_caja")
def resumen():
    dia = _fecha_param()
    sig = dia + timedelta(days=1)
    uid = session["uid"]
    admin = "ver_todas_cajas" in permisos_actuales()
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
    categorias_caja = []
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
                   p.metodo_pago AS metodo, m.categoria, p.valor, u.nombre AS cajero,
                   p.anulado, p.motivo_anulacion, p.confirmado,
                   (SELECT c.estado FROM cajas c WHERE c.id = p.caja_id) AS caja_estado, 0 AS es_traslado
            FROM pagos p
            LEFT JOIN matriculas m ON m.id = p.id_matricula
            LEFT JOIN alumnos a ON a.numero_documento = m.numero_documento
            LEFT JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.fecha_pago >= %s AND p.fecha_pago < %s
              AND p.concepto <> 'Abono histórico previo'{filtro_pago}
            UNION ALL
            SELECT 'ingreso', i.numero_recibo, i.fecha_ingreso, i.concepto,
                   'Efectivo', i.categoria, i.valor, u.nombre, i.anulado, i.motivo_anulacion, 1,
                   (SELECT c.estado FROM cajas c WHERE c.id = i.caja_id), i.es_traslado
            FROM ingresos_caja i
            LEFT JOIN usuarios u ON u.id = i.usuario_id
            WHERE i.fecha_ingreso >= %s AND i.fecha_ingreso < %s{filtro_ingreso}
            UNION ALL
            SELECT 'salida', s.numero_recibo, s.fecha_salida, s.concepto,
                   'Efectivo', s.categoria, s.valor, u.nombre, s.anulado, s.motivo_anulacion, 1,
                   (SELECT c.estado FROM cajas c WHERE c.id = s.caja_id), s.es_traslado
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
                "categoria": movimiento["categoria"],
                "valor": -valor if tipo == "salida" else valor,
                "cajero": movimiento["cajero"] or "—", "anulado": anulado,
                "confirmado": bool(movimiento["confirmado"]),
                "motivo_anulacion": movimiento["motivo_anulacion"],
                "caja_cerrada": (movimiento["caja_estado"] == "CERRADA" if tipo == "pago"
                                 else movimiento["caja_estado"] != "ABIERTA"),
                "es_traslado": bool(movimiento["es_traslado"]),
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
                   c.modificada_despues, c.efectivo_esperado_original, c.fecha_ultima_modificacion,
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

    movimientos_hoy = list(movs)
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
                           p.metodo_pago AS metodo, m.categoria, p.valor, u.nombre AS cajero,
                           p.anulado, p.motivo_anulacion, p.confirmado,
                           (SELECT c.estado FROM cajas c WHERE c.id = p.caja_id) AS caja_estado, 0 AS es_traslado
                    FROM pagos p
                    LEFT JOIN matriculas m ON m.id = p.id_matricula
                    LEFT JOIN alumnos a ON a.numero_documento = m.numero_documento
                    LEFT JOIN usuarios u ON u.id = p.usuario_id
                    WHERE p.concepto <> 'Abono histórico previo'{filtro_pago_todos}
                    UNION ALL
                    SELECT 'ingreso', i.numero_recibo, i.fecha_ingreso, i.concepto,
                           'Efectivo', i.categoria, i.valor, u.nombre, i.anulado, i.motivo_anulacion, 1,
                           (SELECT c.estado FROM cajas c WHERE c.id = i.caja_id), i.es_traslado
                    FROM ingresos_caja i
                    LEFT JOIN usuarios u ON u.id = i.usuario_id
                    WHERE 1 = 1{filtro_ingreso_todos}
                    UNION ALL
                    SELECT 'salida', s.numero_recibo, s.fecha_salida, s.concepto,
                           'Efectivo', s.categoria, s.valor, u.nombre, s.anulado, s.motivo_anulacion, 1,
                           (SELECT c.estado FROM cajas c WHERE c.id = s.caja_id), s.es_traslado
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
                "categoria": fila["categoria"],
                "valor": -float(fila["valor"]) if fila["tipo"] == "salida" else float(fila["valor"]),
                "cajero": fila["cajero"] or "—", "anulado": bool(fila["anulado"]),
                "confirmado": bool(fila["confirmado"]),
                "motivo_anulacion": fila["motivo_anulacion"],
                "caja_cerrada": (fila["caja_estado"] == "CERRADA" if fila["tipo"] == "pago"
                                 else fila["caja_estado"] != "ABIERTA"),
                "es_traslado": bool(fila["es_traslado"]),
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

    reporte_categorias = []
    try:
        filtro_fecha_pago = filtro_fecha_ingreso = filtro_fecha_salida = ""
        parametros_categoria = []
        if historial_modo != "todos":
            filtro_fecha_pago = " AND p.fecha_pago >= %s AND p.fecha_pago < %s"
            filtro_fecha_ingreso = " AND i.fecha_ingreso >= %s AND i.fecha_ingreso < %s"
            filtro_fecha_salida = " AND s.fecha_salida >= %s AND s.fecha_salida < %s"
        filtro_usuario_pago = " AND p.usuario_id = %s" if filtro_usuario is not None else ""
        filtro_usuario_ingreso = " AND i.usuario_id = %s" if filtro_usuario is not None else ""
        filtro_usuario_salida = " AND s.usuario_id = %s" if filtro_usuario is not None else ""
        if historial_modo != "todos":
            parametros_categoria.extend((dia, sig))
        if filtro_usuario is not None:
            parametros_categoria.append(filtro_usuario)
        if historial_modo != "todos":
            parametros_categoria.extend((dia, sig))
        if filtro_usuario is not None:
            parametros_categoria.append(filtro_usuario)
        if historial_modo != "todos":
            parametros_categoria.extend((dia, sig))
        if filtro_usuario is not None:
            parametros_categoria.append(filtro_usuario)
        reporte_categorias = db.fetchall(f"""
            SELECT categoria, SUM(ingresos) AS ingresos, SUM(salidas) AS salidas
            FROM (
                SELECT COALESCE(m.categoria, 'SIN CATEGORÍA') AS categoria,
                       p.valor AS ingresos, 0 AS salidas
                FROM pagos p
                LEFT JOIN matriculas m ON m.id = p.id_matricula
                WHERE p.anulado = 0 AND p.concepto <> 'Abono histórico previo'
                    {filtro_fecha_pago}{filtro_usuario_pago}
                UNION ALL
                SELECT COALESCE(i.categoria, 'SIN CATEGORÍA'), i.valor, 0
                FROM ingresos_caja i
                WHERE i.anulado = 0{filtro_fecha_ingreso}{filtro_usuario_ingreso}
                UNION ALL
                SELECT COALESCE(s.categoria, 'SIN CATEGORÍA'), 0, s.valor
                FROM salidas_caja s
                WHERE s.anulado = 0{filtro_fecha_salida}{filtro_usuario_salida}
            )
            GROUP BY categoria ORDER BY categoria
        """, tuple(parametros_categoria))
    except Exception:
        current_app.logger.exception("No se pudo consultar el reporte por categoría de caja")
        error = error or "No se pudo cargar el reporte por categoría."

    totales["en_caja"] = totales["esperado"]
    try:
        categorias_caja = cacheado("categorias_caja_activas", 60, lambda: db.fetchall(
            "SELECT categoria FROM categorias_caja WHERE activo = 1 ORDER BY categoria"
        ))
    except Exception:
        current_app.logger.exception("No se pudieron consultar las categorías de caja")
        error = error or "No se pudieron cargar las categorías de movimientos."

    admin_cajeros = []
    if admin:
        try:
            admin_cajeros = cacheado("cajeros_activos", 60, lambda: db.fetchall(
                "SELECT id, nombre FROM usuarios WHERE activo = 1 ORDER BY nombre"
            ))
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

    # Bandeja de pendientes: todos los pagos (abonos o pagos totales) sin confirmar, de cualquier fecha.
    pagos_pendientes = []
    if "confirmar_pagos" in permisos_actuales():
        try:
            pagos_pendientes = db.fetchall("""
                SELECT p.numero_recibo, p.fecha_pago, p.concepto, p.metodo_pago, p.valor,
                       p.id_matricula, m.categoria,
                       TRIM(a.nombres || ' ' || a.apellidos) AS alumno,
                       a.numero_documento AS documento,
                       u.nombre AS cajero
                FROM pagos p
                LEFT JOIN matriculas m ON m.id = p.id_matricula
                LEFT JOIN alumnos a ON a.numero_documento = m.numero_documento
                LEFT JOIN usuarios u ON u.id = p.usuario_id
                WHERE p.anulado = 0 AND p.confirmado = 0
                  AND p.concepto <> 'Abono histórico previo'
                ORDER BY p.fecha_pago, p.numero_recibo
            """)
        except Exception:
            current_app.logger.exception("No se pudo consultar los pagos por confirmar")
    pagos_por_confirmar = len(pagos_pendientes)

    destinos_banco = []
    if "gestionar_bancos" in permisos_actuales():
        try:
            destinos_banco = catalogo_destinos()
        except Exception:
            current_app.logger.exception("No se pudieron consultar los bancos")

    return render_template("tesoreria.html", destinos_banco=destinos_banco, pagos_por_confirmar=pagos_por_confirmar, pagos_pendientes=pagos_pendientes, dia=dia, movs=movs, cajas=cajas,
                           t=totales, error=error, admin=admin, cajeros=admin_cajeros,
                           movimientos_hoy=movimientos_hoy,
                           cajero_filtro=cajero_filtro, caja_actual=caja_actual,
                           puede_cobrar=puede_cobrar, recibo_q=recibo_q,
                           busqueda_recibos=busqueda_recibos, recibo_nuevo=recibo_nuevo,
                           historial_modo=historial_modo, pagina_historial=pagina_historial,
                           historial_anterior=historial_anterior,
                           historial_siguiente=historial_siguiente,
                           categorias_caja=categorias_caja,
                           reporte_categorias=reporte_categorias)


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
    denominaciones = (100000, 50000, 20000, 10000, 5000, 2000, 1000, 500, 200, 100, 50)
    conteo = {}
    for denominacion in denominaciones:
        cantidad_texto = request.form.get(f"denominacion_{denominacion}", "0").strip()
        if not cantidad_texto.isascii() or not cantidad_texto.isdecimal():
            flash("El conteo de billetes y monedas debe contener cantidades enteras no negativas.", "error")
            return redirect(url_for("caja.resumen"))
        cantidad = int(cantidad_texto)
        if cantidad > MAX_CAJA // denominacion:
            flash("La cantidad ingresada para una denominación es demasiado alta.", "error")
            return redirect(url_for("caja.resumen"))
        if cantidad:
            conteo[str(denominacion)] = cantidad
    if conteo and sum(int(d) * n for d, n in conteo.items()) != monto:
        flash("El total del conteo de denominaciones debe coincidir con el efectivo contado.", "error")
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
            pendientes = cur.execute(
                "SELECT COUNT(*) AS total FROM pagos WHERE caja_id = %s "
                "AND anulado = 0 AND confirmado = 0 AND concepto <> 'Abono histórico previo'",
                (caja["id"],),
            ).fetchone()["total"]
            esperado = int(caja["monto_apertura"]) + int(pagos) + int(ingresos) - int(salidas)
            diferencia = monto - esperado
            cur.execute("""
                UPDATE cajas
                SET estado = 'CERRADA', fecha_cierre = CURRENT_TIMESTAMP,
                    monto_cierre = %s, efectivo_esperado = %s, diferencia = %s,
                    observaciones_cierre = %s, conteo_denominaciones = %s
                WHERE id = %s AND usuario_id = %s AND estado = 'ABIERTA'
            """, (monto, esperado, diferencia, observaciones,
                  json.dumps(conteo) if conteo else None, caja["id"], session["uid"]))
    except Exception:
        current_app.logger.exception("Error cerrando caja")
        flash("No se pudo cerrar la caja. Intenta de nuevo.", "error")
        return redirect(url_for("caja.resumen"))

    flash(f"Caja cerrada. Efectivo esperado: {cop(esperado)}; diferencia: {cop(diferencia)}.", "ok")
    if pendientes:
        flash(f"Quedan {pendientes} pago(s) de esta caja pendientes de confirmar por el administrador. "
              "La caja se cerró normalmente.", "error")
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
    categoria = " ".join(request.form.get("categoria", "").upper().split()) or None
    valor = _entero_form("valor")
    destino_texto = request.form.get("destino", "").strip()
    if not concepto or len(concepto) > 200:
        flash("El concepto es obligatorio y admite hasta 200 caracteres.", "error")
        return redirect(url_for("caja.resumen"))
    if valor is None or valor <= 0 or valor > 100_000_000:
        flash("El valor debe estar entre $1 y $100.000.000.", "error")
        return redirect(url_for("caja.resumen"))
    if categoria and not re.fullmatch(r"[A-Z0-9][A-Z0-9 .-]{0,44}", categoria):
        flash("La categoría de caja no es válida.", "error")
        return redirect(url_for("caja.resumen"))

    tabla, etiqueta = tablas[tipo]
    en_banco = False
    try:
        with db.transaccion() as cur:
            if categoria and not cur.execute(
                "SELECT categoria FROM categorias_caja WHERE categoria = %s AND activo = 1",
                (categoria,),
            ).fetchone():
                flash("Selecciona una categoría activa o deja el campo sin categoría.", "error")
                return redirect(url_for("caja.resumen"))
            destino = parsear_destino(destino_texto)
            if destino:
                # El dinero entra o sale directamente de un banco: no toca el efectivo de la caja.
                if "gestionar_bancos" not in permisos_actuales():
                    raise BancoError("No tienes permiso para mover dinero de bancos.")
                recibo = movimiento_manual(cur, "ENTRADA" if tipo == "ingreso" else "SALIDA",
                                           destino, valor, concepto, categoria, session["uid"])
                en_banco = True
            else:
                caja = caja_abierta(cur, session["uid"])
                if not caja:
                    flash("Abre tu caja antes de registrar un movimiento.", "error")
                    return redirect(url_for("caja.resumen"))
                recibo = numero_recibo(cur, "ING" if tipo == "ingreso" else "EGR")
                cur.execute(
                    f"INSERT INTO {tabla} (numero_recibo, concepto, valor, usuario_id, caja_id, categoria) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (recibo, concepto, valor, session["uid"], caja["id"], categoria),
                )
    except BancoError as e:
        flash(str(e), "error")
        return redirect(url_for("caja.resumen"))
    except Exception:
        current_app.logger.exception("Error registrando %s en caja", tipo)
        flash("No se pudo registrar el movimiento. Intenta de nuevo.", "error")
        return redirect(url_for("caja.resumen"))

    flash(f"{etiqueta}{' en banco' if en_banco else ''} registrada. Recibo {recibo}.", "ok")
    # Los movimientos de banco no tienen comprobante térmico; los de caja sí.
    return redirect(url_for("caja.resumen") if en_banco else url_for("caja.resumen", recibo_nuevo=recibo))


_MOVIMIENTOS_MANUALES = {"ingreso": ("ingresos_caja", "fecha_ingreso", "INGRESO_CAJA", "ING"),
                         "salida": ("salidas_caja", "fecha_salida", "SALIDA_CAJA", "EGR")}


def _movimiento_para_cambiar(cur, tipo, numero):
    """Bloquea el movimiento manual y valida que se pueda tocar. Devuelve (fila, cerrada) o (None, mensaje)."""
    tabla = _MOVIMIENTOS_MANUALES[tipo][0]
    mov = cur.execute(
        f"SELECT id, numero_recibo, concepto, valor, categoria, anulado, caja_id, es_traslado "
        f"FROM {tabla} WHERE numero_recibo = %s FOR UPDATE", (numero,)).fetchone()
    if not mov:
        return None, "No se encontró el movimiento."
    if mov["anulado"]:
        return None, "Este movimiento ya está anulado."
    if mov["es_traslado"]:
        return None, "Es un traslado con un banco. Anúlalo desde Bancos para que el saldo del banco quede igual."
    cerrada = caja_cerrada(cur, mov["caja_id"])
    if cerrada and "editar_cierres" not in permisos_actuales():
        return None, ("Este movimiento es de una caja ya cerrada. Necesitas el permiso "
                      "«Anulación y edición de cierres anteriores».")
    return (mov, cerrada), None


@bp.route("/caja/movimientos/<tipo>/<numero>/anular", methods=["POST"])
@login_required
@permiso_requerido("gestionar_caja")
def anular_movimiento(tipo, numero):
    if tipo not in _MOVIMIENTOS_MANUALES or not re.fullmatch(r"[A-Za-z0-9-]{6,50}", numero):
        return "Movimiento no válido.", 404
    motivo = " ".join(request.form.get("motivo", "").split())
    if not motivo or len(motivo) > 500:
        flash("El motivo de anulación es obligatorio y admite hasta 500 caracteres.", "error")
        return redirect(url_for("caja.resumen"))
    tabla, _, entidad, _ = _MOVIMIENTOS_MANUALES[tipo]
    recalculado = False
    try:
        with db.transaccion() as cur:
            resultado, error = _movimiento_para_cambiar(cur, tipo, numero)
            if error:
                flash(error, "error")
                return redirect(url_for("caja.resumen"))
            mov, cerrada = resultado
            cur.execute(
                f"UPDATE {tabla} SET anulado = 1, motivo_anulacion = %s, anulado_por = %s, "
                f"fecha_anulacion = CURRENT_TIMESTAMP WHERE id = %s AND anulado = 0",
                (motivo, session["uid"], mov["id"]))
            registrar_auditoria(cur, entidad, mov["id"], "ANULACION", session["uid"],
                                dict(mov), {**mov, "anulado": 1, "motivo_anulacion": motivo}, motivo)
            if cerrada:
                recalculado = bool(recalcular_cierre(cur, mov["caja_id"], session["uid"],
                                                     f"Anulación de {numero}: {motivo}"[:500]))
    except Exception:
        current_app.logger.exception("Error anulando movimiento %s", numero)
        flash("No se pudo anular el movimiento. Intenta de nuevo.", "error")
        return redirect(url_for("caja.resumen"))
    flash(f"Movimiento {numero} anulado." + (" El cierre de esa caja se recalculó." if recalculado else ""), "ok")
    return redirect(url_for("caja.resumen", historial="todos"))


@bp.route("/caja/movimientos/<tipo>/<numero>/editar", methods=["POST"])
@login_required
@permiso_requerido("gestionar_caja")
def editar_movimiento(tipo, numero):
    if tipo not in _MOVIMIENTOS_MANUALES or not re.fullmatch(r"[A-Za-z0-9-]{6,50}", numero):
        return "Movimiento no válido.", 404
    motivo = " ".join(request.form.get("motivo", "").split())
    concepto = " ".join(request.form.get("concepto", "").split())
    categoria = " ".join(request.form.get("categoria", "").upper().split()) or None
    valor = _entero_form("valor")
    destino = url_for("caja.resumen", historial="todos")
    if not motivo or len(motivo) > 500:
        flash("El motivo de la corrección es obligatorio y admite hasta 500 caracteres.", "error")
        return redirect(destino)
    if not concepto or len(concepto) > 200:
        flash("El concepto es obligatorio y admite hasta 200 caracteres.", "error")
        return redirect(destino)
    if valor is None or valor <= 0 or valor > 100_000_000:
        flash("El valor debe estar entre $1 y $100.000.000.", "error")
        return redirect(destino)
    if categoria and not re.fullmatch(r"[A-Z0-9][A-Z0-9 .-]{0,44}", categoria):
        flash("La categoría de caja no es válida.", "error")
        return redirect(destino)
    tabla, _, entidad, _ = _MOVIMIENTOS_MANUALES[tipo]
    recalculado = False
    try:
        with db.transaccion() as cur:
            if categoria and not cur.execute(
                    "SELECT categoria FROM categorias_caja WHERE categoria = %s AND activo = 1",
                    (categoria,)).fetchone():
                flash("Selecciona una categoría activa o deja el campo sin categoría.", "error")
                return redirect(destino)
            resultado, error = _movimiento_para_cambiar(cur, tipo, numero)
            if error:
                flash(error, "error")
                return redirect(destino)
            mov, cerrada = resultado
            if (mov["concepto"], int(mov["valor"]), mov["categoria"]) == (concepto, valor, categoria):
                flash("No cambiaste nada en el movimiento.", "error")
                return redirect(destino)
            cur.execute(f"UPDATE {tabla} SET concepto = %s, valor = %s, categoria = %s WHERE id = %s",
                        (concepto, valor, categoria, mov["id"]))
            registrar_auditoria(cur, entidad, mov["id"], "EDICION", session["uid"],
                                {"concepto": mov["concepto"], "valor": mov["valor"], "categoria": mov["categoria"]},
                                {"concepto": concepto, "valor": valor, "categoria": categoria}, motivo)
            if cerrada:
                recalculado = bool(recalcular_cierre(cur, mov["caja_id"], session["uid"],
                                                     f"Corrección de {numero}: {motivo}"[:500]))
    except Exception:
        current_app.logger.exception("Error editando movimiento %s", numero)
        flash("No se pudo editar el movimiento. Intenta de nuevo.", "error")
        return redirect(destino)
    flash(f"Movimiento {numero} corregido." + (" El cierre de esa caja se recalculó." if recalculado else ""), "ok")
    return redirect(destino)
