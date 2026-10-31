#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vista de Control de Pagos — CEA PRACTICAR
Estética: sidebar oscuro, rojo #C8252A, azul #1A2B6B, Nunito/Bebas Neue.
"""

import uuid
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QMessageBox, QComboBox, QTextEdit, QDialog,
    QFormLayout, QSplitter, QListWidget, QListWidgetItem,
    QDoubleSpinBox, QAbstractItemView, QScrollArea,
    QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from views.salidas_caja import DialogoSalida, obtener_salidas_dia
from views.recibo_generator import generar_recibo_pago, abrir_pdf

from database import Database
from views.ingresos_caja import DialogoIngreso, obtener_ingresos_dia

from views.utils_caja import (
    C_ROJO, C_ROJO_DARK, C_ROJO_LIGHT, C_AZUL, C_AZUL_LIGHT,
    C_GRIS_FONDO, C_GRIS_BORDE, C_GRIS_TEXTO, C_BLANCO,
    C_VERDE, C_VERDE_LIGHT, C_NEGRO, C_GRIS_MED,
    _separador, _lbl_seccion,
)
# ─────────────────────────────────────────────────────────────────
#  CONFIG DB
# ─────────────────────────────────────────────────────────────────



# ─────────────────────────────────────────────────────────────────
#  PALETA
# ─────────────────────────────────────────────────────────────────
C_ROJO        = "#C8252A"
C_ROJO_DARK   = "#9E1C20"
C_ROJO_LIGHT  = "#FDEAEA"
C_AZUL        = "#1A2B6B"
C_AZUL_LIGHT  = "#E8ECF9"
C_GRIS_FONDO  = "#F3F4F8"
C_GRIS_BORDE  = "#D1D5DB"
C_GRIS_TEXTO  = "#374151"
C_BLANCO      = "#FFFFFF"
C_VERDE       = "#15803D"
C_VERDE_LIGHT = "#DCFCE7"
C_SIDEBAR     = "#111827"
C_NEGRO       = "#111827"
C_GRIS_MED    = "#6B7280"

DENOMINACIONES = [
    # (valor, emoji, color_indicador, tipo)
    (100_000, "$100.000", "#059669", "billete"),   # verde esmeralda
    ( 50_000, "$50.000",  "#7C3AED", "billete"),   # púrpura/violeta
    ( 20_000, "$20.000",  "#0EA5E9", "billete"),   # azul celeste
    ( 10_000, "$10.000",  "#EA580C", "billete"),   # naranja/ladrillo
    (  5_000, "$5.000",   "#DC2626", "billete"),   # rojo
    (  2_000, "$2.000",   "#0891B2", "billete"),   # cyan
    (  1_000, "$1.000",   "#B45309", "moneda"),    # cobre/dorado
    (    500, "$500",      "#B45309", "moneda"),    # cobre/dorado
    (    200, "$200",      "#B45309", "moneda"),    # cobre/dorado
    (    100, "$100",      "#9CA3AF", "moneda"),    # plateado/gris
    (     50, "$50",       "#9CA3AF", "moneda"),    # plateado/gris
]


# ─────────────────────────────────────────────────────────────────
#  BASE DE DATOS
# ─────────────────────────────────────────────────────────────────
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


def buscar_alumnos(termino: str, anio: int = None):
    termino = termino.strip()
    if not termino:
        return []
    like = f"%{termino}%"
    db = Database.get_instance()
    if anio:
        return db.fetchall("""
            SELECT m.id AS matricula_id,
                   m.numero_orden, m.anio, m.categoria, m.estado,
                   a.numero_documento, a.nombres, a.apellidos
            FROM matriculas m
            JOIN alumnos a ON a.numero_documento = m.numero_documento
            WHERE m.estado != 'Histórico'
              AND m.anio = %s
              AND (a.numero_documento LIKE %s
               OR a.nombres LIKE %s
               OR a.apellidos LIKE %s
               OR CONCAT(m.numero_orden, '-', RIGHT(m.anio, 2)) LIKE %s)
            ORDER BY m.fecha_registro DESC
            LIMIT 40
        """, (anio, like, like, like, like))
    return db.fetchall("""
        SELECT m.id AS matricula_id,
               m.numero_orden, m.anio, m.categoria, m.estado,
               a.numero_documento, a.nombres, a.apellidos
        FROM matriculas m
        JOIN alumnos a ON a.numero_documento = m.numero_documento
        WHERE (a.numero_documento LIKE %s
           OR a.nombres LIKE %s
           OR a.apellidos LIKE %s
           OR CONCAT(m.numero_orden, '-', RIGHT(m.anio, 2)) LIKE %s)
        ORDER BY m.fecha_registro DESC
        LIMIT 40
    """, (like, like, like, like))

def obtener_pagos_alumno(matricula_id: int):
    db = Database.get_instance()
    return db.fetchall("""
        SELECT p.id, p.numero_recibo, p.concepto, p.valor,
               p.metodo_pago, p.fecha_pago, p.observaciones,
               u.nombre AS cajera
        FROM   pagos p
        JOIN   usuarios u ON u.id = p.usuario_id
        WHERE  p.id_matricula = %s
        ORDER  BY p.fecha_pago DESC
    """, (matricula_id,))


def total_pagado(matricula_id: int) -> float:
    db = Database.get_instance()
    row = db.fetchone(
        "SELECT COALESCE(SUM(valor),0) AS total FROM pagos WHERE id_matricula=%s",
        (matricula_id,)
    )
    return float(row["total"]) if row else 0.0

def obtener_valor_curso(matricula_id: int) -> float:
    db = Database.get_instance()
    row = db.fetchone(
        "SELECT precio_total FROM matriculas WHERE id = %s",
        (matricula_id,)
    )
    return float(row["precio_total"]) if row and row["precio_total"] else 0.0

def obtener_egresos_dia() -> list[dict]:
    from datetime import date
    hoy = date.today().strftime("%Y-%m-%d")
    db = Database.get_instance()
    return db.fetchall("""
        SELECT s.numero_recibo, s.concepto, s.valor,
               TIME_FORMAT(s.fecha_salida, '%H:%i') AS hora,
               u.nombre AS cajero
        FROM salidas_caja s
        JOIN usuarios u ON u.id = s.usuario_id
        WHERE DATE(s.fecha_salida) = %s
        ORDER BY s.fecha_salida DESC
    """, (hoy,))

def generar_numero_recibo() -> str:
    hoy    = datetime.now().strftime("%Y%m%d")
    sufijo = uuid.uuid4().hex[:4].upper()
    return f"CEA-{hoy}-{sufijo}"

def obtener_nombre_usuario(usuario_id: int) -> str:
    db = Database.get_instance()
    row = db.fetchone("SELECT nombre FROM usuarios WHERE id = %s", (usuario_id,))
    return row["nombre"] if row else f"Usuario #{usuario_id}"


def registrar_pago(matricula_id: int, concepto: str, valor: float,
                   metodo: str, observaciones: str, usuario_id: int = 1,
                   desglose: list[dict] | None = None,
                   acompanante: str = "") -> str:

    numero_recibo = generar_numero_recibo()
    db = Database.get_instance()

    pago_id = db.execute("""
        INSERT INTO pagos
            (id_matricula, concepto, valor, metodo_pago, numero_recibo, usuario_id, observaciones, acompanante)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (matricula_id, concepto, valor, metodo,
          numero_recibo, usuario_id, observaciones, acompanante or None))

    if metodo == "Efectivo" and desglose:
        filas = [(pago_id, d["denominacion"], d["cantidad"], d["tipo"])
                 for d in desglose if d["cantidad"] > 0]
        if filas:
            db.execute_many("""
                INSERT INTO desglose_efectivo (pago_id, denominacion, cantidad, tipo)
                VALUES (%s, %s, %s, %s)
            """, filas)

    # Recalcular estado de la matrícula
    row_total = db.fetchone(
        "SELECT COALESCE(SUM(valor), 0) AS total FROM pagos WHERE id_matricula = %s",
        (matricula_id,)
    )
    total_pag = float(row_total["total"] or 0)

    row_precio = db.fetchone(
        "SELECT precio_total FROM matriculas WHERE id = %s",
        (matricula_id,)
    )
    precio = float(row_precio["precio_total"] or 0)

    if total_pag >= precio and precio > 0:
        nuevo_estado = "Cancelado"
    elif total_pag > 0:
        nuevo_estado = "Pendiente Pago"
    else:
        nuevo_estado = "Activo"

    db.execute("UPDATE matriculas SET estado = %s WHERE id = %s", (nuevo_estado, matricula_id))

    return numero_recibo
