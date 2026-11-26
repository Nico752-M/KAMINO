"""Ticket térmico de 80 mm en PDF (sin PyQt). Devuelve bytes, no escribe en disco."""
from datetime import datetime
from io import BytesIO

from config import Config
from utils import cop

MM = 72 / 25.4
ANCHO = 80 * MM
MARGEN = 5 * MM
NEGRO, GRIS, ROJO = (0.07, 0.09, 0.15), (0.42, 0.44, 0.50), (0.78, 0.15, 0.16)

F_TITULO = ("Helvetica-Bold", 13)
F_SUBTIT = ("Helvetica-Bold", 9)
F_NORMAL = ("Helvetica", 8)
F_PEQUE = ("Helvetica", 7)
F_ETIQ = ("Helvetica-Bold", 7)
F_VALOR = ("Helvetica-Bold", 14)


def _cop(v) -> str:
    return cop(v)


def numero_recibo(cur) -> str:
    """Reserva el consecutivo compartido por todos los recibos de caja."""
    fila = cur.execute(
        "SELECT 'CEA-' || LPAD(SEQ_RECIBOS.NEXTVAL, 6, '0') AS numero FROM dual"
    ).fetchone()
    return fila["numero"]


def _ajustar(texto: str, fuente: str, tam: float, ancho: float) -> str:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    texto = str(texto)
    if stringWidth(texto, fuente, tam) <= ancho:
        return texto
    while texto and stringWidth(texto + "…", fuente, tam) > ancho:
        texto = texto[:-1]
    return texto + "…"


class _Ticket:
    def __init__(self):
        self.cmds = []

    def texto(self, t, fuente=F_NORMAL, alinear="L", color=NEGRO):
        self.cmds.append(("texto", str(t), fuente, alinear, color))

    def linea(self, grosor=0.4, punteada=False):
        self.cmds.append(("linea", grosor, punteada))

    def espacio(self, m=2.0):
        self.cmds.append(("espacio", m))

    def par(self, clave, valor, negrita=False):
        self.cmds.append(("par", clave, str(valor), negrita))

    def _altura(self):
        h = 0.0
        for c in self.cmds:
            if c[0] == "texto":
                h += c[2][1] * 1.4
            elif c[0] == "linea":
                h += 4
            elif c[0] == "espacio":
                h += c[1] * MM
            else:
                h += F_NORMAL[1] * 1.4
        return h

    def pdf(self) -> bytes:
        from reportlab.pdfgen import canvas

        alto = self._altura() + 10 * MM
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=(ANCHO, alto))
        c.setTitle("Recibo CEA La 30")
        util = ANCHO - 2 * MARGEN
        y = alto
        for cmd in self.cmds:
            tipo = cmd[0]
            if tipo == "espacio":
                y -= cmd[1] * MM
            elif tipo == "linea":
                y -= 2
                c.setStrokeColorRGB(*GRIS)
                c.setLineWidth(cmd[1])
                c.setDash(2, 3) if cmd[2] else c.setDash()
                c.line(MARGEN, y, ANCHO - MARGEN, y)
                c.setDash()
                y -= 2
            elif tipo == "texto":
                _, t, (fn, fs), al, col = cmd
                y -= fs * 1.4
                c.setFont(fn, fs)
                c.setFillColorRGB(*col)
                t = _ajustar(t, fn, fs, util)
                if al == "C":
                    c.drawCentredString(ANCHO / 2, y, t)
                elif al == "R":
                    c.drawRightString(ANCHO - MARGEN, y, t)
                else:
                    c.drawString(MARGEN, y, t)
            else:
                _, k, v, neg = cmd
                from reportlab.pdfbase.pdfmetrics import stringWidth

                y -= F_NORMAL[1] * 1.4
                c.setFont(*F_NORMAL)
                c.setFillColorRGB(*GRIS)
                c.drawString(MARGEN, y, k)
                fn = "Helvetica-Bold" if neg else "Helvetica"
                c.setFont(fn, F_NORMAL[1])
                c.setFillColorRGB(*NEGRO)
                v = _ajustar(v, fn, F_NORMAL[1], util - stringWidth(k, *F_NORMAL) - 6)
                c.drawRightString(ANCHO - MARGEN, y, v)
        c.save()
        return buf.getvalue()


