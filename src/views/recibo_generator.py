#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
recibo_generator.py — CEA PRACTICAR
Genera tickets térmicos (80 mm) en PDF para:
  - Pagos de alumnos
  - Salidas de caja

Uso:
    from views.recibo_generator import generar_recibo_pago, generar_recibo_salida
    pdf_path = generar_recibo_pago(datos)
    # Luego abrir con os.startfile(pdf_path) o subprocess
"""
from PyQt6 import QtCore, QtGui, QtWidgets
import os
import tempfile
from datetime import datetime

from reportlab.pdfgen  import canvas
from reportlab.lib.units import mm


# ── Dimensiones ticket 80 mm ──────────────────────────────────────
ANCHO_MM   = 80
ANCHO      = ANCHO_MM * mm          # 226.77 pt
MARGEN_H   = 5 * mm                 # márgenes laterales
ANCHO_UTIL = ANCHO - 2 * MARGEN_H  # zona de texto

# ── Tipografía ────────────────────────────────────────────────────
F_TITULO   = ("Helvetica-Bold",   13)
F_SUBTIT   = ("Helvetica-Bold",   9)
F_NORMAL   = ("Helvetica",        8)
F_PEQUEÑO  = ("Helvetica",        7)
F_RECIBO   = ("Helvetica-Bold",  10)
F_VALOR    = ("Helvetica-Bold",  14)

# ── Colores (RGB 0-1) ─────────────────────────────────────────────
C_NEGRO   = (0.07, 0.09, 0.15)
C_GRIS    = (0.42, 0.44, 0.50)
C_ROJO    = (0.78, 0.15, 0.16)
C_BLANCO  = (1.00, 1.00, 1.00)


# ══════════════════════════════════════════════════════════════════
#  CLASE BASE DEL TICKET
# ══════════════════════════════════════════════════════════════════

def _tamanio_adaptativo(dialogo, ancho_ideal, alto_ideal, margen=40):
    """Ajusta el tamaño del diálogo para que quepa en cualquier pantalla,
    incluyendo pantallas con barra de tareas visible."""
    from PyQt6.QtWidgets import QApplication
    screen = QApplication.primaryScreen().availableGeometry()  # descuenta la barra de tareas
    ancho = min(ancho_ideal, screen.width()  - margen)
    alto  = min(alto_ideal,  screen.height() - margen)
    dialogo.setMinimumSize(min(500, ancho), min(400, alto))
    dialogo.resize(ancho, alto)
    fg = dialogo.frameGeometry()
    fg.moveCenter(screen.center())
    dialogo.move(fg.topLeft())
    dialogo.setWindowFlags(
        dialogo.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint
    )

class _TicketBuilder:
    """Constructor interno de tickets térmicos."""

    def __init__(self):
        self._lineas: list[dict] = []   # lista de "comandos" de dibujo
        self._y = 0.0                   # cursor vertical (se llena al build)

    # ── primitivas ───────────────────────────────────────────────

    def _texto(self, texto: str, fuente: tuple, alinear: str = "L",
                color=None, y_extra: float = 0.0):
        """Agrega un texto al buffer."""
        self._lineas.append({
            "tipo": "texto", "texto": str(texto),
            "fuente": fuente, "alinear": alinear,
            "color": color or C_NEGRO, "y_extra": y_extra,
        })

    def _linea_h(self, grosor: float = 0.4, punteada: bool = False):
        self._lineas.append({"tipo": "linea", "grosor": grosor, "punteada": punteada})

    def _espacio(self, mm_: float = 2.0):
        self._lineas.append({"tipo": "espacio", "mm": mm_})

    def _par(self, clave: str, valor: str, bold_val: bool = False):
        """Fila clave – valor en la misma línea."""
        self._lineas.append({
            "tipo": "par", "clave": clave, "valor": valor, "bold_val": bold_val,
        })

    # ── encabezado y pie comunes ──────────────────────────────────

    def _agregar_encabezado(self):
        self._espacio(3)
        self._texto("PRACTICAR",         F_TITULO,  "C", C_ROJO)
        self._texto("Centro de Enseñanza Automovilística", F_PEQUEÑO, "C", C_GRIS)
        self._texto("Cali, Colombia  ·  NIT: 000-000-00",  F_PEQUEÑO, "C", C_GRIS)
        self._espacio(2)
        self._linea_h(grosor=0.8)
        self._espacio(2)

    def _agregar_pie(self, cajero: str, numero_recibo: str):
        self._espacio(2)
        self._linea_h(punteada=True)
        self._espacio(2)
        self._texto(f"Atendido por: {cajero}", F_PEQUEÑO, "C", C_GRIS)
        self._texto(f"Recibo: {numero_recibo}",   F_PEQUEÑO, "C", C_GRIS)
        now = datetime.now().strftime("%d/%m/%Y  %H:%M:%S")
        self._texto(now, F_PEQUEÑO, "C", C_GRIS)
        self._espacio(2)
        self._linea_h(grosor=0.8)
        self._espacio(2)
        self._texto("Conserve este recibo como comprobante", F_PEQUEÑO, "C", C_GRIS)
        self._texto("de su transacción.  ¡Gracias!",        F_PEQUEÑO, "C", C_GRIS)
        self._espacio(5)

    # ── renderizado ───────────────────────────────────────────────

    def _calcular_altura(self) -> float:
        """Estima la altura total del ticket antes de dibujarlo."""
        alto = 0.0
        for cmd in self._lineas:
            t = cmd["tipo"]
            if t == "texto":
                alto += cmd["fuente"][1] * 1.4
            elif t == "linea":
                alto += 4
            elif t == "espacio":
                alto += cmd["mm"] * mm
            elif t == "par":
                alto += F_NORMAL[1] * 1.4
        return alto

    def _render(self, ruta: str):
        """Dibuja todo el buffer en el PDF."""
        alto = self._calcular_altura() + 10 * mm
        c = canvas.Canvas(ruta, pagesize=(ANCHO, alto))
        c.setTitle("Recibo PRACTICAR")

        y = alto  # empezar arriba

        for cmd in self._lineas:
            t = cmd["tipo"]

            if t == "espacio":
                y -= cmd["mm"] * mm

            elif t == "linea":
                y -= 2
                c.setStrokeColorRGB(*C_GRIS)
                c.setLineWidth(cmd["grosor"])
                if cmd["punteada"]:
                    c.setDash(2, 3)
                else:
                    c.setDash()
                c.line(MARGEN_H, y, ANCHO - MARGEN_H, y)
                c.setDash()
                y -= 2

            elif t == "texto":
                fn, fs = cmd["fuente"]
                alto_ln = fs * 1.4
                y -= alto_ln
                c.setFont(fn, fs)
                c.setFillColorRGB(*cmd["color"])
                x_txt = _x_para(cmd["alinear"], MARGEN_H, ANCHO - MARGEN_H)
                if cmd["alinear"] == "C":
                    c.drawCentredString(x_txt, y, cmd["texto"])
                elif cmd["alinear"] == "R":
                    c.drawRightString(x_txt, y, cmd["texto"])
                else:
                    c.drawString(x_txt, y, cmd["texto"])

            elif t == "par":
                alto_ln = F_NORMAL[1] * 1.4
                y -= alto_ln
                # clave izquierda
                c.setFont(*F_NORMAL)
                c.setFillColorRGB(*C_GRIS)
                c.drawString(MARGEN_H, y, cmd["clave"])
                # valor derecha
                fn_val = F_SUBTIT[0] if cmd["bold_val"] else F_NORMAL[0]
                fs_val = F_NORMAL[1]
                c.setFont(fn_val, fs_val)
                c.setFillColorRGB(*C_NEGRO)
                c.drawRightString(ANCHO - MARGEN_H, y, cmd["valor"])

        c.save()


def _x_para(alinear: str, x_izq: float, x_der: float) -> float:
    if alinear == "C":
        return (x_izq + x_der) / 2
    if alinear == "R":
        return x_der
    return x_izq


# ══════════════════════════════════════════════════════════════════
#  TICKET DE PAGO
# ══════════════════════════════════════════════════════════════════

def generar_recibo_pago(datos: dict) -> str:
    """
    Genera el PDF del ticket de INGRESO (pago de alumno).

    Parámetros esperados en `datos`:
        numero_recibo   str   — Ej: "CEA-20260523-A1B2"
        alumno_nombre   str   — Nombres completos
        alumno_doc      str   — Número de cédula
        concepto        str   — Descripción del pago
        valor           float — Valor registrado
        metodo_pago     str   — Efectivo / Nequi / etc.
        cajero          str   — Nombre del cajero en sesión
        acompanante     str   — (opcional) Nombre del acompañante
        observaciones   str   — (opcional)
        cambio          float — (opcional) Cambio devuelto en efectivo

    Retorna:
        Ruta absoluta al PDF generado en directorio temporal.
    """
    b = _TicketBuilder()
    b._agregar_encabezado()

    # Tipo de documento
    b._texto("RECIBO DE PAGO", F_SUBTIT, "C", C_NEGRO)
    b._espacio(2)

    # Datos del alumno
    b._lineas.append({"tipo": "linea", "grosor": 0.3, "punteada": False})
    b._espacio(1.5)
    b._texto("DATOS DEL ALUMNO", ("Helvetica-Bold", 7), "L", C_GRIS)
    b._espacio(1)
    b._par("Nombre:",    datos["alumno_nombre"])
    b._par("C.C.:",      datos["alumno_doc"])

    acompanante = (datos.get("acompanante") or "").strip()
    if acompanante:
        b._par("Acompañante:", acompanante)

    b._espacio(2)

    # Detalle del pago
    b._lineas.append({"tipo": "linea", "grosor": 0.3, "punteada": False})
    b._espacio(1.5)
    b._texto("DETALLE", ("Helvetica-Bold", 7), "L", C_GRIS)
    b._espacio(1)
    b._par("Concepto:", datos["concepto"])
    b._par("Método:",   datos["metodo_pago"])

    obs = (datos.get("observaciones") or "").strip()
    if obs:
        b._par("Notas:", obs[:40])

    b._espacio(2)

    # Valor destacado
    b._lineas.append({"tipo": "linea", "grosor": 0.8, "punteada": False})
    b._espacio(2)
    b._texto("VALOR RECIBIDO", ("Helvetica-Bold", 7), "C", C_GRIS)
    valor_fmt = f"${datos['valor']:,.0f}"
    b._texto(valor_fmt, F_VALOR, "C", C_ROJO)
    b._espacio(1)

    cambio = datos.get("cambio", 0.0) or 0.0
    if cambio > 0:
        b._par("Cambio devuelto:", f"${cambio:,.0f}", bold_val=True)
        b._espacio(1)

    # Pie
    b._agregar_pie(datos["cajero"], datos["numero_recibo"])

    ruta = _ruta_temp(f"recibo_pago_{datos['numero_recibo']}.pdf")
    b._render(ruta)
    return ruta


# ══════════════════════════════════════════════════════════════════
#  TICKET DE SALIDA DE CAJA
# ══════════════════════════════════════════════════════════════════

def generar_recibo_salida(datos: dict) -> str:
    """
    Genera el PDF del ticket de EGRESO (salida de caja).

    Parámetros esperados en `datos`:
        numero_recibo   str   — Ej: "SAL-20260523-C3D4"
        concepto        str   — Descripción del egreso
        valor           float — Valor retirado
        metodo_pago     str   — Efectivo / Transferencia / etc.
        destinatario    str   — (opcional) A quién se entrega
        cajero          str   — Nombre del cajero en sesión
        acompanante     str   — (opcional)
        observaciones   str   — (opcional)

    Retorna:
        Ruta absoluta al PDF generado en directorio temporal.
    """
    b = _TicketBuilder()
    b._agregar_encabezado()

    # Tipo de documento
    b._texto("COMPROBANTE DE EGRESO", F_SUBTIT, "C", C_NEGRO)
    b._espacio(2)

    b._lineas.append({"tipo": "linea", "grosor": 0.3, "punteada": False})
    b._espacio(1.5)
    b._texto("DETALLE DE SALIDA", ("Helvetica-Bold", 7), "L", C_GRIS)
    b._espacio(1)
    b._par("Concepto:", datos["concepto"])
    b._par("Método:",   datos["metodo_pago"])

    dest = (datos.get("destinatario") or "").strip()
    if dest:
        b._par("Destinatario:", dest)

    acomp = (datos.get("acompanante") or "").strip()
    if acomp:
        b._par("Acompañante:", acomp)

    obs = (datos.get("observaciones") or "").strip()
    if obs:
        b._par("Notas:", obs[:40])

    b._espacio(2)

    # Valor
    b._lineas.append({"tipo": "linea", "grosor": 0.8, "punteada": False})
    b._espacio(2)
    b._texto("VALOR EGRESADO", ("Helvetica-Bold", 7), "C", C_GRIS)
    valor_fmt = f"${datos['valor']:,.0f}"
    b._texto(valor_fmt, F_VALOR, "C", C_ROJO)
    b._espacio(1)

    # Pie
    b._agregar_pie(datos["cajero"], datos["numero_recibo"])

    ruta = _ruta_temp(f"recibo_salida_{datos['numero_recibo']}.pdf")
    b._render(ruta)
    return ruta

# ══════════════════════════════════════════════════════════════════
#  TICKET DE INGRESO DE CAJA
# ══════════════════════════════════════════════════════════════════

def generar_recibo_ingreso(datos: dict) -> str:
    """
    Genera el PDF del ticket de INGRESO de caja (dinero que entra sin
    estar asociado a un pago de alumno: apertura, reposición de fondo, etc.)

    Parámetros esperados en `datos`:
        numero_recibo   str
        concepto        str
        valor           float
        metodo_pago     str
        cajero          str
        observaciones   str   — (opcional)

    Retorna:
        Ruta absoluta al PDF generado.
    """
    b = _TicketBuilder()
    b._agregar_encabezado()

    b._texto("COMPROBANTE DE INGRESO", F_SUBTIT, "C", C_NEGRO)
    b._espacio(2)

    b._lineas.append({"tipo": "linea", "grosor": 0.3, "punteada": False})
    b._espacio(1.5)
    b._texto("DETALLE DEL INGRESO", ("Helvetica-Bold", 7), "L", C_GRIS)
    b._espacio(1)
    b._par("Concepto:", datos["concepto"])
    b._par("Método:",   datos["metodo_pago"])

    obs = (datos.get("observaciones") or "").strip()
    if obs:
        b._par("Notas:", obs[:40])

    b._espacio(2)

    b._lineas.append({"tipo": "linea", "grosor": 0.8, "punteada": False})
    b._espacio(2)
    b._texto("VALOR INGRESADO", ("Helvetica-Bold", 7), "C", C_GRIS)
    valor_fmt = f"${datos['valor']:,.0f}"
    b._texto(valor_fmt, F_VALOR, "C", C_ROJO)
    b._espacio(1)

    b._agregar_pie(datos["cajero"], datos["numero_recibo"])

    ruta = _ruta_temp(f"recibo_ingreso_{datos['numero_recibo']}.pdf")
    b._render(ruta)
    return ruta
# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════
def generar_reporte_egresos_dia(egresos: list[dict], fecha: str) -> str:
    """
    Genera el PDF del reporte de egresos del día.
    """
    b = _TicketBuilder()
    b._agregar_encabezado()

    b._texto("REPORTE DE EGRESOS", F_SUBTIT, "C", C_NEGRO)
    b._texto(f"Fecha: {fecha}", F_PEQUEÑO, "C", C_GRIS)
    b._espacio(2)

    b._lineas.append({"tipo": "linea", "grosor": 0.8, "punteada": False})
    b._espacio(1.5)
    b._texto("DETALLE DE SALIDAS", ("Helvetica-Bold", 7), "L", C_GRIS)
    b._espacio(1)

    total = 0.0
    if not egresos:
        b._texto("Sin egresos registrados hoy.", F_NORMAL, "C", C_GRIS)
    else:
        for e in egresos:
            valor = float(e["valor"])
            total += valor
            b._par(e["hora"], f"${valor:,.0f}")
            concepto = (e.get("concepto") or "")[:35]
            b._texto(f"  {concepto}", F_PEQUEÑO, "L", C_GRIS)
            b._espacio(1)

    b._espacio(2)
    b._lineas.append({"tipo": "linea", "grosor": 0.8, "punteada": False})
    b._espacio(2)
    b._texto("TOTAL EGRESOS DEL DÍA", ("Helvetica-Bold", 7), "C", C_GRIS)
    b._texto(f"${total:,.0f}", F_VALOR, "C", C_ROJO)
    b._espacio(2)
    b._lineas.append({"tipo": "linea", "grosor": 0.4, "punteada": True})
    b._espacio(2)
    now = datetime.now().strftime("%d/%m/%Y  %H:%M:%S")
    b._texto(now, F_PEQUEÑO, "C", C_GRIS)
    b._espacio(5)

    ruta = _ruta_temp(f"egresos_dia_{fecha.replace('/', '-')}.pdf")
    b._render(ruta)
    return ruta
def _ruta_temp(nombre: str) -> str:
    """Devuelve la ruta en la carpeta Documentos/Recibos_PRACTICAR del usuario."""
    base = os.path.join(os.path.expanduser("~"), "Documents", "Recibos_PRACTICAR")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, nombre)


def abrir_pdf(ruta: str):
    """Abre el PDF con el visor predeterminado del sistema."""
    import subprocess, sys
    if sys.platform == "win32":
        os.startfile(ruta)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", ruta])
    else:
        subprocess.Popen(["xdg-open", ruta])
