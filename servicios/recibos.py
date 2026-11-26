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


_SECUENCIAS = {"ING": "SEQ_INGRESOS", "EGR": "SEQ_EGRESOS", "TRA": "SEQ_TRASLADOS"}


def numero_recibo(cur, prefijo: str = "ING") -> str:
    """Reserva el siguiente consecutivo: ING-001 (todo lo que entra: pagos de alumnos, abonos
    e ingresos), EGR-001 (todo lo que sale) o TRA-001 (traslados entre bancos)."""
    secuencia = _SECUENCIAS[prefijo]
    fila = cur.execute(f"SELECT {secuencia}.NEXTVAL AS n FROM dual").fetchone()
    return f"{prefijo}-{int(fila['n']):03d}"


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