def _datos_finales(t: _Ticket, d: dict) -> None:
    t.espacio(2); t.linea(punteada=True); t.espacio(2)
    if d.get("copia"):
        t.texto("COPIA", ("Helvetica-Bold", 12), "C", ROJO)
        t.texto(f"Reimpreso: {d['fecha_reimpresion'].strftime('%d/%m/%Y %H:%M:%S')}",
                F_PEQUE, "C", GRIS)
        t.texto(f"Por: {d['usuario_reimpresion']}", F_PEQUE, "C", GRIS)
    t.texto(f"Atendido por: {d['cajero']}", F_PEQUE, "C", GRIS)
    t.texto(f"Recibo: {d['numero_recibo']}", F_PEQUE, "C", GRIS)
    fecha = d.get("fecha") or datetime.now()
    t.texto(fecha.strftime("%d/%m/%Y  %H:%M:%S"), F_PEQUE, "C", GRIS)
    if d.get("anulado"):
        t.espacio(2)
        t.texto("ANULADO", F_SUBTIT, "C", ROJO)
        if d.get("motivo_anulacion"):
            t.par("Motivo:", d["motivo_anulacion"])


def _datos_escuela(t: _Ticket) -> None:
    t.texto("CEA LA 30", F_TITULO, "C", ROJO)
    t.texto("Centro de Enseñanza Automovilística", F_PEQUE, "C", GRIS)
    ubicacion = " · ".join(valor for valor in (
        Config.CEA_CIUDAD, f"NIT: {Config.CEA_NIT}" if Config.CEA_NIT else ""
    ) if valor)
    if ubicacion:
        t.texto(ubicacion, F_PEQUE, "C", GRIS)


def generar_recibo_pago_pdf(d: dict) -> bytes:
    """d: numero_recibo, alumno_nombre, alumno_doc, concepto, valor, metodo_pago,
    cajero, acompanante, observaciones, cambio, fecha (datetime)."""
    t = _Ticket()
    t.espacio(3)
    _datos_escuela(t)
    t.espacio(2); t.linea(0.8); t.espacio(2)

    t.texto("RECIBO DE PAGO", F_SUBTIT, "C")
    t.espacio(2); t.linea(0.3); t.espacio(1.5)
    t.texto("DATOS DEL ALUMNO", F_ETIQ, "L", GRIS); t.espacio(1)
    t.par("Nombre:", d["alumno_nombre"])
    t.par(f"Documento ({d['alumno_tipo_documento']}):", d["alumno_doc"])
    if (d.get("acompanante") or "").strip():
        t.par("Acompañante:", d["acompanante"].strip())

    t.espacio(2); t.linea(0.3); t.espacio(1.5)
    t.texto("DETALLE", F_ETIQ, "L", GRIS); t.espacio(1)
    t.par("Concepto:", d["concepto"])
    t.par("Método:", d["metodo_pago"])
    if (d.get("observaciones") or "").strip():
        t.par("Notas:", d["observaciones"].strip())

    t.espacio(2); t.linea(0.8); t.espacio(2)
    t.texto("VALOR RECIBIDO", F_ETIQ, "C", GRIS)
    t.texto(_cop(d["valor"]), F_VALOR, "C", ROJO)
    t.espacio(1)
    if (d.get("cambio") or 0) > 0:
        t.par("Cambio devuelto:", _cop(d["cambio"]), negrita=True)
        t.espacio(1)

    _datos_finales(t, d)
    t.espacio(2); t.linea(0.8); t.espacio(2)
    t.texto("Conserve este recibo como comprobante", F_PEQUE, "C", GRIS)
    t.texto("de su transacción.  ¡Gracias!", F_PEQUE, "C", GRIS)
    t.espacio(5)
    return t.pdf()


