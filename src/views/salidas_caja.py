#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de Salidas de Caja — CEA PRACTICAR
Registra vueltos, gastos e imprevistos que salen de caja.
Versión simplificada: solo monto + categoría + concepto (sin desglose de billetes).
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QScrollArea, QWidget, QMessageBox,
    QComboBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt

from views.utils_caja import (
    C_AZUL, C_ROJO, C_ROJO_DARK, C_ROJO_LIGHT,
    C_GRIS_FONDO, C_GRIS_BORDE, C_GRIS_MED,
    C_BLANCO, C_NEGRO,
    _lbl_seccion,
)
from database import Database
from views.recibo_generator import generar_recibo_salida, abrir_pdf


# ─────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────

def _generar_numero_salida() -> str:
    import uuid
    from datetime import datetime
    hoy    = datetime.now().strftime("%Y%m%d")
    sufijo = uuid.uuid4().hex[:4].upper()
    return f"SAL-{hoy}-{sufijo}"


def _obtener_nombre_cajero(usuario_id: int) -> str:
    try:
        db = Database.get_instance()
        row = db.fetchone("SELECT nombre FROM usuarios WHERE id = %s", (usuario_id,))
        return row["nombre"] if row else f"Usuario #{usuario_id}"
    except Exception:
        return f"Usuario #{usuario_id}"


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


# ─────────────────────────────────────────────────────────────────
#  CATEGORÍAS
# ─────────────────────────────────────────────────────────────────

def obtener_categorias_egreso() -> list[str]:
    """Devuelve las categorías activas de tipo egreso o ambos."""
    try:
        db = Database.get_instance()
        rows = db.fetchall("""
            SELECT nombre FROM categorias_caja
            WHERE activo = 1 AND tipo IN ('egreso', 'ambos')
            ORDER BY nombre
        """)
        return [r["nombre"] for r in rows]
    except Exception:
        return ["Vuelto a alumno", "Gasto papelería", "Pago a instructor", "Otros gastos"]


# ─────────────────────────────────────────────────────────────────
#  BASE DE DATOS
# ─────────────────────────────────────────────────────────────────