# ─────────────────────────────────────────────────────────────────
#  HELPERS UI
# ─────────────────────────────────────────────────────────────────

def _separador():
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"color: {C_GRIS_BORDE}; background: {C_GRIS_BORDE}; max-height:1px;")
    return sep


def _lbl_seccion(texto: str) -> QLabel:
    lbl = QLabel(texto.upper())
    lbl.setStyleSheet(f"""
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.12em;
        color: {C_GRIS_MED};
        padding-bottom: 2px;
    """)
    return lbl


def _campo_style() -> str:
    return f"""
        QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit, QSpinBox {{
            background: {C_BLANCO};
            border: 1px solid #E2E8F0;
            border-radius: 7px;
            padding: 6px 10px;
            font-size: 13px;
            color: {C_NEGRO};
        }}
        QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
            border: 1.5px solid {C_AZUL};
        }}
        QComboBox::drop-down {{ border: none; }}
    """


# ─────────────────────────────────────────────────────────────────
#  DIÁLOGO: REGISTRAR PAGO
# ─────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────
#  DIÁLOGO: REGISTRAR PAGO  (versión simplificada)
# ─────────────────────────────────────────────────────────────────

class DialogoPago(QDialog):
 
    def __init__(self, alumno: dict, saldo_pendiente: float, valor_curso: float, parent=None):
        super().__init__(parent)
        self.valor_curso     = valor_curso
        self.alumno          = alumno
        self.saldo_pendiente = saldo_pendiente
        self.setWindowTitle("Registrar pago")
        _tamanio_adaptativo(self, 680, 680)
        self.setModal(True)
        self._build()
 
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
 
        # ── Cabecera azul ──────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(f"background: {C_AZUL};")
        header.setFixedHeight(96)
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(32, 16, 32, 16)
        h_lay.setSpacing(3)
 
        lbl_titulo = QLabel("Registrar pago")
        lbl_titulo.setStyleSheet("font-size:18px; font-weight:800; color:#FFFFFF;")
 
        nombre = f"{self.alumno['nombres']} {self.alumno['apellidos']}"
        lbl_nombre = QLabel(nombre)
        lbl_nombre.setStyleSheet("font-size:13px; color:rgba(255,255,255,0.75); font-weight:600;")
 
        lbl_doc = QLabel(
            f"C.C. {self.alumno['numero_documento']}  ·  Categoría {self.alumno['categoria']}"
        )
        lbl_doc.setStyleSheet("font-size:11px; color:rgba(255,255,255,0.55);")
 
        h_lay.addWidget(lbl_titulo)
        h_lay.addWidget(lbl_nombre)
        h_lay.addWidget(lbl_doc)
        root.addWidget(header)
 
        # ── Cuerpo con scroll ─────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {C_BLANCO}; border: none;")
 
        body = QWidget()
        body.setStyleSheet(f"background: {C_BLANCO};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(36, 28, 36, 28)
        body_lay.setSpacing(20)
 
        # ── Resumen saldo ──────────────────────────────────────────
        resumen = QFrame()
        resumen.setStyleSheet(f"""
            QFrame {{
                background: {C_ROJO_LIGHT};
                border: 1.5px solid #FBBDBD;
                border-radius: 10px;
            }}
        """)
        res_lay = QHBoxLayout(resumen)
        res_lay.setContentsMargins(16, 12, 16, 12)
 
        col_saldo = QVBoxLayout()
        col_saldo.setSpacing(2)
        lbl_s_titulo = QLabel("Saldo pendiente")
        lbl_s_titulo.setStyleSheet(f"font-size:11px; font-weight:700; color:{C_ROJO};")
        lbl_saldo_val = QLabel(f"$ {self.saldo_pendiente:,.0f}".replace(",", "."))
        lbl_saldo_val.setStyleSheet(f"font-size:22px; font-weight:800; color:{C_ROJO};")
        col_saldo.addWidget(lbl_s_titulo)
        col_saldo.addWidget(lbl_saldo_val)
        res_lay.addLayout(col_saldo)
        res_lay.addStretch()
 
        col_curso = QVBoxLayout()
        col_curso.setSpacing(2)
        col_curso.setAlignment(Qt.AlignmentFlag.AlignRight)
        lbl_c_titulo = QLabel("Valor del curso")
        lbl_c_titulo.setAlignment(Qt.AlignmentFlag.AlignRight)
        lbl_c_titulo.setStyleSheet(f"font-size:11px; font-weight:700; color:{C_GRIS_TEXTO};")
        lbl_c_val = QLabel(f"$ {self.valor_curso:,.0f}".replace(",", "."))
        lbl_c_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        lbl_c_val.setStyleSheet(f"font-size:16px; font-weight:700; color:{C_GRIS_TEXTO};")
        col_curso.addWidget(lbl_c_titulo)
        col_curso.addWidget(lbl_c_val)
        res_lay.addLayout(col_curso)
        body_lay.addWidget(resumen)
 
        # ── Formulario ────────────────────────────────────────────
        body_lay.addWidget(_lbl_seccion("Información del pago"))
 
        form_frame = QFrame()
        form_frame.setStyleSheet(f"""
            QFrame {{
                background: {C_GRIS_FONDO};
                border: 1.5px solid {C_GRIS_BORDE};
                border-radius: 10px;
            }}
            QComboBox, QLineEdit, QTextEdit {{
                background: {C_BLANCO};
                border: 1.5px solid {C_GRIS_BORDE};
                border-radius: 7px;
                padding: 6px 10px;
                font-size: 13px;
                color: {C_NEGRO};
            }}
            QComboBox:focus, QLineEdit:focus {{ border: 1.5px solid {C_AZUL}; }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
        """)
        form_lay = QGridLayout(form_frame)
        form_lay.setContentsMargins(20, 18, 20, 18)
        form_lay.setSpacing(14)
        form_lay.setColumnStretch(1, 1)
 
        def _lbl_campo(texto):
            l = QLabel(texto)
            l.setStyleSheet(
                f"font-size:11px; font-weight:700; color:{C_AZUL}; letter-spacing:0.05em;"
            )
            l.setMinimumWidth(130)
            return l
 
        # Concepto
        form_lay.addWidget(_lbl_campo("CONCEPTO"), 0, 0)
        self.concepto_input = QLineEdit()
        self.concepto_input.setPlaceholderText("Ej: Abono, Pago total…")
        self.concepto_input.setText("Pago curso de conducción")
        self.concepto_input.setFixedHeight(42)
        form_lay.addWidget(self.concepto_input, 0, 1)
 
        # Método de pago
        form_lay.addWidget(_lbl_campo("MÉTODO DE PAGO"), 1, 0)
        self.metodo_combo = QComboBox()
        self.metodo_combo.addItems(["Efectivo", "Transferencia", "Nequi", "Daviplata", "Otro"])
        self.metodo_combo.setFixedHeight(42)
        self.metodo_combo.currentTextChanged.connect(self._toggle_vuelto)
        form_lay.addWidget(self.metodo_combo, 1, 1)
 
        # Monto que abona
        form_lay.addWidget(_lbl_campo("MONTO QUE ABONA"), 2, 0)
        self.campo_abono = CampoMoneda()
        self.campo_abono.setFixedHeight(44)
        self.campo_abono.setStyleSheet(f"""
            QLineEdit {{
                background: {C_BLANCO};
                border: 1.5px solid {C_GRIS_BORDE};
                border-radius: 7px;
                padding: 6px 14px;
                font-size: 17px;
                font-weight: 700;
                color: {C_NEGRO};
            }}
            QLineEdit:focus {{ border: 1.5px solid {C_AZUL}; }}
        """)
        form_lay.addWidget(self.campo_abono, 2, 1)
 
        # Vuelto (solo efectivo)
        self.lbl_vuelto = _lbl_campo("VUELTO")
        form_lay.addWidget(self.lbl_vuelto, 3, 0)
        self.campo_vuelto = CampoMoneda()
        self.campo_vuelto.setFixedHeight(44)
        self.campo_vuelto.setStyleSheet(f"""
            QLineEdit {{
                background: {C_BLANCO};
                border: 1.5px solid {C_GRIS_BORDE};
                border-radius: 7px;
                padding: 6px 14px;
                font-size: 17px;
                font-weight: 700;
                color: {C_VERDE};
            }}
            QLineEdit:focus {{ border: 1.5px solid {C_AZUL}; }}
        """)
        form_lay.addWidget(self.campo_vuelto, 3, 1)
 
        # Acompañante
        form_lay.addWidget(_lbl_campo("ACOMPAÑANTE"), 4, 0)
        self.acompanante_input = QLineEdit()
        self.acompanante_input.setPlaceholderText("Nombre (dejar vacío si el alumno asiste)")
        self.acompanante_input.setFixedHeight(42)
        form_lay.addWidget(self.acompanante_input, 4, 1)
 
        # Observaciones
        form_lay.addWidget(_lbl_campo("NOTAS"), 5, 0, Qt.AlignmentFlag.AlignTop)
        self.obs_input = QTextEdit()
        self.obs_input.setPlaceholderText("Observaciones opcionales…")
        self.obs_input.setFixedHeight(72)
        form_lay.addWidget(self.obs_input, 5, 1)
 
        body_lay.addWidget(form_frame)
        body_lay.addStretch()
 
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
 
        # ── Footer ────────────────────────────────────────────────
        footer = QFrame()
        footer.setStyleSheet(
            f"QFrame {{ background:{C_BLANCO}; border-top:1px solid {C_GRIS_BORDE}; }}"
        )
        footer.setFixedHeight(76)
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(36, 0, 36, 0)
        f_lay.setSpacing(12)
 
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setFixedHeight(46)
        btn_cancelar.setFixedWidth(130)
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
 
        self.btn_registrar = QPushButton("✓  Confirmar pago")
        self.btn_registrar.setFixedHeight(46)
        self.btn_registrar.setFixedWidth(180)
        self.btn_registrar.setStyleSheet(f"""
            QPushButton {{
                background: {C_ROJO}; color: #FFFFFF;
                border: none; border-radius: 8px;
                font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {C_ROJO_DARK}; }}
            QPushButton:disabled {{ background: {C_GRIS_BORDE}; color: {C_GRIS_MED}; }}
        """)
        self.btn_registrar.clicked.connect(self._validar)
        f_lay.addWidget(self.btn_registrar)
        root.addWidget(footer)
 
        # Estado inicial
        self._toggle_vuelto(self.metodo_combo.currentText())
 
    # ── LÓGICA ───────────────────────────────────────────────────
 
    def _toggle_vuelto(self, metodo: str):
        """Muestra el campo Vuelto solo cuando el método es Efectivo."""
        es_efectivo = metodo == "Efectivo"
        self.lbl_vuelto.setVisible(es_efectivo)
        self.campo_vuelto.setVisible(es_efectivo)
        if not es_efectivo:
            self.campo_vuelto.setValor(0)
        self.lbl_alerta.setText("")
 
    def _validar(self):
        if not self.concepto_input.text().strip():
            QMessageBox.warning(self, "Campo requerido", "Escribe un concepto para el pago.")
            return
        if self.valor <= 0:
            QMessageBox.warning(self, "Valor inválido", "El monto que abona debe ser mayor a $0.")
            return
        self.accept()
 
    # ── PROPIEDADES ──────────────────────────────────────────────
 
    @property
    def concepto(self) -> str:
        return self.concepto_input.text().strip()
 
    @property
    def valor(self) -> float:
        """Monto registrado como abono en la BD."""
        return self.campo_abono.valor()
 
    @property
    def vuelto(self) -> float:
        """Vuelto ingresado manualmente por el empleado."""
        if self.metodo_combo.currentText() != "Efectivo":
            return 0.0
        return self.campo_vuelto.valor()
 
    @property
    def metodo(self) -> str:
        return self.metodo_combo.currentText()
 
    @property
    def observaciones(self) -> str:
        return self.obs_input.toPlainText().strip()
 
    @property
    def acompanante(self) -> str:
        return self.acompanante_input.text().strip()


# ─────────────────────────────────────────────────────────────────
#  TARJETA RESUMEN DEL ALUMNO
# ─────────────────────────────────────────────────────────────────

class TablaMovimientosDia(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        header_row = QHBoxLayout()
        from datetime import date
        fecha_hoy = date.today().strftime("%d/%m/%Y")
        lbl_titulo = QLabel(f"MOVIMIENTOS DEL DÍA — {fecha_hoy}")
        lbl_titulo.setStyleSheet(f"font-size:11px; font-weight:700; letter-spacing:0.1em; color:{C_GRIS_MED};")
        header_row.addWidget(lbl_titulo)
        header_row.addStretch()

        self.lbl_total_ingresos = QLabel("Ingresos: $0")
        self.lbl_total_ingresos.setStyleSheet(f"font-size:13px; font-weight:800; color:{C_VERDE};")
        header_row.addWidget(self.lbl_total_ingresos)

        self.lbl_total_egresos = QLabel("Egresos: $0")
        self.lbl_total_egresos.setStyleSheet(f"font-size:13px; font-weight:800; color:{C_ROJO};")
        header_row.addWidget(self.lbl_total_egresos)

        root.addLayout(header_row)

        self.tabla = QTableWidget()
        cols = ["# Recibo", "Tipo", "Motivo / Concepto", "Valor", "Hora", "Cajero"]
        self.tabla.setColumnCount(len(cols))
        self.tabla.setHorizontalHeaderLabels(cols)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setShowGrid(False)
        self.tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 160)
        self.tabla.setColumnWidth(1, 80)
        self.tabla.setColumnWidth(3, 100)
        self.tabla.setColumnWidth(4, 70)
        self.tabla.setColumnWidth(5, 120)
        root.addWidget(self.tabla)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_imprimir = QPushButton("🖨  Imprimir movimientos del día")
        self.btn_imprimir.setFixedHeight(36)
        self.btn_imprimir.setFixedWidth(250)
        self.btn_imprimir.setStyleSheet(f"""
            QPushButton {{
                background: {C_AZUL}; color: #FFFFFF;
                border: none; border-radius: 8px;
                font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover {{ background: #142258; }}
        """)
        self.btn_imprimir.clicked.connect(self._imprimir)
        btn_row.addWidget(self.btn_imprimir)
        root.addLayout(btn_row)

    def actualizar(self):
        from datetime import date
        fecha_hoy = date.today().strftime("%Y-%m-%d")

        # Cargar egresos
        try:
            egresos = obtener_egresos_dia()
        except Exception:
            egresos = []

        # Cargar ingresos
        try:
            ingresos = obtener_ingresos_dia(fecha_hoy)
        except Exception:
            ingresos = []

        self.tabla.setRowCount(0)
        total_egresos = 0.0
        total_ingresos = 0.0

        # Preparar lista combinada
        movimientos = []

        for e in egresos:
            movimientos.append({
                "tipo": "EGRESO",
                "recibo": e.get("numero_recibo", ""),
                "concepto": e.get("concepto", ""),
                "valor": float(e.get("valor", 0)),
                "hora": e.get("hora", ""),
                "cajero": e.get("cajero", ""),
            })

        for i in ingresos:
            movimientos.append({
                "tipo": "INGRESO",
                "recibo": i.get("numero_recibo", ""),
                "concepto": i.get("concepto", ""),
                "valor": float(i.get("valor", 0)),
                "hora": i.get("hora", ""),
                "cajero": i.get("cajero", ""),
            })

        # Ordenar por hora
        movimientos.sort(key=lambda x: x["hora"])

        if not movimientos:
            self.tabla.setRowCount(1)
            cell = QTableWidgetItem("Sin movimientos registrados hoy.")
            cell.setForeground(QColor(C_GRIS_MED))
            self.tabla.setItem(0, 0, cell)
            self.tabla.setSpan(0, 0, 1, self.tabla.columnCount())
            self.lbl_total_egresos.setText("Egresos: $0")
            self.lbl_total_ingresos.setText("Ingresos: $0")
            return

        for mov in movimientos:
            row = self.tabla.rowCount()
            self.tabla.insertRow(row)
            valor = mov["valor"]

            if mov["tipo"] == "EGRESO":
                total_egresos += valor
            else:
                total_ingresos += valor

            # Badge de tipo
            tipo_texto = "↓ Salida" if mov["tipo"] == "EGRESO" else "↑ Entrada"
            tipo_color = C_ROJO if mov["tipo"] == "EGRESO" else C_VERDE

            valores = [
                mov["recibo"],
                tipo_texto,
                mov["concepto"],
                f"${valor:,.0f}",
                mov["hora"],
                mov["cajero"],
            ]
            for col, texto in enumerate(valores):
                cell = QTableWidgetItem(str(texto))
                cell.setForeground(QColor(C_NEGRO))
                if col == 1:  # Tipo
                    cell.setForeground(QColor(tipo_color))
                    font = QFont()
                    font.setBold(True)
                    cell.setFont(font)
                if col == 3:  # Valor
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    cell.setForeground(QColor(tipo_color))
                self.tabla.setItem(row, col, cell)
            self.tabla.setRowHeight(row, 38)

        self.lbl_total_egresos.setText(f"Egresos: ${total_egresos:,.0f}")
        self.lbl_total_ingresos.setText(f"Ingresos: ${total_ingresos:,.0f}")

    def _imprimir(self):
        try:
            from views.recibo_generator import generar_reporte_movimientos_dia, abrir_pdf
            from datetime import date
            fecha_hoy = date.today().strftime("%Y-%m-%d")
            egresos = obtener_salidas_dia(fecha_hoy)
            ingresos = obtener_ingresos_dia(fecha_hoy)
            pdf_path = generar_reporte_movimientos_dia(egresos, ingresos, date.today().strftime("%d/%m/%Y"))
            abrir_pdf(pdf_path)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo generar el reporte:\n{e}")          


class TarjetaAlumno(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tarjetaAlumno")
        self._build()
        self.hide()

    def _build(self):
        self.setStyleSheet(f"""
            #tarjetaAlumno {{
                background: {C_AZUL};
                border-radius: 12px;
            }}
            #tarjetaAlumno QLabel {{
                background: transparent;
                text-decoration: none;
            }}
        """)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(22, 16, 22, 16)
        outer.setSpacing(0)

        left = QVBoxLayout()
        left.setSpacing(3)
        self.lbl_nombre = QLabel("—")
        self.lbl_nombre.setStyleSheet("font-size:17px; font-weight:800; color:#FFFFFF; text-decoration:none; background:transparent;")
        left.addWidget(self.lbl_nombre)
        self.lbl_doc = QLabel("")
        self.lbl_doc.setStyleSheet("font-size:12px; color:rgba(255,255,255,0.80); text-decoration:none; background:transparent;")
        left.addWidget(self.lbl_doc)
        self.lbl_cat = QLabel("")
        self.lbl_cat.setStyleSheet("font-size:12px; color:rgba(255,255,255,0.80); text-decoration:none; background:transparent;")
        left.addWidget(self.lbl_cat)
        outer.addLayout(left, 1)

        mid = QVBoxLayout()
        mid.setSpacing(4)
        mid.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        lbl_prog = QLabel("PROGRESO DE PAGO")
        lbl_prog.setStyleSheet("font-size:9px; font-weight:700; color:rgba(255,255,255,0.55); letter-spacing:0.1em; background:transparent;")
        lbl_prog.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mid.addWidget(lbl_prog)
        self.barra_cont = QFrame()
        self.barra_cont.setFixedSize(200, 10)
        self.barra_cont.setStyleSheet("background:rgba(255,255,255,0.15); border-radius:5px;")
        self.barra_relleno = QFrame(self.barra_cont)
        self.barra_relleno.setGeometry(0, 0, 0, 10)
        self.barra_relleno.setStyleSheet(f"background:{C_ROJO}; border-radius:5px;")
        mid.addWidget(self.barra_cont, alignment=Qt.AlignmentFlag.AlignCenter)
        self.lbl_pct = QLabel("0%")
        self.lbl_pct.setStyleSheet("font-size:11px; font-weight:700; color:rgba(255,255,255,0.85); background:transparent;")
        self.lbl_pct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mid.addWidget(self.lbl_pct)
        outer.addLayout(mid, 1)

        right = QVBoxLayout()
        right.setSpacing(2)
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_saldo_titulo = QLabel("SALDO PENDIENTE")
        lbl_saldo_titulo.setStyleSheet("font-size:9px; font-weight:700; color:rgba(255,255,255,0.55); letter-spacing:0.1em; background:transparent;")
        lbl_saldo_titulo.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(lbl_saldo_titulo)
        self.lbl_saldo = QLabel("—")
        self.lbl_saldo.setStyleSheet(f"font-size:26px; font-weight:800; color:#FFFFFF; background:transparent; text-decoration:none;")
        self.lbl_saldo.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.lbl_saldo)
        self.lbl_pagado = QLabel("")
        self.lbl_pagado.setStyleSheet("font-size:11px; color:rgba(255,255,255,0.65); background:transparent;")
        self.lbl_pagado.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.lbl_pagado)
        outer.addLayout(right, 1)

    def actualizar(self, alumno: dict, pagado: float, valor_curso: float) -> float:
        saldo = max(valor_curso - pagado, 0)
        pct   = min(pagado / valor_curso, 1.0) if valor_curso > 0 else 0

        self.lbl_nombre.setText(f"{alumno['nombres']} {alumno['apellidos']}")
        self.lbl_doc.setText(f"C.C. {alumno['numero_documento']}  ·  Estado: {alumno['estado']}")
        self.lbl_cat.setText(f"Categoría: {alumno['categoria']}")

        ancho = int(200 * pct)
        self.barra_relleno.setGeometry(0, 0, ancho, 10)
        self.barra_relleno.setStyleSheet(f"background:{'#86EFAC' if pct >= 1.0 else C_ROJO}; border-radius:5px;")
        self.lbl_pct.setText(f"{int(pct*100)}%")

        if saldo == 0:
            self.lbl_saldo.setText("Al día ✓")
            self.lbl_saldo.setStyleSheet("font-size:22px; font-weight:800; color:#86EFAC; background:transparent; text-decoration:none;")
        else:
            self.lbl_saldo.setText(f"${saldo:,.0f}")
            self.lbl_saldo.setStyleSheet(f"font-size:26px; font-weight:800; color:#FFFFFF; background:transparent; text-decoration:none;")

        self.lbl_pagado.setText(f"Pagado: ${pagado:,.0f}  /  Curso: ${valor_curso:,.0f}")
        self.show()
        return saldo


