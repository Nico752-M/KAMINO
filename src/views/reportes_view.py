#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vista de Cierre de Caja - CEA PRACTICAR
Calculadora manual de billetes/monedas para el conteo físico de caja.
"""

import os
from datetime import date, datetime
from decimal import Decimal

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit,
    QLineEdit, QFrame, QScrollArea, QSizePolicy, QMessageBox,
    QGridLayout, QSpinBox
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor

from database import Database
from views.salidas_caja import obtener_salidas_dia, total_salidas_dia
from views.ingresos_caja import obtener_ingresos_dia, total_ingresos_caja_dia

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT


# ─────────────────────────── helpers ────────────────────────────

def fmt_cop(value) -> str:
    try:
        v = float(value or 0)
        return f"${v:,.0f}".replace(",", ".")
    except Exception:
        return "$0"


METODOS = ["Efectivo", "Transferencia", "Nequi", "Daviplata", "Otro"]

COLORS_METODO = {
    "Efectivo":      "#2f855a",
    "Transferencia": "#2b6cb0",
    "Nequi":         "#702459",
    "Daviplata":     "#c05621",
    "Otro":          "#4a5568",
}

BADGE_BG = {
    "Efectivo":      "#c6f6d5",
    "Transferencia": "#bee3f8",
    "Nequi":         "#fed7e2",
    "Daviplata":     "#feebc8",
    "Otro":          "#e2e8f0",
}

# Denominaciones colombianas: (valor, etiqueta, color_indicador, tipo)
DENOMINACIONES = [
    (100_000, "$100.000", "#059669", "billete"),
    ( 50_000,  "$50.000", "#7C3AED", "billete"),
    ( 20_000,  "$20.000", "#0EA5E9", "billete"),
    ( 10_000,  "$10.000", "#EA580C", "billete"),
    (  5_000,   "$5.000", "#DC2626", "billete"),
    (  2_000,   "$2.000", "#0891B2", "billete"),
    (  1_000,   "$1.000", "#B45309", "moneda"),
    (    500,     "$500", "#B45309", "moneda"),
    (    200,     "$200", "#B45309", "moneda"),
    (    100,     "$100", "#9CA3AF", "moneda"),
    (     50,      "$50", "#9CA3AF", "moneda"),
]


def _tamanio_adaptativo(dialogo, ancho_ideal, alto_ideal, margen=40):
    from PyQt6.QtWidgets import QApplication
    screen = QApplication.primaryScreen().availableGeometry()
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


# ─────────────────────── tarjeta resumen método ─────────────────

class TarjetaMetodo(QFrame):
    def __init__(self, metodo: str, cantidad: int, total: Decimal, parent=None):
        super().__init__(parent)
        color = COLORS_METODO.get(metodo, "#4a5568")
        self.setFixedHeight(90)
        self.setStyleSheet(f"""
            QFrame {{
                background: white;
                border-radius: 10px;
                border: 1px solid #e2e8f0;
                border-left: 5px solid {color};
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)

        top = QHBoxLayout()
        lbl_met = QLabel(metodo)
        lbl_met.setStyleSheet(f"font-size:13px; font-weight:700; color:{color}; border:none;")
        lbl_cant = QLabel(f"{cantidad} pago{'s' if cantidad != 1 else ''}")
        lbl_cant.setStyleSheet("font-size:11px; color:#718096; border:none;")
        top.addWidget(lbl_met)
        top.addStretch()
        top.addWidget(lbl_cant)
        lay.addLayout(top)

        lbl_total = QLabel(fmt_cop(total))
        lbl_total.setStyleSheet(f"font-size:20px; font-weight:800; color:{color}; border:none;")
        lay.addWidget(lbl_total)


# ─────────────────────── calculadora de billetes ────────────────

class CalculadoraBilletes(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
        """)
        self._spinners = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        hdr = QHBoxLayout()
        lbl_titulo = QLabel("🏦  Conteo físico de caja")
        lbl_titulo.setStyleSheet(
            "font-size:15px; font-weight:700; color:#2d3748; border:none;"
        )
        hdr.addWidget(lbl_titulo)
        hdr.addStretch()

        btn_limpiar = QPushButton("Limpiar todo")
        btn_limpiar.setFixedHeight(30)
        btn_limpiar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_limpiar.setStyleSheet("""
            QPushButton {
                background: #edf2f7; color: #4a5568;
                border: 1px solid #cbd5e0; border-radius: 6px;
                padding: 0 12px; font-size: 12px; font-weight: 600;
            }
            QPushButton:hover { background: #e2e8f0; }
        """)
        btn_limpiar.clicked.connect(self.limpiar)
        hdr.addWidget(btn_limpiar)
        root.addLayout(hdr)

        col_hdr = QWidget()
        col_hdr.setStyleSheet("background: #f7fafc; border-radius: 6px;")
        ch_lay = QHBoxLayout(col_hdr)
        ch_lay.setContentsMargins(10, 6, 10, 6)
        ch_lay.setSpacing(0)

        def _lbl_col(texto, ancho=None, alin=Qt.AlignmentFlag.AlignLeft):
            l = QLabel(texto)
            l.setStyleSheet(
                "font-size:10px; font-weight:700; color:#718096; "
                "letter-spacing:0.08em; border:none; background:transparent;"
            )
            l.setAlignment(alin)
            if ancho:
                l.setFixedWidth(ancho)
            return l

        ch_lay.addWidget(_lbl_col("DENOMINACIÓN"), 1)
        ch_lay.addWidget(_lbl_col("CANTIDAD", 90, Qt.AlignmentFlag.AlignCenter))
        ch_lay.addWidget(_lbl_col("SUBTOTAL", 110, Qt.AlignmentFlag.AlignRight))
        root.addWidget(col_hdr)

        lbl_billetes = QLabel("  💵  Billetes")
        lbl_billetes.setStyleSheet(
            "font-size:11px; font-weight:700; color:#2f855a; "
            "background:#f0fff4; border-radius:5px; padding:3px 6px; border:none;"
        )
        root.addWidget(lbl_billetes)

        for valor, etiqueta, color, tipo in DENOMINACIONES:
            fila = self._crear_fila(valor, etiqueta, color, tipo)
            root.addWidget(fila)

            if valor == 1_000:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet("color:#e2e8f0; background:#e2e8f0; max-height:1px; border:none;")
                root.addWidget(sep)

                lbl_monedas = QLabel("  🪙  Monedas")
                lbl_monedas.setStyleSheet(
                    "font-size:11px; font-weight:700; color:#B45309; "
                    "background:#FFFBEB; border-radius:5px; padding:3px 6px; border:none;"
                )
                root.addWidget(lbl_monedas)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color:#e2e8f0; background:#e2e8f0; max-height:1px; border:none;")
        root.addWidget(sep2)

        total_frame = QFrame()
        total_frame.setStyleSheet(
            "QFrame { background:#1a202c; border-radius:8px; border:none; }"
        )
        total_frame.setFixedHeight(52)
        tf_lay = QHBoxLayout(total_frame)
        tf_lay.setContentsMargins(14, 0, 14, 0)

        lbl_total_txt = QLabel("TOTAL EN CAJA")
        lbl_total_txt.setStyleSheet(
            "font-size:11px; font-weight:700; color:#a0aec0; "
            "letter-spacing:0.1em; border:none; background:transparent;"
        )
        tf_lay.addWidget(lbl_total_txt)
        tf_lay.addStretch()

        self.lbl_total = QLabel("$ 0")
        self.lbl_total.setStyleSheet(
            "font-size:22px; font-weight:900; color:#68d391; "
            "border:none; background:transparent;"
        )
        tf_lay.addWidget(self.lbl_total)
        root.addWidget(total_frame)

    def _crear_fila(self, valor: int, etiqueta: str, color: str, tipo: str) -> QWidget:
        fila = QWidget()
        fila.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(fila)
        lay.setContentsMargins(10, 2, 10, 2)
        lay.setSpacing(0)

        indicador = QLabel("●")
        indicador.setFixedWidth(18)
        indicador.setStyleSheet(f"color:{color}; font-size:10px; border:none; background:transparent;")

        lbl_den = QLabel(etiqueta)
        lbl_den.setStyleSheet(
            f"font-size:13px; font-weight:700; color:#2d3748; border:none; background:transparent;"
        )

        lay.addWidget(indicador)
        lay.addWidget(lbl_den, 1)

        spin = QSpinBox()
        spin.setRange(0, 9999)
        spin.setValue(0)
        spin.setFixedWidth(80)
        spin.setFixedHeight(32)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setStyleSheet("""
            QSpinBox {
                background: white;
                border: 1.5px solid #e2e8f0;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 700;
                color: #2d3748;
                padding: 0 4px;
            }
            QSpinBox:focus { border-color: #4299e1; }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 20px;
                border: none;
                background: #f7fafc;
                border-radius: 3px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #e2e8f0;
            }
        """)

        lbl_sub = QLabel("$ 0")
        lbl_sub.setFixedWidth(110)
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_sub.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{color}; border:none; background:transparent;"
        )

        lay.addWidget(spin)
        lay.addSpacing(10)
        lay.addWidget(lbl_sub)

        spin.valueChanged.connect(lambda v, val=valor, lbl=lbl_sub: self._actualizar_fila(val, v, lbl))

        self._spinners.append((valor, spin, lbl_sub))
        return fila

    def _actualizar_fila(self, valor: int, cantidad: int, lbl_sub: QLabel):
        subtotal = valor * cantidad
        lbl_sub.setText(fmt_cop(subtotal))
        self._recalcular_total()

    def _recalcular_total(self):
        total = sum(val * spin.value() for val, spin, _ in self._spinners)
        self.lbl_total.setText(fmt_cop(total))

    def limpiar(self):
        for _, spin, lbl_sub in self._spinners:
            spin.blockSignals(True)
            spin.setValue(0)
            spin.blockSignals(False)
            lbl_sub.setText("$ 0")
        self.lbl_total.setText("$ 0")

    def total(self) -> int:
        return sum(val * spin.value() for val, spin, _ in self._spinners)

    def desglose(self) -> list[dict]:
        result = []
        for (valor, etiqueta, color, tipo), (_, spin, _) in zip(DENOMINACIONES, self._spinners):
            if spin.value() > 0:
                result.append({
                    "denominacion": valor,
                    "etiqueta":     etiqueta,
                    "tipo":         tipo,
                    "cantidad":     spin.value(),
                    "subtotal":     valor * spin.value(),
                })
        return result


# ─────────────────────────── vista principal ────────────────────

class ReportesView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db    = Database.get_instance()
        self.pagos = []
        self._build_ui()
        self._cargar_datos()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        inner_widget = QWidget()
        inner_widget.setStyleSheet("background: transparent;")
        scroll_area.setWidget(inner_widget)
        outer.addWidget(scroll_area)

        root = QVBoxLayout(inner_widget)
        root.setContentsMargins(25, 20, 25, 20)
        root.setSpacing(16)

        # ── encabezado ───────────────────────────────────────────
        header = QHBoxLayout()

        col_titulo = QVBoxLayout()
        title = QLabel("🗂  Reportes")
        title.setStyleSheet("font-size:26px; font-weight:800; color:#1a202c;")
        subtitle = QLabel("Resumen de operaciones y pagos")
        subtitle.setStyleSheet("font-size:13px; color:#718096;")
        col_titulo.addWidget(title)
        col_titulo.addWidget(subtitle)

        col_controls = QVBoxLayout()
        col_controls.setAlignment(Qt.AlignmentFlag.AlignRight)

        row_fecha = QHBoxLayout()
        lbl_fecha = QLabel("Fecha:")
        lbl_fecha.setStyleSheet("font-size:13px; color:#4a5568; font-weight:600;")
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setFixedWidth(220)
        self.date_edit.setStyleSheet("""
            QDateEdit {
                border: 1px solid #cbd5e0; border-radius: 6px;
                padding: 5px 8px; font-size: 13px;
                color: #2d3748; background: white;
            }
        """)
        self.date_edit.dateChanged.connect(self._cargar_datos)
        row_fecha.addWidget(lbl_fecha)
        row_fecha.addWidget(self.date_edit)

        row_cajero = QHBoxLayout()
        lbl_cajero = QLabel("Cajero:")
        lbl_cajero.setStyleSheet("font-size:13px; color:#4a5568; font-weight:600;")
        self.input_cajero = QLineEdit()
        self.input_cajero.setPlaceholderText("Nombre de quien cierra caja")
        self.input_cajero.setFixedWidth(220)
        self.input_cajero.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e0; border-radius: 6px;
                padding: 5px 8px; font-size: 13px;
                color: #2d3748; background: white;
            }
            QLineEdit:focus { border-color: #4299e1; }
        """)
        row_cajero.addWidget(lbl_cajero)
        row_cajero.addWidget(self.input_cajero)

        col_controls.addLayout(row_fecha)
        col_controls.addLayout(row_cajero)

        header.addLayout(col_titulo)
        header.addStretch()
        header.addLayout(col_controls)
        root.addLayout(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#e2e8f0;")
        root.addWidget(sep)

        # ── tarjetas por método ───────────────────────────────────
        self.grid_tarjetas = QHBoxLayout()
        self.grid_tarjetas.setSpacing(10)
        root.addLayout(self.grid_tarjetas)

        # ── total general ─────────────────────────────────────────
        frame_total = QFrame()
        frame_total.setStyleSheet("QFrame { background:#1a202c; border-radius:10px; }")
        frame_total.setFixedHeight(56)
        lay_total = QHBoxLayout(frame_total)
        lay_total.setContentsMargins(20, 0, 20, 0)

        lbl_total_text = QLabel("TOTAL DEL DÍA")
        lbl_total_text.setStyleSheet(
            "font-size:13px; font-weight:700; color:#a0aec0; letter-spacing:1px;"
        )
        self.lbl_total_valor = QLabel("$0")
        self.lbl_total_valor.setStyleSheet(
            "font-size:22px; font-weight:900; color:#68d391;"
        )
        self.lbl_num_pagos = QLabel("0 transacciones")
        self.lbl_num_pagos.setStyleSheet("font-size:12px; color:#718096;")

        lay_total.addWidget(lbl_total_text)
        lay_total.addWidget(self.lbl_num_pagos)
        lay_total.addStretch()
        lay_total.addWidget(self.lbl_total_valor)
        root.addWidget(frame_total)

        # ── tabla de pagos ────────────────────────────────────────
        lbl_detalle = QLabel("Detalle de pagos")
        lbl_detalle.setStyleSheet("font-size:15px; font-weight:700; color:#2d3748;")
        root.addWidget(lbl_detalle)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(7)
        self.tabla.setHorizontalHeaderLabels([
            "Recibo", "Alumno", "Concepto", "Método", "Valor", "Hora", "Observaciones"
        ])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e2e8f0; border-radius: 8px;
                background: white; gridline-color: #edf2f7; font-size: 13px;
            }
            QHeaderView::section {
                background: #f7fafc; color: #4a5568;
                font-weight: 700; font-size: 12px;
                padding: 8px; border: none;
                border-bottom: 2px solid #e2e8f0;
            }
            QTableWidget::item { padding: 6px 8px; color: #2d3748; }
            QTableWidget::item:alternate { background: #f7fafc; }
            QTableWidget::item:selected { background: #ebf8ff; color: #2b6cb0; }
        """)
        self.tabla.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tabla.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tabla.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.tabla.setMinimumHeight(200)
        self._TABLA_MAX_FILAS_VISIBLES = 10
        root.addWidget(self.tabla)

        # ── saldo del día (efectivo según recibos) ────────────────
        self.frame_saldo_final = QFrame()
        self.frame_saldo_final.setStyleSheet(
            "QFrame { background:#1a202c; border-radius:10px; }"
        )
        self.frame_saldo_final.setFixedHeight(60)
        lay_sf = QHBoxLayout(self.frame_saldo_final)
        lay_sf.setContentsMargins(20, 0, 20, 0)
        lbl_sf_txt = QLabel("TOTAL RECIBIDO EN EFECTIVO (según recibos del día)")
        lbl_sf_txt.setStyleSheet(
            "font-size:11px; font-weight:700; color:#a0aec0; letter-spacing:1px;"
        )
        self.lbl_saldo_final = QLabel("$0")
        self.lbl_saldo_final.setStyleSheet(
            "font-size:24px; font-weight:900; color:#fbd38d;"
        )
        lay_sf.addWidget(lbl_sf_txt)
        lay_sf.addStretch()
        lay_sf.addWidget(self.lbl_saldo_final)
        root.addWidget(self.frame_saldo_final)

        # ── CALCULADORA DE BILLETES ───────────────────────────────
        self.calculadora = CalculadoraBilletes()
        root.addWidget(self.calculadora)

        # ── botones ───────────────────────────────────────────────
        row_btns = QHBoxLayout()
        row_btns.addStretch()

        btn_actualizar = QPushButton("🔄  Actualizar")
        btn_actualizar.setFixedHeight(40)
        btn_actualizar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_actualizar.setStyleSheet("""
            QPushButton {
                background:#edf2f7; color:#4a5568;
                border-radius:8px; padding:0 20px;
                font-size:13px; font-weight:600;
                border:1px solid #cbd5e0;
            }
            QPushButton:hover { background:#e2e8f0; }
        """)
        btn_actualizar.clicked.connect(self._cargar_datos)

        self.btn_pdf = QPushButton("📄  Generar PDF del Cierre")
        self.btn_pdf.setFixedHeight(40)
        self.btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pdf.setStyleSheet("""
            QPushButton {
                background:#2f855a; color:white;
                border-radius:8px; padding:0 24px;
                font-size:13px; font-weight:700; border:none;
            }
            QPushButton:hover { background:#276749; }
            QPushButton:disabled { background:#a0aec0; }
        """)
        self.btn_pdf.clicked.connect(self._generar_pdf)

        self.btn_excel = QPushButton("📊  Exportar a Excel")
        self.btn_excel.setFixedHeight(40)
        self.btn_excel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_excel.setStyleSheet("""
            QPushButton {
                background:#2b6cb0; color:white;
                border-radius:8px; padding:0 24px;
                font-size:13px; font-weight:700; border:none;
            }
            QPushButton:hover { background:#2c5282; }
        """)
        self.btn_excel.clicked.connect(self._generar_excel)

        row_btns.addWidget(btn_actualizar)
        row_btns.addWidget(self.btn_pdf)
        row_btns.addWidget(self.btn_excel)
        root.addLayout(row_btns)
        root.addStretch()

    # ── carga de datos ────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        hoy = QDate.currentDate()
        self.date_edit.blockSignals(True)
        self.date_edit.setDate(hoy)
        self.date_edit.blockSignals(False)
        self._cargar_datos()

    def _cargar_datos(self):
        try:
            self.db._ensure_connection()
            if self.db._connection and self.db._connection.is_connected():
                self.db._connection.commit()
        except Exception:
            pass

        fecha = self.date_edit.date().toPyDate()
        fecha_str = fecha.strftime("%Y-%m-%d")

        query = """
            SELECT
                p.numero_recibo,
                COALESCE(CONCAT(a.nombres, ' ', a.apellidos), 'Sin alumno') AS alumno,
                p.concepto,
                p.metodo_pago,
                p.valor,
                p.fecha_pago,
                p.observaciones
            FROM pagos p
            LEFT JOIN matriculas m ON m.id = p.id_matricula
            LEFT JOIN alumnos a ON a.numero_documento = m.numero_documento
            WHERE DATE(p.fecha_pago) = %s
              AND p.concepto != 'Abono histórico previo'
            ORDER BY p.fecha_pago ASC
        """

        try:
            rows = self.db.fetchall(query, (fecha_str,))
        except Exception as e:
            QMessageBox.critical(self, "Error de base de datos", str(e))
            return

        self.pagos = []
        for row in rows:
            self.pagos.append({
                "recibo":        row["numero_recibo"],
                "alumno":        row["alumno"],
                "concepto":      row["concepto"],
                "metodo":        row["metodo_pago"],
                "valor":         Decimal(str(row["valor"])),
                "fecha_pago":    row["fecha_pago"],
                "observaciones": row["observaciones"] or "",
            })

        self._actualizar_tabla()
        self._actualizar_tarjetas()
        self._actualizar_efectivo()
        self._actualizar_totales_caja(fecha_str)

    def _actualizar_tabla(self):
        self.tabla.setRowCount(0)
        for pago in self.pagos:
            row = self.tabla.rowCount()
            self.tabla.insertRow(row)
            hora = (
                pago["fecha_pago"].strftime("%H:%M")
                if isinstance(pago["fecha_pago"], datetime)
                else str(pago["fecha_pago"])
            )
            items = [
                pago["recibo"], pago["alumno"], pago["concepto"],
                pago["metodo"], fmt_cop(pago["valor"]), hora,
                pago["observaciones"],
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                if col == 4:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
                    )
                if col == 3:
                    item.setForeground(QColor(COLORS_METODO.get(text, "#4a5568")))
                    f = QFont(); f.setBold(True); item.setFont(f)
                self.tabla.setItem(row, col, item)

        self.tabla.resizeRowsToContents()
        rh = self.tabla.rowHeight(0) if self.tabla.rowCount() > 0 else 30
        hh = self.tabla.horizontalHeader().height()
        filas_vis = min(self.tabla.rowCount(), self._TABLA_MAX_FILAS_VISIBLES)
        total_h = hh + (rh * max(filas_vis, 1)) + 4
        self.tabla.setFixedHeight(max(200, total_h))

    def _actualizar_efectivo(self):
        """Actualiza el total recibido en efectivo según los recibos del día."""
        total_efectivo = sum(
            p["valor"] for p in self.pagos if p["metodo"] == "Efectivo"
        )
        self.lbl_saldo_final.setText(fmt_cop(total_efectivo))

    def _actualizar_tarjetas(self):
        while self.grid_tarjetas.count():
            w = self.grid_tarjetas.takeAt(0).widget()
            if w:
                w.deleteLater()

        totales    = {m: Decimal("0") for m in METODOS}
        cantidades = {m: 0 for m in METODOS}

        for p in self.pagos:
            m = p["metodo"]
            if m in totales:
                totales[m]    += p["valor"]
                cantidades[m] += 1

        total_general = sum(totales.values())
        num_pagos     = len(self.pagos)

        for metodo in METODOS:
            tarjeta = TarjetaMetodo(metodo, cantidades[metodo], totales[metodo])
            self.grid_tarjetas.addWidget(tarjeta)

        self.lbl_total_valor.setText(fmt_cop(total_general))
        self.lbl_num_pagos.setText(
            f"{num_pagos} transacción{'es' if num_pagos != 1 else ''}"
        )
        self.btn_pdf.setEnabled(num_pagos > 0)

    def _actualizar_totales_caja(self, fecha_str: str):
        """Sincroniza ingresos y egresos de caja con los totales mostrados."""
        try:
            total_sal = total_salidas_dia(fecha_str)
            total_ing = total_ingresos_caja_dia(fecha_str)
        except Exception:
            total_sal = 0
            total_ing = 0

        # Efectivo recibido por alumnos + ingresos manuales de caja
        total_efectivo_alumnos = sum(
            p["valor"] for p in self.pagos if p["metodo"] == "Efectivo"
        )
        efectivo_total = float(total_efectivo_alumnos) + total_ing - total_sal
        self.lbl_saldo_final.setText(fmt_cop(efectivo_total))

    # ── generación PDF ────────────────────────────────────────────

    def _generar_pdf(self):
        cajero = self.input_cajero.text().strip()
        if not cajero:
            QMessageBox.warning(self, "Cajero requerido",
                                "Por favor ingresa el nombre del cajero.")
            self.input_cajero.setFocus()
            return

        fecha    = self.date_edit.date().toPyDate()
        carpeta  = os.path.join(
            os.path.expanduser("~"), "OneDrive", "Escritorio",
            "CEA_PRACTICAR", "Cierres_PDF"
        )
        os.makedirs(carpeta, exist_ok=True)
        nombre_archivo = os.path.join(
            carpeta, f"CierreCaja_{fecha.strftime('%Y%m%d')}.pdf"
        )

        try:
            self._exportar_pdf(nombre_archivo, fecha, cajero)
            QMessageBox.information(self, "PDF generado",
                                    f"Guardado en:\n{nombre_archivo}")
            os.startfile(nombre_archivo)
        except Exception as e:
            QMessageBox.critical(self, "Error generando PDF", str(e))

    def _generar_excel(self):
        cajero = self.input_cajero.text().strip()
        if not cajero:
            QMessageBox.warning(self, "Cajero requerido",
                                "Ingresa el nombre del cajero.")
            return

        fecha   = self.date_edit.date().toPyDate()
        carpeta = os.path.join(
            os.path.expanduser("~"), "OneDrive", "Escritorio",
            "CEA_PRACTICAR", "Cierres_Excel"
        )
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(
            carpeta, f"cierre_caja_{fecha.strftime('%Y%m%d')}.xlsx"
        )

        try:
            self._exportar_excel(ruta, fecha, cajero)
            QMessageBox.information(self, "Excel generado",
                                    f"Guardado en:\n{ruta}")
            os.startfile(ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error generando Excel", str(e))

    def _exportar_excel(self, nombre_archivo: str, fecha, cajero: str):
        fecha_str = fecha.strftime("%Y-%m-%d")
        azul  = "0033A0"; rojo = "E31937"; verde = "0D6E55"
        negro = "1A1916"; blanco = "FFFFFF"

        def fill(c):  return PatternFill("solid", fgColor=c)
        def bold(s=11, c=blanco): return Font(bold=True, size=s, color=c)
        def norm(s=10, c=negro):  return Font(size=s, color=c)
        def brd():
            sd = Side(style="thin", color="DDD9D0")
            return Border(left=sd, right=sd, top=sd, bottom=sd)
        def ctr(): return Alignment(horizontal="center", vertical="center", wrap_text=True)
        def rgt(): return Alignment(horizontal="right", vertical="center")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Cierre de Caja"

        ws.merge_cells("A1:G1")
        ws["A1"] = "PRACTICAR — Centro de Enseñanza Automovilística"
        ws["A1"].font = bold(14, azul)
        ws["A1"].fill = fill("EAF1FB")
        ws["A1"].alignment = ctr()
        ws.row_dimensions[1].height = 28

        ws.merge_cells("A2:G2")
        ws["A2"] = f"Cierre de Caja  ·  {fecha.strftime('%d/%m/%Y')}  ·  Cajero: {cajero}"
        ws["A2"].font = Font(size=11, color="5A5650")
        ws["A2"].fill = fill("EAF1FB")
        ws["A2"].alignment = ctr()
        ws.append([])

        hdrs = ["# Recibo", "Alumno", "Documento", "Concepto", "Método", "Hora", "Valor"]
        ws.append(hdrs)
        hr = ws.max_row
        for ci in range(1, 8):
            cell = ws.cell(hr, ci)
            cell.font = bold(10, blanco)
            cell.fill = fill(azul)
            cell.alignment = ctr()
            cell.border = brd()
        ws.row_dimensions[hr].height = 22

        for p in self.pagos:
            hora = (
                p["fecha_pago"].strftime("%H:%M")
                if isinstance(p["fecha_pago"], datetime) else ""
            )
            ws.append([
                p["recibo"], p["alumno"], "", p["concepto"],
                p["metodo"], hora, float(p["valor"])
            ])
            r = ws.max_row
            for ci in range(1, 8):
                cell = ws.cell(r, ci)
                cell.font = norm()
                cell.border = brd()
                cell.alignment = Alignment(vertical="center")
            ws.cell(r, 7).number_format = '"$"#,##0'
            ws.cell(r, 7).alignment = rgt()
            ws.cell(r, 7).font = Font(bold=True, size=10, color=verde)
            ws.row_dimensions[r].height = 18

        # Totales por método
        ws.append([])
        ws.append(["TOTALES POR MÉTODO"])
        r = ws.max_row
        ws.merge_cells(f"A{r}:G{r}")
        ws.cell(r, 1).font = bold(10, azul)
        ws.cell(r, 1).fill = fill("EAF1FB")
        ws.cell(r, 1).alignment = ctr()

        totales = {}
        for p in self.pagos:
            m = p["metodo"]
            totales[m] = totales.get(m, 0.0) + float(p["valor"])
        for met, val in totales.items():
            ws.append(["", met, "", "", "", "", val])
            r = ws.max_row
            ws.cell(r, 7).number_format = '"$"#,##0'
            ws.cell(r, 7).font = Font(bold=True, size=10, color=verde)
            ws.cell(r, 7).alignment = rgt()

        # Conteo físico de caja
        ws.append([])
        ws.append(["CONTEO FÍSICO DE CAJA"])
        r = ws.max_row
        ws.merge_cells(f"A{r}:G{r}")
        ws.cell(r, 1).font = bold(10, "2b6cb0")
        ws.cell(r, 1).fill = fill("EBF8FF")
        ws.cell(r, 1).alignment = ctr()

        desglose = self.calculadora.desglose()
        if desglose:
            ws.append(["Denominación", "Cantidad", "Subtotal", "", "", "", ""])
            r = ws.max_row
            for ci in range(1, 4):
                ws.cell(r, ci).font = bold(10, blanco)
                ws.cell(r, ci).fill = fill("2b6cb0")
                ws.cell(r, ci).alignment = ctr()

            for d in desglose:
                ws.append([
                    d["etiqueta"], d["cantidad"], d["subtotal"],
                    "", "", "", ""
                ])
                r = ws.max_row
                ws.cell(r, 1).font = norm()
                ws.cell(r, 2).font = norm()
                ws.cell(r, 3).font = Font(bold=True, size=10, color=verde)
                ws.cell(r, 3).number_format = '"$"#,##0'
                ws.cell(r, 3).alignment = rgt()

            ws.append(["TOTAL CONTADO", "", self.calculadora.total(), "", "", "", ""])
            r = ws.max_row
            ws.merge_cells(f"A{r}:B{r}")
            ws.cell(r, 1).font = Font(bold=True, size=11, color=blanco)
            ws.cell(r, 1).fill = fill("2b6cb0")
            ws.cell(r, 1).alignment = ctr()
            ws.cell(r, 3).font = Font(bold=True, size=12, color="2b6cb0")
            ws.cell(r, 3).number_format = '"$"#,##0'
            ws.cell(r, 3).alignment = rgt()
            ws.row_dimensions[r].height = 22

        # Totales finales
        ws.append([])
        total_ing     = sum(totales.values())
        total_contado = self.calculadora.total()

        total_sal_dia = total_salidas_dia(fecha_str)
        total_ing_dia = total_ingresos_caja_dia(fecha_str)
        for etiqueta, valor, color in [
            ("TOTAL PAGOS ALUMNOS",     total_ing,              verde),
            ("INGRESOS MANUALES CAJA",  total_ing_dia,          "2f855a"),
            ("EGRESOS MANUALES CAJA",   total_sal_dia,          rojo),
            ("TOTAL CONTADO EN CAJA",   total_contado,          "2b6cb0"),
        ]:
            ws.append([etiqueta, "", "", "", "", "", valor])
            r = ws.max_row
            ws.merge_cells(f"A{r}:F{r}")
            ws.cell(r, 1).font = Font(bold=True, size=11, color=blanco)
            ws.cell(r, 1).fill = fill(color)
            ws.cell(r, 1).alignment = ctr()
            ws.cell(r, 7).font = Font(bold=True, size=12, color=color)
            ws.cell(r, 7).number_format = '"$"#,##0'
            ws.cell(r, 7).alignment = rgt()
            ws.row_dimensions[r].height = 22

        for i, w in enumerate([20, 26, 16, 28, 14, 8, 16], start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        wb.save(nombre_archivo)


    def _exportar_pdf(self, nombre_archivo: str, fecha: date, cajero: str):
        fecha_str = fecha.strftime("%Y-%m-%d")
        doc = SimpleDocTemplate(
            nombre_archivo,
            pagesize=letter,
            rightMargin=1.5*cm, leftMargin=1.5*cm,
            topMargin=2*cm,     bottomMargin=2*cm,
        )

        styles  = getSampleStyleSheet()
        story   = []

        estilo_titulo = ParagraphStyle(
            "Titulo", parent=styles["Heading1"],
            fontSize=18, textColor=colors.HexColor("#1a202c"),
            spaceAfter=4, alignment=TA_CENTER,
        )
        estilo_sub = ParagraphStyle(
            "Sub", parent=styles["Normal"],
            fontSize=10, textColor=colors.HexColor("#718096"),
            spaceAfter=2, alignment=TA_CENTER,
        )
        estilo_seccion = ParagraphStyle(
            "Seccion", parent=styles["Normal"],
            fontSize=11, textColor=colors.HexColor("#2d3748"),
            fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4,
        )

        story.append(Paragraph("CEA PRACTICAR", estilo_titulo))
        story.append(Paragraph("Centro de Enseñanza Automovilística", estilo_sub))
        story.append(Paragraph(
            "CRA 27A # 32-41 · Cali, Colombia · NIT: 66708630", estilo_sub
        ))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(
            f"CIERRE DE CAJA — {fecha.strftime('%d/%m/%Y')}",
            ParagraphStyle("CierreTit", parent=estilo_titulo,
                           fontSize=14, textColor=colors.HexColor("#2f855a"))
        ))
        story.append(Paragraph(f"Cajero: <b>{cajero}</b>", estilo_sub))
        story.append(Paragraph(
            f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", estilo_sub
        ))
        story.append(Spacer(1, 0.5*cm))

        # Resumen por método
        story.append(Paragraph("Resumen por método de pago", estilo_seccion))
        totales    = {m: Decimal("0") for m in METODOS}
        cantidades = {m: 0 for m in METODOS}
        for p in self.pagos:
            m = p["metodo"]
            if m in totales:
                totales[m]    += p["valor"]
                cantidades[m] += 1

        resumen_data = [["Método de pago", "# Transacciones", "Total"]]
        for m in METODOS:
            resumen_data.append([m, str(cantidades[m]), fmt_cop(totales[m])])
        total_general = sum(totales.values())
        resumen_data.append(["TOTAL GENERAL", str(len(self.pagos)), fmt_cop(total_general)])

        resumen_table = Table(resumen_data, colWidths=[8*cm, 4*cm, 5*cm])
        resumen_table.setStyle(TableStyle([
            ("BACKGROUND",  (0,0),  (-1,0),  colors.HexColor("#2d3748")),
            ("TEXTCOLOR",   (0,0),  (-1,0),  colors.white),
            ("FONTNAME",    (0,0),  (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0,0),  (-1,0),  10),
            ("ALIGN",       (1,0),  (-1,-1), "CENTER"),
            ("ALIGN",       (2,0),  (2,-1),  "RIGHT"),
            ("FONTSIZE",    (0,1),  (-1,-1), 9),
            ("ROWBACKGROUNDS", (0,1), (-1,-2), [colors.white, colors.HexColor("#f7fafc")]),
            ("BACKGROUND",  (0,-1), (-1,-1), colors.HexColor("#1a202c")),
            ("TEXTCOLOR",   (0,-1), (-1,-1), colors.HexColor("#68d391")),
            ("FONTNAME",    (0,-1), (-1,-1), "Helvetica-Bold"),
            ("BOX",         (0,0),  (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ("INNERGRID",   (0,0),  (-1,-1), 0.3, colors.HexColor("#e2e8f0")),
            ("TOPPADDING",  (0,0),  (-1,-1), 6),
            ("BOTTOMPADDING",(0,0), (-1,-1), 6),
        ]))
        story.append(resumen_table)
        story.append(Spacer(1, 0.6*cm))

        # Detalle de pagos
        story.append(Paragraph("Detalle de transacciones", estilo_seccion))
        detalle_data = [["Recibo", "Alumno", "Concepto", "Método", "Hora", "Valor"]]
        for p in self.pagos:
            hora = (
                p["fecha_pago"].strftime("%H:%M")
                if isinstance(p["fecha_pago"], datetime) else ""
            )
            detalle_data.append([
                p["recibo"], p["alumno"], p["concepto"],
                p["metodo"], hora, fmt_cop(p["valor"]),
            ])

        det_table = Table(
            detalle_data,
            colWidths=[3.2*cm, 5.5*cm, 4.5*cm, 2.8*cm, 1.8*cm, 3.2*cm]
        )
        det_table.setStyle(TableStyle([
            ("BACKGROUND",  (0,0),  (-1,0),  colors.HexColor("#2d3748")),
            ("TEXTCOLOR",   (0,0),  (-1,0),  colors.white),
            ("FONTNAME",    (0,0),  (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0,0),  (-1,-1), 8),
            ("ALIGN",       (5,0),  (5,-1),  "RIGHT"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f7fafc")]),
            ("BOX",         (0,0),  (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ("INNERGRID",   (0,0),  (-1,-1), 0.3, colors.HexColor("#e2e8f0")),
            ("TOPPADDING",  (0,0),  (-1,-1), 5),
            ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ]))
        story.append(det_table)

        # Agregar después del bloque de salidas, antes del conteo físico


        story.append(Spacer(1, 0.6*cm))
        story.append(Paragraph("Salidas de efectivo del día", estilo_seccion))

        try:
            salidas_pdf = obtener_salidas_dia(fecha_str)
        except Exception:
            salidas_pdf = []

        if salidas_pdf:
            sal_data = [["Concepto", "Método", "Valor"]]
            total_sal_pdf = Decimal("0")
            for row in salidas_pdf:
                valor = Decimal(str(row["valor"]))
                total_sal_pdf += valor
                sal_data.append([
                    str(row["concepto"]), str(row.get("metodo_pago", "")), fmt_cop(valor)
                ])
            sal_data.append(["TOTAL SALIDAS", "", fmt_cop(total_sal_pdf)])

            sal_table = Table(sal_data, colWidths=[8*cm, 4*cm, 5*cm])
            sal_table.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),  (-1,0),  colors.HexColor("#c53030")),
                ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
                ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
                ("FONTSIZE",      (0,0),  (-1,-1), 9),
                ("ALIGN",         (2,0),  (2,-1),  "RIGHT"),
                ("ROWBACKGROUNDS",(0,1),  (-1,-2), [colors.white, colors.HexColor("#fff5f5")]),
                ("BACKGROUND",    (0,-1), (-1,-1), colors.HexColor("#822727")),
                ("TEXTCOLOR",     (0,-1), (-1,-1), colors.white),
                ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
                ("BOX",           (0,0),  (-1,-1), 0.5, colors.HexColor("#fed7d7")),
                ("INNERGRID",     (0,0),  (-1,-1), 0.3, colors.HexColor("#fed7d7")),
                ("TOPPADDING",    (0,0),  (-1,-1), 5),
                ("BOTTOMPADDING", (0,0),  (-1,-1), 5),
            ]))
            story.append(sal_table)
        else:
            story.append(Paragraph(
                "No se registraron salidas para este día.", estilo_seccion
            ))
        story.append(Paragraph("Ingresos manuales de caja", estilo_seccion))

        try:
            ingresos_pdf = obtener_ingresos_dia(fecha_str)
        except Exception:
            ingresos_pdf = []

        if ingresos_pdf:
            ing_data = [["Concepto", "Cajero", "Valor"]]
            total_ing_pdf = Decimal("0")
            for row in ingresos_pdf:
                valor = Decimal(str(row["valor"]))
                total_ing_pdf += valor
                ing_data.append([
                    str(row["concepto"]), str(row.get("cajero", "")), fmt_cop(valor)
                ])
            ing_data.append(["TOTAL INGRESOS", "", fmt_cop(total_ing_pdf)])

            ing_table = Table(ing_data, colWidths=[8*cm, 4*cm, 5*cm])
            ing_table.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),  (-1,0),  colors.HexColor("#2f855a")),
                ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
                ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
                ("FONTSIZE",      (0,0),  (-1,-1), 9),
                ("ALIGN",         (2,0),  (2,-1),  "RIGHT"),
                ("ROWBACKGROUNDS",(0,1),  (-1,-2), [colors.white, colors.HexColor("#f0fff4")]),
                ("BACKGROUND",    (0,-1), (-1,-1), colors.HexColor("#276749")),
                ("TEXTCOLOR",     (0,-1), (-1,-1), colors.white),
                ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
                ("BOX",           (0,0),  (-1,-1), 0.5, colors.HexColor("#c6f6d5")),
                ("INNERGRID",     (0,0),  (-1,-1), 0.3, colors.HexColor("#c6f6d5")),
                ("TOPPADDING",    (0,0),  (-1,-1), 5),
                ("BOTTOMPADDING", (0,0),  (-1,-1), 5),
            ]))
            story.append(ing_table)
        else:
            story.append(Paragraph(
                "No se registraron ingresos manuales para este día.", estilo_seccion
            ))

        # Conteo físico
        story.append(Spacer(1, 0.6*cm))
        story.append(Paragraph("Conteo físico de caja", estilo_seccion))

        desglose = self.calculadora.desglose()
        if desglose:
            caja_data = [["Denominación", "Cantidad", "Subtotal"]]
            for d in desglose:
                caja_data.append([
                    d["etiqueta"], str(d["cantidad"]), fmt_cop(d["subtotal"])
                ])
            caja_data.append(["TOTAL CONTADO", "", fmt_cop(self.calculadora.total())])

            caja_table = Table(caja_data, colWidths=[6*cm, 4*cm, 7*cm])
            caja_table.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),  (-1,0),  colors.HexColor("#2b6cb0")),
                ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
                ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
                ("FONTSIZE",      (0,0),  (-1,-1), 9),
                ("ALIGN",         (1,0),  (-1,-1), "CENTER"),
                ("ALIGN",         (2,0),  (2,-1),  "RIGHT"),
                ("ROWBACKGROUNDS",(0,1),  (-1,-2), [colors.white, colors.HexColor("#EBF8FF")]),
                ("BACKGROUND",    (0,-1), (-1,-1), colors.HexColor("#1a365d")),
                ("TEXTCOLOR",     (0,-1), (-1,-1), colors.white),
                ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
                ("BOX",           (0,0),  (-1,-1), 0.5, colors.HexColor("#bee3f8")),
                ("INNERGRID",     (0,0),  (-1,-1), 0.3, colors.HexColor("#bee3f8")),
                ("TOPPADDING",    (0,0),  (-1,-1), 5),
                ("BOTTOMPADDING", (0,0),  (-1,-1), 5),
            ]))
            story.append(caja_table)
        else:
            story.append(Paragraph(
                "No se realizó conteo físico de caja.", estilo_seccion
            ))

        # Firma
        story.append(Spacer(1, 1.5*cm))
        firma_data = [
            ["_________________________________"],
            [cajero],
            ["Cajero responsable del cierre"],
        ]
        firma_table = Table(firma_data, colWidths=[8*cm])
        firma_table.setStyle(TableStyle([
            ("ALIGN",    (0,0), (-1,-1), "CENTER"),
            ("FONTNAME", (0,1), (0,1),   "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("TEXTCOLOR",(0,0), (-1,-1), colors.HexColor("#4a5568")),
        ]))
        outer_t = Table([[firma_table]], colWidths=[doc.width])
        outer_t.setStyle(TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER")]))
        story.append(outer_t)

        doc.build(story)

    