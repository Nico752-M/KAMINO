#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vista de Renovaciones — CEA PRACTICAR
Flujos:
  1. Alumno existente  → buscar → pago con descuento
  2. Alumno externo    → registrar datos básicos → pago con descuento
No genera clases. Solo pago.
"""

import os
import json
import uuid
from datetime import datetime

from database import Database

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QComboBox, QTextEdit,
    QDialog, QGridLayout, QSizePolicy, QScrollArea,
    QSpinBox, QAbstractItemView, QListWidget, QListWidgetItem,
    QDoubleSpinBox, QGraphicsDropShadowEffect, QDateEdit,
)
from PyQt6.QtCore import Qt, QTimer, QDate
from PyQt6.QtGui import QColor

# ─── Paleta global (idéntica a Nuevo Alumno) ──────────────────────────────────
PAL = {
    "bg":         "#EEF2FB",   # mismo fondo azulado de Nuevo Alumno
    "surface":    "#FDFCF9",
    "border":     "#DDD9D0",
    "border_lt":  "#EAE7E0",
    "text_1":     "#1A1916",
    "text_2":     "#5A5650",
    "text_3":     "#9A9690",
    "blue":       "#0033A0",
    "blue_dark":  "#002880",
    "blue_bg":    "#EAF1FB",
    "teal":       "#0D6E55",
    "teal_bg":    "#E0F4EE",
    "amber":      "#8A5210",
    "amber_bg":   "#FAF0DC",
    "coral":      "#E31937",
    "coral_bg":   "#FAECE6",
    "green":      "#1D9E75",
    "green_light": "#DCFCE7",
}

_PRECIOS_RENOVACION_DEFAULT = {
    "Renovación":    430_000,
    "Renovación x2": 580_000,
}

def _cargar_precios_renovacion() -> dict:
    """Lee los precios de Renovación / Renovación x2 desde precios.json
    (el mismo archivo que edita el botón 💲 Precios en Gestión de Alumnos)."""
    _ruta = os.path.join(os.path.dirname(__file__), '..', 'precios.json')
    try:
        with open(_ruta, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {
            "Renovación":    int(data.get("Renovación", _PRECIOS_RENOVACION_DEFAULT["Renovación"])),
            "Renovación x2": int(data.get("Renovación x2", _PRECIOS_RENOVACION_DEFAULT["Renovación x2"])),
        }
    except Exception:
        return dict(_PRECIOS_RENOVACION_DEFAULT)

PRECIOS_RENOVACION = _cargar_precios_renovacion()


DENOMINACIONES = [
    (100_000, "💵 $100.000"),
    ( 50_000, "💵  $50.000"),
    ( 20_000, "💵  $20.000"),
    ( 10_000, "💵  $10.000"),
    (  5_000, "💵   $5.000"),
    (  2_000, "💵   $2.000"),
    (  1_000, "🪙   $1.000"),
    (    500, "🪙     $500"),
    (    200, "🪙     $200"),
    (    100, "🪙     $100"),
    (     50, "🪙      $50"),
]

# ─── QSS compartido ───────────────────────────────────────────────────────────
FIELD_QSS = f"""
    QLineEdit, QComboBox, QDateEdit {{
        padding: 10px 14px;
        font-size: 13px;
        border: 1.5px solid {PAL['border']};
        border-radius: 8px;
        background-color: {PAL['surface']};
        color: {PAL['text_1']};
    }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
        border: 1.5px solid {PAL['blue']};
        background-color: #FFFFFF;
    }}
    QComboBox::drop-down {{ border: none; width: 28px; }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {PAL['text_2']};
        margin-right: 10px;
    }}
    QDateEdit::drop-down {{ border: none; width: 28px; }}
    QDateEdit::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {PAL['text_2']};
        margin-right: 10px;
    }}
    QTextEdit {{
        border: 1.5px solid {PAL['border']};
        border-radius: 8px;
        padding: 8px;
        font-size: 13px;
        color: {PAL['text_1']};
        background: {PAL['surface']};
    }}
    QTextEdit:focus {{ border: 1.5px solid {PAL['blue']}; }}
"""
# ─── Estilos por tipo de widget (ganan contra app.setStyleSheet) ──────────────
_FIELD = f"""
    QLineEdit {{
        padding: 10px 14px; font-size: 13px;
        border: 1.5px solid {PAL['border']}; border-radius: 8px;
        background-color: {PAL['blue_bg']}; color: {PAL['text_1']};
    }}
    QLineEdit:focus {{
        border: 1.5px solid {PAL['blue']}; background-color: #FFFFFF;
    }}
"""
_COMBO = f"""
    QComboBox {{
        padding: 10px 14px; font-size: 13px;
        border: 1.5px solid {PAL['border']}; border-radius: 8px;
        background-color: {PAL['blue_bg']}; color: {PAL['text_1']};
    }}
    QComboBox:focus {{ border: 1.5px solid {PAL['blue']}; }}
    QComboBox::drop-down {{ border: none; width: 28px; }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent; border-right: 4px solid transparent;
        border-top: 5px solid {PAL['text_2']}; margin-right: 10px;
    }}
    QComboBox QAbstractItemView {{
        border: 1.5px solid {PAL['border']}; border-radius: 8px;
        background: {PAL['surface']};
        selection-background-color: {PAL['blue_bg']};
        selection-color: {PAL['blue']}; padding: 4px;
    }}
"""
_DATE = f"""
    QDateEdit {{
        padding: 10px 14px; font-size: 13px;
        border: 1.5px solid {PAL['border']}; border-radius: 8px;
        background-color: {PAL['blue_bg']}; color: {PAL['text_1']};
        min-width: 140px; min-height: 42px;
    }}
    QDateEdit:focus {{ border: 1.5px solid {PAL['blue']}; }}
    QDateEdit::drop-down {{ border: none; width: 28px; }}
    QDateEdit::down-arrow {{
        image: none;
        border-left: 4px solid transparent; border-right: 4px solid transparent;
        border-top: 5px solid {PAL['text_2']}; margin-right: 10px;
    }}