# ─────────────────────────────────────────────────────────────────
#  VISTA PRINCIPAL DE PAGOS
# ─────────────────────────────────────────────────────────────────

class PagosView(QWidget):
    pago_registrado = pyqtSignal()

    _GLOBAL_STYLE = f"""
        QWidget {{ font-family: 'Nunito', 'Segoe UI', sans-serif; }}
        QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit, QSpinBox {{
            background: {C_BLANCO}; border: 1.5px solid {C_GRIS_BORDE};
            border-radius: 7px; padding: 6px 10px; font-size: 13px; color: {C_NEGRO};
        }}
        QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{ border: 1.5px solid {C_AZUL}; }}
        QListWidget {{
            background: {C_BLANCO}; border: 1.5px solid {C_GRIS_BORDE};
            border-radius: 8px; padding: 4px; color: {C_NEGRO}; font-size: 13px;
        }}
        QListWidget::item {{ border-radius: 6px; padding: 8px 10px; color: {C_NEGRO}; }}
        QListWidget::item:selected {{ background: {C_AZUL_LIGHT}; color: {C_AZUL}; }}
        QListWidget::item:hover {{ background: {C_GRIS_FONDO}; }}
        QTableWidget {{
            background: {C_BLANCO}; border: 1.5px solid {C_GRIS_BORDE};
            border-radius: 8px; gridline-color: {C_GRIS_FONDO}; color: {C_NEGRO}; font-size: 13px;
        }}
        QHeaderView::section {{
            background: {C_GRIS_FONDO}; color: {C_GRIS_TEXTO}; font-size: 11px;
            font-weight: 700; letter-spacing: 0.06em; padding: 8px;
            border: none; border-bottom: 1px solid {C_GRIS_BORDE};
        }}
        QTableWidget::item {{ padding: 6px 8px; color: {C_NEGRO}; }}
        QTableWidget::item:selected {{ background: {C_AZUL_LIGHT}; color: {C_AZUL}; }}
        QPushButton {{
            background: {C_AZUL}; color: #FFFFFF; border: none;
            border-radius: 8px; padding: 0 16px; font-size: 13px; font-weight: 700;
        }}
        QPushButton:hover {{ background: #142258; }}
        QPushButton:disabled {{ background: {C_GRIS_BORDE}; color: {C_GRIS_MED}; }}
    """

    def __init__(self, usuario_id: int = 1):
        super().__init__()
        self.usuario_id   = usuario_id
        self._alumno      = None
        self._valor_curso = 0.0
        self.setStyleSheet(self._GLOBAL_STYLE)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"background: {C_BLANCO}; border: none;")

        body = QWidget()
        body.setStyleSheet(f"background: {C_BLANCO};")
        inner = QVBoxLayout(body)
        inner.setContentsMargins(28, 16, 28, 16)
        inner.setSpacing(12)

        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por código, cédula, nombre o apellido…")
        self.search_input.setFixedHeight(42)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {C_BLANCO}; border: 1.5px solid {C_GRIS_BORDE};
                border-radius: 7px; padding: 6px 10px; font-size: 13px; color: {C_NEGRO};
            }}
            QLineEdit:focus {{ border: 1.5px solid {C_AZUL}; }}
        """)
        self.search_input.returnPressed.connect(self._buscar)
        search_row.addWidget(self.search_input)

        from datetime import datetime as _dt_now
        anio_actual = _dt_now.now().year
        self.cmb_anio_filtro = QComboBox()
        self.cmb_anio_filtro.setFixedHeight(42)
        self.cmb_anio_filtro.setMinimumWidth(110)
        self.cmb_anio_filtro.addItem("Todos los años", 0)
        for a in range(anio_actual, anio_actual - 15, -1):
            self.cmb_anio_filtro.addItem(str(a), a)
        self.cmb_anio_filtro.setStyleSheet(f"""
            QComboBox {{
                background: {C_BLANCO}; border: 1.5px solid {C_GRIS_BORDE};
                border-radius: 7px; padding: 6px 10px; font-size: 13px; color: {C_NEGRO};
            }}
            QComboBox:focus {{ border: 1.5px solid {C_AZUL}; }}
            QComboBox::drop-down {{ border: none; width: 22px; }}
        """)
        search_row.addWidget(self.cmb_anio_filtro)

        btn_buscar = QPushButton("🔍  Buscar")
        btn_buscar.setFixedHeight(42)
        btn_buscar.setMinimumWidth(120)
        btn_buscar.clicked.connect(self._buscar)
        search_row.addWidget(btn_buscar)

        btn_salida = QPushButton("↓ Registrar salida")
        btn_salida.setFixedHeight(42)
        btn_salida.setMinimumWidth(160)
        btn_salida.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_salida.setStyleSheet(f"""
            QPushButton {{
                background: {C_ROJO}; color: #FFFFFF;
                border: none; border-radius: 8px;
                font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {C_ROJO_DARK}; }}
        """)
        btn_salida.clicked.connect(self._registrar_salida)
        search_row.addWidget(btn_salida)

        btn_ingreso = QPushButton("↑ Registrar ingreso")
        btn_ingreso.setFixedHeight(42)
        btn_ingreso.setMinimumWidth(160)
        btn_ingreso.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ingreso.setStyleSheet(f"""
            QPushButton {{
                background: {C_VERDE}; color: #FFFFFF;
                border: none; border-radius: 8px;
                font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover {{ background: #15803D; }}
        """)
        btn_ingreso.clicked.connect(self._registrar_ingreso)
        search_row.addWidget(btn_ingreso)

        inner.addLayout(search_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {C_GRIS_BORDE}; }}")

        left_panel = QWidget()
        left_panel.setMinimumWidth(220)
        left_panel.setMaximumWidth(290)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(_lbl_seccion("Resultados"))
        self.lista = QListWidget()
        self.lista.currentItemChanged.connect(self._on_alumno_seleccionado)
        left_layout.addWidget(self.lista)
        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(14)

        self.tarjeta = TarjetaAlumno()
        right_layout.addWidget(self.tarjeta)

        hist_row = QHBoxLayout()
        hist_row.addWidget(_lbl_seccion("Historial de pagos"))
        hist_row.addStretch()
        self.btn_pago = QPushButton("+ Registrar pago")
        self.btn_pago.setFixedHeight(36)
        self.btn_pago.setMinimumWidth(150)
        self.btn_pago.setEnabled(False)
        self.btn_pago.setStyleSheet(f"""
            QPushButton {{ background: {C_VERDE}; color: #FFFFFF; border: none; border-radius: 8px; font-size: 13px; font-weight: 700; }}
            QPushButton:hover {{ background: #15803D; }}
            QPushButton:disabled {{ background: {C_GRIS_BORDE}; color: {C_GRIS_MED}; }}
        """)
        self.btn_pago.clicked.connect(self._registrar_pago)
        hist_row.addWidget(self.btn_pago)

        self.btn_reimprimir = QPushButton("🖨 Reimprimir recibo")
        self.btn_reimprimir.setFixedHeight(36)
        self.btn_reimprimir.setMinimumWidth(165)
        self.btn_reimprimir.setEnabled(False)
        self.btn_reimprimir.setStyleSheet(f"""
            QPushButton {{ background: {C_AZUL}; color: #FFFFFF; border: none; border-radius: 8px; font-size: 13px; font-weight: 700; }}
            QPushButton:hover {{ background: #142258; }}
            QPushButton:disabled {{ background: {C_GRIS_BORDE}; color: {C_GRIS_MED}; }}
        """)
        self.btn_reimprimir.clicked.connect(self._reimprimir_recibo)
        hist_row.addWidget(self.btn_reimprimir)
        right_layout.addLayout(hist_row)

        self.tabla = QTableWidget()
        self._init_tabla()
        self.tabla.itemSelectionChanged.connect(self._on_fila_seleccionada)
        right_layout.addWidget(self.tabla)

        self.btn_volver = QPushButton("← Volver a movimientos del día")
        self.btn_volver.setFixedHeight(32)
        self.btn_volver.setMinimumWidth(200)
        self.btn_volver.setVisible(False)
        self.btn_volver.setStyleSheet(f"""
            QPushButton {{
                background: {C_GRIS_FONDO}; color: {C_AZUL};
                border: 1.5px solid {C_AZUL}; border-radius: 8px;
                font-size: 12px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {C_AZUL_LIGHT}; }}
        """)
        self.btn_volver.clicked.connect(self._mostrar_movimientos)
        hist_row.addWidget(self.btn_volver)

        self.movimientos_widget = TablaMovimientosDia()
        self.movimientos_widget.actualizar()
        self.movimientos_widget.tabla.itemSelectionChanged.connect(self._on_fila_movimiento_seleccionada)
        right_layout.addWidget(self.movimientos_widget)

        self.placeholder = QLabel("")
        self.placeholder.hide()
        right_layout.addWidget(self.placeholder)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        inner.addWidget(splitter)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    def _init_tabla(self):
        cols = ["# Recibo", "Concepto", "Valor", "Método", "Fecha", "Cajera", "Notas"]
        self.tabla.setColumnCount(len(cols))
        self.tabla.setHorizontalHeaderLabels(cols)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setShowGrid(False)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 165)
        self.tabla.setColumnWidth(2, 100)
        self.tabla.setColumnWidth(3, 115)
        self.tabla.setColumnWidth(4, 145)
        self.tabla.setColumnWidth(5, 120)
        self.tabla.hide()

    def _buscar(self):
        termino = self.search_input.text().strip()
        if not termino:
            QMessageBox.information(self, "Búsqueda vacía", "Escribe una cédula o nombre.")
            return
        try:
            anio_filtro = self.cmb_anio_filtro.currentData()
            resultados = buscar_alumnos(termino, anio_filtro if anio_filtro else None)
        except Exception as e:
            QMessageBox.critical(self, "Error de conexión", f"No se pudo conectar:\n{e}")
            return

        self.lista.clear()
        self._alumno = None
        self.tarjeta.hide()
        self.tabla.hide()
        self.placeholder.show()
        self.btn_pago.setEnabled(False)

        if not resultados:
            item = QListWidgetItem("Sin resultados")
            item.setForeground(QColor(C_GRIS_MED))
            self.lista.addItem(item)
            return

        for a in resultados:
            codigo = f"{a['numero_orden']}-{str(a['anio'])[-2:]}"
            texto = f"[{codigo}] {a['apellidos']}, {a['nombres']}\n{a['numero_documento']}  ·  Cat. {a['categoria']}"
            item = QListWidgetItem(texto)
            item.setForeground(QColor(C_NEGRO))
            item.setData(Qt.ItemDataRole.UserRole, a)  
            self.lista.addItem(item)

    def _on_alumno_seleccionado(self, current, _prev):
        if current is None:
            return
        alumno = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(alumno, dict):
            return
        self._alumno = alumno
        self.movimientos_widget.hide()      # ← CORREGIDO
        self.btn_volver.setVisible(True)
        self._cargar_pagos(alumno)

    def _cargar_pagos(self, alumno: dict):
        try:
            matricula_id = alumno["matricula_id"]
            pagos             = obtener_pagos_alumno(matricula_id)
            pagado            = total_pagado(matricula_id)
            self._valor_curso = obtener_valor_curso(matricula_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudieron cargar los pagos:\n{e}")
            return

        self.tarjeta.actualizar(alumno, pagado, self._valor_curso)
        self.placeholder.hide()
        self.btn_pago.setEnabled(True)
        self.tabla.show()
        self.tabla.setRowCount(0)

        if not pagos:
            self.tabla.setRowCount(1)
            cell = QTableWidgetItem("Sin pagos registrados para este alumno.")
            cell.setForeground(QColor(C_GRIS_MED))
            self.tabla.setItem(0, 0, cell)
            self.tabla.setSpan(0, 0, 1, self.tabla.columnCount())
            return

        for pago in pagos:
            row = self.tabla.rowCount()
            self.tabla.insertRow(row)
            fecha_str = (pago["fecha_pago"].strftime("%d/%m/%Y %H:%M")
                         if isinstance(pago["fecha_pago"], datetime)
                         else str(pago["fecha_pago"]))
            valores = [
                pago["numero_recibo"], pago["concepto"],
                f"${float(pago['valor']):,.0f}", pago["metodo_pago"],
                fecha_str, pago["cajera"], pago["observaciones"] or "—",
            ]
            for col, texto in enumerate(valores):
                cell = QTableWidgetItem(str(texto))
                cell.setForeground(QColor(C_NEGRO))
                if col == 2:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    cell.setForeground(QColor(C_VERDE))
                # Guardar dict completo del pago en la primera celda
                if col == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, pago)
                self.tabla.setItem(row, col, cell)
            self.tabla.setRowHeight(row, 38)

    def _on_fila_seleccionada(self):
        """Activa/desactiva el botón reimprimir según si hay fila seleccionada."""
        filas = self.tabla.selectedItems()
        self.btn_reimprimir.setEnabled(len(filas) > 0)

    def _reimprimir_recibo(self):
        """Regenera el PDF del recibo del pago o egreso seleccionado."""
                # Si estamos en vista de movimientos (egresos + ingresos)
        if self.movimientos_widget.isVisible():
            fila = self.movimientos_widget.tabla.currentRow()
            if fila < 0:
                return
            item_tipo = self.movimientos_widget.tabla.item(fila, 1)
            item_recibo = self.movimientos_widget.tabla.item(fila, 0)
            item_concepto = self.movimientos_widget.tabla.item(fila, 2)
            item_valor = self.movimientos_widget.tabla.item(fila, 3)
            item_cajero = self.movimientos_widget.tabla.item(fila, 5)
            if not item_recibo:
                return

            tipo = "salida" if "Salida" in item_tipo.text() else "ingreso"
            numero = item_recibo.text()

            respuesta = QMessageBox.question(
                self, "Reimprimir comprobante",
                f"¿Desea reimprimir el comprobante N°: {numero}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if respuesta != QMessageBox.StandardButton.Yes:
                return

            try:
                from views.recibo_generator import generar_recibo_salida, generar_recibo_ingreso, abrir_pdf
                valor_str = item_valor.text().replace("$", "").replace(",", "").replace(".", "")
                datos_recibo = {
                    "numero_recibo": numero,
                    "concepto":      item_concepto.text() if item_concepto else "",
                    "valor":         float(valor_str) if valor_str else 0.0,
                    "metodo_pago":   "Efectivo",
                    "cajero":        item_cajero.text() if item_cajero else "",
                    "observaciones": "",
                }
                if tipo == "salida":
                    pdf_path = generar_recibo_salida(datos_recibo)
                else:
                    pdf_path = generar_recibo_ingreso(datos_recibo)
                abrir_pdf(pdf_path)
            except Exception as e:
                QMessageBox.critical(self, "Error al generar recibo", str(e))
            return

        # Vista normal de pagos de alumno
        filas = self.tabla.selectedItems()
        if not filas:
            return
        fila = self.tabla.currentRow()
        item = self.tabla.item(fila, 0)
        if item is None:
            return
        pago = item.data(Qt.ItemDataRole.UserRole)
        if not pago or not isinstance(pago, dict):
            QMessageBox.warning(self, "Sin datos", "No se pudieron recuperar los datos de este recibo.")
            return

        respuesta = QMessageBox.question(
            self,
            "Reimprimir recibo",
            f"¿Desea reimprimir el recibo N°: {pago['numero_recibo']}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            cajero = obtener_nombre_usuario(self.usuario_id)
            datos_recibo = {
                "numero_recibo": pago["numero_recibo"],
                "alumno_nombre": f"{self._alumno['nombres']} {self._alumno['apellidos']}",
                "alumno_doc":    self._alumno["numero_documento"],
                "concepto":      pago["concepto"],
                "valor":         float(pago["valor"]),
                "metodo_pago":   pago["metodo_pago"],
                "cajero":        pago.get("cajera", cajero),
                "acompanante":   "",
                "observaciones": pago.get("observaciones") or "",
                "cambio":        0.0,
            }
            pdf_path = generar_recibo_pago(datos_recibo)
            abrir_pdf(pdf_path)
        except Exception as e:
            QMessageBox.critical(self, "Error al generar recibo", str(e))

   # ─────────────────────────────────────────────────────────────────
#  AJUSTE EN _registrar_pago (dentro de PagosView)
#  Reemplaza el método completo — sin lógica de calculadora ni desglose
# ─────────────────────────────────────────────────────────────────
 
    def _registrar_pago(self):
        if not self._alumno:
            return
        try:
            pagado = total_pagado(self._alumno["matricula_id"])
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
 
        saldo   = max(self._valor_curso - pagado, 0)
        dialogo = DialogoPago(self._alumno, saldo, self._valor_curso, parent=self)
 
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            try:
                recibo = registrar_pago(
                    matricula_id  = self._alumno["matricula_id"],
                    concepto      = dialogo.concepto,
                    valor         = dialogo.valor,
                    metodo        = dialogo.metodo,
                    observaciones = dialogo.observaciones,
                    usuario_id    = self.usuario_id,
                    acompanante   = dialogo.acompanante,
                )
 
                QMessageBox.information(
                    self, "Pago registrado",
                    f"✓ Pago registrado exitosamente.\n\nRecibo N°: {recibo}"
                )
 
                # ―― Preguntar si desea imprimir el recibo ――
                resp = QMessageBox.question(
                    self,
                    "Imprimir recibo",
                    f"¿Desea generar e imprimir el recibo N°: {recibo}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if resp == QMessageBox.StandardButton.Yes:
                    try:
                        cajero = obtener_nombre_usuario(self.usuario_id)
                        datos_recibo = {
                            "numero_recibo": recibo,
                            "alumno_nombre": f"{self._alumno['nombres']} {self._alumno['apellidos']}",
                            "alumno_doc":    self._alumno["numero_documento"],
                            "concepto":      dialogo.concepto,
                            "valor":         dialogo.valor,
                            "metodo_pago":   dialogo.metodo,
                            "cajero":        cajero,
                            "acompanante":   dialogo.acompanante,
                            "observaciones": dialogo.observaciones,
                            "cambio":        dialogo.vuelto,   # ← vuelto manual
                        }
                        pdf_path = generar_recibo_pago(datos_recibo)
                        abrir_pdf(pdf_path)
                    except Exception as e_pdf:
                        QMessageBox.warning(
                            self, "Recibo no generado",
                            f"No se pudo generar el PDF:\n{e_pdf}"
                        )
 
                self._cargar_pagos(self._alumno)
                self.pago_registrado.emit()
 
            except Exception as e:
                QMessageBox.critical(self, "Error al guardar", str(e))
 

    def _on_fila_movimiento_seleccionada(self):
        filas = self.movimientos_widget.tabla.selectedItems()
        self.btn_reimprimir.setEnabled(len(filas) > 0)

    # El método ya existe y está bien, pero verifica que incluya:
    def _mostrar_movimientos(self):
        self._alumno = None
        self.tarjeta.hide()
        self.tabla.hide()                   # ← asegurar que se oculte
        self.btn_pago.setEnabled(False)
        self.btn_reimprimir.setEnabled(False)
        self.btn_volver.setVisible(False)
        self.lista.clearSelection()
        self.movimientos_widget.actualizar()
        self.movimientos_widget.show()

    def showEvent(self, event):
        super().showEvent(event)
        self._mostrar_movimientos()

    def _registrar_ingreso(self):
        dialogo = DialogoIngreso(parent=self, usuario_id=self.usuario_id)
        if dialogo.exec():
            self.movimientos_widget.actualizar()  # ← REFRESCAR

    def _registrar_salida(self):
        dialogo = DialogoSalida(parent=self, usuario_id=self.usuario_id)
        if dialogo.exec():
            self.movimientos_widget.actualizar()  # ← YA ESTÁ, VERIFICAR QUE FUNCIONE


# ─────────────────────────────────────────────────────────────────
#  WIDGET: CAMPO NUMÉRICO CON FORMATO DE MILES
#  Muestra puntos como separadores de miles mientras se escribe
# ─────────────────────────────────────────────────────────────────
 
class CampoMoneda(QLineEdit):
    """
    QLineEdit que formatea el número con puntos de miles (1.500.000).
    - Inicia mostrando "0" formateado.
    - Al hacer clic dentro, limpia para que el usuario escriba fácil.
    - Al salir, vuelve a formatear con puntos.
    - Solo acepta dígitos mientras se escribe.
    """
 
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._editando = False
        # Mostrar "0" con formato desde el inicio
        self.setText("0")
        self.textChanged.connect(self._solo_digitos)
 
    def _formatear(self):
        """Convierte el texto actual a formato con puntos de miles."""
        texto = self.text().replace(".", "").replace(",", "").replace("$", "").replace(" ", "").strip()
        try:
            numero = int(texto) if texto else 0
        except ValueError:
            numero = 0
        formateado = f"{numero:,}".replace(",", ".")
        # Bloquear señal para no entrar en bucle
        self.blockSignals(True)
        self.setText(formateado)
        self.blockSignals(False)
 
    def _solo_digitos(self, texto):
        """Mientras se edita, solo permite dígitos (sin puntos ni letras)."""
        if not self._editando:
            return
        limpio = "".join(c for c in texto if c.isdigit())
        if limpio != texto:
            self.blockSignals(True)
            cursor = len(limpio)
            self.setText(limpio)
            self.setCursorPosition(cursor)
            self.blockSignals(False)
 
    def focusInEvent(self, event):
        self._editando = True
        # Mostrar solo el número crudo para editar cómodamente
        texto = self.text().replace(".", "").strip()
        self.blockSignals(True)
        self.setText("" if texto == "0" else texto)
        self.blockSignals(False)
        self.textChanged.connect(self._solo_digitos)
        super().focusInEvent(event)
 
    def focusOutEvent(self, event):
        self._editando = False
        super().focusOutEvent(event)
        self._formatear()
 
    def valor(self) -> float:
        texto = self.text().replace(".", "").replace(",", "").replace("$", "").strip()
        try:
            return float(texto) if texto else 0.0
        except ValueError:
            return 0.0
 
    def setValor(self, v: float):
        self._editando = False
        formateado = f"{int(v):,}".replace(",", ".")
        self.blockSignals(True)
        self.setText(formateado)
        self.blockSignals(False)
 
    def valor(self) -> float:
        texto = self.text().replace(".", "").replace(",", "").replace("$", "").strip()
        try:
            return float(texto) if texto else 0.0
        except ValueError:
            return 0.0
 
    def setValor(self, v: float):
        self.setText(f"{int(v):,}".replace(",", "."))
 