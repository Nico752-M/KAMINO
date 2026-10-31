#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
practicar_style.py
==================
Estilo global del sistema CEA PRACTICAR.
Reemplaza completamente la función setup_app_style() en main.py.

USO EN main.py:
    from practicar_style import setup_app_style
    setup_app_style(app)

FUENTES:
    Si Bebas Neue y Nunito no están instaladas en el sistema,
    coloca los archivos .ttf en src/assets/fonts/ y este módulo
    los cargará automáticamente con QFontDatabase.
"""

import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QFontDatabase, QPalette, QColor

# ── Colores de la paleta PRACTICAR (úsalos en tus vistas) ──────────────────
ROJO          = "#C8252A"
ROJO_DARK     = "#9E1C20"
ROJO_LIGHT    = "#f9e8e8"
AZUL          = "#1A2B6B"
AZUL_MID      = "#263894"
AZUL_LIGHT    = "#e8ecf9"
BLANCO        = "#FFFFFF"
GRIS_FONDO    = "#F3F4F8"
GRIS_CARD     = "#FFFFFF"
GRIS_BORDE    = "#E0E3EE"
GRIS_TEXTO    = "#6B7080"
VERDE         = "#1DA462"
VERDE_LIGHT   = "#e6f7ef"
AMARILLO      = "#E8A020"
AMARILLO_LIGHT= "#fef3e2"
SIDEBAR_BG    = "#111827"
SIDEBAR_HOVER = "#1f2a40"

# ── QSS completo ────────────────────────────────────────────────────────────
QSS = """
/* ═══════════════════════════════════════════════════
   GLOBAL
═══════════════════════════════════════════════════ */
QMainWindow, QWidget {
    background-color: #F3F4F8;
    color: #1A2B6B;
    font-family: 'Nunito', 'Segoe UI', sans-serif;
}

