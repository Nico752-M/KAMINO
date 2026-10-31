#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vista de Gestión de Alumnos - CEA PRACTICAR
Estilo PRACTICAR: fondo crema, tarjetas blancas, colores del logo
"""

import os
os.environ["QT_QPA_PLATFORM"] = "windows:darkmode=0"

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QDialog, QFormLayout, QComboBox, QDateEdit,
    QScrollArea, QFrame, QGridLayout, QFileDialog, QSizePolicy,
    QGraphicsDropShadowEffect, QMenu, QApplication
)
from PyQt6.QtCore import Qt, QDate, QPropertyAnimation, QEasingCurve, QRect, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor, QFont, QPalette, QIcon

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database import Database


# ─── Paleta global PRACTICAR ───────────────────────────────────────────────────
PAL = {
    "bg":         "#EEF2FB",
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
}

# ─── Precios por categoría/licencia ───────────────────────────────────────────
def _cargar_precios() -> dict:
    import json
    _ruta = os.path.join(os.path.dirname(__file__), '..', 'precios.json')
    try:
        with open(_ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {
            "A2": 1_065_000, "B1": 1_250_000, "C1": 1_380_000,
            "C2": 1_800_000, "A2 + B1": 2_250_000,
            "A2 + C1": 2_350_000, "C2 + A2": 2_860_000,
        }

PRECIOS_LICENCIA = _cargar_precios()

# Las categorías de Renovación tienen su propio flujo (ver renovaciones_view.py)
# y no deben aparecer como "Categoría / Licencia" al registrar un alumno nuevo.
_CATEGORIAS_RENOVACION = {"Renovación", "Renovación x2"}
CATEGORIAS = [c for c in PRECIOS_LICENCIA.keys() if c not in _CATEGORIAS_RENOVACION]

CATEGORIAS = list(PRECIOS_LICENCIA.keys())

# Recargo automático cuando el método de pago es Sistecredit
RECARGO_SISTECREDITO = 50_000

# ─── Stylesheet global ─────────────────────────────────────────────────────────
GLOBAL_QSS = f"""
        QWidget {{
            QMessageBox QPushButton {{
            color: {PAL['text_1']};
        }}
        QDialog QPushButton {{
            color: {PAL['text_1']};
        }}
    }}
    QLabel {{
        background: transparent;
    }}
    QLineEdit {{
        padding: 10px 14px;
        font-size: 13px;
        border: 1.5px solid {PAL['border']};
        border-radius: 8px;
        background-color: {PAL['surface']};
        color: {PAL['text_1']};
    }}
    QLineEdit:focus {{
        border: 1.5px solid {PAL['blue']};
        background-color: #FFFFFF;
    }}
    QLineEdit:disabled {{
        background-color: {PAL['bg']};
        color: {PAL['text_3']};
    }}
    QComboBox {{
        padding: 10px 14px;
        font-size: 13px;
        border: 1.5px solid {PAL['border']};
        border-bottom: 1.5px solid {PAL['border']};
        border-radius: 8px;
        background-color: {PAL['surface']};
        color: {PAL['text_1']};
    }}
    QComboBox:focus {{
        border: 1.5px solid {PAL['blue']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 28px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {PAL['text_2']};
        margin-right: 10px;
    }}
    QComboBox QAbstractItemView {{
        border: 1.5px solid {PAL['border']};
        border-radius: 8px;
        background: {PAL['surface']};
        selection-background-color: {PAL['blue_bg']};
        selection-color: {PAL['blue']};
        padding: 4px;
    }}
    
    
    QDateEdit {{
        padding: 10px 14px;
        font-size: 13px;
        border: 1.5px solid {PAL['border']};
        border-bottom: 1.5px solid {PAL['border']};
        border-radius: 8px;
        background-color: {PAL['surface']};
        color: {PAL['text_1']};
        min-width: 140px;
        min-height: 42px;
    }}

    QDateEdit:focus {{
        border: 1.5px solid {PAL['blue']};
    }}
    QDateEdit::drop-down {{
        border: none;
        width: 28px;
    }}
    QDateEdit::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {PAL['text_2']};
        margin-right: 10px;
    }}


    QCalendarWidget QAbstractItemView:enabled {{
        background-color: #FFFFFF;
        color: {PAL['text_1']};
        selection-background-color: #0033A0;
        selection-color: #FFFFFF;
        font-size: 13px;
    }}
    QCalendarWidget QAbstractItemView:disabled {{
        color: {PAL['text_3']};
    }}
    QCalendarWidget QSpinBox {{
        min-width: 80px;
        max-width: 80px;
        font-size: 13px;
        color: {PAL['text_1']};
        background: #FFFFFF;
        border: 1px solid {PAL['border']};
        border-radius: 4px;
        padding: 2px 4px;
    }}
    QCalendarWidget QToolButton {{
        min-width: 24px;
        min-height: 24px;
        font-size: 13px;
        color: {PAL['text_1']};
    }}
    QScrollBar:vertical {{
        width: 6px;
        background: transparent;
        border-radius: 3px;
    }}
    QScrollBar::handle:vertical {{
        background: {PAL['border']};
        border-radius: 3px;
        min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        height: 6px;
        background: transparent;
    }}
    QScrollBar::handle:horizontal {{
        background: {PAL['border']};
        border-radius: 3px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QTableWidget {{
        background-color: {PAL['surface']};
        border-radius: 12px;
        border: 1.5px solid {PAL['border_lt']};
        gridline-color: {PAL['border_lt']};
        outline: none;
    }}
    QTableWidget::item {{
        padding: 0px 14px;
        border-bottom: 1px solid {PAL['border_lt']};
        color: {PAL['text_1']};
    }}
    QTableWidget::item:hover {{
        background-color: #f3f4fb;
    }}
    QTableWidget::item:selected {{
        background-color: {PAL['blue_bg']};
        color: {PAL['blue']};
    }}
    QHeaderView::section {{
        background-color: {PAL['blue']};
        padding: 13px 14px;
        border: none;
        border-right: 1px solid rgba(255,255,255,0.08);
        font-weight: 600;
        font-size: 11px;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: rgba(255,255,255,0.80);
    }}
    QHeaderView::section:first {{
        border-top-left-radius: 10px;
    }}
    QHeaderView::section:last {{
        border-top-right-radius: 10px;
        border-right: none;
    }}
    QMessageBox {{
        background-color: {PAL['surface']};
    }}
"""


def make_btn_primary(text, icon_char=""):
    btn = QPushButton(f"{icon_char}  {text}".strip() if icon_char else text)
    btn.setStyleSheet(f"""
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
        QPushButton:hover {{
            background-color: {PAL['blue_dark']};
        }}
        QPushButton:pressed {{
            background-color: #001E60;
        }}
    """)
    return btn


def make_btn_secondary(text):
    btn = QPushButton(text)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {PAL['bg']};
            color: {PAL['text_1']};
            border: 1.5px solid {PAL['border']};
            border-radius: 9px;
            padding: 11px 22px;
            font-size: 13px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {PAL['border_lt']};
            border-color: {PAL['border']};
        }}
        QPushButton:pressed {{
            background-color: {PAL['border']};
        }}
    """)
    return btn


def make_section_label(text):
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 16, 0, 6)
    row.setSpacing(10)

    accent = QWidget()
    accent.setFixedSize(3, 16)
    accent.setStyleSheet(f"background-color: {PAL['blue']}; border-radius: 2px; border: none;")
    row.addWidget(accent, 0, Qt.AlignmentFlag.AlignVCenter)

    lbl = QLabel(text.upper())
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
    line.setStyleSheet(f"background-color: {PAL['border_lt']}; border: none; max-height: 1px;")
    row.addWidget(line)

    return container

def _make_section_header(icono: str, texto: str) -> QWidget:
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 12, 0, 6)
    row.setSpacing(8)

    lbl_icon = QLabel(icono)
    lbl_icon.setStyleSheet("font-size: 16px; background: transparent;")
    row.addWidget(lbl_icon)

    lbl_text = QLabel(texto.upper())
    lbl_text.setStyleSheet("""
        font-size: 11px; font-weight: 700;
        letter-spacing: 0.10em; color: #002D6B;
        background: transparent;
    """)
    row.addWidget(lbl_text)

    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("background: #D0D5DD; border: none; max-height: 1px;")
    row.addWidget(line, 1)

    return container

def make_field_label(text):
    lbl = QLabel(text)
    lbl.setStyleSheet(f"""
        font-size: 11px;
        font-weight: 600;
        color: {PAL['text_3']};
        background: transparent;
        padding-bottom: 1px;
    """)
    return lbl


def add_shadow(widget, blur=16, offset_y=4, opacity=0.08):
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, offset_y)
    shadow.setColor(QColor(26, 25, 22, int(opacity * 255)))
    widget.setGraphicsEffect(shadow)


def fmt_cop(valor: int) -> str:
    """Formatea un entero como precio COP: $ 1.065.000"""
    return f"$ {valor:,.0f}".replace(",", ".")


# ══════════════════════════════════════════════════════════════════════════════
#  DIÁLOGO: NUEVO / EDITAR ALUMNO
# ══════════════════════════════════════════════════════════════════════════════