"""
_TEXT = f"""
    QTextEdit {{
        border: 1.5px solid {PAL['border']}; border-radius: 8px;
        padding: 8px; font-size: 13px;
        color: {PAL['text_1']}; background: {PAL['blue_bg']};
    }}
    QTextEdit:focus {{ border: 1.5px solid {PAL['blue']}; background: #FFFFFF; }}
"""

# ─── DB helpers ───────────────────────────────────────────────────────────────

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

def _buscar_alumnos(termino: str):
    termino = termino.strip()
    if not termino:
        return []
    like = f"%{termino}%"
    db = Database.get_instance()
    return db.fetchall("""
        SELECT m.id AS matricula_id,
               m.categoria, m.estado,
               a.numero_documento, a.nombres, a.apellidos
        FROM matriculas m
        JOIN alumnos a ON a.numero_documento = m.numero_documento
        WHERE a.numero_documento LIKE %s OR a.nombres LIKE %s OR a.apellidos LIKE %s
        ORDER BY m.fecha_registro DESC
        LIMIT 40
    """, (like, like, like))

def _registrar_alumno_externo(numero_documento: str, tipo_documento: str,
                               nombres: str, apellidos: str,
                               fecha_nacimiento: str, celular: str,
                               precio_total: int, tipo_renovacion: str,
                               email: str = None,
                               responsable_tipo_documento: str = None,
                               responsable_numero_documento: str = None,
                               responsable_nombres: str = None,
                               responsable_apellidos: str = None,
                               responsable_celular: str = None,
                               responsable_email: str = None,
                               responsable_relacion: str = None) -> int:
    db = Database.get_instance()

    existe = db.fetchone(
        "SELECT numero_documento FROM alumnos WHERE numero_documento = %s",
        (numero_documento,)
    )
    if not existe:
        db.execute("""
            INSERT INTO alumnos
                (numero_documento, tipo_documento, nombres, apellidos,
                fecha_nacimiento, celular, email,
                responsable_tipo_documento, responsable_numero_documento,
                responsable_nombres, responsable_apellidos,
                responsable_celular, responsable_email, responsable_relacion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (numero_documento, tipo_documento, nombres, apellidos,
            fecha_nacimiento or None, celular or None, email or None,
            responsable_tipo_documento or None, responsable_numero_documento or None,
            responsable_nombres or None, responsable_apellidos or None,
            responsable_celular or None, responsable_email or None,
            responsable_relacion or None))

    from datetime import datetime as _dt
    anio_actual = _dt.now().year
    ultimo = db.fetchone(
        "SELECT numero_orden FROM matriculas WHERE anio = %s ORDER BY numero_orden DESC LIMIT 1",
        (anio_actual,)
    )
    num_nuevo = int(ultimo["numero_orden"]) + 1 if ultimo and ultimo["numero_orden"] else 1
    numero_orden = f"{num_nuevo:03d}"

    matricula_id = db.execute("""
        INSERT INTO matriculas
            (numero_documento, numero_orden, anio, categoria, estado, precio_total)
        VALUES (%s, %s, %s, %s, 'Activo', %s)
    """, (numero_documento, numero_orden, anio_actual, tipo_renovacion, precio_total))

    return matricula_id

def _generar_recibo() -> str:
    hoy    = datetime.now().strftime("%Y%m%d")
    sufijo = uuid.uuid4().hex[:4].upper()
    return f"REN-{hoy}-{sufijo}"


def _registrar_pago(matricula_id: int, tipo_renovacion: str,
                    valor: float, metodo: str,
                    observaciones: str, usuario_id: int = 1,
                    desglose: list | None = None) -> str:
    numero_recibo = _generar_recibo()
    concepto = f"Renovación de licencia — {tipo_renovacion}"
    db = Database.get_instance()

    pago_id = db.execute("""
        INSERT INTO pagos
            (id_matricula, concepto, valor, metodo_pago, numero_recibo, usuario_id, observaciones)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (matricula_id, concepto, valor, metodo, numero_recibo, usuario_id, observaciones))

    if metodo == "Efectivo" and desglose:
        filas = [
            (pago_id, d["denominacion"], d["cantidad"], d["tipo"])
            for d in desglose if d["cantidad"] > 0
        ]
        if filas:
            db.execute_many("""
                INSERT INTO desglose_efectivo (pago_id, denominacion, cantidad, tipo)
                VALUES (%s, %s, %s, %s)
            """, filas)

    return numero_recibo

# ─── UI helpers ───────────────────────────────────────────────────────────────

def _shadow(w, blur=16, oy=4, alpha=0.08):
    sh = QGraphicsDropShadowEffect()
    sh.setBlurRadius(blur)
    sh.setOffset(0, oy)
    sh.setColor(QColor(26, 25, 22, int(alpha * 255)))
    w.setGraphicsEffect(sh)


def _sep():
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"background: {PAL['border_lt']}; border: none; max-height: 1px;")
    return f


def _make_section_label(texto: str) -> QWidget:
    """Header de sección con barra vertical azul + línea — igual a Nuevo Alumno."""
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 16, 0, 6)
    row.setSpacing(10)

    accent = QWidget()
    accent.setFixedSize(3, 16)
    accent.setStyleSheet(
        f"background-color: {PAL['blue']}; border-radius: 2px; border: none;"
    )
    row.addWidget(accent, 0, Qt.AlignmentFlag.AlignVCenter)

    lbl = QLabel(texto.upper())
    lbl.setStyleSheet(f"""
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.14em;
        color: {PAL['blue']};
        background: transparent;
    """)
    lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    row.addWidget(lbl)

    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    line.setStyleSheet(
        f"background-color: {PAL['border_lt']}; border: none; max-height: 1px;"
    )
    row.addWidget(line)

    return container


def _make_field_label(texto: str) -> QLabel:
    """Etiqueta de campo en gris claro — igual a Nuevo Alumno."""
    lbl = QLabel(texto)
    lbl.setStyleSheet(f"""
        font-size: 11px;
        font-weight: 600;
        color: {PAL['text_3']};
        background: transparent;
        padding-bottom: 1px;
    """)
    return lbl


def _fmt(v: int) -> str:
    return f"$ {v:,.0f}".replace(",", ".")


def _card() -> QFrame:
    """Card limpia sin borde de color superior — igual a Nuevo Alumno."""
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame {{
            background: {PAL['surface']};
            border: 1.5px solid {PAL['border_lt']};
            border-radius: 10px;
        }}
    """)
    _shadow(f, blur=12, oy=3, alpha=0.06)
    return f


def _btn_primary(texto: str) -> QPushButton:
    b = QPushButton(texto)
    b.setStyleSheet(f"""
        QPushButton {{
            background-color: {PAL['blue']};
            color: #FFFFFF;
            border: none;
            border-radius: 9px;
            padding: 11px 22px;
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.01em;
        }}
        QPushButton:hover {{ background-color: {PAL['blue_dark']}; }}
        QPushButton:pressed {{ background-color: #001E60; }}
    """)
    return b


def _btn_secondary(texto: str) -> QPushButton:
    b = QPushButton(texto)
    b.setStyleSheet(f"""
        QPushButton {{
            background-color: {PAL['bg']};
            color: {PAL['text_1']};
            border: 1.5px solid {PAL['border']};
            border-radius: 9px;
            padding: 11px 22px;
            font-size: 13px;
            font-weight: 500;
        }}
        QPushButton:hover {{ background-color: {PAL['border_lt']}; border-color: {PAL['border']}; }}
        QPushButton:pressed {{ background-color: {PAL['border']}; }}
    """)
    return b


# ══════════════════════════════════════════════════════════════════════════════
#  WIDGET: CALCULADORA DE BILLETES
# ══════════════════════════════════════════════════════════════════════════════

class _Calculadora(QWidget):
    from PyQt6.QtCore import pyqtSignal
    total_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._spinners = []
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {PAL['surface']};")
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)

        # Cabecera de columnas
        for col, txt in enumerate(["Denominación", "Cantidad", "Subtotal"]):
            lbl = QLabel(txt)
            lbl.setStyleSheet(
                f"font-size:10px; font-weight:700; color:{PAL['text_3']};"
                f" letter-spacing:0.08em;"
            )
            lbl.setAlignment(
                Qt.AlignmentFlag.AlignCenter if col > 0 else Qt.AlignmentFlag.AlignLeft
            )
            grid.addWidget(lbl, 0, col)

        for row_idx, (valor, etiqueta) in enumerate(DENOMINACIONES, start=1):
            lbl_den = QLabel(etiqueta)
            lbl_den.setStyleSheet(
                f"font-size:13px; color:{PAL['text_1']}; font-weight:600;"
                f" font-family:'Courier New',monospace;"
            )
            grid.addWidget(lbl_den, row_idx, 0)

            spin = QSpinBox()
            spin.setMinimum(0); spin.setMaximum(999); spin.setValue(0)
            spin.setFixedWidth(72)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin.setStyleSheet(f"""
                QSpinBox {{
                    border: 1.5px solid {PAL['border']}; border-radius: 6px;
                    background: {PAL['surface']}; color: {PAL['text_1']};
                    font-size: 13px; padding: 4px;
                }}
                QSpinBox:focus {{ border: 1.5px solid {PAL['blue']}; }}
            """)
            spin.valueChanged.connect(self._recalcular)
            grid.addWidget(spin, row_idx, 1, Qt.AlignmentFlag.AlignCenter)

            lbl_sub = QLabel("$0")
            lbl_sub.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_sub.setStyleSheet(
                f"font-size:13px; color:{PAL['text_1']}; font-weight:500; min-width:90px;"
            )
            grid.addWidget(lbl_sub, row_idx, 2)
            self._spinners.append((valor, spin, lbl_sub))

        grid.setColumnStretch(0, 1)

    def _recalcular(self):
        total = 0.0
        for valor, spin, lbl_sub in self._spinners:
            sub = valor * spin.value()
            total += sub
            lbl_sub.setText(f"${sub:,.0f}" if sub > 0 else "$0")
        self.total_changed.emit(total)

    def total(self) -> float:
        return sum(v * s.value() for v, s, _ in self._spinners)

    def reset(self):
        for _, spin, lbl in self._spinners:
            spin.setValue(0); lbl.setText("$0")

    def desglose(self) -> list:
        result = []
        for valor, spin, _ in self._spinners:
            if spin.value() > 0:
                tipo = "billete" if valor >= 1000 else "moneda"
                result.append({"denominacion": valor, "cantidad": spin.value(), "tipo": tipo})
        return result


# ══════════════════════════════════════════════════════════════════════════════
#  WIDGET: SECCIÓN DE PRECIO CON DESCUENTO
# ══════════════════════════════════════════════════════════════════════════════

class _SeccionPrecio(QWidget):
    from PyQt6.QtCore import pyqtSignal
    precio_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._precio_base = 0
        self._bloq = False
        self._build()

    # ── _SeccionPrecio._build() — reemplaza solo las líneas de los dos campos ──────
    def _build(self):
        self.setStyleSheet("background: transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        card = _card()
        card.setStyleSheet(f"""
            QFrame {{
                background: {PAL['surface']};
                border: 1.5px solid {PAL['border_lt']};
                border-top: 3px solid {PAL['teal']};
                border-radius: 10px;
            }}
        """)
        grid = QGridLayout(card)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(10)
        grid.setContentsMargins(20, 22, 20, 22)

        grid.addWidget(_make_field_label("Precio base"), 0, 0)
        grid.addWidget(_make_field_label("Descuento ($ pesos)"), 0, 1)
        grid.addWidget(_make_field_label("% Descuento"), 0, 2)

        self.lbl_precio_base = QLabel(_fmt(0))
        self.lbl_precio_base.setStyleSheet(f"""
            font-size: 15px; font-weight: 700; color: {PAL['text_2']};
            background: {PAL['bg']}; border: 1.5px solid {PAL['border']};
            border-radius: 8px; padding: 10px 14px;
        """)
        grid.addWidget(self.lbl_precio_base, 1, 0)

        self.field_desc_pesos = QLineEdit()
        self.field_desc_pesos.setPlaceholderText("Ej: 50000")
        self.field_desc_pesos.setStyleSheet(_FIELD)
        self.field_desc_pesos.textChanged.connect(self._on_desc_pesos)
        grid.addWidget(self.field_desc_pesos, 1, 1)

        self.field_desc_pct = QLineEdit()
        self.field_desc_pct.setPlaceholderText("Ej: 10")
        self.field_desc_pct.setStyleSheet(_FIELD)
        self.field_desc_pct.textChanged.connect(self._on_desc_pct)
        grid.addWidget(self.field_desc_pct, 1, 2)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {PAL['border_lt']}; border: none; max-height: 1px;")
        grid.addWidget(sep, 2, 0, 1, 3)

        grid.addWidget(_make_field_label("Total a pagar *"), 3, 0)
        hint = QLabel("Puedes modificar el valor directamente")
        hint.setStyleSheet(f"font-size: 11px; color: {PAL['text_3']}; font-weight: 400;")
        grid.addWidget(hint, 3, 1, 1, 2)

        self.field_total = QLineEdit()
        self.field_total.setPlaceholderText("0")
        self.field_total.setStyleSheet(f"""
            QLineEdit {{
                font-size: 18px; font-weight: 700; color: {PAL['blue']};
                border: 2px solid {PAL['blue']}; border-radius: 8px;
                padding: 10px 14px; background: {PAL['blue_bg']};
            }}
            QLineEdit:focus {{
                border: 2px solid {PAL['blue_dark']}; background: #FFFFFF;
            }}
        """)
        self.field_total.setFixedHeight(52)
        self.field_total.textChanged.connect(self._on_total_changed)
        grid.addWidget(self.field_total, 4, 0, 1, 3)

        root.addWidget(card)  # ← solo una vez, aquí termina _build

    def set_precio_base(self, precio: int):
        self._precio_base = precio
        self.lbl_precio_base.setText(_fmt(precio))
        self._bloq = True
        self.field_desc_pesos.clear()
        self.field_desc_pct.clear()
        self._bloq = False
        self._recalcular()

    def _on_desc_pesos(self, texto: str):
        if self._bloq: return
        self._bloq = True
        try:
            val = int(texto.replace(".", "").replace(",", "").strip() or "0")
            if self._precio_base > 0:
                pct = round((val / self._precio_base) * 100, 2)
                self.field_desc_pct.setText(str(pct) if pct > 0 else "")
        except ValueError:
            self.field_desc_pct.clear()
        finally:
            self._bloq = False
        self._recalcular()

    def _on_desc_pct(self, texto: str):
        if self._bloq: return
        self._bloq = True
        try:
            pct   = float(texto.replace(",", ".").strip() or "0")
            pesos = int(self._precio_base * pct / 100)
            self.field_desc_pesos.setText(str(pesos) if pesos > 0 else "")
        except ValueError:
            self.field_desc_pesos.clear()
        finally:
            self._bloq = False
        self._recalcular()

    def _on_total_changed(self, texto: str):
        if self._bloq: return
        self._bloq = True
        try:
            total     = int(texto.replace(".", "").replace(",", "").replace("$", "").strip() or "0")
            descuento = self._precio_base - total
            if descuento > 0:
                self.field_desc_pesos.setText(str(descuento))
                if self._precio_base > 0:
                    pct = round((descuento / self._precio_base) * 100, 2)
                    self.field_desc_pct.setText(str(pct))
            else:
                self.field_desc_pesos.clear()
                self.field_desc_pct.clear()
        except ValueError:
            pass
        finally:
            self._bloq = False

    def _recalcular(self):
        try:
            desc = int(
                self.field_desc_pesos.text().replace(".", "").replace(",", "").strip() or "0"
            )
        except ValueError:
            desc = 0
        total = max(self._precio_base - desc, 0)
        self._bloq = True
        self.field_total.setText(str(total))
        self._bloq = False
        self.precio_changed.emit(total)

    def get_total(self) -> int:
        try:
            return int(
                self.field_total.text()
                    .replace(".", "").replace(",", "").replace("$", "").strip()
                or "0"
            )
        except ValueError:
            return 0


# ══════════════════════════════════════════════════════════════════════════════
#  DIÁLOGO: REGISTRAR PAGO DE RENOVACIÓN
# ══════════════════════════════════════════════════════════════════════════════

class DialogoRenovacion(QDialog):

    def __init__(self, alumno: dict, parent=None):
        super().__init__(parent)
        self.alumno = alumno
        self.setWindowTitle("Registrar Renovación")
        _tamanio_adaptativo(self, 720, 800)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {PAL['bg']}; }}
            QDialog QLineEdit {{
                padding: 10px 14px; font-size: 13px;
                border: 1.5px solid {PAL['border']}; border-radius: 8px;
                background-color: {PAL['surface']}; color: {PAL['text_1']};
            }}
            QDialog QLineEdit:focus {{
                border: 1.5px solid {PAL['blue']}; background-color: #FFFFFF;
            }}
            QDialog QComboBox {{
                padding: 10px 14px; font-size: 13px;
                border: 1.5px solid {PAL['border']}; border-radius: 8px;
                background-color: {PAL['surface']}; color: {PAL['text_1']};
            }}
            QDialog QComboBox:focus {{ border: 1.5px solid {PAL['blue']}; }}
            QDialog QComboBox::drop-down {{ border: none; width: 28px; }}
            QDialog QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent; border-right: 4px solid transparent;
                border-top: 5px solid {PAL['text_2']}; margin-right: 10px;
            }}
            QDialog QTextEdit {{
                border: 1.5px solid {PAL['border']}; border-radius: 8px;
                padding: 8px; font-size: 13px;
                color: {PAL['text_1']}; background: {PAL['surface']};
            }}
            QDialog QTextEdit:focus {{ border: 1.5px solid {PAL['blue']}; }}
            QLabel {{ background: transparent; }}
            QLineEdit {{
                padding: 10px 14px; font-size: 13px;
                border: 1.5px solid {PAL['border']}; border-radius: 8px;
                background-color: {PAL['surface']}; color: {PAL['text_1']};
            }}
            QLineEdit:focus {{
                border: 1.5px solid {PAL['blue']}; background-color: #FFFFFF;
            }}
            QComboBox {{
                padding: 10px 14px; font-size: 13px;
                border: 1.5px solid {PAL['border']}; border-radius: 8px;
                background-color: {PAL['surface']}; color: {PAL['text_1']};
            }}
            QComboBox:focus {{ border: 1.5px solid {PAL['blue']}; }}
            QComboBox::drop-down {{ border: none; width: 28px; }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent; border-right: 4px solid transparent;
                border-top: 5px solid {PAL['text_2']}; margin-right: 10px;
            }}
            QComboBox QAbstractItemView {{
                border: 1.5px solid {PAL['border']}; border-radius: 8px;
                background: {PAL['surface']};
                selection-background-color: {PAL['blue_bg']};
                selection-color: {PAL['blue']}; padding: 4px;
            }}
            QScrollBar:vertical {{
                width: 6px; background: transparent; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {PAL['border']}; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        PRECIOS_RENOVACION.update(_cargar_precios_renovacion())
        self._build()

    # ── DialogoRenovacion._build() — solo el bloque de tipo y método de pago ──────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # cabecera — sin cambios
        header = QFrame()
        header.setStyleSheet(f"background: {PAL['blue']};")
        header.setFixedHeight(80)
        h_outer = QHBoxLayout(header)
        h_outer.setContentsMargins(0, 0, 0, 0)
        h_outer.setSpacing(0)
        h_inner = QVBoxLayout()
        h_inner.setContentsMargins(28, 10, 28, 10)
        h_inner.setSpacing(3)
        nombre = f"{self.alumno['nombres']} {self.alumno['apellidos']}"
        lbl_t = QLabel("🔄  Renovación de Licencia")
        lbl_t.setStyleSheet("font-size:18px; font-weight:800; color:#FFFFFF;")
        lbl_n = QLabel(nombre)
        lbl_n.setStyleSheet("font-size:13px; color:rgba(255,255,255,0.80); font-weight:600;")
        lbl_d = QLabel(
            f"C.C. {self.alumno.get('numero_documento','—')}  ·  "
            f"Categoría: {self.alumno.get('categoria','Renovación')}"
        )
        lbl_d.setStyleSheet("font-size:11px; color:rgba(255,255,255,0.55);")
        h_inner.addWidget(lbl_t); h_inner.addWidget(lbl_n); h_inner.addWidget(lbl_d)
        h_outer.addLayout(h_inner)
        h_outer.addStretch()
        red = QWidget()
        red.setFixedSize(48, 80)
        red.setStyleSheet(f"background: {PAL['coral']}; border: none;")
        h_outer.addWidget(red)
        root.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {PAL['bg']}; border: none;")
        body = QWidget()
        body.setStyleSheet(f"background: {PAL['bg']};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(28, 22, 28, 22)
        body_lay.setSpacing(4)

        # tipo renovación
        body_lay.addWidget(_make_section_label("Tipo de Renovación"))
        tipo_card = _card()
        tipo_grid = QGridLayout(tipo_card)
        tipo_grid.setContentsMargins(20, 18, 20, 18)
        tipo_grid.setSpacing(12)
        tipo_grid.addWidget(_make_field_label("Tipo:"), 0, 0)
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(list(PRECIOS_RENOVACION.keys()))
        self.combo_tipo.setFixedHeight(42)
        self.combo_tipo.setStyleSheet(_COMBO)                
        cat_actual = self.alumno.get('categoria')
        if cat_actual in PRECIOS_RENOVACION:
            idx_cat = self.combo_tipo.findText(cat_actual)
            if idx_cat >= 0:
                self.combo_tipo.setCurrentIndex(idx_cat)
        self.combo_tipo.setEnabled(False)
        self.combo_tipo.currentTextChanged.connect(self._on_tipo_changed)
        tipo_grid.addWidget(self.combo_tipo, 1, 0)
        lbl_nota = QLabel("✓ Sin clases — solo pago")
        lbl_nota.setStyleSheet(f"font-size:11px; color:{PAL['teal']}; font-weight:600;")
        tipo_grid.addWidget(lbl_nota, 1, 1)
        body_lay.addWidget(tipo_card)

        # precio
        body_lay.addWidget(_make_section_label("Valor del Curso"))
        self.seccion_precio = _SeccionPrecio()
        self.seccion_precio.set_precio_base(
            PRECIOS_RENOVACION.get(self.combo_tipo.currentText(), list(PRECIOS_RENOVACION.values())[0])
        )
        self.seccion_precio.precio_changed.connect(self._on_precio_changed)
        body_lay.addWidget(self.seccion_precio)

        # método de pago
        body_lay.addWidget(_make_section_label("Método de Pago"))
        pago_card = _card()
        pago_card.setFixedHeight(130)
        pago_card.setFixedHeight(150)
        pago_grid = QGridLayout(pago_card)
        pago_grid.setContentsMargins(14, 12, 14, 12)
        pago_grid.setSpacing(8)

        pago_grid.addWidget(_make_field_label("Método:"), 0, 0)
        self.combo_metodo = QComboBox()
        self.combo_metodo.addItems(["Efectivo", "Transferencia", "Nequi", "Daviplata", "Sistecredit", "Otro"])
        self.combo_metodo.setFixedHeight(42)
        self.combo_metodo.setStyleSheet(_COMBO)              # ← aquí
        self.combo_metodo.currentTextChanged.connect(self._toggle_calculadora)
        pago_grid.addWidget(self.combo_metodo, 1, 0)

        self.lbl_monto_campo = _make_field_label("Monto:")
        self.lbl_monto_campo.setFixedHeight(16)
        pago_grid.addWidget(self.lbl_monto_campo, 0, 1)
        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setMinimum(1_000); self.spin_monto.setMaximum(10_000_000)
        self.spin_monto.setSingleStep(10_000); self.spin_monto.setDecimals(0)
        self.spin_monto.setPrefix("$ "); self.spin_monto.setFixedHeight(42)
        self.spin_monto.setValue(list(PRECIOS_RENOVACION.values())[0])
        self.spin_monto.setStyleSheet(f"""
            QDoubleSpinBox {{
                border: 1.5px solid {PAL['border']}; border-radius: 8px;
                padding: 8px 12px; font-size: 14px; font-weight: 700;
                color: {PAL['blue']}; background: {PAL['blue_bg']};
            }}
            QDoubleSpinBox:focus {{ border: 1.5px solid {PAL['blue_dark']}; }}
        """)
        pago_grid.addWidget(self.spin_monto, 1, 1)

        lbl_notas = _make_field_label("Notas:")
        lbl_notas.setFixedHeight(16)
        pago_grid.addWidget(lbl_notas, 0, 2)
        self.obs_input = QTextEdit()
        self.obs_input.setPlaceholderText("Observaciones opcionales…")
        self.obs_input.setFixedHeight(68)
        self.obs_input.setStyleSheet(_TEXT)                  # ← aquí
        pago_grid.addWidget(self.obs_input, 1, 2)
        pago_grid.setRowStretch(0, 0)
        pago_grid.setRowStretch(1, 0)
        body_lay.addWidget(pago_card)

        # calculadora — sin cambios
        self.calc_section = QWidget()
        self.calc_section.setStyleSheet("background: transparent;")
        calc_lay = QVBoxLayout(self.calc_section)
        calc_lay.setContentsMargins(0, 0, 0, 0)
        calc_lay.setSpacing(4)
        calc_lay.addWidget(_make_section_label("Billetes y Monedas Recibidos"))
        calc_card = _card()
        calc_card_lay = QVBoxLayout(calc_card)
        calc_card_lay.setContentsMargins(16, 14, 16, 14)
        calc_card_lay.setSpacing(10)
        self.calculadora = _Calculadora()
        self.calculadora.total_changed.connect(self._actualizar_cambio)
        calc_card_lay.addWidget(self.calculadora)
        calc_card_lay.addWidget(_sep())

        tot_grid = QGridLayout()
        tot_grid.setSpacing(6)
        def _k(t):
            l = QLabel(t)
            l.setStyleSheet(f"font-size:12px; color:{PAL['text_2']}; font-weight:600;")
            return l
        def _v(t, c=PAL["text_1"]):
            l = QLabel(t)
            l.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            l.setStyleSheet(f"font-size:14px; font-weight:800; color:{c};")
            return l
        tot_grid.addWidget(_k("💵  Efectivo entregado:"), 0, 0)
        self.lbl_entregado = _v("$0")
        tot_grid.addWidget(self.lbl_entregado, 0, 1)
        tot_grid.addWidget(_k("📋  A registrar:"), 1, 0)
        self.lbl_a_registrar = _v("$0", PAL["blue"])
        tot_grid.addWidget(self.lbl_a_registrar, 1, 1)

        cambio_frame = QFrame()
        cambio_frame.setStyleSheet(
            f"QFrame {{ background: {PAL['teal_bg']}; border: 1.5px solid #86EFAC; border-radius: 8px; }}"
        )
        cambio_lay2 = QHBoxLayout(cambio_frame)
        cambio_lay2.setContentsMargins(12, 8, 12, 8)
        lk = QLabel("🔄  Cambio a devolver:")
        lk.setStyleSheet(f"font-size:13px; font-weight:700; color:{PAL['teal']};")
        self.lbl_cambio = QLabel("$0")
        self.lbl_cambio.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_cambio.setStyleSheet(f"font-size:20px; font-weight:800; color:{PAL['teal']};")
        cambio_lay2.addWidget(lk); cambio_lay2.addStretch(); cambio_lay2.addWidget(self.lbl_cambio)
        calc_card_lay.addLayout(tot_grid)
        calc_card_lay.addWidget(cambio_frame)
        calc_lay.addWidget(calc_card)
        body_lay.addWidget(self.calc_section)
        body_lay.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, 1)



        # footer — sin cambios
        footer = QFrame()
        footer.setStyleSheet(
            f"QFrame {{ background: {PAL['surface']}; border-top: 1.5px solid {PAL['border_lt']}; }}"
        )
        footer.setFixedHeight(70)
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(28, 0, 28, 0)
        f_lay.setSpacing(12)
        btn_cancelar = _btn_secondary("Cancelar")
        btn_cancelar.setFixedHeight(42)
        btn_cancelar.clicked.connect(self.reject)
        f_lay.addWidget(btn_cancelar)
        f_lay.addStretch()
        self.lbl_alerta = QLabel("")
        self.lbl_alerta.setStyleSheet(f"font-size:12px; color:{PAL['coral']}; font-weight:600;")
        f_lay.addWidget(self.lbl_alerta)
        self.btn_confirmar = _btn_primary("✓   Confirmar Renovación")
        self.btn_confirmar.setFixedHeight(42)
        self.btn_confirmar.setMinimumWidth(200)
        self.btn_confirmar.clicked.connect(self._validar)
        f_lay.addWidget(self.btn_confirmar)
        root.addWidget(footer)

        self._toggle_calculadora(self.combo_metodo.currentText())
    # ── Lógica ────────────────────────────────────────────────────────────────

    def _on_tipo_changed(self, tipo: str):
        precio = PRECIOS_RENOVACION.get(tipo, 0)
        recargo = 50_000 if self.combo_metodo.currentText() == "Sistecredit" else 0
        self.seccion_precio.set_precio_base(precio + recargo)
        self.spin_monto.setValue(precio + recargo)

    def _on_precio_changed(self, total: int):
        self.spin_monto.setValue(total)
        self._actualizar_cambio()

    def _toggle_calculadora(self, metodo: str):
        
        es_efectivo = metodo == "Efectivo"
        es_sistecredit = metodo == "Sistecredit"
        self.calc_section.setVisible(es_efectivo)
        self.spin_monto.setHidden(es_efectivo)
        self.lbl_monto_campo.setHidden(es_efectivo)
        self.lbl_recargo.setVisible(es_sistecredit)
        if not es_efectivo:
            self.calculadora.reset()
            self.lbl_alerta.setText("")
        # Actualizar precio base con o sin recargo
        tipo_actual = self.combo_tipo.currentText()
        precio_sin_recargo = PRECIOS_RENOVACION.get(tipo_actual, 0)
        recargo = 50_000 if es_sistecredit else 0
        self.seccion_precio.set_precio_base(precio_sin_recargo + recargo)
        self._actualizar_cambio()
    
    def _actualizar_cambio(self):
        total     = self.seccion_precio.get_total()
        entregado = self.calculadora.total()
        abono     = min(entregado, total)
        cambio    = entregado - abono
        self.lbl_a_registrar.setText(f"${abono:,.0f}")
        self.lbl_entregado.setText(f"${entregado:,.0f}")
        if cambio < 0:
                # Abono parcial: mostrar saldo pendiente (informativo, no bloqueante)
            self.lbl_cambio.setText(f"${abs(cambio):,.0f}")
            self.lbl_cambio.setStyleSheet(f"font-size:20px; font-weight:800; color:{PAL['amber']};")
            self.lbl_alerta.setText(f"💳 Saldo pendiente: ${abs(cambio):,.0f}")
        else:
            self.lbl_cambio.setText(f"${cambio:,.0f}")
            self.lbl_cambio.setStyleSheet(f"font-size:20px; font-weight:800; color:{PAL['teal']};")
            self.lbl_alerta.setText("")

    def _validar(self):
        if self.seccion_precio.get_total() <= 0:
            QMessageBox.warning(self, "Valor inválido", "El total debe ser mayor a $0.")
            return
        if self.combo_metodo.currentText() == "Efectivo" and self.calculadora.total() == 0:
            resp = QMessageBox.question(
                self, "Sin abono",
                "No se han ingresado billetes. ¿Deseas inscribir al alumno sin registrar abono?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if resp == QMessageBox.StandardButton.No:
                return
        self.accept()

    @property
    def tipo_renovacion(self) -> str: return self.combo_tipo.currentText()
    @property
    def valor(self) -> float:
        if self.combo_metodo.currentText() == "Efectivo":
            return min(self.calculadora.total(), self.seccion_precio.get_total())
        return self.spin_monto.value()
    @property
    def metodo(self) -> str: return self.combo_metodo.currentText()
    @property
    def observaciones(self) -> str: return self.obs_input.toPlainText().strip()
    @property
    def desglose(self) -> list: return self.calculadora.desglose()


# ══════════════════════════════════════════════════════════════════════════════
#  DIÁLOGO: REGISTRAR ALUMNO EXTERNO
# ══════════════════════════════════════════════════════════════════════════════

class DialogoAlumnoExterno(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Renovación — Alumno Externo")
        _tamanio_adaptativo(self, 1200, 960)

        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {PAL['bg']}; }}
            QLabel {{ background: transparent; }}
        """)
        self.fields = {}
        PRECIOS_RENOVACION.update(_cargar_precios_renovacion())
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ═══════════════════════════════════════════════════════
        #  HEADER
        # ═══════════════════════════════════════════════════════
        header = QFrame()
        header.setStyleSheet(f"background: {PAL['blue']};")
        header.setFixedHeight(96)
        h_outer = QHBoxLayout(header)
        h_outer.setContentsMargins(0, 0, 0, 0)
        h_outer.setSpacing(0)

        h_inner = QVBoxLayout()
        h_inner.setContentsMargins(28, 14, 28, 14)
        h_inner.setSpacing(3)

        lbl_t = QLabel("🔄  Nueva Renovación — Alumno Externo")
        lbl_t.setStyleSheet("font-size:18px; font-weight:800; color:#FFFFFF;")
        lbl_s = QLabel("Persona que nunca ha estudiado en esta escuela")
        lbl_s.setStyleSheet("font-size:12px; color:rgba(255,255,255,0.65);")

        h_inner.addWidget(lbl_t)
        h_inner.addWidget(lbl_s)
        h_outer.addLayout(h_inner)
        h_outer.addStretch()

        step_lbl = QLabel("Renovación")
        step_lbl.setStyleSheet(f"""
            font-size: 11px; font-weight: 600; color: rgba(255,255,255,0.90);
            background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25);
            padding: 6px 16px; border-radius: 20px;
        """)
        h_outer.addWidget(step_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        red = QWidget()
        red.setFixedSize(48, 96)
        red.setStyleSheet(f"background: {PAL['coral']}; border: none;")
        h_outer.addWidget(red)

        root.addWidget(header)

        # ═══════════════════════════════════════════════════════
        #  BARRA DE PROGRESO
        # ═══════════════════════════════════════════════════════
        progress_bg = QWidget()
        progress_bg.setFixedHeight(4)
        progress_bg.setStyleSheet(f"background-color: {PAL['border_lt']};")
        progress_bar_layout = QHBoxLayout(progress_bg)
        progress_bar_layout.setContentsMargins(0, 0, 0, 0)
        progress_bar_layout.setSpacing(0)

        progress_fill = QWidget()
        progress_fill.setFixedHeight(4)
        progress_fill.setMaximumWidth(430)
        progress_fill.setStyleSheet(f"""
            background-color: {PAL['blue']};
            border-right: 4px solid {PAL['coral']};
            border: none;
        """)
        progress_bar_layout.addWidget(progress_fill)
        progress_bar_layout.addStretch()
        root.addWidget(progress_bg)

        # ═══════════════════════════════════════════════════════
        #  SCROLL + BODY
        # ═══════════════════════════════════════════════════════
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {PAL['bg']}; border: none;")

        body = QWidget()
        body.setStyleSheet(f"background: {PAL['bg']};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(32, 16, 32, 16)
        body_lay.setSpacing(0)

        # ══════════════════════════════════════════════════════
        #  COLUMNAS
        # ══════════════════════════════════════════════════════
        cols = QHBoxLayout()
        cols.setSpacing(20)
        cols.setContentsMargins(0, 0, 0, 0)

        col_left = QVBoxLayout()
        col_left.setSpacing(8)

        col_right = QVBoxLayout()
        col_right.setSpacing(8)

        # ═══════════════════════════════════════════════════════
        #  COLUMNA IZQUIERDA
        # ═══════════════════════════════════════════════════════

        # ── Identificación ────────────────────────────────────
        col_left.addWidget(_make_section_label("Identificación"))

        id_card = _card()
        id_card.setStyleSheet(f"""
            QFrame {{
                background: {PAL['surface']};
                border: 1.5px solid {PAL['blue_bg']};
                border-radius: 12px;
            }}
        """)
        id_grid = QGridLayout(id_card)
        id_grid.setSpacing(14)
        id_grid.setContentsMargins(14, 14, 14, 14)

        id_grid.addWidget(_make_field_label("Número Documento *"), 0, 0, 1, 2)
        self.fields["numero_documento"] = QLineEdit()
        self.fields["numero_documento"].setPlaceholderText("Ej: 94427466")
        self.fields["numero_documento"].setFixedHeight(42)
        self.fields["numero_documento"].setStyleSheet(_FIELD)
        id_grid.addWidget(self.fields["numero_documento"], 1, 0, 1, 2)

        id_grid.addWidget(_make_field_label("Tipo Documento"), 0, 2)
        self.fields["tipo_documento"] = QComboBox()
        self.fields["tipo_documento"].addItems(["CC", "CE", "TI", "PAS"])
        self.fields["tipo_documento"].setFixedHeight(42)
        self.fields["tipo_documento"].setStyleSheet(_COMBO)
        id_grid.addWidget(self.fields["tipo_documento"], 1, 2)

        id_grid.addWidget(_make_field_label("Tipo Renovación *"), 2, 0, 1, 2)
        self.fields["tipo_renovacion"] = QComboBox()
        self.fields["tipo_renovacion"].addItems(list(PRECIOS_RENOVACION.keys()))
        self.fields["tipo_renovacion"].setFixedHeight(42)
        self.fields["tipo_renovacion"].setStyleSheet(_COMBO)
        self.fields["tipo_renovacion"].currentTextChanged.connect(self._on_tipo_changed)
        id_grid.addWidget(self.fields["tipo_renovacion"], 3, 0, 1, 2)

        col_left.addWidget(id_card)

        # ── Datos Personales ──────────────────────────────────
        col_left.addWidget(_make_section_label("Datos Personales"))

        pers_card = _card()
        pers_card.setStyleSheet(f"""
            QFrame {{
                background: {PAL['surface']};
                border: 1.5px solid {PAL['border_lt']};
                border-radius: 12px;
            }}
        """)
        pers_grid = QGridLayout(pers_card)
        pers_grid.setHorizontalSpacing(14)
        pers_grid.setVerticalSpacing(10)
        pers_grid.setContentsMargins(14, 16, 14, 14)

        pers_grid.addWidget(_make_field_label("Nombres *"), 0, 0, 1, 2)
        self.fields["nombres"] = QLineEdit()
        self.fields["nombres"].setPlaceholderText("Ej: Carlos Arturo")
        self.fields["nombres"].setFixedHeight(42)
        self.fields["nombres"].setStyleSheet(_FIELD)
        pers_grid.addWidget(self.fields["nombres"], 1, 0, 1, 2)

        pers_grid.addWidget(_make_field_label("Apellidos *"), 0, 2, 1, 2)
        self.fields["apellidos"] = QLineEdit()
        self.fields["apellidos"].setPlaceholderText("Ej: Hoyos Patino")
        self.fields["apellidos"].setFixedHeight(42)
        self.fields["apellidos"].setStyleSheet(_FIELD)
        pers_grid.addWidget(self.fields["apellidos"], 1, 2, 1, 2)

        pers_grid.setColumnStretch(0, 1)
        pers_grid.setColumnStretch(1, 1)
        pers_grid.setColumnStretch(2, 1)
        pers_grid.setColumnStretch(3, 1)

        spacer_a = QFrame()
        spacer_a.setFixedHeight(8)
        spacer_a.setStyleSheet("background: transparent; border: none;")
        pers_grid.addWidget(spacer_a, 2, 0, 1, 4)

        pers_grid.addWidget(_make_field_label("Fecha Nacimiento"), 3, 0)
        self.fields["fecha_nacimiento"] = QDateEdit()
        self.fields["fecha_nacimiento"].setCalendarPopup(True)
        self.fields["fecha_nacimiento"].setDate(QDate.currentDate().addYears(-25))
        self.fields["fecha_nacimiento"].setDisplayFormat("dd/MM/yyyy")
        self.fields["fecha_nacimiento"].setFixedHeight(42)
        self.fields["fecha_nacimiento"].setStyleSheet(_DATE)
        pers_grid.addWidget(self.fields["fecha_nacimiento"], 4, 0)

        pers_grid.addWidget(_make_field_label("Celular"), 3, 1, 1, 3)
        self.fields["celular"] = QLineEdit()
        self.fields["celular"].setPlaceholderText("Ej: 3502199752")
        self.fields["celular"].setFixedHeight(42)
        self.fields["celular"].setStyleSheet(_FIELD)
        pers_grid.addWidget(self.fields["celular"], 4, 1, 1, 3)

        spacer_b = QFrame()
        spacer_b.setFixedHeight(8)
        spacer_b.setStyleSheet("background: transparent; border: none;")
        pers_grid.addWidget(spacer_b, 5, 0, 1, 4)

        pers_grid.addWidget(_make_field_label("Email"), 6, 0, 1, 4)
        self.fields["email"] = QLineEdit()
        self.fields["email"].setPlaceholderText("Ej: carlos@email.com")
        self.fields["email"].setFixedHeight(42)
        self.fields["email"].setStyleSheet(_FIELD)
        pers_grid.addWidget(self.fields["email"], 7, 0, 1, 4)

        col_left.addWidget(pers_card)

         # ── Responsable de Inscripción ────────────────────────
        col_left.addWidget(_make_section_label("Responsable de Inscripción"))

        resp_card = _card()
        resp_card.setStyleSheet(f"""
            QFrame {{
                background: {PAL['surface']};
                border: 1.5px solid {PAL['border_lt']};
                border-radius: 12px;
            }}
        """)
        resp_grid = QGridLayout(resp_card)
        resp_grid.setSpacing(8)
        resp_grid.setContentsMargins(14, 10, 14, 10)

        resp_grid.addWidget(_make_field_label("Tipo Documento"), 0, 0)
        self.fields["responsable_tipo_documento"] = QComboBox()
        self.fields["responsable_tipo_documento"].addItems(["CC", "CE", "TI", "PAS"])
        self.fields["responsable_tipo_documento"].setFixedHeight(38)
        self.fields["responsable_tipo_documento"].setStyleSheet(_COMBO)
        resp_grid.addWidget(self.fields["responsable_tipo_documento"], 1, 0)

        resp_grid.addWidget(_make_field_label("Número Documento"), 0, 1)
        self.fields["responsable_numero_documento"] = QLineEdit()
        self.fields["responsable_numero_documento"].setPlaceholderText("Ej: 94427466")
        self.fields["responsable_numero_documento"].setFixedHeight(38)
        self.fields["responsable_numero_documento"].setStyleSheet(_FIELD)
        resp_grid.addWidget(self.fields["responsable_numero_documento"], 1, 1)

        resp_grid.addWidget(_make_field_label("Nombres"), 2, 0)
        self.fields["responsable_nombres"] = QLineEdit()
        self.fields["responsable_nombres"].setPlaceholderText("Ej: María Elena")
        self.fields["responsable_nombres"].setFixedHeight(38)
        self.fields["responsable_nombres"].setStyleSheet(_FIELD)
        resp_grid.addWidget(self.fields["responsable_nombres"], 3, 0)

        resp_grid.addWidget(_make_field_label("Apellidos"), 2, 1)
        self.fields["responsable_apellidos"] = QLineEdit()
        self.fields["responsable_apellidos"].setPlaceholderText("Ej: Hoyos Patiño")
        self.fields["responsable_apellidos"].setFixedHeight(38)
        self.fields["responsable_apellidos"].setStyleSheet(_FIELD)
        resp_grid.addWidget(self.fields["responsable_apellidos"], 3, 1)

        resp_grid.addWidget(_make_field_label("Celular"), 4, 0)
        self.fields["responsable_celular"] = QLineEdit()
        self.fields["responsable_celular"].setPlaceholderText("Ej: 3502199752")
        self.fields["responsable_celular"].setFixedHeight(38)
        self.fields["responsable_celular"].setStyleSheet(_FIELD)
        resp_grid.addWidget(self.fields["responsable_celular"], 5, 0)

        resp_grid.addWidget(_make_field_label("Email"), 4, 1)
        self.fields["responsable_email"] = QLineEdit()
        self.fields["responsable_email"].setPlaceholderText("Ej: maria@email.com")
        self.fields["responsable_email"].setFixedHeight(38)
        self.fields["responsable_email"].setStyleSheet(_FIELD)
        resp_grid.addWidget(self.fields["responsable_email"], 5, 1)

        resp_grid.addWidget(_make_field_label("Relación con alumno"), 6, 0, 1, 2)
        self.fields["responsable_relacion"] = QComboBox()
        self.fields["responsable_relacion"].addItems([
            "Padre", "Madre", "Cónyuge", "Hermano/a", "Amigo/a",
            "Tutor legal", "Representante", "Otro"
        ])
        self.fields["responsable_relacion"].setFixedHeight(38)
        self.fields["responsable_relacion"].setStyleSheet(_COMBO)
        resp_grid.addWidget(self.fields["responsable_relacion"], 7, 0, 1, 2)

        col_left.addWidget(resp_card)

        # ── Valor del Curso ───────────────────────────────────
        col_left.addWidget(_make_section_label("Valor del Curso"))

        precio_card = _card()
        precio_card.setStyleSheet(f"""
            QFrame {{
                background: {PAL['surface']};
                border: 1.5px solid {PAL['border_lt']};
                border-radius: 12px;
            }}
        """)
        precio_grid = QGridLayout(precio_card)
        precio_grid.setHorizontalSpacing(20)
        precio_grid.setVerticalSpacing(10)
        precio_grid.setContentsMargins(14, 16, 14, 14)

        precio_grid.addWidget(_make_field_label("Precio base"), 0, 0)
        precio_grid.addWidget(_make_field_label("Descuento ($ pesos)"), 0, 1)
        precio_grid.addWidget(_make_field_label("% Descuento"), 0, 2)

        self.lbl_precio_base = QLabel(_fmt(list(PRECIOS_RENOVACION.values())[0]))
        self.lbl_precio_base.setStyleSheet(f"""
            font-size: 15px; font-weight: 700; color: {PAL['text_2']};
            background: {PAL['bg']}; border: 1.5px solid {PAL['border']};
            border-radius: 8px; padding: 10px 14px;
        """)
        precio_grid.addWidget(self.lbl_precio_base, 1, 0)

        self.field_desc_pesos = QLineEdit()
        self.field_desc_pesos.setPlaceholderText("Ej: 50000")
        self.field_desc_pesos.setStyleSheet(_FIELD)
        self.field_desc_pesos.textChanged.connect(self._on_desc_pesos)
        precio_grid.addWidget(self.field_desc_pesos, 1, 1)

        self.field_desc_pct = QLineEdit()
        self.field_desc_pct.setPlaceholderText("Ej: 10")
        self.field_desc_pct.setStyleSheet(_FIELD)
        self.field_desc_pct.textChanged.connect(self._on_desc_pct)
        precio_grid.addWidget(self.field_desc_pct, 1, 2)

        sep = _sep()
        precio_grid.addWidget(sep, 2, 0, 1, 3)

        precio_grid.addWidget(_make_field_label("Total a pagar *"), 3, 0)

        lbl_total_hint = QLabel("Puedes modificar el valor directamente")
        lbl_total_hint.setStyleSheet(f"font-size: 11px; color: {PAL['text_3']}; font-weight: 400;")
        precio_grid.addWidget(lbl_total_hint, 3, 1, 1, 2)

        self.field_total = QLineEdit()
        self.field_total.setPlaceholderText("0")
        self.field_total.setStyleSheet(f"""
            QLineEdit {{
                font-size: 18px; font-weight: 700; color: {PAL['blue']};
                border: 2px solid {PAL['blue']}; border-radius: 8px;
                padding: 10px 14px; background: {PAL['blue_bg']};
            }}
            QLineEdit:focus {{
                border: 2px solid {PAL['blue_dark']}; background: #FFFFFF;
            }}
        """)
        self.field_total.setFixedHeight(52)
        self.field_total.textChanged.connect(self._on_total_changed)
        precio_grid.addWidget(self.field_total, 4, 0, 1, 3)

        col_left.addWidget(precio_card)

        
       

        col_left.addStretch()

        # ═══════════════════════════════════════════════════════
        #  COLUMNA DERECHA
        # ═══════════════════════════════════════════════════════

        # ── Método de Pago ────────────────────────────────────
        col_right.addWidget(_make_section_label("Método de Pago"))

        pago_card = _card()
        pago_card.setStyleSheet(f"""
            QFrame {{
                background: {PAL['surface']};
                border: 1.5px solid {PAL['border_lt']};
                border-radius: 12px;
            }}
        """)
        pago_grid = QGridLayout(pago_card)
        pago_grid.setContentsMargins(14, 14, 14, 14)
        pago_grid.setSpacing(10)

        lbl_metodo = _make_field_label("Método:")
        lbl_metodo.setFixedHeight(16)
        pago_grid.addWidget(lbl_metodo, 0, 0)
        self.combo_metodo = QComboBox()
        self.combo_metodo.addItems(["Efectivo", "Transferencia", "Nequi", "Daviplata", "Sistecredit", "Otro"])
        self.combo_metodo.setFixedHeight(42)
        self.combo_metodo.setStyleSheet(_COMBO)
        self.combo_metodo.currentTextChanged.connect(self._toggle_calculadora)
        pago_grid.addWidget(self.combo_metodo, 1, 0)

        # Aviso recargo Sistecredit
        self.lbl_recargo = QLabel("⚡  Se agregan $50.000 por pago con Sistecredit")
        self.lbl_recargo.setStyleSheet(f"""
            font-size: 11px; font-weight: 600;
            color: {PAL['amber']}; background: {PAL['amber_bg']};
            border-radius: 6px; padding: 5px 10px;
        """)
        self.lbl_recargo.setVisible(False)
        pago_grid.addWidget(self.lbl_recargo, 2, 0, 1, 2)

        # Aviso recargo Sistecredit
        self.lbl_recargo = QLabel("⚡  Se agregan $50.000 por pago con Sistecredit")
        self.lbl_recargo.setStyleSheet(f"""
            font-size: 11px; font-weight: 600;
            color: {PAL['amber']}; background: {PAL['amber_bg']};
            border-radius: 6px; padding: 5px 10px;
        """)
        self.lbl_recargo.setVisible(False)
        pago_grid.addWidget(self.lbl_recargo, 2, 0, 1, 3)

        self.lbl_monto_campo = _make_field_label("Monto:")
        pago_grid.addWidget(self.lbl_monto_campo, 0, 1)
        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setMinimum(1_000); 
        self.spin_monto.setMaximum(10_000_000)
        self.spin_monto.setSingleStep(10_000); 
        self.spin_monto.setDecimals(0)
        self.spin_monto.setPrefix("$ "); self.spin_monto.setFixedHeight(42)
        self.spin_monto.setValue(list(PRECIOS_RENOVACION.values())[0])
        self.spin_monto.setStyleSheet(f"""
            QDoubleSpinBox {{
                border: 1.5px solid {PAL['border']}; border-radius: 8px;
                padding: 8px 12px; font-size: 14px; font-weight: 700;
                color: {PAL['blue']}; background: {PAL['blue_bg']};
            }}
            QDoubleSpinBox:focus {{ border: 1.5px solid {PAL['blue_dark']}; }}
        """)
        pago_grid.addWidget(self.spin_monto, 1, 1)

        notas_col = QVBoxLayout()
        notas_col.setSpacing(4)
        notas_col.setContentsMargins(0, 0, 0, 0)
        lbl_notas = _make_field_label("Notas:")
        lbl_notas.setFixedHeight(16)
        notas_col.addWidget(lbl_notas)
        self.obs_input = QTextEdit()
        self.obs_input.setPlaceholderText("Observaciones opcionales…")
        self.obs_input.setFixedHeight(55)
        self.obs_input.setStyleSheet(_TEXT)
        notas_col.addWidget(self.obs_input)
        notas_widget = QWidget()
        notas_widget.setStyleSheet("background: transparent;")
        notas_widget.setLayout(notas_col)
        pago_grid.addWidget(notas_widget, 0, 2, 2, 1)

        col_right.addWidget(pago_card)

        # ── Billetes y Monedas ────────────────────────────────
        col_right.addWidget(_make_section_label("Billetes y Monedas Recibidos"))

        calc_card = _card()
        calc_card.setStyleSheet(f"""
            QFrame {{
                background: {PAL['surface']};
                border: 1.5px solid {PAL['border_lt']};
                border-radius: 12px;
            }}
        """)
        calc_layout = QVBoxLayout(calc_card)
        calc_layout.setContentsMargins(14, 14, 14, 14)
        calc_layout.setSpacing(8)

        # Cabecera
        header_grid = QGridLayout()
        header_grid.setColumnStretch(0, 1)
        header_lbl1 = QLabel("Denominación")
        header_lbl1.setStyleSheet(f"font-size:10px; font-weight:700; color:{PAL['text_3']}; letter-spacing:0.08em;")
        header_lbl2 = QLabel("Cantidad")
        header_lbl2.setStyleSheet(f"font-size:10px; font-weight:700; color:{PAL['text_3']}; letter-spacing:0.08em;")
        header_lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        calc_layout.addLayout(header_grid)

        # Calculadora en 2 columnas
        calc_inner = QHBoxLayout()
        calc_inner.setSpacing(20)

        # Billetes
        billetes_col = QVBoxLayout()
        billetes_col.setSpacing(3)
        billetes_title = QLabel("Billetes")
        billetes_title.setStyleSheet(f"font-size:10px; font-weight:700; color:{PAL['text_3']}; letter-spacing:0.08em; text-transform:uppercase;")
        billetes_col.addWidget(billetes_title)

        self._spinners = []
        billetes_data = [
            (100_000, "💵 $100.000"), (50_000, "💵  $50.000"), (20_000, "💵  $20.000"),
            (10_000, "💵  $10.000"), (5_000, "💵   $5.000"), (2_000, "💵   $2.000"),
        ]

        for valor, etiqueta in billetes_data:
            row = QHBoxLayout()
            row.setSpacing(12)
            lbl = QLabel(etiqueta)
            lbl.setStyleSheet(f"font-size:13px; color:{PAL['text_1']}; font-weight:600; font-family:'Courier New',monospace;")
            row.addWidget(lbl)
            row.addStretch()
            spin = QSpinBox()
            spin.setMinimum(0); spin.setMaximum(999); spin.setValue(0)
            spin.setFixedWidth(72); spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin.setStyleSheet(f"""
                QSpinBox {{ border: 1.5px solid {PAL['border']}; border-radius: 6px;
                    background: {PAL['surface']}; color: {PAL['text_1']}; font-size: 13px; padding: 4px; }}
                QSpinBox:focus {{ border: 1.5px solid {PAL['blue']}; }}
            """)
            spin.valueChanged.connect(self._recalcular_billetes)
            row.addWidget(spin)
            billetes_col.addLayout(row)
            self._spinners.append((valor, spin))

        calc_inner.addLayout(billetes_col, stretch=1)

        # Monedas
        monedas_col = QVBoxLayout()
        monedas_col.setSpacing(3)
        monedas_title = QLabel("Monedas")
        monedas_title.setStyleSheet(f"font-size:10px; font-weight:700; color:{PAL['text_3']}; letter-spacing:0.08em; text-transform:uppercase;")
        monedas_col.addWidget(monedas_title)

        monedas_data = [
            (1_000, "🪙   $1.000"), (500, "🪙     $500"), (200, "🪙     $200"),
            (100, "🪙     $100"), (50, "🪙      $50"),
        ]

        for valor, etiqueta in monedas_data:
            row = QHBoxLayout()
            row.setSpacing(12)
            lbl = QLabel(etiqueta)
            lbl.setStyleSheet(f"font-size:13px; color:{PAL['text_1']}; font-weight:600; font-family:'Courier New',monospace;")
            row.addWidget(lbl)
            row.addStretch()
            spin = QSpinBox()
            spin.setMinimum(0); spin.setMaximum(999); spin.setValue(0)
            spin.setFixedWidth(72); spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin.setStyleSheet(f"""
                QSpinBox {{ border: 1.5px solid {PAL['border']}; border-radius: 6px;
                    background: {PAL['surface']}; color: {PAL['text_1']}; font-size: 13px; padding: 4px; }}
                QSpinBox:focus {{ border: 1.5px solid {PAL['blue']}; }}
            """)
            spin.valueChanged.connect(self._recalcular_billetes)
            row.addWidget(spin)
            monedas_col.addLayout(row)
            self._spinners.append((valor, spin))

        calc_inner.addLayout(monedas_col, stretch=1)
        calc_layout.addLayout(calc_inner)

        calc_layout.addWidget(_sep())

        # Totales
        tot_grid = QGridLayout()
        tot_grid.setSpacing(6)

        def _k(t):
            l = QLabel(t)
            l.setStyleSheet(f"font-size:12px; color:{PAL['text_2']}; font-weight:600;")
            return l

        def _v(t, c=PAL["text_1"]):
            l = QLabel(t)
            l.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            l.setStyleSheet(f"font-size:14px; font-weight:800; color:{c};")
            return l

        tot_grid.addWidget(_k("💵  Efectivo entregado:"), 0, 0)
        self.lbl_entregado = _v("$0")
        tot_grid.addWidget(self.lbl_entregado, 0, 1)

        tot_grid.addWidget(_k("📋  A registrar:"), 1, 0)
        self.lbl_a_registrar = _v("$0", PAL["blue"])
        tot_grid.addWidget(self.lbl_a_registrar, 1, 1)

        calc_layout.addLayout(tot_grid)

        cambio_frame = QFrame()
        cambio_frame.setStyleSheet(f"QFrame {{ background: {PAL['teal_bg']}; border: 1.5px solid #86EFAC; border-radius: 8px; }}")
        cambio_lay = QHBoxLayout(cambio_frame)
        cambio_lay.setContentsMargins(12, 8, 12, 8)

        lk = QLabel("🔄  Cambio a devolver:")
        lk.setStyleSheet(f"font-size:13px; font-weight:700; color:{PAL['teal']};")
        self.lbl_cambio = QLabel("$0")
        self.lbl_cambio.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_cambio.setStyleSheet(f"font-size:20px; font-weight:800; color:{PAL['teal']};")

        cambio_lay.addWidget(lk)
        cambio_lay.addStretch()
        cambio_lay.addWidget(self.lbl_cambio)

        calc_layout.addWidget(cambio_frame)

        col_right.addWidget(calc_card)
        # GUARDAR REFERENCIA para _toggle_calculadora
        self.calc_card = calc_card
        col_right.addStretch()

        # ═══════════════════════════════════════════════════════
        #  ENSAMBLAR
        # ═══════════════════════════════════════════════════════
        cols.addLayout(col_left, stretch=1)
        cols.addLayout(col_right, stretch=1)
        body_lay.addLayout(cols)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        

        # ═══════════════════════════════════════════════════════
        #  FOOTER
        # ═══════════════════════════════════════════════════════
        footer = QFrame()
        footer.setStyleSheet(f"QFrame {{ background: {PAL['surface']}; border-top: 1.5px solid {PAL['border_lt']}; }}")
        footer.setFixedHeight(60)
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(28, 0, 28, 0)
        f_lay.setSpacing(12)

        req = QLabel("* Campos obligatorios")
        req.setStyleSheet(f"font-size:11px; color:{PAL['text_3']};")
        f_lay.addWidget(req)

        f_lay.addStretch()

        self.lbl_alerta = QLabel("")
        self.lbl_alerta.setStyleSheet(f"font-size:12px; color:{PAL['coral']}; font-weight:600;")
        f_lay.addWidget(self.lbl_alerta)

        btn_cancelar = _btn_secondary("Cancelar")
        btn_cancelar.setFixedHeight(42)
        btn_cancelar.clicked.connect(self.reject)
        f_lay.addWidget(btn_cancelar)

        self.btn_guardar = _btn_primary("✓   Registrar y Cobrar")
        self.btn_guardar.setFixedHeight(42)
        self.btn_guardar.setMinimumWidth(200)
        self.btn_guardar.clicked.connect(self._validar)
        f_lay.addWidget(self.btn_guardar)

        root.addWidget(footer)

        # Inicializar
        self._precio_base = list(PRECIOS_RENOVACION.values())[0]
        self._bloq = False
        self._toggle_calculadora(self.combo_metodo.currentText())
        self._on_tipo_changed(self.fields["tipo_renovacion"].currentText())

    # ══════════════════════════════════════════════════════════════════════════
    #  MÉTODOS DE LÓGICA
    # ══════════════════════════════════════════════════════════════════════════

    def _on_tipo_changed(self, tipo: str):
        precio = PRECIOS_RENOVACION.get(tipo, 0)
        recargo = 50_000 if self.combo_metodo.currentText() == "Sistecredit" else 0
        self._precio_base = precio + recargo
        self.lbl_precio_base.setText(_fmt(self._precio_base))
        self._bloq = True
        self.field_desc_pesos.clear()
        self.field_desc_pct.clear()
        self._bloq = False
        self._recalcular_precio()

    def _on_desc_pesos(self, texto: str):
        if self._bloq: return
        self._bloq = True
        try:
            val = int(texto.replace(".", "").replace(",", "").strip() or "0")
            if self._precio_base > 0:
                pct = round((val / self._precio_base) * 100, 2)
                self.field_desc_pct.setText(str(pct) if pct > 0 else "")
        except ValueError:
            self.field_desc_pct.clear()
        finally:
            self._bloq = False
        self._recalcular_precio()

    def _on_desc_pct(self, texto: str):
        if self._bloq: return
        self._bloq = True
        try:
            pct = float(texto.replace(",", ".").strip() or "0")
            pesos = int(self._precio_base * pct / 100)
            self.field_desc_pesos.setText(str(pesos) if pesos > 0 else "")
        except ValueError:
            self.field_desc_pesos.clear()
        finally:
            self._bloq = False
        self._recalcular_precio()

    def _on_total_changed(self, texto: str):
        if self._bloq: return
        self._bloq = True
        try:
            total = int(texto.replace(".", "").replace(",", "").replace("$", "").strip() or "0")
            descuento = self._precio_base - total
            if descuento > 0:
                self.field_desc_pesos.setText(str(descuento))
                if self._precio_base > 0:
                    pct = round((descuento / self._precio_base) * 100, 2)
                    self.field_desc_pct.setText(str(pct))
            else:
                self.field_desc_pesos.clear()
                self.field_desc_pct.clear()
        except ValueError:
            pass
        finally:
            self._bloq = False

    def _recalcular_precio(self):
        try:
            desc = int(self.field_desc_pesos.text().replace(".", "").replace(",", "").strip() or "0")
        except ValueError:
            desc = 0
        total = max(self._precio_base - desc, 0)
        self._bloq = True
        self.field_total.setText(str(total))
        self._bloq = False
        self.spin_monto.setValue(total)
        self._actualizar_cambio()

    def _toggle_calculadora(self, metodo: str):
        es_efectivo = metodo == "Efectivo"
        es_sistecredit = metodo == "Sistecredit"
        self.calc_card.setVisible(es_efectivo)
        self.spin_monto.setVisible(not es_efectivo)
        self.lbl_monto_campo.setVisible(not es_efectivo)
        self.lbl_recargo.setVisible(es_sistecredit)
        if not es_efectivo:
            for _, spin in self._spinners:
                spin.setValue(0)
            self.lbl_alerta.setText("")
        # Recalcular precio con/sin recargo Sistecredit
        tipo_actual = self.fields["tipo_renovacion"].currentText()
        precio_sin_recargo = PRECIOS_RENOVACION.get(tipo_actual, 0)
        recargo = 50_000 if es_sistecredit else 0
        self._precio_base = precio_sin_recargo + recargo
        self.lbl_precio_base.setText(_fmt(self._precio_base))
        self._recalcular_precio()
        self._actualizar_cambio()

    def _recalcular_billetes(self):
        total = sum(v * s.value() for v, s in self._spinners)
        self.lbl_entregado.setText(f"${total:,.0f}".replace(",", "."))
        self._actualizar_cambio()

    def _actualizar_cambio(self):
        try:
            total = int(self.field_total.text().replace(".", "").replace(",", "").strip() or "0")
        except ValueError:
            total = 0
        entregado = sum(v * s.value() for v, s in self._spinners)
        abono = min(entregado, total)
        cambio = entregado - abono

        self.lbl_a_registrar.setText(f"${abono:,.0f}".replace(",", "."))

        if cambio < 0:
            # Abono parcial: mostrar saldo pendiente (informativo, no bloqueante)
            self.lbl_cambio.setText(f"${abs(cambio):,.0f}".replace(",", "."))
            self.lbl_cambio.setStyleSheet(f"font-size:20px; font-weight:800; color:{PAL['amber']};")
            self.lbl_alerta.setText(f"💳 Saldo pendiente: ${abs(cambio):,.0f}".replace(",", "."))
        else:
            self.lbl_cambio.setText(f"${cambio:,.0f}".replace(",", "."))
            self.lbl_cambio.setStyleSheet(f"font-size:20px; font-weight:800; color:{PAL['teal']};")
            self.lbl_alerta.setText("")
            
    def _validar(self):
        faltantes = []
        if not self.fields["numero_documento"].text().strip():
            faltantes.append("Número de Documento")
        if not self.fields["nombres"].text().strip():
            faltantes.append("Nombres")
        if not self.fields["apellidos"].text().strip():
            faltantes.append("Apellidos")

        try:
            total = int(self.field_total.text().replace(".", "").replace(",", "").strip() or "0")
        except ValueError:
            total = 0
        if total <= 0:
            faltantes.append("Total a pagar (debe ser mayor a $0)")

        if faltantes:
            QMessageBox.warning(self, "Campos requeridos",
                                "Por favor complete:\n\n• " + "\n• ".join(faltantes))
            return

        if self.combo_metodo.currentText() == "Efectivo":
            entregado = sum(v * s.value() for v, s in self._spinners)
            if entregado == 0:
                resp = QMessageBox.question(
                    self, "Sin abono",
                    "No se han ingresado billetes. ¿Deseas inscribir al alumno sin registrar abono?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if resp == QMessageBox.StandardButton.No:
                    return

        self.accept()

    @property
    def numero_documento(self) -> str:
        return self.fields["numero_documento"].text().strip()

    @property
    def tipo_documento(self) -> str:
        return self.fields["tipo_documento"].currentText()

    @property
    def nombres(self) -> str:
        return self.fields["nombres"].text().strip()

    @property
    def apellidos(self) -> str:
        return self.fields["apellidos"].text().strip()

    @property
    def fecha_nacimiento(self) -> str:
        return self.fields["fecha_nacimiento"].date().toString("yyyy-MM-dd")

    @property
    def celular(self) -> str:
        return self.fields["celular"].text().strip()

    @property
    def email(self) -> str:
        return self.fields["email"].text().strip()

    @property
    def tipo_renovacion(self) -> str:
        return self.fields["tipo_renovacion"].currentText()

    @property
    def precio_total(self) -> int:
        try:
            return int(self.field_total.text().replace(".", "").replace(",", "").strip() or "0")
        except ValueError:
            return 0

    @property
    def valor(self) -> float:
        if self.combo_metodo.currentText() == "Efectivo":
            return min(sum(v * s.value() for v, s in self._spinners), self.precio_total)
        return self.spin_monto.value()

    @property
    def metodo(self) -> str:
        return self.combo_metodo.currentText()

    @property
    def observaciones(self) -> str:
        return self.obs_input.toPlainText().strip()

    @property
    def desglose(self) -> list:
        result = []
        for valor, spin in self._spinners:
            if spin.value() > 0:
                tipo = "billete" if valor >= 1000 else "moneda"
                result.append({"denominacion": valor, "cantidad": spin.value(), "tipo": tipo})
        return result
# ══════════════════════════════════════════════════════════════════════════════
#  VISTA PRINCIPAL — RenovacionesView
# ══════════════════════════════════════════════════════════════════════════════

class RenovacionesView(QWidget):

    def __init__(self, usuario_id: int = 1, parent=None):
        super().__init__(parent)
        self.usuario_id = usuario_id
        self._alumno_sel: dict | None = None
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._ejecutar_busqueda)
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {PAL['bg']};")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # ── Cabecera ──────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(88)
        header.setStyleSheet(f"background: {PAL['blue']};")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(32, 0, 0, 0); h_lay.setSpacing(0)

        col = QVBoxLayout(); col.setSpacing(3)
        lbl_t = QLabel("🔄  Renovaciones")
        lbl_t.setStyleSheet("font-size:22px; font-weight:800; color:#FFFFFF;")
        lbl_s = QLabel("Registra renovaciones de licencia — sin clases")
        lbl_s.setStyleSheet("font-size:12px; color:rgba(255,255,255,0.65);")
        col.addWidget(lbl_t); col.addWidget(lbl_s)
        h_lay.addLayout(col); h_lay.addStretch()

        red = QWidget(); red.setFixedSize(48, 88)
        red.setStyleSheet(f"background: {PAL['coral']}; border: none;")
        h_lay.addWidget(red)
        root.addWidget(header)

        # ── Barra búsqueda + botón externo ───────────────────────────────────
        search_bar = QWidget()
        search_bar.setStyleSheet(
            f"background: {PAL['surface']}; border-bottom: 1.5px solid {PAL['border_lt']};"
        )
        search_bar.setFixedHeight(64)
        s_lay = QHBoxLayout(search_bar)
        s_lay.setContentsMargins(32, 0, 32, 0); s_lay.setSpacing(12)

        lbl_ico = QLabel("🔍")
        lbl_ico.setStyleSheet("font-size:18px; background:transparent;")
        s_lay.addWidget(lbl_ico)

        self.inp_busqueda = QLineEdit()
        self.inp_busqueda.setPlaceholderText("Buscar alumno existente por nombre o documento…")
        self.inp_busqueda.setFixedHeight(40)
        self.inp_busqueda.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {PAL['border']}; border-radius: 9px;
                padding: 8px 14px; font-size: 14px;
                color: {PAL['text_1']}; background: {PAL['bg']};
            }}
            QLineEdit:focus {{ border: 1.5px solid {PAL['blue']}; background: #FFFFFF; }}
        """)
        self.inp_busqueda.textChanged.connect(lambda t: self._timer.start(300))
        s_lay.addWidget(self.inp_busqueda)

        btn_externo = QPushButton("➕  Alumno externo")
        btn_externo.setFixedHeight(40)
        btn_externo.setStyleSheet(f"""
            QPushButton {{
                background: {PAL['teal_bg']}; color: {PAL['teal']};
                border: 1.5px solid {PAL['teal']}; border-radius: 9px;
                font-size: 13px; font-weight: 700; padding: 0 18px;
            }}
            QPushButton:hover {{ background: {PAL['teal']}; color: #FFFFFF; }}
        """)
        btn_externo.setToolTip("Registrar renovación de una persona que nunca ha estudiado aquí")
        btn_externo.clicked.connect(self._abrir_externo)
        s_lay.addWidget(btn_externo)
        root.addWidget(search_bar)

        # ── Cuerpo ────────────────────────────────────────────────────────────
        body = QWidget(); body.setStyleSheet(f"background: {PAL['bg']};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(32, 24, 32, 24); body_lay.setSpacing(16)

        # Lista resultados búsqueda
        self.lista = QListWidget()
        self.lista.setMaximumHeight(220)
        self.lista.setStyleSheet(f"""
            QListWidget {{
                background: {PAL['surface']}; border: 1.5px solid {PAL['border_lt']};
                border-radius: 10px; outline: none;
                font-size: 13px; color: {PAL['text_1']};
            }}
            QListWidget::item {{ padding: 10px 16px; border-bottom: 1px solid {PAL['border_lt']}; }}
            QListWidget::item:hover {{ background: {PAL['blue_bg']}; }}
            QListWidget::item:selected {{
                background: {PAL['blue_bg']}; color: {PAL['blue']}; font-weight:600;
            }}
        """)
        self.lista.itemClicked.connect(self._on_alumno_seleccionado)
        self.lista.hide()
        body_lay.addWidget(self.lista)

        # Tarjeta alumno seleccionado
        self.tarjeta = QFrame()
        self.tarjeta.hide()
        self.tarjeta.setStyleSheet(
            f"QFrame {{ background: {PAL['blue']}; border-radius: 14px; }}"
            f" QLabel {{ background: transparent; }}"
        )
        _shadow(self.tarjeta, blur=20, oy=6, alpha=0.12)
        tarjeta_lay = QHBoxLayout(self.tarjeta)
        tarjeta_lay.setContentsMargins(24, 20, 24, 20); tarjeta_lay.setSpacing(20)

        self.lbl_avatar = QLabel("👤")
        self.lbl_avatar.setFixedSize(56, 56)
        self.lbl_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_avatar.setStyleSheet(
            "background: rgba(255,255,255,0.2); border-radius: 28px; font-size:24px;"
        )
        tarjeta_lay.addWidget(self.lbl_avatar)

        info_col = QVBoxLayout(); info_col.setSpacing(3)
        self.lbl_nombre = QLabel("—")
        self.lbl_nombre.setStyleSheet("font-size:18px; font-weight:800; color:#FFFFFF;")
        self.lbl_doc2 = QLabel("")
        self.lbl_doc2.setStyleSheet("font-size:12px; color:rgba(255,255,255,0.70); font-weight:600;")
        self.lbl_cat = QLabel("")
        self.lbl_cat.setStyleSheet("font-size:11px; color:rgba(255,255,255,0.55);")
        info_col.addWidget(self.lbl_nombre)
        info_col.addWidget(self.lbl_doc2)
        info_col.addWidget(self.lbl_cat)
        tarjeta_lay.addLayout(info_col); tarjeta_lay.addStretch()

        self.lbl_estado_badge = QLabel("")
        self.lbl_estado_badge.setStyleSheet(f"""
            font-size:11px; font-weight:700; padding: 5px 14px;
            border-radius: 20px; background: rgba(255,255,255,0.15); color: #FFFFFF;
        """)
        tarjeta_lay.addWidget(self.lbl_estado_badge)
        body_lay.addWidget(self.tarjeta)

        # Botón renovar
        self.btn_renovar = QPushButton("🔄   Registrar Renovación")
        self.btn_renovar.setFixedHeight(52)
        self.btn_renovar.hide()
        self.btn_renovar.setStyleSheet(f"""
            QPushButton {{
                background: {PAL['blue']}; color: #FFFFFF; border: none;
                border-radius: 12px; font-size:15px; font-weight:700;
            }}
            QPushButton:hover {{ background: {PAL['blue_dark']}; }}
        """)
        self.btn_renovar.clicked.connect(self._abrir_dialogo_renovacion)
        body_lay.addWidget(self.btn_renovar)

        # Historial
        self.frame_historial = QFrame()
        self.frame_historial.hide()
        self.frame_historial.setStyleSheet(f"""
            QFrame {{
                background: {PAL['surface']};
                border: 1.5px solid {PAL['border_lt']};
                border-top: 3px solid {PAL['teal']};
                border-radius: 12px;
            }}
        """)
        _shadow(self.frame_historial)
        hist_lay = QVBoxLayout(self.frame_historial)
        hist_lay.setContentsMargins(20, 16, 20, 16); hist_lay.setSpacing(8)
        lbl_ht = QLabel("Historial de Pagos")
        lbl_ht.setStyleSheet(f"font-size:13px; font-weight:700; color:{PAL['text_1']};")
        hist_lay.addWidget(lbl_ht); hist_lay.addWidget(_sep())
        self.lista_historial = QListWidget()
        self.lista_historial.setMaximumHeight(160)
        self.lista_historial.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.lista_historial.setStyleSheet(f"""
            QListWidget {{ background: transparent; border: none; outline: none;
                font-size: 12px; color: {PAL['text_2']}; }}
            QListWidget::item {{ padding: 6px 0px; }}
        """)
        hist_lay.addWidget(self.lista_historial)
        body_lay.addWidget(self.frame_historial)

        # Estado vacío
        self.lbl_vacio = QLabel(
            "Busca un alumno existente o usa  ➕ Alumno externo  para renovar"
        )
        self.lbl_vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_vacio.setStyleSheet(
            f"font-size:14px; color:{PAL['text_3']}; font-weight:500; padding:60px 0;"
        )
        body_lay.addWidget(self.lbl_vacio)
        body_lay.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {PAL['bg']}; border: none;")
        scroll.setWidget(body)
        root.addWidget(scroll)

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _ejecutar_busqueda(self):
        texto = self.inp_busqueda.text().strip()
        self.lista.clear()
        self._alumno_sel = None
        self.tarjeta.hide(); self.btn_renovar.hide(); self.frame_historial.hide()
        self.lbl_vacio.show()

        if len(texto) < 2:
            self.lista.hide(); return

        try:
            resultados = _buscar_alumnos(texto)
        except Exception as e:
            QMessageBox.critical(self, "Error de conexión", str(e)); return

        if not resultados:
            self.lista.hide()
            self.lbl_vacio.setText("No se encontraron alumnos"); return

        self.lbl_vacio.hide()
        for r in resultados:
            item = QListWidgetItem(
                f"  {r['nombres']} {r['apellidos']}   ·   CC {r['numero_documento']}"
                f"   ·   {r['categoria']}   [{r['estado']}]"
            )
            item.setData(Qt.ItemDataRole.UserRole, r)
            self.lista.addItem(item)
        self.lista.show()

    def _on_alumno_seleccionado(self, item: QListWidgetItem):
        alumno = item.data(Qt.ItemDataRole.UserRole)
        self._alumno_sel = alumno
        self.lista.hide()
        self.lbl_nombre.setText(f"{alumno['nombres']} {alumno['apellidos']}")
        self.lbl_doc2.setText(f"C.C. {alumno['numero_documento']}")
        self.lbl_cat.setText(f"Categoría: {alumno['categoria']}")
        self.lbl_estado_badge.setText(alumno['estado'])
        self.tarjeta.show(); self.btn_renovar.show()
        self._cargar_historial(alumno['matricula_id'])
        self.lbl_vacio.hide()

    def _cargar_historial(self, matricula_id: int):
        self.lista_historial.clear()
        try:
            db = Database.get_instance()
            pagos = db.fetchall("""
                SELECT numero_recibo, concepto, valor, metodo_pago, fecha_pago
                FROM pagos WHERE id_matricula = %s
                ORDER BY fecha_pago DESC LIMIT 10
            """, (matricula_id,))
        except Exception:
            pagos = []
        # ... el resto del método queda igual (el for que recorre `pagos`)

    def _abrir_dialogo_renovacion(self):
        if not self._alumno_sel: return
        dlg = DialogoRenovacion(alumno=self._alumno_sel, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._confirmar_pago(
                alumno_id = self._alumno_sel['matricula_id'],
                tipo_renovacion = dlg.tipo_renovacion,
                valor           = dlg.valor,
                metodo          = dlg.metodo,
                observaciones   = dlg.observaciones,
                desglose        = dlg.desglose,
                nombre          = f"{self._alumno_sel['nombres']} {self._alumno_sel['apellidos']}",
                reload_id       = self._alumno_sel['matricula_id'],
            )

    def _abrir_externo(self):
        
        dlg = DialogoAlumnoExterno(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                alumno_id = _registrar_alumno_externo(
                    numero_documento = dlg.numero_documento,
                    tipo_documento   = dlg.tipo_documento,
                    nombres          = dlg.nombres,
                    apellidos        = dlg.apellidos,
                    fecha_nacimiento = dlg.fecha_nacimiento,
                    celular          = dlg.celular,
                    precio_total     = dlg.precio_total,
                    tipo_renovacion = dlg.tipo_renovacion,
                    email            = dlg.email,
                    responsable_tipo_documento    = dlg.fields.get("responsable_tipo_documento", QComboBox()).currentText() or None,
                    responsable_numero_documento  = dlg.fields.get("responsable_numero_documento", QLineEdit()).text().strip() or None,
                    responsable_nombres           = dlg.fields.get("responsable_nombres", QLineEdit()).text().strip() or None,
                    responsable_apellidos         = dlg.fields.get("responsable_apellidos", QLineEdit()).text().strip() or None,
                    responsable_celular           = dlg.fields.get("responsable_celular", QLineEdit()).text().strip() or None,
                    responsable_email             = dlg.fields.get("responsable_email", QLineEdit()).text().strip() or None,
                    responsable_relacion          = dlg.fields.get("responsable_relacion", QComboBox()).currentText() or None,
                )
            except Exception as e:
                QMessageBox.critical(self, "Error al registrar alumno", str(e)); return

            self._confirmar_pago(
                alumno_id       = alumno_id,
                tipo_renovacion = dlg.tipo_renovacion,
                valor           = dlg.valor,
                metodo          = dlg.metodo,
                observaciones   = dlg.observaciones,
                desglose        = dlg.desglose,
                nombre          = f"{dlg.nombres} {dlg.apellidos}",
                reload_id       = None,
            )

    def _confirmar_pago(self, alumno_id: int, tipo_renovacion: str, valor: float,
                        metodo: str, observaciones: str, desglose: list,
                        nombre: str, reload_id: int | None):
        try:
            recibo = _registrar_pago(
                matricula_id    = alumno_id,
                tipo_renovacion = tipo_renovacion,
                valor           = valor,
                metodo          = metodo,
                observaciones   = observaciones,
                usuario_id      = self.usuario_id,
                desglose        = desglose if metodo == "Efectivo" else None,
            )
            msg = QMessageBox(self)
            msg.setWindowTitle("✅ Renovación registrada")
            msg.setText(
                f"<b>Renovación registrada exitosamente</b><br><br>"
                f"Alumno: <b>{nombre}</b><br>"
                f"Tipo: <b>{tipo_renovacion}</b><br>"
                f"Valor cobrado: <b>$ {int(valor):,}</b><br>"
                f"Recibo: <b>{recibo}</b>"
            )
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setStyleSheet(f"background-color: {PAL['surface']};")
            msg.exec()
            if reload_id:
                self._cargar_historial(reload_id)
        except Exception as e:
            QMessageBox.critical(self, "Error al registrar pago", str(e))