/* ═══════════════════════════════════════════════════
   BOTÓN PRIMARIO  (rojo PRACTICAR)
═══════════════════════════════════════════════════ */
QPushButton {
    background-color: #C8252A;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-family: 'Nunito', 'Segoe UI', sans-serif;
    font-weight: 700;
    font-size: 13px;
}
QPushButton:hover   { background-color: #9E1C20; }
QPushButton:pressed { background-color: #7a1418; }
QPushButton:disabled {
    background-color: #E0E3EE;
    color: #9CA3AF;
}

/* Botón secundario — usa setProperty("class","btn-secondary") */
QPushButton[class="btn-secondary"] {
    background-color: #FFFFFF;
    color: #1A2B6B;
    border: 1.5px solid #E0E3EE;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton[class="btn-secondary"]:hover {
    background-color: #e8ecf9;
    border-color: #263894;
}

/* Botón azul — usa setProperty("class","btn-azul") */
QPushButton[class="btn-azul"] {
    background-color: #1A2B6B;
}
QPushButton[class="btn-azul"]:hover { background-color: #263894; }

/* Botón verde — usa setProperty("class","btn-verde") */
QPushButton[class="btn-verde"] {
    background-color: #1DA462;
}
QPushButton[class="btn-verde"]:hover { background-color: #178a52; }

/* ═══════════════════════════════════════════════════
   INPUTS
═══════════════════════════════════════════════════ */
QLineEdit {
    border: 1.5px solid #E0E3EE;
    border-radius: 8px;
    padding: 10px 14px;
    background-color: #FFFFFF;
    font-size: 13px;
    color: #1A2B6B;
    font-family: 'Nunito', 'Segoe UI', sans-serif;
}
QLineEdit:focus {
    border: 2px solid #0033A0;
    background-color: #FFFFFF;
}
QLineEdit:disabled {
    background-color: #F3F4F8;
    color: #9CA3AF;
}

QTextEdit {
    border: 1.5px solid #E0E3EE;
    border-radius: 8px;
    padding: 8px 12px;
    background-color: #FFFFFF;
    font-size: 13px;
    color: #1A2B6B;
    font-family: 'Nunito', 'Segoe UI', sans-serif;
}
QTextEdit:focus { border: 2px solid #C8252A; }

/* ═══════════════════════════════════════════════════
   COMBOBOX
═══════════════════════════════════════════════════ */
QComboBox {
    border: 1.5px solid #E0E3EE;
    border-bottom: 1.5px solid #E0E3EE;
    border-radius: 8px;
    padding: 9px 14px;
    background-color: #FFFFFF;
    font-size: 13px;
    color: #1A2B6B;
    font-family: 'Nunito', 'Segoe UI', sans-serif;
    min-width: 100px;
}
QComboBox:focus { border: 2px solid #0033A0; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #E0E3EE;
    border-radius: 8px;
    selection-background-color: #e8ecf9;
    selection-color: #1A2B6B;
    font-size: 13px;
}

/* ═══════════════════════════════════════════════════
   SPINBOX
═══════════════════════════════════════════════════ */
QDoubleSpinBox, QSpinBox {
    border: 1.5px solid #E0E3EE;
    border-radius: 8px;
    padding: 9px 14px;
    background-color: #FFFFFF;
    font-size: 13px;
    color: #1A2B6B;
    font-family: 'Nunito', 'Segoe UI', sans-serif;
}
QDoubleSpinBox:focus, QSpinBox:focus { border: 2px solid #C8252A; }

/* ═══════════════════════════════════════════════════
   TABLAS
═══════════════════════════════════════════════════ */
QTableWidget {
    border: 1px solid #E0E3EE;
    border-radius: 12px;
    background-color: #FFFFFF;
    gridline-color: #F3F4F8;
    font-size: 13px;
    color: #1A2B6B;
}
QTableWidget::item {
    padding: 12px 14px;
    border-bottom: 1px solid #F3F4F8;
    color: #1A2B6B;
}
QTableWidget::item:selected {
    background-color: #e8ecf9;
    color: #1A2B6B;
}
QTableWidget::item:alternate { background-color: #fafbfd; }
QHeaderView::section {
    background-color: #F3F4F8;
    color: #6B7080;
    padding: 12px 14px;
    border: none;
    border-bottom: 2px solid #E0E3EE;
    font-weight: 700;
    font-size: 11px;
    font-family: 'Nunito', 'Segoe UI', sans-serif;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

/* ═══════════════════════════════════════════════════
   LISTAS
═══════════════════════════════════════════════════ */
QListWidget {
    border: 1px solid #E0E3EE;
    border-radius: 10px;
    background-color: #FFFFFF;
    font-size: 13px;
    color: #1A2B6B;
}
QListWidget::item {
    padding: 10px 12px;
    border-bottom: 1px solid #F3F4F8;
}
QListWidget::item:selected {
    background-color: #e8ecf9;
    color: #1A2B6B;
    border-left: 3px solid #C8252A;
}
QListWidget::item:hover { background-color: #fafbfd; }

/* ═══════════════════════════════════════════════════
   SCROLLBAR
═══════════════════════════════════════════════════ */
QScrollBar:vertical {
    background-color: #F3F4F8;
    width: 8px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #E0E3EE;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background-color: #9CA3AF; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background-color: #F3F4F8;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background-color: #E0E3EE;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background-color: #9CA3AF; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ═══════════════════════════════════════════════════
   LABELS
═══════════════════════════════════════════════════ */
QLabel {
    color: #1A2B6B;
    background: transparent;
    font-family: 'Nunito', 'Segoe UI', sans-serif;
}

/* ═══════════════════════════════════════════════════
   GROUPBOX
═══════════════════════════════════════════════════ */
QGroupBox {
    border: 1px solid #E0E3EE;
    border-radius: 12px;
    margin-top: 12px;
    padding: 20px 16px 16px;
    background-color: #FFFFFF;
    font-weight: 700;
    font-size: 13px;
    color: #1A2B6B;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
}

/* ═══════════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════════ */
QTabWidget::pane {
    border: 1px solid #E0E3EE;
    border-radius: 12px;
    background-color: #FFFFFF;
}
QTabBar::tab {
    background-color: #F3F4F8;
    border: none;
    padding: 10px 22px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 600;
    font-size: 13px;
    color: #6B7080;
}
QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #C8252A;
    border-bottom: 3px solid #C8252A;
}
QTabBar::tab:hover:!selected {
    background-color: #E0E3EE;
    color: #1A2B6B;
}

/* ═══════════════════════════════════════════════════
   DIALOGS Y MENSAJES
═══════════════════════════════════════════════════ */
QMessageBox {
    background-color: #FFFFFF;
    font-family: 'Nunito', 'Segoe UI', sans-serif;
}
QDialog {
    background-color: #FFFFFF;
}

/* ═══════════════════════════════════════════════════
   DATE EDIT + CALENDAR POPUP
═══════════════════════════════════════════════════ */
QDateEdit {
    border: 1.5px solid #E0E3EE;
    border-bottom: 1.5px solid #E0E3EE;
    border-radius: 8px;
    padding: 9px 14px;
    background-color: #FFFFFF;
    font-size: 13px;
    color: #1A2B6B;
    min-width: 140px;
    min-height: 42px;
}
QDateEdit:focus { border: 2px solid #C8252A; }
QDateEdit::drop-down { border: none; width: 28px; }
QDateEdit::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #6B7080;
    margin-right: 10px;
}

/* Calendario popup — solo días y selección, sin tocar la navegación nativa */
QCalendarWidget QAbstractItemView:enabled {
    background-color: #FFFFFF;
    color: #1A2B6B;
    selection-background-color: #C8252A;
    selection-color: #FFFFFF;
    font-size: 13px;
}
QCalendarWidget QAbstractItemView:disabled { color: #9CA3AF; }
QCalendarWidget QSpinBox {
    min-width: 80px;
    max-width: 80px;
    font-size: 13px;
    color: #1A2B6B;
    background: #FFFFFF;
    border: 1px solid #E0E3EE;
    border-radius: 4px;
    padding: 2px 4px;
}
QCalendarWidget QToolButton {
    min-width: 24px;
    min-height: 24px;
    font-size: 13px;
    color: #1A2B6B;
}

/* ═══════════════════════════════════════════════════
   SPLITTER
═══════════════════════════════════════════════════ */
QSplitter::handle {
    background-color: #E0E3EE;
    width: 1px;
}

/* ═══════════════════════════════════════════════════
   TOOLTIP
═══════════════════════════════════════════════════ */
QToolTip {
    background-color: #1A2B6B;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}
"""


def _cargar_fuentes():
    """
    Intenta cargar Bebas Neue y Nunito desde src/assets/fonts/.
    Si no existen los archivos, PyQt usará la fuente de fallback del QSS.
    """
    base = os.path.dirname(os.path.abspath(__file__))
    fonts_dir = os.path.join(base, "src", "assets", "fonts")

    fuentes = [
        "BebasNeue-Regular.ttf",
        "Nunito-Regular.ttf",
        "Nunito-SemiBold.ttf",
        "Nunito-Bold.ttf",
        "Nunito-ExtraBold.ttf",
    ]

    cargadas = []
    for nombre in fuentes:
        ruta = os.path.join(fonts_dir, nombre)
        if os.path.exists(ruta):
            fid = QFontDatabase.addApplicationFont(ruta)
            if fid != -1:
                cargadas.append(nombre)

    if cargadas:
        print(f"[Fuentes] Cargadas: {', '.join(cargadas)}")
    else:
        print("[Fuentes] No se encontraron archivos .ttf en src/assets/fonts/ — usando fuentes del sistema.")


def setup_app_style(app: QApplication):
    """
    Punto de entrada principal.
    Llama a esta función en main.py en lugar de la anterior setup_app_style.
    """
    _cargar_fuentes()

    # Fuente base
    font = QFont("Nunito", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    # Paleta Qt (afecta widgets nativos del SO)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(GRIS_FONDO))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(AZUL))
    palette.setColor(QPalette.ColorRole.Base,            QColor(BLANCO))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(GRIS_FONDO))
    palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor(AZUL))
    palette.setColor(QPalette.ColorRole.ToolTipText,     QColor(BLANCO))
    palette.setColor(QPalette.ColorRole.Text,            QColor(AZUL))
    palette.setColor(QPalette.ColorRole.Button,          QColor(BLANCO))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(BLANCO))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(ROJO))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(BLANCO))
    app.setPalette(palette)

    # QSS
    app.setStyleSheet(QSS)
    print("[Estilo] Tema PRACTICAR aplicado.")