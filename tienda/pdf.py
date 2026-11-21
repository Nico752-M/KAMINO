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
              ", ".join(f"{i['cant']} x {i['nombre']}" for i in v["items"]),
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


def ticket_venta(v, items):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    mm = 72 / 25.4
    ancho, alto = 80 * mm, (70 + 5 * len(items)) * mm   # medidas del ticket
    pagina_ancho, pagina_alto = A4
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Venta {v['id']}")
    # El ticket se dibuja pegado a la esquina superior izquierda de la hoja
    c.translate(8 * mm, pagina_alto - alto - 8 * mm)
    # Marco punteado para saber por dónde recortar
    c.setDash(2, 2)
    c.setLineWidth(0.4)
    c.rect(0, 0, ancho, alto)
    c.setDash()
    y = alto - 8 * mm

    def fila(izq, der="", f="Helvetica", s=8, centro=False):
        nonlocal y
        c.setFont(f, s)
        if centro:
            c.drawCentredString(ancho / 2, y, izq)
        else:
            c.drawString(4 * mm, y, izq[:32])
            if der:
                c.drawRightString(ancho - 4 * mm, y, der)
        y -= s * 1.6

    fila("TODO EN TRANSITO", f="Helvetica-Bold", s=13, centro=True)
    fila(f"Venta #{v['id']}", s=9, centro=True)
    fila(v["fecha"].strftime("%d/%m/%Y %H:%M"), s=7, centro=True)
    fila(f"Atendió: {v['usuario_nombre']}", s=7)
    fila("-" * 48, s=7)
    for i in items:
        fila(f"{i['cantidad']} x {i['nombre']}", cop(int(i["cantidad"]) * int(i["precio"])))
    fila("-" * 48, s=7)
    if v["descuento"]:
        fila("Subtotal", cop(int(v["total"]) + int(v["descuento"])))
        fila("Descuento", "- " + cop(v["descuento"]))
    fila("TOTAL", cop(v["total"]), "Helvetica-Bold", 10)
    if v["metodo"] == "Efectivo":
        if v["metodo2"]:
            fila("Efectivo", cop(v["recibido"]))
            fila(v["metodo2"], cop(v["monto_metodo2"]))
        else:
            fila("Pago: Efectivo")
            fila("Recibido", cop(v["recibido"]))
            fila("Devuelta", cop(v["cambio"]))
    else:
        fila(f"Pago: {v['metodo']}")
    if int(v["anulada"]) == 1:
        fila("VENTA ANULADA", f="Helvetica-Bold", s=11, centro=True)
    fila("¡Gracias por su compra!", s=7, centro=True)
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