def registrar_salidas(monto: float, categoria: str,
                      concepto: str, usuario_id: int = 1) -> str:
    """
    Registra una salida de caja sin desglose de billetes.
    Devuelve el número de recibo generado.
    """
    if monto <= 0:
        return ""

    db = Database.get_instance()
    concepto_final = f"{categoria}" + (f" — {concepto}" if concepto else "")
    numero_recibo  = _generar_numero_salida()

    db.execute("""
        INSERT INTO salidas_caja
            (numero_recibo, concepto, valor, metodo_pago, observaciones, usuario_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (numero_recibo, concepto_final, monto, "Efectivo", concepto or None, usuario_id))

    return numero_recibo


def obtener_salidas_dia(fecha_str: str) -> list[dict]:
    db = Database.get_instance()
    return db.fetchall("""
        SELECT
            s.numero_recibo, s.concepto, s.valor,
            s.metodo_pago, s.observaciones,
            TIME_FORMAT(s.fecha_salida, '%H:%i') AS hora,
            u.nombre AS cajero
        FROM salidas_caja s
        JOIN usuarios u ON u.id = s.usuario_id
        WHERE DATE(s.fecha_salida) = %s
        ORDER BY s.fecha_salida DESC
    """, (fecha_str,))


def total_salidas_dia(fecha_str: str) -> float:
    db = Database.get_instance()
    row = db.fetchone("""
        SELECT COALESCE(SUM(valor), 0) AS total
        FROM salidas_caja
        WHERE DATE(fecha_salida) = %s
    """, (fecha_str,))
    return float(row["total"]) if row else 0.0


# ─────────────────────────────────────────────────────────────────
#  DIÁLOGO
# ─────────────────────────────────────────────────────────────────

class DialogoSalida(QDialog):

    def __init__(self, parent=None, usuario_id: int = 1):
        super().__init__(parent)
        self.usuario_id = usuario_id
        self.setWindowTitle("Registrar salida de caja")
        _tamanio_adaptativo(self, 620, 420)
        self.setModal(True)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── cabecera roja ─────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(f"background: {C_ROJO};")
        header.setFixedHeight(76)
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(28, 14, 28, 14)
        h_lay.setSpacing(2)
        lbl_titulo = QLabel("↓  Registrar salida de caja")
        lbl_titulo.setStyleSheet("font-size:18px; font-weight:800; color:#FFFFFF;")
        lbl_sub = QLabel("Vueltos, gastos o imprevistos del día")
        lbl_sub.setStyleSheet("font-size:12px; color:rgba(255,255,255,0.75);")
        h_lay.addWidget(lbl_titulo)
        h_lay.addWidget(lbl_sub)
        root.addWidget(header)

        # ── cuerpo ────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {C_BLANCO};")

        body = QWidget()
        body.setStyleSheet(f"background: {C_BLANCO};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(28, 20, 28, 20)
        body_lay.setSpacing(16)

        body_lay.addWidget(_lbl_seccion("Detalle de la salida"))

        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background: {C_GRIS_FONDO};
                border: 1.5px solid {C_GRIS_BORDE};
                border-radius: 10px;
            }}
            QComboBox, QLineEdit, QDoubleSpinBox {{
                background: {C_BLANCO};
                border: 1.5px solid {C_GRIS_BORDE};
                border-radius: 7px;
                padding: 6px 10px;
                font-size: 13px;
                color: {C_NEGRO};
            }}
            QComboBox:focus, QLineEdit:focus, QDoubleSpinBox:focus {{
                border: 1.5px solid {C_AZUL};
            }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
        """)
        info_lay = QVBoxLayout(info_frame)
        info_lay.setContentsMargins(16, 14, 16, 14)
        info_lay.setSpacing(12)

        def _lbl_campo(texto: str) -> QLabel:
            l = QLabel(texto)
            l.setStyleSheet(
                f"font-size:11px; font-weight:700; color:{C_AZUL};"
                f" letter-spacing:0.05em; min-width:110px;"
            )
            return l

        # Categoría
        row_cat = QHBoxLayout()
        row_cat.setSpacing(10)
        row_cat.addWidget(_lbl_campo("CATEGORÍA"))
        self.combo_categoria = QComboBox()
        self.combo_categoria.setFixedHeight(38)
        for cat in obtener_categorias_egreso():
            self.combo_categoria.addItem(cat)
        row_cat.addWidget(self.combo_categoria, 1)
        info_lay.addLayout(row_cat)

        # Monto
        row_monto = QHBoxLayout()
        row_monto.setSpacing(10)
        row_monto.addWidget(_lbl_campo("MONTO ($)"))
        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setFixedHeight(38)
        self.spin_monto.setRange(0, 99_999_999)
        self.spin_monto.setDecimals(0)
        self.spin_monto.setSingleStep(1000)
        self.spin_monto.setPrefix("$ ")
        self.spin_monto.setValue(0)
        self.spin_monto.valueChanged.connect(self._on_monto_changed)
        row_monto.addWidget(self.spin_monto, 1)
        info_lay.addLayout(row_monto)

        # Descripción
        row_desc = QHBoxLayout()
        row_desc.setSpacing(10)
        row_desc.addWidget(_lbl_campo("DESCRIPCIÓN"))
        self.input_desc = QLineEdit()
        self.input_desc.setPlaceholderText("Opcional — ej: Vuelto alumno García, compra papelería…")
        self.input_desc.setFixedHeight(38)
        row_desc.addWidget(self.input_desc, 1)
        info_lay.addLayout(row_desc)

        body_lay.addWidget(info_frame)

        # Total visual
        total_frame = QFrame()
        total_frame.setStyleSheet(f"""
            QFrame {{
                background: {C_ROJO_LIGHT};
                border: 1.5px solid #FBBDBD;
                border-radius: 10px;
            }}
        """)
        total_lay = QHBoxLayout(total_frame)
        total_lay.setContentsMargins(16, 12, 16, 12)
        lbl_key = QLabel("↓  Total que sale de caja")
        lbl_key.setStyleSheet(f"font-size:13px; font-weight:700; color:{C_ROJO};")
        total_lay.addWidget(lbl_key)
        total_lay.addStretch()
        self.lbl_total = QLabel("$ 0")
        self.lbl_total.setStyleSheet(f"font-size:24px; font-weight:800; color:{C_ROJO};")
        total_lay.addWidget(self.lbl_total)
        body_lay.addWidget(total_frame)

        body_lay.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # ── footer ────────────────────────────────────────────────
        footer = QFrame()
        footer.setStyleSheet(
            f"QFrame {{ background:{C_BLANCO}; border-top:1px solid {C_GRIS_BORDE}; }}"
        )
        footer.setFixedHeight(68)
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(28, 0, 28, 0)
        f_lay.setSpacing(12)

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setFixedHeight(42)
        btn_cancelar.setFixedWidth(120)
        btn_cancelar.setStyleSheet(f"""
            QPushButton {{
                background: {C_GRIS_FONDO}; color: {C_NEGRO};
                border: 1.5px solid {C_GRIS_BORDE}; border-radius: 8px;
                font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {C_GRIS_BORDE}; }}
        """)
        btn_cancelar.clicked.connect(self.reject)
        f_lay.addWidget(btn_cancelar)
        f_lay.addStretch()

        self.lbl_alerta = QLabel("")
        self.lbl_alerta.setStyleSheet(f"font-size:12px; color:{C_ROJO}; font-weight:600;")
        f_lay.addWidget(self.lbl_alerta)

        self.btn_confirmar = QPushButton("✓  Confirmar salida")
        self.btn_confirmar.setFixedHeight(42)
        self.btn_confirmar.setFixedWidth(180)
        self.btn_confirmar.setStyleSheet(f"""
            QPushButton {{
                background: {C_ROJO}; color: #FFFFFF;
                border: none; border-radius: 8px;
                font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {C_ROJO_DARK}; }}
            QPushButton:disabled {{ background: {C_GRIS_BORDE}; color: {C_GRIS_MED}; }}
        """)
        self.btn_confirmar.clicked.connect(self._confirmar)
        f_lay.addWidget(self.btn_confirmar)
        root.addWidget(footer)

    # ── lógica ───────────────────────────────────────────────────

    def _on_monto_changed(self, valor: float):
        self.lbl_total.setText(f"$ {valor:,.0f}")
        self.lbl_alerta.setText(
            "" if valor > 0 else "⚠ Ingresa un monto mayor a cero"
        )

    def _confirmar(self):
        monto = self.spin_monto.value()
        if monto <= 0:
            QMessageBox.warning(self, "Monto requerido",
                                "Ingresa el monto que sale de caja.")
            return

        categoria   = self.combo_categoria.currentText()
        descripcion = self.input_desc.text().strip()

        try:
            numero_recibo = registrar_salidas(
                monto=monto,
                categoria=categoria,
                concepto=descripcion,
                usuario_id=self.usuario_id,
            )

            QMessageBox.information(
                self, "Salida registrada",
                f"✓ Salida de $ {monto:,.0f} registrada exitosamente."
            )

            respuesta = QMessageBox.question(
                self, "Imprimir comprobante",
                f"¿Desea generar e imprimir el comprobante N°: {numero_recibo}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if respuesta == QMessageBox.StandardButton.Yes:
                try:
                    cajero = _obtener_nombre_cajero(self.usuario_id)
                    concepto_final = f"{categoria}" + (f" — {descripcion}" if descripcion else "")
                    datos_recibo = {
                        "numero_recibo": numero_recibo,
                        "concepto":      concepto_final,
                        "valor":         monto,
                        "metodo_pago":   "Efectivo",
                        "cajero":        cajero,
                        "observaciones": descripcion,
                    }
                    pdf_path = generar_recibo_salida(datos_recibo)
                    abrir_pdf(pdf_path)
                except Exception as e_pdf:
                    QMessageBox.warning(self, "Recibo no generado",
                                        f"No se pudo generar el PDF:\n{e_pdf}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))