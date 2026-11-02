"""Ticket térmico de 80 mm en PDF (sin PyQt). Devuelve bytes, no escribe en disco."""
from datetime import datetime
from io import BytesIO

from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from utils import cop

ANCHO = 80 * mm
MARGEN = 5 * mm
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
                h += c[1] * mm
            else:
                h += F_NORMAL[1] * 1.4
        return h

    def pdf(self) -> bytes:
        alto = self._altura() + 10 * mm
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=(ANCHO, alto))
        c.setTitle("Recibo PRACTICAR")
        util = ANCHO - 2 * MARGEN
        y = alto
        for cmd in self.cmds:
            tipo = cmd[0]
            if tipo == "espacio":
                y -= cmd[1] * mm
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


def generar_recibo_pago_pdf(d: dict) -> bytes:
    """d: numero_recibo, alumno_nombre, alumno_doc, concepto, valor, metodo_pago,
    cajero, acompanante, observaciones, cambio, fecha (datetime)."""
    t = _Ticket()
    t.espacio(3)
    t.texto("PRACTICAR", F_TITULO, "C", ROJO)
    t.texto("Centro de Enseñanza Automovilística", F_PEQUE, "C", GRIS)
    t.texto("Cali, Colombia  ·  NIT: 66708630", F_PEQUE, "C", GRIS)
    t.espacio(2); t.linea(0.8); t.espacio(2)

    t.texto("RECIBO DE PAGO", F_SUBTIT, "C")
    t.espacio(2); t.linea(0.3); t.espacio(1.5)
    t.texto("DATOS DEL ALUMNO", F_ETIQ, "L", GRIS); t.espacio(1)
    t.par("Nombre:", d["alumno_nombre"])
    t.par("C.C.:", d["alumno_doc"])
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
    t.texto("PRACTICAR", F_TITULO, "C", ROJO)
    t.texto("Centro de Enseñanza Automovilística", F_PEQUE, "C", GRIS)
    t.texto("Cali, Colombia  ·  NIT: 66708630", F_PEQUE, "C", GRIS)
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