def generar_recibo_movimiento_pdf(d: dict) -> bytes:
    """Genera comprobantes de ingresos y egresos de caja."""
    t = _Ticket()
    t.espacio(3)
    _datos_escuela(t)
    t.espacio(2); t.linea(0.8); t.espacio(2)
    t.texto("COMPROBANTE DE INGRESO" if d["tipo"] == "INGRESO"
            else "COMPROBANTE DE EGRESO", F_SUBTIT, "C")
    t.espacio(2); t.linea(0.3); t.espacio(1.5)
    t.par("Concepto:", d["concepto"])
    t.espacio(2); t.linea(0.8); t.espacio(2)
    t.texto("VALOR", F_ETIQ, "C", GRIS)
    t.texto(_cop(d["valor"]), F_VALOR, "C", ROJO)
    _datos_finales(t, d)
    t.espacio(5)
    return t.pdf()


def generar_recibo_caja_cea_pdf(d: dict) -> bytes:
    """Recibo de caja del CEA en hoja carta: dos copias (estudiante y CEA) en la misma hoja.

    d: numero_recibo, fecha, categoria, alumno_nombre, alumno_tipo_documento, alumno_doc,
    concepto, valor_total, valor, saldo, metodo_pago, observaciones, anulado, motivo_anulacion,
    copia (bool), fecha_reimpresion.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    ancho, alto = letter
    margen = 14 * MM
    util = ancho - 2 * margen
    mitad = alto / 2
    nit = Config.CEA_NIT or "901837104"
    fecha = d.get("fecha") or datetime.now()

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle(f"Recibo de caja {d['numero_recibo']}")

    def texto(x, y, t, fuente="Helvetica", tam=9, alinear="L", color=(0, 0, 0), max_ancho=None):
        t = str(t or "")
        if max_ancho:
            t = _ajustar(t, fuente, tam, max_ancho)
        c.setFont(fuente, tam)
        c.setFillColorRGB(*color)
        {"L": c.drawString, "R": c.drawRightString, "C": c.drawCentredString}[alinear](x, y, t)

    def campo(x, y, etiqueta, valor, ancho_campo, negrita=False, alinear="L"):
        texto(x, y, etiqueta, "Helvetica-Bold", 8.5)
        x0 = x + stringWidth(etiqueta, "Helvetica-Bold", 8.5) + 4
        c.setStrokeColorRGB(0.55, 0.55, 0.55)
        c.setLineWidth(0.5)
        c.line(x0, y - 2.5, x + ancho_campo, y - 2.5)
        fuente = "Helvetica-Bold" if negrita else "Helvetica"
        xt = x0 + 2 if alinear == "L" else x + ancho_campo - 2
        texto(xt, y, valor, fuente, 9.5, alinear, max_ancho=x + ancho_campo - x0 - 4)

    def copia(base, quien):
        """base = borde superior de la mitad de hoja."""
        top = base - 8 * MM
        # Encabezado negro
        c.setFillColorRGB(0.12, 0.12, 0.12)
        c.rect(margen, top - 9 * MM, util, 9 * MM, stroke=0, fill=1)
        texto(ancho / 2, top - 6.2 * MM,
              f"CEA LA 30 - NIT {nit}  CRA 30 #15-14  |  RECIBO DE CAJA",
              "Helvetica-Bold", 11.5, "C", (1, 1, 1))
        # Marco general
        marco_alto = mitad - 16 * MM
        c.setStrokeColorRGB(0.12, 0.12, 0.12)
        c.setLineWidth(1)
        c.rect(margen, base - 8 * MM - marco_alto, util, marco_alto, stroke=1, fill=0)

        x = margen + 4 * MM
        w = util - 8 * MM
        col = w * 0.58
        y = top - 17 * MM
        texto(margen + util - 4 * MM, top - 13.5 * MM, quien, "Helvetica-Bold", 8, "R", (0.42, 0.44, 0.5))

        # Consecutivo resaltado
        c.setFillColorRGB(0.98, 0.9, 0.82)
        c.rect(x + 28 * MM, y - 2.2 * MM, 42 * MM, 6.5 * MM, stroke=0, fill=1)
        texto(x, y, "Consecutivo:", "Helvetica-Bold", 9)
        texto(x + 49 * MM, y, d["numero_recibo"], "Helvetica-Bold", 11, "C")

        y -= 8 * MM
        campo(x, y, "Fecha:", fecha.strftime("%d/%m/%Y"), col - 6 * MM)
        campo(x + col, y, "Categoría:", d.get("categoria") or "—", w - col)
        y -= 7 * MM
        campo(x, y, "Nombre del cliente:", d["alumno_nombre"], w)
        y -= 7 * MM
        campo(x, y, "Tipo de documento:", d.get("alumno_tipo_documento") or "CC", col - 6 * MM)
        campo(x + col, y, "N.º de documento:", d["alumno_doc"], w - col, alinear="R")
        y -= 7 * MM
        campo(x, y, "Concepto:", d["concepto"], w)
        y -= 8 * MM
        campo(x, y, "Valor total:", cop(d["valor_total"]), col - 6 * MM, alinear="R")
        campo(x + col, y, "Medio de pago:", d["metodo_pago"], w - col)
        y -= 6 * MM
        campo(x, y, "Valor recibido:", cop(d["valor"]), col - 6 * MM, negrita=True, alinear="R")
        y -= 6 * MM
        campo(x, y, "Saldo pendiente:", cop(d["saldo"]), col - 6 * MM, alinear="R")
        y -= 8 * MM
        campo(x, y, "Observaciones:", d.get("observaciones") or "", w)
        y -= 6 * MM
        c.line(x, y - 2.5, x + w, y - 2.5)

        # Firmas
        y_f = base - 8 * MM - marco_alto + 11 * MM
        texto(ancho / 2, y_f + 8 * MM, "Recibí de la persona indicada el valor registrado en este comprobante.",
              "Helvetica", 8, "C")
        c.setStrokeColorRGB(0.3, 0.3, 0.3)
        c.line(x, y_f, x + w * 0.45, y_f)
        c.line(x + w * 0.55, y_f, x + w, y_f)
        texto(x, y_f - 3.5 * MM, "Firma de quien recibe", "Helvetica", 8)
        texto(x + w * 0.55, y_f - 3.5 * MM, "Firma del cliente", "Helvetica", 8)

        if d.get("copia"):
            texto(x, base - 8 * MM - marco_alto + 2.5 * MM,
                  f"REIMPRESIÓN {d['fecha_reimpresion'].strftime('%d/%m/%Y %H:%M')}"
                  f" · {d.get('usuario_reimpresion', '')}", "Helvetica-Bold", 7, color=ROJO)
        if d.get("anulado"):
            c.saveState()
            c.translate(ancho / 2, base - 8 * MM - marco_alto / 2)
            c.rotate(18)
            texto(0, 0, "ANULADO", "Helvetica-Bold", 44, "C", (0.85, 0.25, 0.25))
            c.restoreState()
            if d.get("motivo_anulacion"):
                texto(x, base - 8 * MM - marco_alto + 6 * MM, f"Motivo: {d['motivo_anulacion']}",
                      "Helvetica", 7.5, color=ROJO, max_ancho=w)

    copia(alto, "COPIA ESTUDIANTE")
    c.setDash(3, 3)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(margen, mitad, ancho - margen, mitad)
    c.setDash()
    copia(mitad, "COPIA CEA")
    c.save()
    return buf.getvalue()