class AlumnoDialog(QDialog):
    """Diálogo para crear/editar alumno — con precio por licencia y descuento."""

    def __init__(self, alumno_id=None, parent=None):
        
        super().__init__(parent)
        self.alumno_id = alumno_id
        self.foto_path = None
        self._precio_base = 0          # precio según categoría seleccionada
        self._recargo_sistecredito = 0  # $50.000 si paga con Sistecredit
        self._bloqueando_signals = False

        self.setWindowTitle("Nuevo Alumno" if not self.alumno_id else "Editar Alumno")

        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        margen = 40  # un poco de aire para que no quede pegado al borde

        ancho_deseado = 1200
        alto_deseado  = 860

        ancho_final = min(ancho_deseado, screen.width()  - margen)
        alto_final  = min(alto_deseado,  screen.height() - margen)
        self._ancho_dialog = ancho_final  # lo guardamos para decidir el layout en setup_ui


        # Tamaño mínimo más bajo, para que el formulario siempre pueda
        # scrollear en vez de forzar una ventana más grande que la pantalla
        self.setMinimumSize(min(700, ancho_final), min(500, alto_final))

        self.resize(ancho_final, alto_final)

        fg = self.frameGeometry()
        fg.moveCenter(screen.center())
        self.move(fg.topLeft())

        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint
        )
        # ──────────────────────────────────────────────────────────────
        
        self.setStyleSheet(f"""
        QDialog {{
            background-color: {PAL['bg']};
        }}
        QDialog QLineEdit {{
            padding: 10px 14px;
            font-size: 13px;
            border: 1.5px solid {PAL['border']};
            border-radius: 8px;
            background-color: {PAL['surface']};
            color: {PAL['text_1']};
        }}
        QDialog QLineEdit:focus {{
            border: 1.5px solid {PAL['blue']};
            background-color: #FFFFFF;
        }}
        QDialog QLineEdit:disabled {{
            background-color: {PAL['bg']};
            color: {PAL['text_3']};
        }}
        QDialog QComboBox {{
            padding: 10px 14px;
            font-size: 13px;
            border: 1.5px solid {PAL['border']};
            border-radius: 8px;
            background-color: {PAL['surface']};
            color: {PAL['text_1']};
        }}
        QDialog QComboBox:focus {{
            border: 1.5px solid {PAL['blue']};
        }}
        QDialog QComboBox::drop-down {{
            border: none;
            width: 28px;
        }}
        QDialog QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {PAL['text_2']};
            margin-right: 10px;
        }}
        QDialog QDateEdit {{
            padding: 10px 14px;
            font-size: 13px;
            border: 1.5px solid {PAL['border']};
            border-radius: 8px;
            background-color: {PAL['surface']};
            color: {PAL['text_1']};
            min-width: 140px;
            min-height: 42px;
        }}
        QDialog QDateEdit:focus {{
            border: 1.5px solid {PAL['blue']};
        }}
        QDialog QDateEdit::drop-down {{
            border: none;
            width: 28px;
        }}
        QDialog QDateEdit::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {PAL['text_2']};
            margin-right: 10px;
        }}
        """ + GLOBAL_QSS)

        self.setup_ui()
        if self.alumno_id:
            self._load_datos()
        
    # ── Cargar datos existentes (modo Editar) ─────────────────────────────────

    def _load_datos(self):
        try:
            db = Database.get_instance()
            # Traer alumno + matrícula juntos
            row = db.fetchone("""
                SELECT a.*, m.categoria, m.precio_total
                FROM matriculas m
                JOIN alumnos a ON a.numero_documento = m.numero_documento
                WHERE m.id = %s
            """, (self.alumno_id,))

            if not row:
                QMessageBox.warning(self, "No encontrado", "No se encontró la matrícula.")
                self.reject()
                return

            texto_campos = [
                "numero_documento", "nombres", "apellidos",
                "lugar_nacimiento", "celular", "email", "ocupacion",
            ]
            for campo in texto_campos:
                if campo in self.fields and row.get(campo):
                    self.fields[campo].setText(str(row[campo]))

            combos = {
                "tipo_documento":  str(row.get("tipo_documento") or "CC"),
                "categoria":       str(row.get("categoria")      or "A2"),
                "sexo":            str(row.get("sexo")           or "M"),
                "estado_civil":    str(row.get("estado_civil")   or "Soltero"),
                "grupo_sanguineo": str(row.get("grupo_sanguineo") or "O+"),
            }
            for campo, valor in combos.items():
                if campo in self.fields:
                    idx = self.fields[campo].findText(valor)
                    if idx >= 0:
                        self.fields[campo].setCurrentIndex(idx)

            responsable_campos = [
                "responsable_tipo_documento", "responsable_numero_documento",
                "responsable_nombres", "responsable_apellidos",
                "responsable_celular", "responsable_email", "responsable_relacion",
            ]
            for campo in responsable_campos:
                if campo in self.fields and row.get(campo):
                    if isinstance(self.fields[campo], QLineEdit):
                        self.fields[campo].setText(str(row[campo]))
                    elif isinstance(self.fields[campo], QComboBox):
                        idx = self.fields[campo].findText(str(row[campo]))
                        if idx >= 0:
                            self.fields[campo].setCurrentIndex(idx)

            if row.get("fecha_nacimiento"):
                fecha = QDate.fromString(str(row["fecha_nacimiento"]), "yyyy-MM-dd")
                if fecha.isValid():
                    self.fields["fecha_nacimiento"].setDate(fecha)

            # Categoría no editable en modo edición
            self.fields["categoria"].setEnabled(False)
            self.fields["categoria"].setStyleSheet(f"""
                QComboBox {{
                    padding: 10px 14px; font-size: 13px;
                    border: 1.5px solid {PAL['border']}; border-radius: 8px;
                    background-color: {PAL['bg']}; color: {PAL['text_3']};
                }}
                QComboBox::drop-down {{ border: none; }}
                QComboBox::down-arrow {{ image: none; }}
            """)

            # Precio desde matrícula
            precio_guardado = int(row.get("precio_total") or 0)
            cat = str(row.get("categoria") or "A2")
            self._precio_base = PRECIOS_LICENCIA.get(cat, 0)
            descuento = self._precio_base - precio_guardado
            if descuento > 0:
                self._bloqueando_signals = True
                self.field_descuento.setText(str(descuento))
                self._bloqueando_signals = False
            self._recalcular_precio()

        except (ConnectionError, RuntimeError) as e:
            QMessageBox.critical(self, "Error al cargar", str(e))

    # ── UI ────────────────────────────────────────────────────────────────────

    def setup_ui(self):
        
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ═════════════════════════════════════════════════════════════════
        # HEADER
        # ═════════════════════════════════════════════════════════════════
        header_outer = QWidget()
        header_outer.setFixedHeight(96)
        header_outer.setStyleSheet(f"background-color: {PAL['blue']};")

        header_layout = QHBoxLayout(header_outer)
        header_layout.setContentsMargins(32, 0, 0, 0)
        header_layout.setSpacing(0)

        header_left = QVBoxLayout()
        header_left.setSpacing(4)

        lbl_title = QLabel("Nuevo Alumno" if not self.alumno_id else "Editar Alumno")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #FFFFFF;")
        header_left.addWidget(lbl_title)

        lbl_sub = QLabel("Complete todos los campos obligatorios marcados con *")
        lbl_sub.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.65);")
        header_left.addWidget(lbl_sub)

        header_layout.addLayout(header_left)
        header_layout.addStretch()

        step_lbl = QLabel("Datos Personales")
        step_lbl.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 600;
            color: rgba(255,255,255,0.90);
            background: rgba(255,255,255,0.15);
            border: 1px solid rgba(255,255,255,0.25);
            padding: 6px 16px;
            border-radius: 20px;
        """)
        step_lbl.setContentsMargins(0, 0, 16, 0)
        header_layout.addWidget(step_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        red_panel = QWidget()
        red_panel.setFixedSize(48, 96)
        red_panel.setStyleSheet(f"background-color: {PAL['coral']}; border: none;")
        header_layout.addWidget(red_panel)

        root.addWidget(header_outer)

        # ═════════════════════════════════════════════════════════════════
        # BARRA DE PROGRESO
        # ═════════════════════════════════════════════════════════════════
        progress_bg = QWidget()
        progress_bg.setFixedHeight(4)
        progress_bg.setStyleSheet(f"background-color: {PAL['border_lt']};")
        progress_bar_layout = QHBoxLayout(progress_bg)
        progress_bar_layout.setContentsMargins(0, 0, 0, 0)
        progress_bar_layout.setSpacing(0)

        progress_fill = QWidget()
        progress_fill.setFixedHeight(4)
        progress_fill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        progress_fill.setFixedWidth(430)
        progress_fill.setStyleSheet(f"""
            background-color: {PAL['blue']};
            border-right: 4px solid {PAL['coral']};
            border: none;
        """)
        progress_bar_layout.addWidget(progress_fill)
        progress_bar_layout.addStretch()

        root.addWidget(progress_bg)

        # ═════════════════════════════════════════════════════════════════
        # CUERPO CON SCROLL
        # ═════════════════════════════════════════════════════════════════
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {PAL['bg']}; border: none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        body = QWidget()
        body.setStyleSheet(f"background: {PAL['bg']};")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(32, 28, 32, 28)
        body_layout.setSpacing(0)

        self.fields = {}

        # ── Layout de columnas (SOLO UNA VEZ) ─────────────────────────
        UMBRAL_APILAR = 900  # si el diálogo tiene menos de este ancho, las columnas se apilan
        apilar = getattr(self, "_ancho_dialog", 1200) < UMBRAL_APILAR

        cols = QVBoxLayout() if apilar else QHBoxLayout()
        cols.setSpacing(20)
        cols.setContentsMargins(0, 0, 0, 0)

        col_left = QVBoxLayout()
        col_left.setSpacing(12)

        col_right = QVBoxLayout()
        col_right.setSpacing(12)

        # ═════════════════════════════════════════════════════════════════
        # COLUMNA IZQUIERDA
        # ═════════════════════════════════════════════════════════════════

        # ── Sección: Identificación ───────────────────────────────────
        col_left.addWidget(make_section_label("Identificación"))
        card_id = self._make_card()
        grid_id = QGridLayout(card_id)
        grid_id.setSpacing(14)
        grid_id.setContentsMargins(20, 20, 20, 20)

        grid_id.addWidget(make_field_label("Número Documento *"), 0, 0, 1, 2)
        self.fields["numero_documento"] = QLineEdit()
        self.fields["numero_documento"].setPlaceholderText("Ej: 94427466")
        grid_id.addWidget(self.fields["numero_documento"], 1, 0, 1, 2)

        grid_id.addWidget(make_field_label("Tipo Documento"), 0, 2)
        self.fields["tipo_documento"] = QComboBox()
        self.fields["tipo_documento"].addItems(["CC", "CE", "TI", "PAS"])
        grid_id.addWidget(self.fields["tipo_documento"], 1, 2)

        grid_id.addWidget(make_field_label("Categoría / Licencia *"), 0, 3)
        self.fields["categoria"] = QComboBox()
        self.fields["categoria"].addItems(CATEGORIAS)
        # ❌ NO conectar la señal aquí (lbl_precio_base aún no existe)
        grid_id.addWidget(self.fields["categoria"], 1, 3)

        col_left.addWidget(card_id)

        # ── Sección: Información de Contacto ─────────────────────────
        col_left.addWidget(make_section_label("Información de Contacto"))
        card_contacto = self._make_card()
        grid_c = QGridLayout(card_contacto)
        grid_c.setSpacing(14)
        grid_c.setContentsMargins(20, 20, 20, 20)

        grid_c.addWidget(make_field_label("Celular"), 0, 0)
        self.fields["celular"] = QLineEdit()
        self.fields["celular"].setPlaceholderText("Ej: 3502199752")
        grid_c.addWidget(self.fields["celular"], 1, 0)

        grid_c.addWidget(make_field_label("Email"), 0, 1)
        self.fields["email"] = QLineEdit()
        self.fields["email"].setPlaceholderText("Ej: carlos@email.com")
        grid_c.addWidget(self.fields["email"], 1, 1)
        grid_c.setColumnStretch(0, 1)
        grid_c.setColumnStretch(1, 2)

        col_left.addWidget(card_contacto)
        
        # ── Sección: Responsable de Inscripción ───────────────────────
        col_left.addWidget(make_section_label("Responsable de Inscripción"))
        card_resp = self._make_card()
        grid_r = QGridLayout(card_resp)
        grid_r.setSpacing(14)
        grid_r.setContentsMargins(20, 20, 20, 20)

        grid_r.addWidget(make_field_label("Tipo Documento"), 0, 0)
        self.fields["responsable_tipo_documento"] = QComboBox()
        self.fields["responsable_tipo_documento"].addItems(["CC", "CE", "TI", "PAS"])
        grid_r.addWidget(self.fields["responsable_tipo_documento"], 1, 0)

        grid_r.addWidget(make_field_label("Número Documento"), 0, 1)
        self.fields["responsable_numero_documento"] = QLineEdit()
        self.fields["responsable_numero_documento"].setPlaceholderText("Ej: 94427466")
        grid_r.addWidget(self.fields["responsable_numero_documento"], 1, 1)

        grid_r.addWidget(make_field_label("Nombres"), 2, 0)
        self.fields["responsable_nombres"] = QLineEdit()
        self.fields["responsable_nombres"].setPlaceholderText("Ej: María Elena")
        grid_r.addWidget(self.fields["responsable_nombres"], 3, 0)

        grid_r.addWidget(make_field_label("Apellidos"), 2, 1)
        self.fields["responsable_apellidos"] = QLineEdit()
        self.fields["responsable_apellidos"].setPlaceholderText("Ej: Hoyos Patiño")
        grid_r.addWidget(self.fields["responsable_apellidos"], 3, 1)

        grid_r.addWidget(make_field_label("Celular"), 4, 0)
        self.fields["responsable_celular"] = QLineEdit()
        self.fields["responsable_celular"].setPlaceholderText("Ej: 3502199752")
        grid_r.addWidget(self.fields["responsable_celular"], 4, 0)

        grid_r.addWidget(make_field_label("Email"), 4, 1)
        self.fields["responsable_email"] = QLineEdit()
        self.fields["responsable_email"].setPlaceholderText("Ej: maria@email.com")
        grid_r.addWidget(self.fields["responsable_email"], 4, 1)

        grid_r.addWidget(make_field_label("Relación con alumno"), 5, 0, 1, 2)
        self.fields["responsable_relacion"] = QComboBox()
        self.fields["responsable_relacion"].addItems([
            "Padre", "Madre", "Cónyuge", "Hermano/a", "Amigo/a",
            "Tutor legal", "Representante", "Otro"
        ])
        self.fields["responsable_relacion"].setFixedHeight(42)
        grid_r.addWidget(self.fields["responsable_relacion"], 6, 0, 1, 2)

        col_left.addWidget(card_resp)
        
        col_left.addStretch()

        # ═════════════════════════════════════════════════════════════════
        # COLUMNA DERECHA
        # ═════════════════════════════════════════════════════════════════

        # ── Sección: Datos Personales ─────────────────────────────────
        col_right.addWidget(make_section_label("Datos Personales"))
        card_personal = self._make_card()
        grid_p = QGridLayout(card_personal)
        grid_p.setHorizontalSpacing(14)
        grid_p.setVerticalSpacing(10)
        grid_p.setContentsMargins(20, 22, 20, 22)

        grid_p.addWidget(make_field_label("Nombres *"), 0, 0, 1, 2)
        self.fields["nombres"] = QLineEdit()
        self.fields["nombres"].setPlaceholderText("Ej: Carlos Arturo")
        grid_p.addWidget(self.fields["nombres"], 1, 0, 1, 2)

        grid_p.addWidget(make_field_label("Apellidos *"), 0, 2, 1, 2)
        self.fields["apellidos"] = QLineEdit()
        self.fields["apellidos"].setPlaceholderText("Ej: Hoyos Patino")
        grid_p.addWidget(self.fields["apellidos"], 1, 2, 1, 2)

        spacer_a = QFrame()
        spacer_a.setFixedHeight(8)
        spacer_a.setStyleSheet("background: transparent; border: none;")
        grid_p.addWidget(spacer_a, 2, 0, 1, 4)

        grid_p.addWidget(make_field_label("Fecha Nacimiento"), 3, 0)
        self.fields["fecha_nacimiento"] = QDateEdit()
        self.fields["fecha_nacimiento"].setCalendarPopup(True)
        self.fields["fecha_nacimiento"].setDate(QDate.currentDate().addYears(-25))
        self.fields["fecha_nacimiento"].setFixedHeight(42)
        self.fields["fecha_nacimiento"].setMinimumWidth(160)
        self.fields["fecha_nacimiento"].setDisplayFormat("dd/MM/yyyy")
        grid_p.addWidget(self.fields["fecha_nacimiento"], 4, 0)

        grid_p.addWidget(make_field_label("Lugar Nacimiento"), 3, 1)
        self.fields["lugar_nacimiento"] = QLineEdit()
        self.fields["lugar_nacimiento"].setPlaceholderText("Ej: Cali, Valle")
        grid_p.addWidget(self.fields["lugar_nacimiento"], 4, 1)

        grid_p.addWidget(make_field_label("Sexo"), 3, 2)
        self.fields["sexo"] = QComboBox()
        self.fields["sexo"].addItems(["M", "F"])
        self.fields["sexo"].setFixedHeight(42)
        grid_p.addWidget(self.fields["sexo"], 4, 2)

        grid_p.addWidget(make_field_label("Estado Civil"), 3, 3)
        self.fields["estado_civil"] = QComboBox()
        self.fields["estado_civil"].addItems(["Soltero", "Casado", "Divorciado", "Viudo", "Unión Libre"])
        self.fields["estado_civil"].setFixedHeight(42)
        grid_p.addWidget(self.fields["estado_civil"], 4, 3)

        spacer_b = QFrame()
        spacer_b.setFixedHeight(8)
        spacer_b.setStyleSheet("background: transparent; border: none;")
        grid_p.addWidget(spacer_b, 5, 0, 1, 4)

        grid_p.addWidget(make_field_label("Grupo Sanguíneo"), 6, 0)
        self.fields["grupo_sanguineo"] = QComboBox()
        self.fields["grupo_sanguineo"].addItems(["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"])
        self.fields["grupo_sanguineo"].setFixedHeight(42)
        grid_p.addWidget(self.fields["grupo_sanguineo"], 7, 0)

        grid_p.addWidget(make_field_label("Ocupación"), 6, 1)
        self.fields["ocupacion"] = QLineEdit()
        self.fields["ocupacion"].setPlaceholderText("Ej: Empleado")
        grid_p.addWidget(self.fields["ocupacion"], 7, 1)

        col_right.addWidget(card_personal)

        # ── Sección: Valor del Curso ──────────────────────────────────
        col_right.addWidget(make_section_label("Valor del Curso"))
        card_precio = self._make_card_precio()
        grid_v = QGridLayout(card_precio)
        grid_v.setHorizontalSpacing(20)
        grid_v.setVerticalSpacing(10)
        grid_v.setContentsMargins(20, 22, 20, 22)

        grid_v.addWidget(make_field_label("Precio base"), 0, 0)
        grid_v.addWidget(make_field_label("Descuento ($ pesos)"), 0, 1)
        grid_v.addWidget(make_field_label("% Descuento"), 0, 2)

        self.lbl_precio_base = QLabel(fmt_cop(0))
        self.lbl_precio_base.setStyleSheet(f"""
            font-size: 15px;
            font-weight: 700;
            color: {PAL['text_2']};
            background: {PAL['bg']};
            border: 1.5px solid {PAL['border']};
            border-radius: 8px;
            padding: 10px 14px;
        """)
        grid_v.addWidget(self.lbl_precio_base, 1, 0)

        self.field_descuento = QLineEdit()
        self.field_descuento.setPlaceholderText("Ej: 50000")
        self.field_descuento.textChanged.connect(self._on_descuento_pesos_changed)
        grid_v.addWidget(self.field_descuento, 1, 1)

        self.field_descuento_pct = QLineEdit()
        self.field_descuento_pct.setPlaceholderText("Ej: 10")
        self.field_descuento_pct.textChanged.connect(self._on_descuento_pct_changed)
        grid_v.addWidget(self.field_descuento_pct, 1, 2)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {PAL['border_lt']}; border: none; max-height: 1px;")
        grid_v.addWidget(sep, 2, 0, 1, 3)

        # Método de pago
        grid_v.addWidget(make_field_label("Método de pago"), 3, 0, 1, 3)
        self.combo_metodo_pago = QComboBox()
        self.combo_metodo_pago.addItems([
            "Efectivo", "Transferencia", "Tarjeta", "Sistecredit"
        ])
        self.combo_metodo_pago.currentTextChanged.connect(self._on_metodo_pago_changed)
        grid_v.addWidget(self.combo_metodo_pago, 4, 0, 1, 3)

        # Aviso recargo Sistecredit
        self.lbl_recargo = QLabel("⚡  Se agregan $50.000 por pago con Sistecredit")
        self.lbl_recargo.setStyleSheet(f"""
            font-size: 11px; font-weight: 600;
            color: {PAL['amber']}; background: {PAL['amber_bg']};
            border-radius: 6px; padding: 5px 10px;
        """)
        self.lbl_recargo.setVisible(False)
        grid_v.addWidget(self.lbl_recargo, 5, 0, 1, 3)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background: {PAL['border_lt']}; border: none; max-height: 1px;")
        grid_v.addWidget(sep2, 6, 0, 1, 3)

        grid_v.addWidget(make_field_label("Total a pagar *"), 7, 0)

        lbl_total_hint = QLabel("Puedes modificar el valor directamente")
        lbl_total_hint.setStyleSheet(f"font-size: 11px; color: {PAL['text_3']}; font-weight: 400;")
        grid_v.addWidget(lbl_total_hint, 7, 1, 1, 2)

        self.field_precio_total = QLineEdit()
        self.field_precio_total.setPlaceholderText("0")
        self.field_precio_total.setStyleSheet(f"""
            QLineEdit {{
                font-size: 18px;
                font-weight: 700;
                color: {PAL['blue']};
                border: 2px solid {PAL['blue']};
                border-radius: 8px;
                padding: 10px 14px;
                background: {PAL['blue_bg']};
            }}
            QLineEdit:focus {{
                border: 2px solid {PAL['blue_dark']};
                background: #FFFFFF;
            }}
        """)
        self.field_precio_total.setFixedHeight(52)
        self.field_precio_total.textChanged.connect(self._on_precio_total_changed)
        grid_v.addWidget(self.field_precio_total, 8, 0, 1, 3)

        col_right.addWidget(card_precio)
        col_right.addStretch()

        # ── Conectar columnas al layout del body ─────────────────────
        cols.addLayout(col_left, 1)
        cols.addLayout(col_right, 1)
        body_layout.addLayout(cols)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # ✅ CONECTAR SEÑAL AHORA QUE lbl_precio_base EXISTE
        self.fields["categoria"].currentTextChanged.connect(self._on_categoria_changed)

        # Inicializar precio solo para nuevos alumnos
        if not self.alumno_id:
            self._on_categoria_changed(self.fields["categoria"].currentText())

        # ═════════════════════════════════════════════════════════════════
        # FOOTER
        # ═════════════════════════════════════════════════════════════════
        footer = QWidget()
        footer.setMinimumHeight(70)
        footer.setMaximumHeight(90)
        footer.setStyleSheet(f"""
            background-color: {PAL['surface']};
            border-top: 1.5px solid {PAL['border_lt']};
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(32, 0, 32, 0)

        req_lbl = QLabel("* Campos obligatorios")
        req_lbl.setStyleSheet(f"font-size: 11px; color: {PAL['text_3']};")
        footer_layout.addWidget(req_lbl)

        footer_layout.addStretch()

        btn_cancel = make_btn_secondary("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        footer_layout.addWidget(btn_cancel)

        btn_save = make_btn_primary("Guardar Alumno")
        btn_save.setMinimumHeight(48)
        btn_save.setMinimumWidth(200)
        btn_save.setStyleSheet(btn_save.styleSheet() + "font-size: 15px;")
        btn_save.clicked.connect(self.save_alumno)
        footer_layout.addWidget(btn_save)

        root.addWidget(footer)
    # ── Lógica de precio ──────────────────────────────────────────────────────

    def _on_categoria_changed(self, categoria: str):
        """Actualiza precio base al cambiar categoría y recalcula total."""
        self._precio_base = PRECIOS_LICENCIA.get(categoria, 0)
        self.lbl_precio_base.setText(fmt_cop(self._precio_base))
        # Limpiar descuentos al cambiar categoría
        self._bloqueando_signals = True
        self.field_descuento.clear()
        self.field_descuento_pct.clear()
        self._bloqueando_signals = False
        self._recalcular_precio()

    def _on_descuento_pesos_changed(self, texto: str):
        """Al cambiar descuento en pesos, actualiza % y total."""
        if self._bloqueando_signals:
            return
        self._bloqueando_signals = True
        try:
            valor = int(texto.replace(".", "").replace(",", "").strip() or "0")
            if self._precio_base > 0:
                pct = round((valor / self._precio_base) * 100, 2)
                self.field_descuento_pct.setText(str(pct) if pct > 0 else "")
        except ValueError:
            self.field_descuento_pct.clear()
        finally:
            self._bloqueando_signals = False
        self._recalcular_precio()

    def _on_descuento_pct_changed(self, texto: str):
        """Al cambiar % descuento, actualiza pesos y total."""
        if self._bloqueando_signals:
            return
        self._bloqueando_signals = True
        try:
            pct = float(texto.replace(",", ".").strip() or "0")
            pesos = int(self._precio_base * pct / 100)
            self.field_descuento.setText(str(pesos) if pesos > 0 else "")
        except ValueError:
            self.field_descuento.clear()
        finally:
            self._bloqueando_signals = False
        self._recalcular_precio()

    def _on_precio_total_changed(self, texto: str):
        """Al editar total directamente, actualiza descuento en pesos y %."""
        if self._bloqueando_signals:
            return
        self._bloqueando_signals = True
        try:
            total = int(texto.replace(".", "").replace(",", "").replace("$", "").strip() or "0")
            descuento = self._precio_base - total
            if descuento > 0:
                self.field_descuento.setText(str(descuento))
                if self._precio_base > 0:
                    pct = round((descuento / self._precio_base) * 100, 2)
                    self.field_descuento_pct.setText(str(pct))
            else:
                self.field_descuento.clear()
                self.field_descuento_pct.clear()
        except ValueError:
            pass
        finally:
            self._bloqueando_signals = False

    def _on_metodo_pago_changed(self, metodo: str):
        """Agrega o quita el recargo de $50.000 según método de pago."""
        if metodo == "Sistecredit":
            self._recargo_sistecredito = RECARGO_SISTECREDITO
            self.lbl_recargo.setVisible(True)
        else:
            self._recargo_sistecredito = 0
            self.lbl_recargo.setVisible(False)
        self._recalcular_precio()

    def _recalcular_precio(self):
        """Recalcula precio total desde base - descuento + recargo Sistecredit."""
        try:
            desc_texto = self.field_descuento.text().replace(".", "").replace(",", "").strip()
            descuento = int(desc_texto or "0")
        except ValueError:
            descuento = 0

        total = max(self._precio_base - descuento + self._recargo_sistecredito, 0)
        self._bloqueando_signals = True
        self.field_precio_total.setText(str(total))
        self._bloqueando_signals = False

    def _get_precio_total(self) -> int:
        """Devuelve el precio total final como entero."""
        try:
            return int(
                self.field_precio_total.text()
                    .replace(".", "").replace(",", "")
                    .replace("$", "").strip()
                or "0"
            )
        except ValueError:
            return 0

    def _make_card(self):
        card = QWidget()
        card.setObjectName("card")
        card.setStyleSheet(f"""
            QWidget#card {{
                background-color: {PAL['surface']};
                border-radius: 12px;
                border: 1px solid {PAL['border_lt']};
                border-top: 3px solid {PAL['blue']};
            }}
        """)
        add_shadow(card, blur=20, offset_y=6, opacity=0.12)
        return card

    def _make_card_precio(self):
        """Tarjeta especial con acento verde/teal para la sección de precio."""
        card = QWidget()
        card.setObjectName("cardPrecio")
        card.setStyleSheet(f"""
            QWidget#cardPrecio {{
                background-color: {PAL['surface']};
                border-radius: 12px;
                border: 1px solid {PAL['border_lt']};
                border-top: 3px solid {PAL['teal']};
            }}
        """)
        add_shadow(card, blur=16, offset_y=4, opacity=0.08)
        return card

    # ── Guardar ───────────────────────────────────────────────────────────────

    def save_alumno(self):
        
        datos = {}
        for key, field in self.fields.items():
            if isinstance(field, QLineEdit):
                datos[key] = field.text().strip() or None
            elif isinstance(field, QComboBox):
                datos[key] = field.currentText()
            elif isinstance(field, QDateEdit):
                datos[key] = field.date().toString("yyyy-MM-dd")

        precio_total = self._get_precio_total()

        faltantes = []
        if not datos.get("numero_documento"):
            faltantes.append("Número de Documento")
        if not datos.get("nombres"):
            faltantes.append("Nombres")
        if not datos.get("apellidos"):
            faltantes.append("Apellidos")
        if precio_total <= 0:
            faltantes.append("Precio total (debe ser mayor a 0)")

        if faltantes:
            msg = QMessageBox(self)
            msg.setWindowTitle("Campos requeridos")
            msg.setText("Por favor complete los siguientes campos:\n\n• " + "\n• ".join(faltantes))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStyleSheet(f"background-color: {PAL['surface']};")
            msg.exec()
            return

        try:
            db = Database.get_instance()

            if self.alumno_id:
            # self.alumno_id aquí es matricula_id
            # Actualizar datos personales del alumno
                db.execute("""
                    UPDATE alumnos SET
                        tipo_documento = %s, nombres = %s, apellidos = %s,
                        fecha_nacimiento = %s, lugar_nacimiento = %s,
                        sexo = %s, estado_civil = %s, grupo_sanguineo = %s,
                        celular = %s, email = %s, ocupacion = %s,
                        responsable_tipo_documento = %s, responsable_numero_documento = %s,
                        responsable_nombres = %s, responsable_apellidos = %s,
                        responsable_celular = %s, responsable_email = %s,
                        responsable_relacion = %s
                    WHERE numero_documento = (SELECT numero_documento FROM matriculas WHERE id = %s)
                """, (
                    datos.get("tipo_documento"),
                    datos.get("nombres"),      datos.get("apellidos"),
                    datos.get("fecha_nacimiento"), datos.get("lugar_nacimiento"),
                    datos.get("sexo"),         datos.get("estado_civil"),
                    datos.get("grupo_sanguineo"),
                    datos.get("celular"),      datos.get("email"),
                    datos.get("ocupacion"),
                    datos.get("responsable_tipo_documento"),
                    datos.get("responsable_numero_documento"),
                    datos.get("responsable_nombres"),  datos.get("responsable_apellidos"),
                    datos.get("responsable_celular"),  datos.get("responsable_email"),
                    datos.get("responsable_relacion"),
                    self.alumno_id
                ))
                # Actualizar precio de la matrícula
                db.execute(
                    "UPDATE matriculas SET precio_total = %s WHERE id = %s",
                    (precio_total, self.alumno_id)
                )
                msg_texto = f"Alumno {datos['nombres']} {datos['apellidos']} actualizado correctamente."

            else:
                # ── Paso 1: crear alumno solo si no existe ─────────────────
                existe = db.fetchone(
                    "SELECT numero_documento FROM alumnos WHERE numero_documento = %s",
                    (datos.get("numero_documento"),)
                )
                if not existe:
                    db.execute("""
                        INSERT INTO alumnos (
                            numero_documento, tipo_documento,
                            nombres, apellidos,
                            fecha_nacimiento, lugar_nacimiento,
                            sexo, estado_civil, grupo_sanguineo,
                            celular, email, ocupacion,
                            responsable_tipo_documento, responsable_numero_documento,
                            responsable_nombres, responsable_apellidos,
                            responsable_celular, responsable_email, responsable_relacion
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        datos.get("numero_documento"), datos.get("tipo_documento"),
                        datos.get("nombres"),          datos.get("apellidos"),
                        datos.get("fecha_nacimiento"), datos.get("lugar_nacimiento"),
                        datos.get("sexo"),             datos.get("estado_civil"),
                        datos.get("grupo_sanguineo"),
                        datos.get("celular"),          datos.get("email"),
                        datos.get("ocupacion"),
                        datos.get("responsable_tipo_documento"),
                        datos.get("responsable_numero_documento"),
                        datos.get("responsable_nombres"),
                        datos.get("responsable_apellidos"),
                        datos.get("responsable_celular"),
                        datos.get("responsable_email"),
                        datos.get("responsable_relacion")
                    ))

                # ── Paso 2: generar número de orden y crear matrícula ──────
                from datetime import datetime as _dt
                anio_actual = _dt.now().year
                anio_corto  = str(anio_actual)[-2:]

                ultimo = db.fetchone(
                    "SELECT numero_orden FROM matriculas WHERE anio = %s ORDER BY numero_orden DESC LIMIT 1",
                    (anio_actual,)
                )
                if ultimo and ultimo.get("numero_orden"):
                    try:
                        num_nuevo = int(ultimo["numero_orden"]) + 1
                    except ValueError:
                        num_nuevo = 1
                else:
                    num_nuevo = 1

                numero_orden = f"{num_nuevo:03d}"  # "001", "002", ...

                db.execute("""
                    INSERT INTO matriculas (
                        numero_documento, numero_orden, anio,
                        categoria, estado, precio_total
                    ) VALUES (%s, %s, %s, %s, 'Activo', %s)
                """, (
                    datos.get("numero_documento"),
                    numero_orden,
                    anio_actual,
                    datos.get("categoria"),
                    precio_total
                ))

                msg_texto = (
                    f"{datos['nombres']} {datos['apellidos']} registrado.\n"
                    f"Matrícula: {numero_orden}-{anio_corto} · {datos.get('categoria')}"
                )

            msg = QMessageBox(self)
            msg.setWindowTitle("Guardado")
            msg.setText(msg_texto)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setStyleSheet(f"background-color: {PAL['surface']};")
            msg.exec()
            self.accept()

        except RuntimeError as e:
            msg = QMessageBox(self)
            msg.setWindowTitle("Error al guardar")
            msg.setText(str(e))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setStyleSheet(f"background-color: {PAL['surface']};")
            msg.exec()
        except ConnectionError as e:
            msg = QMessageBox(self)
            msg.setWindowTitle("Sin conexión")
            msg.setText(str(e))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setStyleSheet(f"background-color: {PAL['surface']};")
            msg.exec()


# ══════════════════════════════════════════════════════════════════════════════
#  DIÁLOGO: VER ALUMNO (solo lectura)
# ══════════════════════════════════════════════════════════════════════════════

class AlumnoVerDialog(QDialog):
    """Muestra todos los datos del alumno en modo solo lectura."""

    ESTADO_COLOR = {
        "Activo":         (PAL["teal_bg"],   PAL["teal"]),
        "Completado":     (PAL["blue_bg"],   PAL["blue"]),
        "Pendiente Pago": (PAL["amber_bg"],  PAL["amber"]),
        "Cancelado":      (PAL["coral_bg"],  PAL["coral"]),
    }

    def __init__(self, alumno_id: int, parent=None):
        
        super().__init__(parent)
        self.alumno_id = alumno_id
        self.setWindowTitle("Detalle del Alumno")
        self.setMinimumSize(900, 750)
        self.resize(920, 900)
        self.setStyleSheet("""
            QDialog {
                background-color: #F5F7FA;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                background: transparent;
                border: none;
                padding: 0;
            }
            QScrollArea {
                background: #F5F7FA;
                border: none;
            }
            QWidget#infoCard {
                background-color: #FBF9F2;
                border-radius: 8px;
                border: 1px solid #E4E2DA;
            }
            QWidget {
                border: none;
                background: transparent;
            }
        """)
        self.setup_ui()
        self._load_datos()

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        self.header_widget = QWidget()
        self.header_widget.setFixedHeight(90)
        self.header_widget.setStyleSheet("background-color: #002D6B;")
        hl = QHBoxLayout(self.header_widget)
        hl.setContentsMargins(32, 0, 32, 0)

        self.lbl_avatar = QLabel()
        self.lbl_avatar.setFixedSize(54, 54)
        self.lbl_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_avatar.setStyleSheet("""
            background: rgba(255,255,255,0.2);
            border-radius: 27px;
            font-size: 22px;
        """)
        self.lbl_avatar.setText("👤")
        hl.addWidget(self.lbl_avatar)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title_col.setContentsMargins(12, 0, 0, 0)
        self.lbl_nombre_header = QLabel("Cargando...")
        self.lbl_nombre_header.setStyleSheet("font-size: 19px; font-weight: 700; color: #FFFFFF;")
        title_col.addWidget(self.lbl_nombre_header)
        self.lbl_doc_header = QLabel("")
        self.lbl_doc_header.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.75);")
        title_col.addWidget(self.lbl_doc_header)
        hl.addLayout(title_col)
        hl.addStretch()

        self.lbl_estado_badge = QLabel("")
        self.lbl_estado_badge.setStyleSheet("""
            font-size: 12px; font-weight: 600;
            padding: 6px 16px; border-radius: 20px;
        """)
        hl.addWidget(self.lbl_estado_badge)

        root.addWidget(self.header_widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: #F8F7F4; border: none;")

        self.body = QWidget()
        self.body.setStyleSheet("background: #F8F7F4;")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(28, 12, 28, 24)
        self.body_layout.setSpacing(20)

        scroll.setWidget(self.body)
        root.addWidget(scroll)

        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet("background: #FFFFFF; border-top: 1px solid #E4E2DA;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(28, 0, 28, 0)

        lbl_footer_info = QLabel("Información del alumno · Sistema v1.2")
        lbl_footer_info.setStyleSheet("font-size: 11px; color: #9AA3B0; background: transparent;")
        fl.addWidget(lbl_footer_info)
        fl.addStretch()

        btn_editar = QPushButton("✏  Editar")
        btn_editar.setFixedHeight(38)
        btn_editar.setFixedWidth(110)
        btn_editar.setStyleSheet("""
            QPushButton {
                background: #3973BF; color: #FFFFFF;
                border: none; border-radius: 6px;
                font-size: 13px; font-weight: 500; padding: 0 16px;
            }
            QPushButton:hover { background: #2D5FA3; }
        """)
        btn_editar.clicked.connect(self._abrir_edicion)
        fl.addWidget(btn_editar)

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setFixedHeight(38)
        btn_cerrar.setFixedWidth(90)
        btn_cerrar.setStyleSheet("""
            QPushButton {
                background: #EFF2F5; color: #2C3E50;
                border: 1px solid #E0E0E0; border-radius: 6px;
                font-size: 13px; font-weight: 500; padding: 0 16px;
            }
            QPushButton:hover { background: #E2E6EA; }
        """)
        btn_cerrar.clicked.connect(self.accept)
        fl.addWidget(btn_cerrar)

        root.addWidget(footer)

    def _load_datos(self):
        
        try:
            db  = Database.get_instance()
            row = db.fetchone("""
                SELECT a.*, m.categoria, m.estado, m.precio_total,
                    m.numero_orden, m.anio,
                    DATE_FORMAT(m.fecha_registro, '%Y-%m-%d') AS fecha_registro,
                    m.anio AS anio_registro
                FROM matriculas m
                JOIN alumnos a ON a.numero_documento = m.numero_documento
                WHERE m.id = %s
            """, (self.alumno_id,))
        except (ConnectionError, RuntimeError) as e:
            QMessageBox.critical(self, "Error", str(e))
            self.reject()
            return

        if not row:
            QMessageBox.warning(self, "No encontrado", "Matrícula no encontrada.")
            self.reject()
            return

        nombre_completo = f"{row.get('nombres', '')} {row.get('apellidos', '')}"

        
        self.lbl_nombre_header.setText(nombre_completo)
        self.lbl_doc_header.setText(
            f"{row.get('tipo_documento','CC')}  {row.get('numero_documento','')}"
        )

        estado = row.get("estado", "Activo")
        BADGE_COLORS = {
            "Activo":         ("#1D9E75", "#FFFFFF"),
            "Cancelado":      ("#D32F2F", "#FFFFFF"),
            "Pendiente Pago": ("#8A5210", "#FFFFFF"),
            "Completado":     ("#0033A0", "#FFFFFF"),
        }
        badge_bg, badge_fg = BADGE_COLORS.get(estado, ("#888", "#FFFFFF"))
        self.lbl_estado_badge.setText(estado.upper())
        self.lbl_estado_badge.setFixedHeight(32)
        self.lbl_estado_badge.setMinimumWidth(0)
        self.lbl_estado_badge.setMaximumWidth(140)
        self.lbl_estado_badge.setStyleSheet(f"""
            font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
            padding: 0px 16px; border-radius: 16px;
            background: {badge_bg}; color: {badge_fg};
        """)

        if row.get("foto_path"):
            pix = QPixmap(row["foto_path"])
            if not pix.isNull():
                self.lbl_avatar.setPixmap(
                    pix.scaled(54, 54,
                               Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
                )
                self.lbl_avatar.setStyleSheet("border-radius: 27px; border: 2px solid rgba(255,255,255,0.4);")

        self.body_layout.addWidget(_make_section_header("🪪", "Identificación y categoría"))

        # Precio base y total para mostrar en vista
        cat = str(row.get("categoria") or "A2")
        precio_base = PRECIOS_LICENCIA.get(cat, 0)
        precio_total = int(row.get("precio_total") or precio_base)
        descuento = precio_base - precio_total

        self.body_layout.addWidget(self._make_info_card([
            ("Número Documento", row.get("numero_documento")),
            ("Tipo Documento",   row.get("tipo_documento")),
            ("Categoría",        row.get("categoria")),
            ("Estado",           row.get("estado")),
            ("Fecha Registro",   str(row.get("anio_registro", "")) if row.get("estado") == "Histórico" else (str(row.get("fecha_registro", ""))[:10] if row.get("fecha_registro") else str(row.get("anio_registro", "")))),
        ]))

        self.body_layout.addWidget(_make_section_header("👤", "Datos personales"))
        self.body_layout.addWidget(self._make_info_card([
            ("Nombres",          row.get("nombres")),
            ("Apellidos",        row.get("apellidos")),
            ("Fecha Nacimiento", str(row.get("fecha_nacimiento", ""))),
            ("Lugar Nacimiento", row.get("lugar_nacimiento")),
            ("Sexo",             row.get("sexo")),
            ("Estado Civil",     row.get("estado_civil")),
            ("Grupo Sanguíneo",  row.get("grupo_sanguineo")),
            ("Ocupación",        row.get("ocupacion")),
        ]))

        self.body_layout.addWidget(_make_section_header("✉", "Contacto"))
        self.body_layout.addWidget(self._make_info_card([
            ("Celular", row.get("celular")),
            ("Email",   row.get("email")),
        ]))

        # ── Bloque de responsable (solo si tiene datos) ─────────────
        tiene_responsable = any([
            row.get("responsable_nombres"),
            row.get("responsable_apellidos"),
            row.get("responsable_numero_documento"),
        ])
        if tiene_responsable:
            self.body_layout.addWidget(_make_section_header("👥", "Responsable de Inscripción"))
            resp_campos = [
                ("Nombres",           row.get("responsable_nombres")),
                ("Apellidos",         row.get("responsable_apellidos")),
                ("Tipo Documento",    row.get("responsable_tipo_documento")),
                ("Número Documento",  row.get("responsable_numero_documento")),
                ("Celular",           row.get("responsable_celular")),
                ("Email",             row.get("responsable_email")),
                ("Relación",          row.get("responsable_relacion")),
            ]
            # Filtrar vacíos
            resp_campos = [(k, v) for k, v in resp_campos if v]
            self.body_layout.addWidget(self._make_info_card(resp_campos))

        # ── Bloque de precio en vista ─────────────────────────────────────────
        self.body_layout.addWidget(_make_section_header("💰", "Valor del Curso"))
        precio_campos = [
            ("Precio base",    fmt_cop(precio_base)),
            ("Descuento",      fmt_cop(descuento) if descuento > 0 else "Sin descuento"),
            ("Total a pagar",  fmt_cop(precio_total)),
        ]
        self.body_layout.addWidget(self._make_info_card(precio_campos))

        if row.get("observaciones"):
            self.body_layout.addWidget(_make_section_header("📝", "Observaciones"))
            obs_card = self._make_card()
            obs_layout = QVBoxLayout(obs_card)
            obs_layout.setContentsMargins(20, 16, 20, 16)
            lbl_obs = QLabel(row["observaciones"])
            lbl_obs.setWordWrap(True)
            lbl_obs.setStyleSheet(f"font-size: 13px; color: {PAL['text_2']}; line-height: 1.6;")
            obs_layout.addWidget(lbl_obs)
            self.body_layout.addWidget(obs_card)

        self.body_layout.addStretch()

    def _make_info_card(self, campos: list) -> QWidget:
        container = QWidget()
        container.setObjectName("cardContainer")
        container.setStyleSheet("QWidget#cardContainer { background: transparent; border: none; }")
        
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        col = 0
        row_idx = 0
        for label, valor in campos:
            if valor is None or str(valor).strip() == "":
                valor = "—"

            # Cada campo es su propia tarjeta individual
            field_card = QWidget()
            field_card.setObjectName("fieldCard")
            field_card.setStyleSheet("""
                QWidget#fieldCard {
                    background-color: #F0EEE6;
                    border-radius: 8px;
                    border: 1px solid #DDD9D0;
                }
            """)

            cell = QVBoxLayout(field_card)
            cell.setContentsMargins(12, 10, 12, 10)
            cell.setSpacing(3)

            lbl_key = QLabel(label.upper())
            lbl_key.setStyleSheet("""
                font-size: 10px; font-weight: 600;
                color: #5D6A81; letter-spacing: 0.07em;
                background: transparent; border: none;
            """)
            cell.addWidget(lbl_key)

            lbl_val = QLabel(str(valor))
            lbl_val.setWordWrap(True)
            
            if label == "Total a pagar":
                lbl_val.setStyleSheet("""
                    font-size: 15px; font-weight: 700;
                    color: #002D6B; background: transparent; border: none;
                """)
            else:
                lbl_val.setStyleSheet("""
                    font-size: 13px; font-weight: 700;
                    color: #2C3E50; background: transparent; border: none;
                """)
            cell.addWidget(lbl_val)

            grid.addWidget(field_card, row_idx, col)

            col += 1
            if col >= 3:
                col = 0
                row_idx += 1

        return container

    def _make_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("infoCard")
        card.setMinimumHeight(80)          # ← agrega esta línea
        card.setStyleSheet("""
            QWidget#infoCard {
                background-color: #FBF9F2;
                border-radius: 8px;
                border: 1px solid #E4E2DA;
            }
        """)
        return card 

    def _abrir_edicion(self):
        self.accept()
        dialog = AlumnoDialog(alumno_id=self.alumno_id, parent=self.parent())
        dialog.exec()


# ══════════════════════════════════════════════════════════════════════════════
#  VISTA PRINCIPAL: GESTIÓN DE ALUMNOS
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
#  DIÁLOGO: ALUMNO HISTÓRICO (datos mínimos para digitalización de libros)
# ══════════════════════════════════════════════════════════════════════════════

class AlumnoHistoricoDialog(QDialog):
    """Formulario simplificado para registrar alumnos de los libros físicos."""

    CATEGORIAS = ["A2", "B1", "C1", "C2", "A2 + B1", "A2 + C1", "C2 + A2"]

    def __init__(self, parent=None):
        
        super().__init__(parent)
        self.setWindowTitle("Registrar Alumno Histórico")
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        margen = 40
        ancho_final = min(520, screen.width()  - margen)
        alto_final  = min(700, screen.height() - margen)
        self.setMinimumSize(min(420, ancho_final), min(400, alto_final))
        self.resize(ancho_final, alto_final)
        fg = self.frameGeometry()
        fg.moveCenter(screen.center())
        self.move(fg.topLeft())
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.setModal(True)
        self.setStyleSheet(GLOBAL_QSS if "GLOBAL_QSS" in dir() else "")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(72)
        header.setStyleSheet(f"background: {PAL['amber']}; border-bottom: 3px solid #D4A017;")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(24, 12, 24, 12)
        lbl_t = QLabel("📚  Alumno Histórico")
        lbl_t.setStyleSheet("font-size: 16px; font-weight: 800; color: #FFF;")
        lbl_s = QLabel("Registro rápido para digitalización de libros físicos")
        lbl_s.setStyleSheet("font-size: 11px; color: rgba(255,255,255,0.80);")
        hl.addWidget(lbl_t)
        hl.addWidget(lbl_s)
        root.addWidget(header)

        # Cuerpo
        body = QWidget()
        body.setStyleSheet(f"background: {PAL['bg']};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(28, 24, 28, 24)
        body_lay.setSpacing(14)

        def _campo(label_txt):
            lbl = QLabel(label_txt)
            lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {PAL['blue']}; letter-spacing: 0.05em;")
            return lbl

        campo_style = f"""
            QLineEdit, QComboBox {{
                background: {PAL['surface']}; border: 1.5px solid {PAL['border']};
                border-radius: 8px; padding: 8px 12px; font-size: 13px; color: {PAL['text_1']};
            }}
            QLineEdit:focus, QComboBox:focus {{ border-color: {PAL['blue']}; }}
            QComboBox::drop-down {{ border: none; }}
        """
        body.setStyleSheet(body.styleSheet() + campo_style)

        # Cédula
        body_lay.addWidget(_campo("NÚMERO DE DOCUMENTO *"))
        self.inp_doc = QLineEdit()
        self.inp_doc.setPlaceholderText("Ej: 94427466")
        self.inp_doc.setFixedHeight(40)
        body_lay.addWidget(self.inp_doc)

        # Nombres
        body_lay.addWidget(_campo("NOMBRES *"))
        self.inp_nombres = QLineEdit()
        self.inp_nombres.setPlaceholderText("Ej: Carlos Arturo")
        self.inp_nombres.setFixedHeight(40)
        body_lay.addWidget(self.inp_nombres)

        # Apellidos
        body_lay.addWidget(_campo("APELLIDOS *"))
        self.inp_apellidos = QLineEdit()
        self.inp_apellidos.setPlaceholderText("Ej: Hoyos Patiño")
        self.inp_apellidos.setFixedHeight(40)
        body_lay.addWidget(self.inp_apellidos)

        # Categoría + Año fila
        fila = QHBoxLayout()
        fila.setSpacing(12)
        col_cat = QVBoxLayout()
        col_cat.addWidget(_campo("CATEGORÍA *"))
        self.cmb_cat = QComboBox()
        self.cmb_cat.addItems(self.CATEGORIAS)
        self.cmb_cat.setFixedHeight(40)
        col_cat.addWidget(self.cmb_cat)
        fila.addLayout(col_cat)

        # Día
        col_dia = QVBoxLayout()
        col_dia.addWidget(_campo("DÍA"))
        self.inp_dia = QLineEdit()
        self.inp_dia.setPlaceholderText("Ej: 15")
        self.inp_dia.setFixedHeight(40)
        col_dia.addWidget(self.inp_dia)
        fila.addLayout(col_dia)

        # Mes
        col_mes = QVBoxLayout()
        col_mes.addWidget(_campo("MES"))
        self.inp_mes = QLineEdit()
        self.inp_mes.setPlaceholderText("Ej: 06")
        self.inp_mes.setFixedHeight(40)
        col_mes.addWidget(self.inp_mes)
        fila.addLayout(col_mes)

        # Año
        col_anio = QVBoxLayout()
        col_anio.addWidget(_campo("AÑO"))
        self.inp_anio = QLineEdit()
        self.inp_anio.setPlaceholderText("Ej: 2022")
        self.inp_anio.setFixedHeight(40)
        col_anio.addWidget(self.inp_anio)
        fila.addLayout(col_anio)
        body_lay.addLayout(fila)

        # Precio original
        body_lay.addWidget(_campo("PRECIO ORIGINAL DEL CURSO"))
        self.inp_precio = QLineEdit()
        self.inp_precio.setPlaceholderText("Ej: 1250000  (dejar vacío si no aplica)")
        self.inp_precio.setFixedHeight(40)
        body_lay.addWidget(self.inp_precio)

        
        def _formatear_precio(texto):
            solo_digitos = texto.replace(".", "").replace(",", "").replace("$", "")
            if solo_digitos.isdigit():
                self.inp_precio.blockSignals(True)
                cursor = len(f"{int(solo_digitos):,}".replace(",", "."))
                self.inp_precio.setText(f"{int(solo_digitos):,}".replace(",", "."))
                self.inp_precio.setCursorPosition(cursor)
                self.inp_precio.blockSignals(False)

        self.inp_precio.textChanged.connect(_formatear_precio)

    
        # Abono histórico previo
        body_lay.addWidget(_campo("ABONO PREVIO (lo que ya pagó antes)"))
        self.inp_abono = QLineEdit()
        self.inp_abono.setPlaceholderText("Ej: 100000  (dejar vacío si no pagó nada antes)")
        self.inp_abono.setFixedHeight(40)
        body_lay.addWidget(self.inp_abono)

        def _formatear_abono(texto):
            solo_digitos = texto.replace(".", "").replace(",", "").replace("$", "")
            if solo_digitos.isdigit():
                self.inp_abono.blockSignals(True)
                cursor = len(f"{int(solo_digitos):,}".replace(",", "."))
                self.inp_abono.setText(f"{int(solo_digitos):,}".replace(",", "."))
                self.inp_abono.setCursorPosition(cursor)
                self.inp_abono.blockSignals(False)

        self.inp_abono.textChanged.connect(_formatear_abono)

        # Nota informativa
        nota = QLabel("* Campos obligatorios. El resto se puede completar después desde la ficha del alumno.")
        nota.setWordWrap(True)
        nota.setStyleSheet(f"font-size: 11px; color: {PAL['text_3']}; padding-top: 4px;")
        body_lay.addWidget(nota)

        self.inp_doc.textChanged.connect(lambda: self._limpiar_error(self.inp_doc))
        self.inp_nombres.textChanged.connect(lambda: self._limpiar_error(self.inp_nombres))
        self.inp_apellidos.textChanged.connect(lambda: self._limpiar_error(self.inp_apellidos))
        self.inp_dia.textChanged.connect(lambda: self._limpiar_error(self.inp_dia))
        self.inp_mes.textChanged.connect(lambda: self._limpiar_error(self.inp_mes))
        self.inp_anio.textChanged.connect(lambda: self._limpiar_error(self.inp_anio))
        self.inp_precio.textChanged.connect(lambda: self._limpiar_error(self.inp_precio))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"background: {PAL['bg']}; border: none;")
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Footer
        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet(f"background: {PAL['surface']}; border-top: 1.5px solid {PAL['border_lt']};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 0, 24, 0)
        fl.setSpacing(10)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedHeight(38)
        btn_cancel.setFixedWidth(110)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: {PAL['bg']}; color: {PAL['text_2']};
                border: 1.5px solid {PAL['border']}; border-radius: 8px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {PAL['border_lt']}; }}
        """)
        btn_cancel.clicked.connect(self.reject)
        fl.addWidget(btn_cancel)
        fl.addStretch()

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet(f"font-size: 12px; color: {PAL['coral']}; font-weight: 600;")
        fl.addWidget(self.lbl_error)

        btn_guardar = QPushButton("✓  Guardar histórico")
        btn_guardar.setFixedHeight(38)
        btn_guardar.setFixedWidth(170)
        btn_guardar.setStyleSheet(f"""
            QPushButton {{
                background: {PAL['amber']}; color: #FFF; border: none;
                border-radius: 8px; font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover {{ background: #C8940A; }}
        """)
        btn_guardar.clicked.connect(self._guardar)
        fl.addWidget(btn_guardar)
        root.addWidget(footer)


    def _marcar_error(self, widget):
        widget.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid {PAL['coral']};
                border-radius: 8px;
                background: {PAL['coral_bg']};
                padding: 8px 12px;
                font-size: 13px;
                color: {PAL['text_1']};
            }}
        """)
        widget.setPlaceholderText("⚠ Falta llenar este campo")

    def _limpiar_error(self, widget):
        widget.setStyleSheet("")

    def _guardar(self):
        doc       = self.inp_doc.text().strip()
        nombres   = self.inp_nombres.text().strip()
        apellidos = self.inp_apellidos.text().strip()
        categoria = self.cmb_cat.currentText()
        dia       = self.inp_dia.text().strip() or "01"
        mes       = self.inp_mes.text().strip() or "01"
        anio      = self.inp_anio.text().strip() or "2000"
        precio_texto = self.inp_precio.text().strip().replace(".", "").replace(",", "").replace("$", "")
        
        try:
            precio_original = int(precio_texto) if precio_texto else 0
        except ValueError:
            precio_original = 0

        abono_texto = self.inp_abono.text().strip().replace(".", "").replace(",", "").replace("$", "")
        try:
            abono_previo = int(abono_texto) if abono_texto else 0
        except ValueError:
            abono_previo = 0

        self._limpiar_error(self.inp_doc)
        self._limpiar_error(self.inp_nombres)
        self._limpiar_error(self.inp_apellidos)
        self._limpiar_error(self.inp_dia)
        self._limpiar_error(self.inp_mes)
        self._limpiar_error(self.inp_anio)
        self._limpiar_error(self.inp_precio)

        hay_error = False
        if not doc:
            self._marcar_error(self.inp_doc)
            hay_error = True
        if not nombres:
            self._marcar_error(self.inp_nombres)
            hay_error = True
        if not apellidos:
            self._marcar_error(self.inp_apellidos)
            hay_error = True
        if not self.inp_dia.text().strip():
            self._marcar_error(self.inp_dia)
            hay_error = True
        if not self.inp_mes.text().strip():
            self._marcar_error(self.inp_mes)
            hay_error = True
        if not self.inp_anio.text().strip():
            self._marcar_error(self.inp_anio)
            hay_error = True
        if not self.inp_precio.text().strip():
            self._marcar_error(self.inp_precio)
            hay_error = True
        if hay_error:
            self.lbl_error.setText("⚠ Completa los campos marcados en rojo")
            return

        try:
            db = Database.get_instance()

            # Verificar si ya existe el alumno
            existe = db.fetchone("SELECT numero_documento FROM alumnos WHERE numero_documento = %s", (doc,))
            if existe:
                self.lbl_error.setText("⚠ Ya existe un alumno con esa cédula.")
                return

            # Insertar alumno
            db.execute("""
                INSERT INTO alumnos
                    (numero_documento, tipo_documento, nombres, apellidos,
                    estado_civil, sexo, grupo_sanguineo)
                VALUES (%s, 'CC', %s, %s, 'Soltero', 'M', 'O+')
            """, (doc, nombres, apellidos))

            # Generar número de orden para el año indicado
            from datetime import datetime as _dt
            anio_int = int(anio) if anio.isdigit() else _dt.now().year
            mes_int = int(mes) if mes.isdigit() and 1 <= int(mes) <= 12 else 1
            dia_int = int(dia) if dia.isdigit() and 1 <= int(dia) <= 31 else 1

            ultimo = db.fetchone(
                "SELECT numero_orden FROM matriculas WHERE anio = %s ORDER BY numero_orden DESC LIMIT 1",
                (anio_int,)
            )
            if ultimo and ultimo.get("numero_orden"):
                try:
                    num_nuevo = int(ultimo["numero_orden"]) + 1
                except ValueError:
                    num_nuevo = 1
            else:
                num_nuevo = 1

            from datetime import datetime
            fecha_historico = datetime(anio_int, mes_int, dia_int).strftime("%Y-%m-%d")
            
            db.execute("""
                INSERT INTO matriculas (numero_documento, numero_orden, anio, categoria, estado, precio_total, fecha_registro)
                VALUES (%s, %s, %s, %s, 'Histórico', %s, %s)
            """, (doc, f"{num_nuevo:03d}", anio_int, categoria, precio_original, fecha_historico))

            if abono_previo > 0:
                matricula_row = db.fetchone(
                    "SELECT id FROM matriculas WHERE numero_documento = %s AND anio = %s",
                    (doc, anio_int)
                )
                if matricula_row:
                    db.execute("""
                        INSERT INTO pagos
                            (id_matricula, concepto, valor, metodo_pago, numero_recibo, usuario_id, fecha_pago)
                        VALUES (%s, 'Abono histórico previo', %s, 'Otro', %s, 1, %s)
                    """, (
                        matricula_row["id"],
                        abono_previo,
                        f"HIST-{doc}-{anio_int}",
                        fecha_historico
                    ))

            QMessageBox.information(
                self, "Alumno registrado",
                f"✓ {nombres} {apellidos} registrado como histórico.\n\nAhora puedes abrir su ficha y subir el PDF del expediente."
            )
            self.accept()

        except Exception as e:
            self.lbl_error.setText(f"Error: {str(e)[:60]}")


class PreciosDialog(QDialog):
    """Permite editar los precios por categoría y guardarlos en precios.json."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar precios por categoría")
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        margen = 40
        ancho_final = min(440, screen.width()  - margen)
        alto_final  = min(600, screen.height() - margen)
        self.setMinimumSize(min(360, ancho_final), min(300, alto_final))
        self.resize(ancho_final, alto_final)
        fg = self.frameGeometry()
        fg.moveCenter(screen.center())
        self.move(fg.topLeft())
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.setModal(True)
        self.setStyleSheet(GLOBAL_QSS)
        self._fields = {}
        self._build()

    def _build(self):
        import json
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(64)
        header.setStyleSheet(f"background: {PAL['blue']};")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(24, 12, 24, 12)
        lbl = QLabel("💲  Precios por categoría")
        lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #FFF;")
        hl.addWidget(lbl)
        root.addWidget(header)

        body = QWidget()
        body.setStyleSheet(f"background: {PAL['bg']};")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        precios = _cargar_precios()
        for cat, precio in precios.items():
            fila = QHBoxLayout()
            lbl_cat = QLabel(cat)
            lbl_cat.setFixedWidth(110)
            lbl_cat.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {PAL['text_1']};")
            inp = QLineEdit(str(precio))
            inp.setFixedHeight(38)
            inp.setStyleSheet(f"""
                QLineEdit {{
                    background: {PAL['surface']}; border: 1.5px solid {PAL['border']};
                    border-radius: 7px; padding: 6px 10px; font-size: 13px; color: {PAL['text_1']};
                }}
                QLineEdit:focus {{ border-color: {PAL['blue']}; }}
            """)
            self._fields[cat] = inp
            fila.addWidget(lbl_cat)
            fila.addWidget(inp)
            lay.addLayout(fila)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"background: {PAL['bg']}; border: none;")
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        footer = QWidget()
        footer.setFixedHeight(60)
        footer.setStyleSheet(f"background: {PAL['surface']}; border-top: 1.5px solid {PAL['border_lt']};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 0, 20, 0)
        fl.setSpacing(10)

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet(f"font-size: 12px; color: {PAL['coral']}; font-weight: 600;")
        fl.addWidget(self.lbl_error)
        fl.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setFixedWidth(100)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: {PAL['bg']}; color: {PAL['text_2']};
                border: 1.5px solid {PAL['border']}; border-radius: 7px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {PAL['border_lt']}; }}
        """)
        btn_cancel.clicked.connect(self.reject)
        fl.addWidget(btn_cancel)

        btn_guardar = QPushButton("✓  Guardar")
        btn_guardar.setFixedHeight(36)
        btn_guardar.setFixedWidth(110)
        btn_guardar.setStyleSheet(f"""
            QPushButton {{
                background: {PAL['blue']}; color: #FFF; border: none;
                border-radius: 7px; font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {PAL['blue_dark']}; }}
        """)
        btn_guardar.clicked.connect(self._guardar)
        fl.addWidget(btn_guardar)
        root.addWidget(footer)

    def _guardar(self):
        import json
        nuevos = {}
        for cat, inp in self._fields.items():
            txt = inp.text().strip().replace(".", "").replace(",", "")
            try:
                nuevos[cat] = int(txt)
            except ValueError:
                self.lbl_error.setText(f"⚠ Precio inválido en {cat}")
                return

        _ruta = os.path.join(os.path.dirname(__file__), '..', 'precios.json')
        try:
            with open(_ruta, 'w', encoding='utf-8') as f:
                json.dump(nuevos, f, ensure_ascii=False, indent=4)
            global PRECIOS_LICENCIA
            PRECIOS_LICENCIA = nuevos
            QMessageBox.information(self, "Guardado", "✓ Precios actualizados correctamente.\n\nAl crear el próximo alumno ya se usarán los nuevos precios.")
            self.accept()
        except Exception as e:
            self.lbl_error.setText(f"Error: {str(e)[:50]}")

class AlumnosView(QWidget):
    # Señal que se emite cuando se registra un alumno nuevo
    alumno_registrado = pyqtSignal()
    """Vista principal de alumnos — estilo PRACTICAR refinado."""

    ESTADO_STYLES = {
        "Activo":         (PAL["teal_bg"],   PAL["teal"]),
        "Completado":     (PAL["blue_bg"],   PAL["blue"]),
        "Pendiente Pago": (PAL["amber_bg"],  PAL["amber"]),
        "Cancelado":      (PAL["coral_bg"],  PAL["coral"]),
        "Histórico":      (PAL["bg"],        PAL["text_3"]),
    }

    def __init__(self):
        super().__init__()
        self._mes_seleccionado = None
        self.setStyleSheet(f"background-color: {PAL['bg']};" + GLOBAL_QSS)
        self.setup_ui()
        self.load_alumnos()
    
    def _calcular_estado(self, matricula_id, precio_total):
        try:
            db = Database.get_instance()
            result = db.fetchone("""
                SELECT COALESCE(SUM(valor), 0) AS total
                FROM pagos WHERE id_matricula = %s
            """, (matricula_id,))
            pagado = int(result["total"] if result and result["total"] else 0)
            if pagado >= precio_total and precio_total > 0:
                return "Cancelado"
            elif pagado > 0:
                return "Pendiente Pago"
            else:
                return "Activo"
        except:
            return "Activo"

    def setup_ui(self):
        # Capa exterior: la vista solo contiene un scroll, sin márgenes
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Capa interior: aquí vive el contenido real, exactamente como antes
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(20)

        header = QHBoxLayout()
        header.setSpacing(14)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_title = QLabel("Gestión de Alumnos")
        lbl_title.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {PAL['text_1']};")
        title_col.addWidget(lbl_title)
        lbl_sub = QLabel("Consulta, registra y administra el historial de cada alumno")
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {PAL['text_2']};")
        title_col.addWidget(lbl_sub)
        header.addLayout(title_col)

        header.addStretch()

        search_wrap = QWidget()
        search_wrap.setMinimumWidth(180)
        search_wrap.setMaximumWidth(360)
        search_wrap.setStyleSheet(f"""
            QWidget {{
                background: {PAL['surface']};
                border: 1.5px solid {PAL['border']};
                border-radius: 9px;
            }}
        """)
        search_inner = QHBoxLayout(search_wrap)
        search_inner.setContentsMargins(12, 0, 12, 0)
        search_inner.setSpacing(8)

        lbl_ico = QLabel("🔍")
        lbl_ico.setStyleSheet("background: transparent; border: none; font-size: 14px;")
        search_inner.addWidget(lbl_ico)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por nombre, cédula o categoría...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 13px;
                padding: 10px 0;
            }
            QLineEdit:focus { border: none; }
        """)
        self.search_input.textChanged.connect(self.filter_table)
        search_inner.addWidget(self.search_input)

        header.addWidget(search_wrap)

        btn_nuevo = make_btn_primary("+ Nuevo Alumno")
        btn_nuevo.clicked.connect(self.nuevo_alumno)
        header.addWidget(btn_nuevo)

        self.cmb_anio = QComboBox()
        self.cmb_anio.setFixedHeight(38)
        self.cmb_anio.setMinimumWidth(100)
        self.cmb_anio.setMaximumWidth(130)
        self.cmb_anio.setStyleSheet(f"""
            QComboBox {{
                background: {PAL['surface']}; color: {PAL['text_1']};
                border: 1.5px solid {PAL['border']}; border-radius: 9px;
                padding: 0 10px; font-size: 13px;
            }}
            QComboBox::drop-down {{ border: none; }}
        """)
        self._cargar_anios_combo()
        self.cmb_anio.currentTextChanged.connect(self._on_anio_changed)
        header.addWidget(self.cmb_anio)

        btn_historico = QPushButton("📚  Alumno Histórico")
        btn_historico.setFixedHeight(38)
        btn_historico.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_historico.setStyleSheet(f"""
            QPushButton {{
                background: {PAL['amber_bg']}; color: {PAL['amber']};
                border: 1.5px solid {PAL['amber']}; border-radius: 9px;
                padding: 0 18px; font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover {{ background: #F5E1B0; }}
        """)
        btn_historico.clicked.connect(self.nuevo_alumno_historico)
        header.addWidget(btn_historico)

        btn_precios = QPushButton("💲  Precios")
        btn_precios.setFixedHeight(38)
        btn_precios.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_precios.setStyleSheet(f"""
            QPushButton {{
                background: {PAL['teal_bg']}; color: {PAL['teal']};
                border: 1.5px solid {PAL['teal']}; border-radius: 9px;
                padding: 0 18px; font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover {{ background: #C5EBE0; }}
        """)
        btn_precios.clicked.connect(lambda: PreciosDialog(parent=self).exec())
        header.addWidget(btn_precios)

        root.addLayout(header)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)

        self.stat_widgets = {}
        stats_data = [
            ("total",    "Total alumnos",    "0",  PAL["blue"],  PAL["blue_bg"]),
            ("activos",  "Activos",           "0",  PAL["teal"],  PAL["teal_bg"]),
            ("pendiente","Pendiente pago",    "0",  PAL["amber"], PAL["amber_bg"]),
            ("cancelado","Cancelados",        "0",  PAL["coral"], PAL["coral_bg"]),
        ]
        for key, label, val, color, bg in stats_data:
            card = self._make_stat_card(label, val, color, bg)
            self.stat_widgets[key] = card["value_lbl"]
            stats_row.addWidget(card["widget"])

        root.addLayout(stats_row)

        self.table = QTableWidget()
        self.table.setObjectName("alumnosTable")
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "#", "Código", "Documento", "Nombres", "Apellidos", "Categoría",
            "Estado", "Fecha Registro", "Progreso", "Acciones"
        ])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setDefaultSectionSize(54)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(4, 110)
        self.table.setColumnWidth(5, 120)
        self.table.setColumnWidth(6, 170)
        self.table.setColumnWidth(7, 130)
        self.table.setColumnWidth(8, 260)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(9, 130)
        self.table.verticalHeader().setDefaultSectionSize(58)

        self.table.horizontalHeader().setStyleSheet(f"""
            QHeaderView::section {{
                background-color: {PAL['blue']};
                padding: 13px 14px;
                border: none;
                border-right: 1px solid rgba(255,255,255,0.10);
                font-weight: 700;
                font-size: 11px;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                color: rgba(255,255,255,0.85);
            }}
            QHeaderView::section:first {{
                border-top-left-radius: 10px;
            }}
            QHeaderView::section:last {{
                border-top-right-radius: 10px;
                border-right: none;
            }}
        """)

        add_shadow(self.table, blur=14, offset_y=3, opacity=0.05)
        root.addWidget(self.table)

        # ── Sección: Estudiantes por Mes ──────────────────────────────
        root.addWidget(make_section_label("Estudiantes por Mes"))
        self.mes_scroll = QScrollArea()
        self.mes_scroll.setWidgetResizable(True)
        self.mes_scroll.setFixedHeight(130)
        self.mes_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.mes_scroll.setStyleSheet("background: transparent; border: none;")
        self.mes_container = QWidget()
        self.mes_container.setStyleSheet("background: transparent;")
        self.mes_layout = QHBoxLayout(self.mes_container)
        self.mes_layout.setContentsMargins(0, 4, 0, 4)
        self.mes_layout.setSpacing(10)
        self.mes_layout.addStretch()
        self.mes_scroll.setWidget(self.mes_container)
        root.addWidget(self.mes_scroll)

        footer_row = QHBoxLayout()
        self.lbl_count = QLabel("Mostrando 0 registros")
        self.lbl_count.setStyleSheet(f"font-size: 12px; color: {PAL['text_3']};")
        footer_row.addWidget(self.lbl_count)
        footer_row.addStretch()

        btn_export = make_btn_secondary("↓  Exportar PDF")
        btn_export.setFixedHeight(36)
        footer_row.addWidget(btn_export)

        root.addLayout(footer_row)

        scroll.setWidget(body)
        root_layout.addWidget(scroll)

    def _make_stat_card(self, label, value, color, bg):
        widget = QWidget()
        widget.setStyleSheet(f"""
            QWidget {{
                background-color: {PAL['surface']};
                border-radius: 10px;
                border: 1px solid {PAL['border_lt']};
            }}
        """)
        add_shadow(widget, blur=10, offset_y=2, opacity=0.05)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"background: {color}; border-radius: 5px; border: none;")
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size: 11px; color: {PAL['text_2']}; font-weight: 500;")
        text_col.addWidget(lbl)

        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {PAL['text_1']};")
        text_col.addWidget(val_lbl)

        layout.addLayout(text_col)
        layout.addStretch()

        return {"widget": widget, "value_lbl": val_lbl}

    def load_alumnos(self):
        db = Database.get_instance()
        try:
            db._connection.commit()  # ← fuerza lectura fresca
        except Exception:
            pass
        try:
            db = Database.get_instance()
            anio_filtro = getattr(self, '_anio_filtro', None)
            where_anio = ""
            params = ()
            if anio_filtro:
                where_anio = "WHERE m.anio = %s"
                params = (anio_filtro,)
            
            rows = db.fetchall(f"""
                SELECT
                    m.numero_orden,
                    m.anio,
                    a.numero_documento,
                    a.nombres,
                    a.apellidos,
                    m.categoria,
                    m.estado,
                    m.precio_total,
                    DATE_FORMAT(m.fecha_registro, '%Y-%m-%d') AS fecha_registro,
                    m.id AS matricula_id,
                    COALESCE((SELECT SUM(p.valor) FROM pagos p WHERE p.id_matricula = m.id), 0) AS total_pagado
                FROM matriculas m
                JOIN alumnos a ON a.numero_documento = m.numero_documento
                {where_anio}
                ORDER BY m.fecha_registro DESC
            """, params)

            TOTAL_POR_CAT = {
                "A2": 20, "B1": 30, "C1": 40, "C2": 40,
                "A2 + B1": 50, "A2 + C1": 60, "C2 + A2": 60,
                "Renovación": 10, "Renovación x2": 20,
            }

            self.all_alumnos = [
                (
                    f"{r['numero_orden']}-{str(r['anio'])[-2:]}",  # código visible: "001-26"
                    r["numero_documento"],
                    r["nombres"],
                    r["apellidos"],
                    r["categoria"],
                    r["estado"] if r["estado"] == "Histórico" else self._calcular_estado(r["matricula_id"], int(r.get("precio_total") or 0)),                    r["fecha_registro"] or "",
                    r["matricula_id"],          # ← ahora es id de matrícula, no de alumno
                    int(r["total_pagado"] or 0),
                    int(r.get("precio_total") or 0),
                )
                for r in rows
            ]
        except (ConnectionError, RuntimeError) as e:
            QMessageBox.critical(self, "Error de conexión", str(e))
            self.all_alumnos = []

        self._render_table(self.all_alumnos)
        self._update_stats(self.all_alumnos)
        self._load_meses()

    def _render_table(self, data):
        self.table.setRowCount(len(data))

        for i, row in enumerate(data):
            codigo, doc, nom, ape, cat, estado, fecha, alumno_id, total_pagado, precio_total = row

            num_item = QTableWidgetItem(f"{i+1:03d}")
            num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            num_item.setForeground(QColor(PAL["text_3"]))
            num_item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 0, num_item)

            cod_item = QTableWidgetItem(str(codigo))
            cod_item.setFlags(cod_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            cod_item.setForeground(QColor(PAL["blue"]))
            cod_item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            cod_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 1, cod_item)

            for col_offset, val in enumerate([doc, nom, ape, cat, estado, fecha]):
                col = col_offset + 2

                if col == 7 and val:
                    try:
                        from datetime import datetime as _dt
                        _MESES = ["","enero","febrero","marzo","abril","mayo","junio",
                                  "julio","agosto","septiembre","octubre","noviembre","diciembre"]
                        d = _dt.strptime(str(val), "%Y-%m-%d")
                        display_val = f"{d.day} de {_MESES[d.month]} de {d.year}"
                    except Exception:
                        display_val = str(val)
                else:
                    display_val = str(val) if val else ""

                if col == 5:
                    # Badges de categoría: A=coral, B=blue, C=teal, combinadas=amber, Renovación=green
                    CAT_COLORS = {
                        "A2":          (PAL["coral_bg"],  PAL["coral"]),
                        "B1":          (PAL["blue_bg"],   PAL["blue"]),
                        "C1":          (PAL["teal_bg"],   PAL["teal"]),
                        "C2":          (PAL["teal_bg"],   PAL["teal"]),
                        "A2 + B1":     (PAL["amber_bg"],  PAL["amber"]),
                        "A2 + C1":     (PAL["amber_bg"],  PAL["amber"]),
                        "C2 + A2":     (PAL["amber_bg"],  PAL["amber"]),
                        "Renovación":  (PAL["bg"],        PAL["text_2"]),
                        "Renovación x2": (PAL["bg"],      PAL["text_2"]),
                    }
                    cbg, cfg = CAT_COLORS.get(str(val), (PAL["bg"], PAL["text_2"]))
                    cat_w = QWidget()
                    cat_w.setStyleSheet("background: transparent;")
                    cat_l = QHBoxLayout(cat_w)
                    cat_l.setContentsMargins(10, 0, 8, 0)
                    cat_l.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    lbl_cat = QLabel(display_val)
                    lbl_cat.setStyleSheet(f"""
                        background: {cbg}; color: {cfg};
                        border-radius: 8px;
                        padding: 3px 12px;
                        font-size: 12px; font-weight: 700;
                    """)
                    cat_l.addWidget(lbl_cat)
                    self.table.setCellWidget(i, col, cat_w)
                    continue

                if col == 6:
                    bg, fg = self.ESTADO_STYLES.get(val, (PAL["bg"], PAL["text_2"]))
                    est_w = QWidget()
                    est_w.setStyleSheet("background: transparent;")
                    est_l = QHBoxLayout(est_w)
                    est_l.setContentsMargins(10, 0, 8, 0)
                    est_l.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    lbl_est = QLabel(display_val)
                    lbl_est.setStyleSheet(f"""
                        background: {bg}; color: {fg};
                        border-radius: 8px;
                        padding: 3px 12px;
                        font-size: 12px; font-weight: 600;
                    """)
                    est_l.addWidget(lbl_est)
                    self.table.setCellWidget(i, col, est_w)
                    continue

                item = QTableWidgetItem(display_val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, col, item)

            # Barra de progreso
            prog_w = QWidget()
            prog_w.setStyleSheet("background: transparent;")
            prog_l = QHBoxLayout(prog_w)
            prog_l.setContentsMargins(10, 0, 10, 0)
            prog_l.setSpacing(8)
            prog_l.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            if precio_total > 0:
                prog_val = min(int((total_pagado / precio_total) * 100), 100)
            elif estado == "Completado":
                prog_val = 100
            else:
                prog_val = 0

            prog_color = {
                "Activo":         PAL["teal"],
                "Completado":     PAL["blue"],
                "Pendiente Pago": PAL["amber"],
                "Cancelado":      PAL["coral"],
            }.get(estado, PAL["text_3"])

            from PyQt6.QtWidgets import QProgressBar as _PB
            bar = _PB()
            bar.setValue(prog_val)
            bar.setTextVisible(False)
            bar.setFixedHeight(7)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background: {PAL['border_lt']};
                    border-radius: 4px;
                    border: none;
                }}
                QProgressBar::chunk {{
                    background: {prog_color};
                    border-radius: 4px;
                }}
            """)
            prog_l.addWidget(bar, 1)

            lbl_pct = QLabel(f"{prog_val}%")
            lbl_pct.setFixedWidth(34)
            lbl_pct.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {prog_color};")
            prog_l.addWidget(lbl_pct)
            self.table.setCellWidget(i, 8, prog_w)

            # Acciones
            
            actions_widget = QWidget()
            actions_widget.setStyleSheet("background: transparent;")
            al = QHBoxLayout(actions_widget)
            al.setContentsMargins(8, 6, 8, 6)
            al.setAlignment(Qt.AlignmentFlag.AlignCenter)

            btn_menu = QPushButton("⋯  Acciones")
            btn_menu.setFixedHeight(32)
            btn_menu.setFixedWidth(110)
            btn_menu.setStyleSheet(f"""
                QPushButton {{
                    font-size: 12px; font-weight: 600;
                    background-color: {PAL['blue_bg']}; color: {PAL['blue']};
                    border: 1.5px solid {PAL['blue']}; border-radius: 7px; padding: 0 10px;
                }}
                QPushButton:hover {{ background-color: {PAL['blue']}; color: #FFF; }}
                QPushButton::menu-indicator {{ image: none; }}
            """)

            menu = QMenu(btn_menu)
            menu.setStyleSheet(f"""
                QMenu {{
                    background: {PAL['surface']}; border: 1.5px solid {PAL['border']};
                    border-radius: 8px; padding: 4px;
                }}
                QMenu::item {{
                    padding: 8px 20px; font-size: 13px; color: {PAL['text_1']};
                    border-radius: 6px;
                }}
                QMenu::item:selected {{ background: {PAL['blue_bg']}; color: {PAL['blue']}; }}
            """)

            act_ver = menu.addAction("👁  Ver")
            act_editar = menu.addAction("✏  Editar")
            menu.addSeparator()
            act_eliminar = menu.addAction("✕  Eliminar")

            act_ver.triggered.connect(lambda _, aid=alumno_id: self.ver_alumno(aid))
            act_editar.triggered.connect(lambda _, aid=alumno_id: self.editar_alumno(aid))
            act_eliminar.triggered.connect(lambda _, aid=alumno_id, n=f"{nom} {ape}": self.eliminar_alumno(aid, n))

            btn_menu.setMenu(menu)
            al.addWidget(btn_menu)
            self.table.setCellWidget(i, 9, actions_widget)

        self.lbl_count.setText(f"Mostrando {len(data)} registro{'s' if len(data) != 1 else ''}")

    def _update_stats(self, data):
        conteos = {"total": len(data), "activos": 0, "pendiente": 0, "cancelado": 0}
        for row in data:
            estado = row[5]
            if estado == "Activo":
                conteos["activos"] += 1
            elif estado == "Pendiente Pago":
                conteos["pendiente"] += 1
            elif estado == "Cancelado":
                conteos["cancelado"] += 1

        for key, lbl in self.stat_widgets.items():
            lbl.setText(str(conteos.get(key, 0)))
            
    def _cargar_anios_combo(self):
        try:
            db = Database.get_instance()
            rows = db.fetchall("SELECT DISTINCT anio FROM matriculas ORDER BY anio DESC")
            self.cmb_anio.clear()
            self.cmb_anio.addItem("Todos los años")
            for r in rows:
                self.cmb_anio.addItem(str(r["anio"]))
        except Exception:
            self.cmb_anio.clear()
            self.cmb_anio.addItem("Todos los años")
            from datetime import datetime as _dt
            anio_actual = _dt.now().year
            for a in range(anio_actual, anio_actual - 5, -1):
                self.cmb_anio.addItem(str(a))

    def _on_anio_changed(self, texto):
        if texto == "Todos los años" or not texto:
            self._anio_filtro = None
        else:
            try:
                self._anio_filtro = int(texto)
            except ValueError:
                self._anio_filtro = None
        self.load_alumnos()
    def _load_meses(self):
        while self.mes_layout.count() > 1:
            item = self.mes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        try:
            from datetime import datetime as _dt
            anio_actual = _dt.now().year
            db = Database.get_instance()
            rows = db.fetchall("""
                SELECT MONTH(fecha_registro) AS mes, COUNT(*) AS total
                FROM matriculas
                WHERE YEAR(fecha_registro) = %s
                GROUP BY MONTH(fecha_registro)
                ORDER BY mes
            """, (anio_actual,))
            conteo_mes = {r["mes"]: int(r["total"]) for r in rows}
        except Exception:
            conteo_mes = {}

        import datetime
        mes_actual = datetime.datetime.now().month
        self._mes_seleccionado = getattr(self, "_mes_seleccionado", None)

        for num_mes in range(1, 13):
            total = conteo_mes.get(num_mes, 0)
            es_actual = (num_mes == mes_actual)
            es_seleccionado = (self._mes_seleccionado == num_mes)

            if es_seleccionado:
                border_color = PAL["coral"]
                bg_color = PAL["coral_bg"]
            elif es_actual:
                border_color = PAL["blue"]
                bg_color = PAL["blue_bg"]
            else:
                border_color = PAL["border_lt"]
                bg_color = PAL["surface"]

            card = QPushButton()
            card.setFixedSize(88, 90)
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setStyleSheet(f"""
                QPushButton {{
                    background: {bg_color};
                    border-radius: 10px;
                    border: 2px solid {border_color};
                }}
                QPushButton:hover {{
                    background: {PAL['blue_bg']};
                    border: 2px solid {PAL['blue']};
                }}
            """)

            cl = QVBoxLayout(card)
            cl.setContentsMargins(8, 10, 8, 10)
            cl.setSpacing(4)
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            num_color = PAL["coral"] if es_seleccionado else (PAL["blue"] if es_actual else (PAL["teal"] if total > 0 else PAL["text_3"]))
            lbl_num = QLabel(str(total))
            lbl_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_num.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {num_color}; background: transparent;")
            lbl_num.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            cl.addWidget(lbl_num)

            lbl_mes = QLabel(MESES[num_mes - 1][:3].upper())
            lbl_mes.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_mes.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {PAL['text_3']}; letter-spacing: 0.08em; background: transparent;")
            lbl_mes.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            cl.addWidget(lbl_mes)

            card.clicked.connect(lambda _, m=num_mes: self._toggle_mes(m))
            self.mes_layout.insertWidget(self.mes_layout.count() - 1, card)

    def _toggle_mes(self, num_mes: int):
        if self._mes_seleccionado == num_mes:
            self._mes_seleccionado = None
        else:
            self._mes_seleccionado = num_mes

        self._load_meses()

        texto = self.search_input.text().lower()

        if self._mes_seleccionado is None:
            if not texto:
                self._render_table(self.all_alumnos)
                self._update_stats(self.all_alumnos)
            else:
                filtered = [r for r in self.all_alumnos if any(texto in str(c).lower() for c in r)]
                self._render_table(filtered)
                self._update_stats(filtered)
        else:
            from datetime import datetime as _dt
            def _es_del_mes(row):
                try:
                    d = _dt.strptime(str(row[6]), "%Y-%m-%d")
                    return d.month == self._mes_seleccionado
                except Exception:
                    return False

            filtered = [r for r in self.all_alumnos if _es_del_mes(r)]
            if texto:
                filtered = [r for r in filtered if any(texto in str(c).lower() for c in r)]
            self._render_table(filtered)
            self._update_stats(filtered)

    def filter_table(self, text):
        text = text.lower()
        mes = getattr(self, "_mes_seleccionado", None)

        from datetime import datetime as _dt
        def _es_del_mes(row):
            if mes is None:
                return True
            try:
                d = _dt.strptime(str(row[6]), "%Y-%m-%d")
                return d.month == mes
            except Exception:
                return False

        filtered = [
            r for r in self.all_alumnos
            if _es_del_mes(r) and (not text or any(text in str(c).lower() for c in r))
        ]
        self._render_table(filtered)
        self._update_stats(filtered)

    def nuevo_alumno(self):
        dialog = AlumnoDialog(parent=self)

        if dialog.exec():
            self.load_alumnos()
            self.alumno_registrado.emit()  # Notifica al badge de RUNT

    def nuevo_alumno_historico(self):
        """Crea un alumno histórico con solo los datos mínimos."""
        dialog = AlumnoHistoricoDialog(parent=self)
        if dialog.exec():
            self._cargar_anios_combo()
            self.load_alumnos()

    def editar_alumno(self, alumno_id: int):
        dialog = AlumnoDialog(alumno_id=alumno_id, parent=self)
        if dialog.exec():
            self.load_alumnos()

    def ver_alumno(self, alumno_id: int):
        dialog = AlumnoVerDialog(alumno_id=alumno_id, parent=self)
        dialog.exec()
        self.load_alumnos()

    def eliminar_alumno(self, matricula_id: int, nombre: str):
        try:
            db = Database.get_instance()

            # Guardar numero_documento ANTES de borrar
            mat = db.fetchone("SELECT numero_documento FROM matriculas WHERE id = %s", (matricula_id,))
            num_doc = mat["numero_documento"] if mat else None

            pagos        = db.fetchone("SELECT COUNT(*) AS total FROM pagos        WHERE id_matricula = %s", (matricula_id,))
            clases       = db.fetchone("SELECT COUNT(*) AS total FROM clases       WHERE id_matricula = %s", (matricula_id,))
            evaluaciones = db.fetchone("SELECT COUNT(*) AS total FROM evaluaciones WHERE id_matricula = %s", (matricula_id,))

            n_pagos        = pagos["total"]        if pagos        else 0
            n_clases       = clases["total"]       if clases       else 0
            n_evaluaciones = evaluaciones["total"] if evaluaciones else 0

            tiene_asociados = n_pagos > 0 or n_clases > 0 or n_evaluaciones > 0

            if tiene_asociados:
                detalle = []
                if n_pagos        > 0: detalle.append(f"• {n_pagos} pago{'s' if n_pagos != 1 else ''}")
                if n_clases       > 0: detalle.append(f"• {n_clases} clase{'s' if n_clases != 1 else ''}")
                if n_evaluaciones > 0: detalle.append(f"• {n_evaluaciones} evaluación{'es' if n_evaluaciones != 1 else ''}")
                texto = (
                    f"<b>{nombre}</b> tiene registros asociados que también serán eliminados:\n\n"
                    + "\n".join(detalle)
                    + "\n\n<b>Esta acción no se puede deshacer.</b> ¿Deseas continuar?"
                )
            else:
                texto = f"¿Estás seguro de que deseas eliminar la matrícula de <b>{nombre}</b>?\n\nEsta acción no se puede deshacer."

            confirm = QMessageBox(self)
            confirm.setWindowTitle("Confirmar eliminación")
            confirm.setText(texto)
            confirm.setIcon(QMessageBox.Icon.Warning)
            confirm.setStyleSheet(f"""
                QMessageBox {{ background-color: {PAL['surface']}; }}
                QMessageBox QLabel {{ color: {PAL['text_1']}; font-size: 13px; }}
                QPushButton {{
                    background-color: {PAL['bg']}; color: {PAL['text_1']};
                    border: 1.5px solid {PAL['border']}; border-radius: 8px;
                    padding: 8px 20px; font-size: 13px; font-weight: 500; min-width: 110px;
                }}
                QPushButton:hover {{ background-color: {PAL['border_lt']}; }}
            """)
            btn_si     = confirm.addButton("Sí, eliminar", QMessageBox.ButtonRole.AcceptRole)
            btn_cancel = confirm.addButton("Cancelar",     QMessageBox.ButtonRole.RejectRole)
            confirm.setDefaultButton(btn_cancel)
            confirm.exec()

            if confirm.clickedButton() != btn_si:
                return

            # Borrar en orden correcto
            if n_evaluaciones > 0:
                db.execute("DELETE FROM evaluaciones WHERE id_matricula = %s", (matricula_id,))
            if n_clases > 0:
                db.execute("DELETE FROM clases       WHERE id_matricula = %s", (matricula_id,))
            if n_pagos > 0:
                db.execute("DELETE FROM pagos        WHERE id_matricula = %s", (matricula_id,))
            db.execute("DELETE FROM matriculas WHERE id = %s", (matricula_id,))

            # Si el alumno ya no tiene más matrículas, borrarlo también
            if num_doc:
                otras = db.fetchone(
                    "SELECT COUNT(*) AS total FROM matriculas WHERE numero_documento = %s", (num_doc,)
                )
                if otras and otras["total"] == 0:
                    db.execute("DELETE FROM alumnos WHERE numero_documento = %s", (num_doc,))

            self.load_alumnos()

            msg = QMessageBox(self)
            msg.setWindowTitle("Eliminado")
            msg.setText(f"Matrícula de <b>{nombre}</b> eliminada correctamente.")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setStyleSheet(f"background-color: {PAL['surface']};")
            msg.exec()

        except (ConnectionError, RuntimeError) as e:
            QMessageBox.critical(self, "Error", str(e))