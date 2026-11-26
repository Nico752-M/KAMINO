"""PDFs de la tienda con reportlab."""
from io import BytesIO
from xml.sax.saxutils import escape

from utils import ahora, cop


def _tabla(titulo, subtitulo, encabezados, filas, resumen=(), horizontal=False):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    est = getSampleStyleSheet()
    celda = ParagraphStyle("c", parent=est["BodyText"], fontSize=8, leading=9)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4) if horizontal else A4, title=titulo, leftMargin=12 * mm,
                            rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    story = [Paragraph(escape(titulo), est["Title"]),
             Paragraph(escape(subtitulo), est["BodyText"]), Spacer(1, 6)]
    if resumen:
        r = Table([[k, v] for k, v in resumen], hAlign="LEFT")
        r.setStyle(TableStyle([("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                               ("FONTSIZE", (0, 0), (-1, -1), 9)]))
        story += [r, Spacer(1, 8)]
    datos = [encabezados] + [[Paragraph(escape(str(c)), celda) for c in f] for f in filas]
    if not filas:
        datos.append(["Sin datos"] + [""] * (len(encabezados) - 1))
    t = Table(datos, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#253449")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#ccd2da")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f5f7")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    doc.build(story)
    return buf.getvalue()


def _fecha():
    return "Generado: " + ahora().strftime("%d/%m/%Y %H:%M")


def inventario(productos):
    valor = sum(p["stock"] * p["costo"] for p in productos)
    filas = [(p["nombre"], p["cat"], cop(p["costo"]), cop(p["precio"]), p["stock"],
              "Agotado" if p["stock"] <= 0 else "Bajo" if p["stock"] <= p["minimo"] else "Ok")
             for p in productos]
    return _tabla("Inventario", _fecha(),
                  ["Producto", "Categoría", "Costo", "Precio", "Stock", "Estado"], filas,
                  [("Productos", len(productos)), ("Valor a costo", cop(valor))])


def ventas(lista):
    validas = [v for v in lista if not v["anulada"]]
    filas = [(v["id"], (v["fecha"] or "")[:16].replace("T", " "),
              ", ".join(f"{i['cant']} x {i['nombre']}" + (f" ({i['detalle']})" if i.get("detalle") else "")
                        for i in v["items"]),
              v["metodo"] + (" + " + v["metodo2"] if v["metodo2"] else ""),
              cop(v["total"]), v["cajero"], "Anulada" if v["anulada"] else "Válida")
             for v in lista]
    return _tabla("Ventas", _fecha(),
                  ["#", "Fecha", "Detalle", "Pago", "Total", "Atendió", "Estado"], filas,
                  [("Ventas válidas", len(validas)),
                   ("Total vendido", cop(sum(v["total"] for v in validas)))])


def ganancias(d, a, periodo):
    dias = d["porDia"]
    bruto = sum(x["ventas"] for x in dias)
    costo = sum(x["costo"] for x in dias)
    no_ef = sum(x["noEfectivo"] for x in dias)
    comision = no_ef * a["comision"] / 100 if a["usarComision"] else 0
    impuesto = bruto * a["impuesto"] / 100 if a["usarImpuesto"] else 0
    gastos = a["gastosMes"] / 30 * d["dias"] if a["usarGastos"] else 0
    gcaja = sum(x["gastos"] for x in dias)
    mermas = sum(x["mermas"] for x in dias)
    neta = bruto - costo - comision - impuesto - gastos - gcaja - mermas
    filas = [(x["fecha"], x["n"], cop(x["ventas"]), cop(x["costo"]), cop(x["ventas"] - x["costo"]))
             for x in dias]
    resumen = [("Ventas", cop(bruto)), ("Costo mercancía", cop(costo)),
               ("Ganancia bruta", cop(bruto - costo)), ("Comisión", cop(comision)),
               ("Impuesto", cop(impuesto)), ("Gastos fijos", cop(gastos)),
               ("Gastos de caja", cop(gcaja)), ("Mermas", cop(mermas)),
               ("Ganancia neta", cop(neta))]
    resumen += [("Más vendidos (ganancia)",
                 ", ".join(f"{t['nombre']} {cop(t['ganancia'])}" for t in d["top"][:3]) or "—")]
    return _tabla("Ganancias", f"Últimos {d['dias']} día(s) · {_fecha()}",
                  ["Fecha", "Ventas (n)", "Vendido", "Costo", "Ganancia bruta"], filas, resumen)


# Datos del encabezado de la factura de venta (edítalos aquí cuando cambien)
FACTURA = {
    "nombre": "TODO EN TRÁNSITO",
    "lema": "FOTOASESORÍAS Y SERVICIOS DE TRÁNSITO Y TRANSPORTE",
    "servicios": "LICENCIAS · MATRÍCULAS · TRASPASOS · LIQUIDACIÓN DE IMPUESTOS",
    "titular": "James González",
    "cargo": "TÉCNICO EN TRÁNSITO Y TRANSPORTE",
    "nit": "NIT. 16.354.101-3 No Responsable de IVA",
    "direccion": "Carrera 30 No. 15 - 14  Tels.: 602 232 5067",
    "celulares": "Cel.: 317 286 0766  ·  WhatsApp 314 623 0452  ·  Tuluá - Valle",
}


def ticket_venta(v, items):
    """Factura de venta con el estilo del talonario azul: se imprime en media hoja (A5)."""
    from textwrap import wrap

    from reportlab.lib.pagesizes import A5
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    mm = 72 / 25.4
    azul = (0.13, 0.20, 0.62)
    rojo = (0.78, 0.12, 0.14)
    ancho = A5[0]
    mi = 9 * mm                      # margen izquierdo y derecho
    util = ancho - 2 * mi

    # Cada ítem ocupa una fila: nombre (hasta 2 líneas) + detalle en letra pequeña
    filas = []
    for i in items:
        lineas = wrap(str(i["nombre"]), 34)[:2] or [""]
        extra = wrap(str(i["detalle"]), 44)[:3] if i.get("detalle") else []
        filas.append((i, lineas, extra))
    def alto_fila(f):
        base = 5.5 * mm + (len(f[1]) - 1) * 9 + 5
        if f[2]:
            base = 5.5 * mm + len(f[1]) * 9 + (len(f[2]) - 1) * 7.5 + 4
        return max(7.5 * mm, base)
    altos = [alto_fila(f) for f in filas]
    min_alto_tabla = 8 * 7.5 * mm
    alto_tabla = max(min_alto_tabla, sum(altos))
    descuento = int(v["descuento"] or 0)
    extra_pie = (2 if descuento else 0) * 5 * mm
    alto = A5[1] + (alto_tabla - min_alto_tabla) + extra_pie   # crece si hay muchos ítems

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(ancho, alto))
    c.setTitle(f"Factura de venta {v['id']}")
    c.setLineWidth(0.8)

    def txt(x, y, t, f="Helvetica", s=8, col=azul, al="L"):
        c.setFont(f, s)
        c.setFillColorRGB(*col)
        {"L": c.drawString, "R": c.drawRightString, "C": c.drawCentredString}[al](x, y, str(t))

    c.setStrokeColorRGB(*azul)
    c.roundRect(mi - 3 * mm, 6 * mm, util + 6 * mm, alto - 12 * mm, 3 * mm, stroke=1, fill=0)

    y = alto - 14 * mm
    # Logo ovalado
    c.setFillColorRGB(*azul)
    c.ellipse(mi, y - 17 * mm, mi + 36 * mm, y + 3 * mm, stroke=0, fill=1)
    txt(mi + 18 * mm, y - 3 * mm, "TODO EN", "Helvetica-Bold", 10, (1, 1, 1), "C")
    txt(mi + 18 * mm, y - 9.5 * mm, "TRÁNSITO", "Helvetica-Bold", 10, (1, 1, 1), "C")
    txt(mi + 18 * mm, y - 14 * mm, "Fotoasesorías y servicios", "Helvetica", 4.6, (1, 1, 1), "C")

    xd = mi + 40 * mm
    xr = ancho - mi
    xc = (xd + xr) / 2
    txt(xc, y + 1 * mm, FACTURA["servicios"], "Helvetica-Bold", 4.8, al="C")
    txt(xc, y - 4.5 * mm, FACTURA["titular"], "Helvetica-BoldOblique", 12, al="C")
    txt(xc, y - 8.5 * mm, FACTURA["cargo"], "Helvetica", 5.5, al="C")
    txt(xc, y - 12 * mm, FACTURA["nit"], "Helvetica", 5.5, al="C")
    txt(xc, y - 16 * mm, FACTURA["direccion"], "Helvetica-Bold", 6.3, al="C")
    txt(xc, y - 19.5 * mm, FACTURA["celulares"], "Helvetica-Bold", 5.6, al="C")

    # Fecha y número
    y -= 30 * mm
    f = v["fecha"]
    bx = mi
    for rotulo, valor, w in (("DÍA", f"{f.day:02d}", 13 * mm), ("MES", f"{f.month:02d}", 13 * mm),
                             ("AÑO", f"{f.year}", 18 * mm)):
        c.setFillColorRGB(0.85, 0.88, 0.97)
        c.rect(bx, y + 4 * mm, w, 4.5 * mm, stroke=1, fill=1)
        txt(bx + w / 2, y + 5.4 * mm, rotulo, "Helvetica-Bold", 6, al="C")
        c.rect(bx, y - 4 * mm, w, 8 * mm, stroke=1, fill=0)
        txt(bx + w / 2, y - 1.2 * mm, valor, "Helvetica", 9, al="C")
        bx += w
    txt(ancho - mi - 36 * mm, y + 1 * mm, "FACTURA", "Helvetica-Bold", 9, al="R")
    txt(ancho - mi - 36 * mm, y - 4 * mm, "DE VENTA", "Helvetica-Bold", 9, al="R")
    c.roundRect(ancho - mi - 33 * mm, y - 6 * mm, 33 * mm, 12 * mm, 1.5 * mm, stroke=1, fill=0)
    txt(ancho - mi - 16.5 * mm, y - 2.5 * mm, v["id"], "Helvetica-Bold", 15, rojo, "C")

    # Datos del cliente (en blanco, para llenar a mano)
    y -= 12 * mm
    top = y
    c.roundRect(mi, y - 27 * mm, util, 27 * mm, 1.5 * mm, stroke=1, fill=0)
    for k in (1, 2, 3):
        c.line(mi, y - 9 * mm * k, mi + util, y - 9 * mm * k) if k < 3 else None
    c.line(mi + util * 0.62, y - 9 * mm, mi + util * 0.62, y - 27 * mm)
    txt(mi + 2 * mm, y - 6 * mm, "Señor (es)", "Helvetica", 7)
    txt(mi + 2 * mm, y - 15 * mm, "C.C. o NIT.", "Helvetica", 7)
    txt(mi + util * 0.62 + 2 * mm, y - 15 * mm, "Tel.", "Helvetica", 7)
    txt(mi + 2 * mm, y - 24 * mm, "Dirección", "Helvetica", 7)
    txt(mi + util * 0.62 + 2 * mm, y - 24 * mm, "Ciudad", "Helvetica", 7)

    # Tabla de detalle
    y -= 31 * mm
    cx = (mi, mi + 14 * mm, mi + util * 0.64, mi + util * 0.82, mi + util)
    c.setFillColorRGB(*azul)
    c.rect(mi, y - 6.5 * mm, util, 6.5 * mm, stroke=0, fill=1)
    for xx, t, al in ((cx[0] + 7 * mm, "Cant.", "C"), ((cx[1] + cx[2]) / 2, "D E T A L L E", "C"),
                      ((cx[2] + cx[3]) / 2, "Vr. Unit.", "C"), ((cx[3] + cx[4]) / 2, "TOTAL", "C")):
        txt(xx, y - 4.6 * mm, t, "Helvetica-Bold", 7, (1, 1, 1), al)
    y -= 6.5 * mm
    y_tabla = y
    c.setStrokeColorRGB(*azul)
    c.setLineWidth(0.6)
    yy = y
    for (i, lineas, extra), h in zip(filas, altos):
        cant = int(i["cantidad"])
        precio = int(i["precio"])
        base = yy - 5.5 * mm
        txt(cx[0] + 7 * mm, base, cant, "Helvetica", 8.5, (0.1, 0.1, 0.1), "C")
        for n, linea in enumerate(lineas):
            txt(cx[1] + 2 * mm, base - n * 9, linea, "Helvetica", 8, (0.1, 0.1, 0.1))
        for n, linea in enumerate(extra):
            txt(cx[1] + 2 * mm, base - len(lineas) * 9 - n * 7.5 + 1, linea, "Helvetica-Oblique", 6.3, (0.35, 0.35, 0.4))
        txt(cx[3] - 2 * mm, base, cop(precio), "Helvetica", 8, (0.1, 0.1, 0.1), "R")
        txt(cx[4] - 2 * mm, base, cop(cant * precio), "Helvetica", 8, (0.1, 0.1, 0.1), "R")
        yy -= h
        c.line(mi, yy, mi + util, yy)
    # Filas vacías hasta completar el alto mínimo de la tabla
    y_fin = y_tabla - alto_tabla
    while yy - 7.5 * mm >= y_fin - 0.5:
        yy -= 7.5 * mm
        c.line(mi, yy, mi + util, yy)
    c.setLineWidth(0.8)
    for xx in cx[1:4]:
        c.line(xx, y_tabla, xx, y_fin)
    c.line(mi, y_tabla, mi, y_fin)
    c.line(mi + util, y_tabla, mi + util, y_fin)
    c.line(mi, y_fin, mi + util, y_fin)

    # Total
    y = y_fin - 3 * mm
    if descuento:
        txt(cx[3] - 2 * mm, y - 3 * mm, "Subtotal", "Helvetica", 7.5, al="R")
        txt(cx[4] - 2 * mm, y - 3 * mm, cop(int(v["total"]) + descuento), "Helvetica", 8, (0.1, 0.1, 0.1), "R")
        txt(cx[3] - 2 * mm, y - 8 * mm, "Descuento", "Helvetica", 7.5, al="R")
        txt(cx[4] - 2 * mm, y - 8 * mm, "- " + cop(descuento), "Helvetica", 8, (0.1, 0.1, 0.1), "R")
        y -= 10 * mm
    txt(cx[3] - 2 * mm, y - 6 * mm, "TOTAL $", "Helvetica-Bold", 11, al="R")
    c.rect(cx[3], y - 9 * mm, cx[4] - cx[3], 9 * mm, stroke=1, fill=0)
    txt(cx[4] - 2 * mm, y - 6 * mm, cop(v["total"]), "Helvetica-Bold", 10, (0.1, 0.1, 0.1), "R")

    # Forma de pago
    if v["metodo"] == "Efectivo" and not v["metodo2"]:
        pago = f"Pago: Efectivo · Recibido {cop(v['recibido'])} · Devuelta {cop(v['cambio'])}"
    elif v["metodo2"]:
        pago = f"Pago: Efectivo {cop(v['recibido'])} + {v['metodo2']} {cop(v['monto_metodo2'])}"
    else:
        pago = f"Pago: {v['metodo']}"
    txt(mi, y - 4.5 * mm, pago, "Helvetica-Bold", 7, (0.1, 0.1, 0.1))
    txt(mi, y - 9 * mm, f"Atendió: {v['usuario_nombre']}", "Helvetica", 6.5, (0.35, 0.35, 0.4))

    # Pie
    y -= 16 * mm
    leyenda = ("APRECIADO CLIENTE: en algunas ocasiones los tiempos de entrega de su trámite pueden "
               "variar por causas ajenas a nuestra voluntad debido a que nuestro cumplimiento está "
               "sujeto a la agilidad con que trabajen los organismos de tránsito.")
    for n, linea in enumerate(wrap(leyenda, 62)):
        txt(mi, y - n * 7, linea, "Helvetica", 5.2)
    txt(mi, y - 30, "Recibí a Satisfacción", "Helvetica", 7)
    c.line(mi, y - 52, mi + 70 * mm, y - 52)
    txt(mi, y - 60, "C.C.", "Helvetica", 7)
    for n, linea in enumerate(wrap("Esta es una Factura de Venta se asimila en todos sus efectos a una letra "
                                   "de cambio. Art. 733 del Código de Comercio.", 36)):
        txt(ancho - mi, y - 38 - n * 7, linea, "Helvetica", 5.2, al="R")

    if int(v["anulada"]) == 1:
        c.saveState()
        c.translate(ancho / 2, alto / 2)
        c.rotate(30)
        txt(0, 0, "ANULADA", "Helvetica-Bold", 48, (0.85, 0.25, 0.25), "C")
        c.restoreState()
    c.save()
    return buf.getvalue()


def reposicion(productos):
    bajos = [p for p in productos if p["stock"] <= p["minimo"]]
    sugerido = lambda p: max(p["minimo"] * 2 - p["stock"], 1)
    filas = [(p["nombre"], p["cat"], p["stock"], p["minimo"], sugerido(p), cop(sugerido(p) * p["costo"]))
             for p in bajos]
    total = sum(sugerido(p) * p["costo"] for p in bajos)
    return _tabla("Pedido de reposición", _fecha() + " · Sugerido = para quedar con el doble del mínimo",
                  ["Producto", "Categoría", "Stock", "Mínimo", "Sugerido", "Costo est."], filas,
                  [("Productos por reponer", len(bajos)), ("Inversión estimada", cop(total))])


def reporte(r):
    filas = [(f["fecha"], f["n"], cop(f["Efectivo"]), cop(f["Nequi"]), cop(f["Tarjeta"]), cop(f["ventas"]),
              cop(f["desc"]), cop(f["ventas"] - f["costo"]), cop(f["ing"]), cop(f["egr"]), cop(f["mer"]),
              "—" if f["contado"] is None else cop(f["contado"]),
              "—" if f["dif"] is None else cop(f["dif"])) for f in r["dias"]]
    t = r["tot"]
    return _tabla("Reporte de caja", f"{r['desde']} a {r['hasta']} · {_fecha()}",
                  ["Fecha", "# Ventas", "Efectivo", "Nequi", "Tarjeta", "Total", "Descuentos", "Gan. bruta",
                   "Entradas", "Salidas", "Mermas", "Contado", "Dif."], filas,
                  [("Total vendido", cop(t["ventas"])), ("Ganancia bruta", cop(t["ventas"] - t["costo"])),
                   ("Salidas de caja", cop(t["egr"])), ("Mermas", cop(t["mer"]))], horizontal=True)
