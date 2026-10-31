#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vista de Base de Datos / Archivo Histórico - CEA PRACTICAR
Busca alumnos, muestra resumen completo: datos, pagos, clases y evaluaciones.
Estilo PRACTICAR: paleta PAL, cards blancas, mismo patrón que alumnos_view.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFrame, QScrollArea, QGridLayout, QDialog,
    QGraphicsDropShadowEffect, QSizePolicy, QTabWidget,
    QFileDialog, QStackedWidget
)
import shutil
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import pyqtSignal


import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database import Database

# ─── Paleta PRACTICAR ──────────────────────────────────────────────────────────
PAL = {
    "bg":         "#F4F3EF",
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
    "sidebar":    "#111827",
}

GLOBAL_QSS = f"""
    QLabel {{ background: transparent; }}
    QLineEdit {{
        padding: 10px 14px; font-size: 13px;
        border: 1.5px solid {PAL['border']}; border-radius: 8px;
        background-color: {PAL['surface']}; color: {PAL['text_1']};
    }}
    QLineEdit:focus {{ border: 1.5px solid {PAL['blue']}; background: #FFFFFF; }}
    QTableWidget {{
        background-color: {PAL['surface']}; border-radius: 12px;
        border: 1.5px solid {PAL['border_lt']}; gridline-color: {PAL['border_lt']}; outline: none;
    }}
    QTableWidget::item {{
        padding: 0px 14px; border-bottom: 1px solid {PAL['border_lt']}; color: {PAL['text_1']};
    }}
    QTableWidget::item:selected {{ background-color: {PAL['blue_bg']}; color: {PAL['blue']}; }}
    QHeaderView::section {{
        background-color: {PAL['bg']}; padding: 12px 14px; border: none;
        border-bottom: 2px solid {PAL['border']}; font-weight: 600;
        font-size: 11px; letter-spacing: 0.05em; color: {PAL['text_2']};
    }}
    QScrollBar:vertical {{ width: 6px; background: transparent; border-radius: 3px; }}
    QScrollBar::handle:vertical {{ background: {PAL['border']}; border-radius: 3px; min-height: 30px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QTabWidget::pane {{
        border: 1.5px solid {PAL['border_lt']}; border-radius: 10px;
        background: {PAL['surface']}; top: -1px;
    }}
    QTabBar::tab {{
        background: {PAL['bg']}; color: {PAL['text_2']};
        padding: 9px 20px; border-radius: 8px 8px 0 0;
        font-size: 13px; font-weight: 600; margin-right: 3px;
        border: 1.5px solid {PAL['border_lt']}; border-bottom: none;
    }}
    QTabBar::tab:selected {{ background: {PAL['surface']}; color: {PAL['blue']}; }}
    QTabBar::tab:hover:!selected {{ background: {PAL['border_lt']}; }}
"""

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

def _shadow(widget, blur=14, dy=3, opacity=0.06):
    s = QGraphicsDropShadowEffect()
    s.setBlurRadius(blur)
    s.setOffset(0, dy)
    s.setColor(QColor(26, 25, 22, int(opacity * 255)))
    widget.setGraphicsEffect(s)


def _btn_primary(text):
    b = QPushButton(text)
    b.setStyleSheet(f"""
        QPushButton {{
            background-color: {PAL['blue']}; color: #FFF; border: none;
            border-radius: 9px; padding: 10px 20px; font-size: 13px; font-weight: 600;
        }}
        QPushButton:hover {{ background-color: {PAL['blue_dark']}; }}
        QPushButton:pressed {{ background-color: #001E60; }}
    """)
    return b


def _btn_secondary(text):
    b = QPushButton(text)
    b.setStyleSheet(f"""
        QPushButton {{
            background-color: {PAL['bg']}; color: {PAL['text_1']};
            border: 1.5px solid {PAL['border']}; border-radius: 9px;
            padding: 10px 20px; font-size: 13px; font-weight: 500;
        }}
        QPushButton:hover {{ background-color: {PAL['border_lt']}; }}
    """)
    return b


def _section_lbl(text):
    l = QLabel(text.upper())
    l.setStyleSheet(f"""
        font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
        color: {PAL['text_3']}; padding-bottom: 2px;
    """)
    return l


def _card():
    w = QWidget()
    w.setStyleSheet(f"""
        QWidget {{
            background-color: {PAL['surface']}; border-radius: 12px;
            border: 1px solid {PAL['border_lt']};
        }}
    """)
    _shadow(w, blur=10, dy=2, opacity=0.05)
    return w


# ══════════════════════════════════════════════════════════════════════════════
#  DIÁLOGO: FICHA COMPLETA DEL ALUMNO
# ══════════════════════════════════════════════════════════════════════════════

class FichaAlumnoDialog(QDialog):
    """Ficha completa: datos, pagos, clases y evaluaciones."""

    ESTADO_COLOR = {
        "Activo":         (PAL["teal_bg"],  PAL["teal"]),
        "Completado":     (PAL["blue_bg"],  PAL["blue"]),
        "Pendiente Pago": (PAL["amber_bg"], PAL["amber"]),
        "Cancelado":      (PAL["coral_bg"], PAL["coral"]),
    }

    def __init__(self, alumno_id: int, parent=None):
        
        super().__init__(parent)
        self.alumno_id = alumno_id
        self.setWindowTitle("Ficha del Alumno")
        _tamanio_adaptativo(self, 920, 740)
        
        self.setStyleSheet("""
            QDialog { background-color: #F5F7FA; font-family: 'Segoe UI', sans-serif; }
            QLabel { background: transparent; border: none; padding: 0; }
            QScrollArea { background: #F5F7FA; border: none; }
            QWidget#fieldCard { background-color: #F0EEE6; border-radius: 8px; border: 1px solid #DDD9D0; }
            QWidget#cardContainer { background: transparent; border: none; }
        """ + GLOBAL_QSS)
        self._build_ui()
        self._load()

    def _build_ui(self):
        from PyQt6.QtWidgets import QApplication
        _s = QApplication.primaryScreen().availableGeometry()
        _w = min(920, _s.width()  - 40)
        _h = min(740, _s.height() - 40)
        self.setMinimumSize(min(600, _w), min(480, _h))
        self.resize(_w, _h)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        _fg = self.frameGeometry(); _fg.moveCenter(_s.center()); self.move(_fg.topLeft())

        root = QVBoxLayout(self)      
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        # Header azul
        self.header = QWidget()
        self.header.setFixedHeight(88)
        self.header.setStyleSheet("background: #002D6B; border-bottom: 4px solid #D32F2F;")
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(28, 0, 28, 0)

        avatar = QLabel("👤")
        avatar.setFixedSize(50, 50)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet("background: rgba(255,255,255,0.18); border-radius: 25px; font-size: 22px;")
        hl.addWidget(avatar)

        name_col = QVBoxLayout()
        name_col.setSpacing(3)
        name_col.setContentsMargins(12, 0, 0, 0)
        self.lbl_nombre = QLabel("Cargando...")
        self.lbl_nombre.setStyleSheet("font-size: 18px; font-weight: 700; color: #FFF;")
        name_col.addWidget(self.lbl_nombre)
        self.lbl_doc = QLabel("")
        self.lbl_doc.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.72);")
        name_col.addWidget(self.lbl_doc)
        hl.addLayout(name_col)
        hl.addStretch()

        self.lbl_estado = QLabel("")
        self.lbl_estado.setStyleSheet("font-size: 12px; font-weight: 600; padding: 6px 16px; border-radius: 20px;")
        hl.addWidget(self.lbl_estado)

        root.addWidget(self.header)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(GLOBAL_QSS)

        # Tab Datos
        self.tab_datos = QScrollArea()
        self.tab_datos.setWidgetResizable(True)
        self.tab_datos.setFrameShape(QFrame.Shape.NoFrame)
        self.tab_datos.setStyleSheet(f"background: {PAL['bg']}; border: none;")
        self.tab_datos_body = QWidget()
        self.tab_datos_body.setStyleSheet(f"background: {PAL['bg']};")
        self.tab_datos_layout = QVBoxLayout(self.tab_datos_body)
        self.tab_datos_layout.setContentsMargins(24, 20, 24, 20)
        self.tab_datos_layout.setSpacing(16)
        self.tab_datos.setWidget(self.tab_datos_body)
        self.tabs.addTab(self.tab_datos, "📋  Datos Personales")

        # Tab Pagos
        self.tab_pagos_w = QWidget()
        self.tab_pagos_w.setStyleSheet(f"background: {PAL['bg']};")
        pv = QVBoxLayout(self.tab_pagos_w)
        pv.setContentsMargins(24, 20, 24, 20)
        pv.setSpacing(14)
        self.lbl_resumen_pagos = QLabel("")
        self.lbl_resumen_pagos.setStyleSheet(f"font-size: 13px; color: {PAL['text_2']};")
        pv.addWidget(self.lbl_resumen_pagos)
        self.tbl_pagos = self._make_table(["Fecha", "Concepto", "Método", "Valor", "Observaciones"])
        self.tbl_pagos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_pagos.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) 
        pv.addWidget(self.tbl_pagos)
        self.tabs.addTab(self.tab_pagos_w, "💳  Pagos")

        root.addWidget(self.tabs, 1)

        # Footer
        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet(f"background: {PAL['surface']}; border-top: 1.5px solid {PAL['border_lt']};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 0, 24, 0)

        btn_reportes = QPushButton("📎  Reportes")
        btn_reportes.setFixedHeight(38)
        btn_reportes.setStyleSheet(f"""
            QPushButton {{
                background-color: {PAL['amber_bg']}; color: {PAL['amber']};
                border: 1.5px solid {PAL['amber']}; border-radius: 9px;
                padding: 0 18px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #F5E1B0; }}
        """)
        btn_reportes.clicked.connect(self._abrir_reportes)
        fl.addWidget(btn_reportes)

        fl.addStretch()
        btn_cerrar = _btn_secondary("Cerrar")
        btn_cerrar.clicked.connect(self.accept)
        fl.addWidget(btn_cerrar)
        root.addWidget(footer)

    def _make_table(self, headers):
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setStretchLastSection(True)
        t.verticalHeader().setVisible(False)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.setShowGrid(False)
        t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        t.verticalHeader().setDefaultSectionSize(46)
        _shadow(t, blur=10, dy=2, opacity=0.04)
        return t

    def _set_table_row(self, table, row_idx, values):
        for col, val in enumerate(values):
            item = QTableWidgetItem(str(val) if val is not None else "—")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row_idx, col, item)

    def _info_card(self, campos):
        container = QWidget()
        container.setObjectName("cardContainer")
        container.setStyleSheet("QWidget#cardContainer { background: transparent; border: none; }")

        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        col = 0
        row_i = 0
        for label, valor in campos:
            if valor is None or str(valor).strip() == "":
                valor = "—"

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

            lk = QLabel(label.upper())
            lk.setStyleSheet("""
                font-size: 10px; font-weight: 600;
                color: #5D6A81; letter-spacing: 0.07em;
                background: transparent; border: none;
            """)
            cell.addWidget(lk)

            lv = QLabel(str(valor))
            lv.setWordWrap(True)
            lv.setStyleSheet("""
                font-size: 13px; font-weight: 700;
                color: #2C3E50; background: transparent; border: none;
            """)
            cell.addWidget(lv)

            grid.addWidget(field_card, row_i, col)
            col += 1
            if col >= 3:
                col = 0
                row_i += 1

        return container

    def _load(self):
        try:
            db = Database.get_instance()

            # ── Datos del alumno ──
            row = db.fetchone("""
                SELECT a.*, m.categoria, m.estado, m.precio_total,
                    DATE_FORMAT(m.fecha_registro, '%Y-%m-%d') AS fecha_registro,
                m.anio AS anio_registro
                FROM matriculas m
                JOIN alumnos a ON a.numero_documento = m.numero_documento
                WHERE m.id = %s
            """, (self.alumno_id,))
            if not row:
                QMessageBox.warning(self, "No encontrado", "Alumno no encontrado.")
                self.reject()
                return

            self._alumno_row = row
            nombre = f"{row.get('nombres','')} {row.get('apellidos','')}"
            self.lbl_nombre.setText(nombre)
            self.lbl_doc.setText(f"{row.get('tipo_documento','CC')}  {row.get('numero_documento','')}")

            estado = row.get("estado", "Activo")
            bg_e, fg_e = self.ESTADO_COLOR.get(estado, (PAL["bg"], PAL["text_2"]))
            BADGE_COLORS = {
                "Activo":         ("#1D9E75", "#FFFFFF"),
                "Cancelado":      ("#D32F2F", "#FFFFFF"),
                "Pendiente Pago": ("#8A5210", "#FFFFFF"),
                "Completado":     ("#0033A0", "#FFFFFF"),
            }
            badge_bg, badge_fg = BADGE_COLORS.get(estado, ("#888", "#FFFFFF"))
            self.lbl_estado.setText(estado.upper())
            self.lbl_estado.setFixedHeight(32)
            self.lbl_estado.setMaximumWidth(140)
            self.lbl_estado.setStyleSheet(f"""
                font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
                padding: 0px 16px; border-radius: 16px;
                background: {badge_bg}; color: {badge_fg};
            """)

            # Tab Datos
            self.tab_datos_layout.addWidget(_section_lbl("Identificación y Categoría"))
            self.tab_datos_layout.addWidget(self._info_card([
                ("Número Documento", row.get("numero_documento")),
                ("Tipo Documento",   row.get("tipo_documento")),
                ("Categoría",        row.get("categoria")),
                ("Estado",           row.get("estado")),
                ("Fecha Registro",   str(row.get("anio_registro", "")) if row.get("estado") == "Histórico" else str(row.get("fecha_registro", ""))[:10]),
            ]))
            self.tab_datos_layout.addWidget(_section_lbl("Datos Personales"))
            self.tab_datos_layout.addWidget(self._info_card([
                ("Nombres",          row.get("nombres")),
                ("Apellidos",        row.get("apellidos")),
                ("Fecha Nacimiento", str(row.get("fecha_nacimiento", ""))),
                ("Lugar Nacimiento", row.get("lugar_nacimiento")),
                ("Sexo",             row.get("sexo")),
                ("Estado Civil",     row.get("estado_civil")),
                ("Grupo Sanguíneo",  row.get("grupo_sanguineo")),
                ("Ocupación",        row.get("ocupacion")),
            ]))
            self.tab_datos_layout.addWidget(_section_lbl("Contacto"))
            self.tab_datos_layout.addWidget(self._info_card([
                ("Celular", row.get("celular")),
                ("Email",   row.get("email")),
            ]))
            self.tab_datos_layout.addStretch()

            # Tab Datos — Responsable
            tiene_responsable = any([
                row.get("responsable_nombres"),
                row.get("responsable_apellidos"),
                row.get("responsable_numero_documento"),
            ])
            if tiene_responsable:
                self.tab_datos_layout.addWidget(_section_lbl("Responsable de Inscripción"))
                resp_campos = [
                    ("Nombres",           row.get("responsable_nombres")),
                    ("Apellidos",         row.get("responsable_apellidos")),
                    ("Tipo Documento",    row.get("responsable_tipo_documento")),
                    ("Número Documento",  row.get("responsable_numero_documento")),
                    ("Celular",           row.get("responsable_celular")),
                    ("Email",             row.get("responsable_email")),
                    ("Relación",          row.get("responsable_relacion")),
                ]
                resp_campos = [(k, v) for k, v in resp_campos if v]
                self.tab_datos_layout.addWidget(self._info_card(resp_campos))

            # ── Pagos ──
            pagos = db.fetchall(
                "SELECT DATE_FORMAT(fecha_pago,'%Y-%m-%d') AS fecha, concepto, metodo_pago, valor, observaciones "
                "FROM pagos WHERE id_matricula = %s ORDER BY fecha_pago DESC",
                (self.alumno_id,)
            )
            total_pagado = sum(float(p.get("valor") or 0) for p in pagos)
            self.lbl_resumen_pagos.setText(
                f"Total pagado: <b>${total_pagado:,.0f}</b>   ·   {len(pagos)} transacción{'es' if len(pagos) != 1 else ''}"
            )
            self.lbl_resumen_pagos.setTextFormat(Qt.TextFormat.RichText)
            self.tbl_pagos.setRowCount(len(pagos))
            for i, p in enumerate(pagos):
                self._set_table_row(self.tbl_pagos, i, [
                    p.get("fecha"), p.get("concepto"), p.get("metodo_pago"),
                    f"${float(p.get('valor') or 0):,.0f}", p.get("observaciones")
                ])
                # Color valor
                val_item = self.tbl_pagos.item(i, 3)
                if val_item:
                    val_item.setForeground(QColor(PAL["teal"]))
                    val_item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))

        except (ConnectionError, RuntimeError) as e:
            QMessageBox.critical(self, "Error de conexión", str(e))


    def _abrir_reportes(self):
        alumno = getattr(self, "_alumno_row", None)
        if not alumno:
            return
        dlg = ReportesAlumnoDialog(alumno, parent=self)
        dlg.exec()



# ──────────────────────────────────────────────────────────────────────────────
#  DIÁLOGO: REPORTES DEL ALUMNO (Documentación + Evaluación)
# ──────────────────────────────────────────────────────────────────────────────

class ReportesAlumnoDialog(QDialog):
    """Expediente digital del alumno: un PDF con todo el paquete + evaluaciones."""

    def __init__(self, alumno: dict, parent=None):
        super().__init__(parent)
        self.alumno = alumno
        nombre = f"{alumno.get('nombres','')} {alumno.get('apellidos','')}".strip() or alumno.get('numero_documento','')
        self.setWindowTitle(f"Expediente — {nombre}")
        _tamanio_adaptativo(self, 820, 600)
        self.setStyleSheet(f"QDialog {{ background-color: {PAL['bg']}; }}" + GLOBAL_QSS)
        self._build()

    def _carpeta_expediente(self) -> str:
        try:
            from database import RUTA_EXPEDIENTES
            base = RUTA_EXPEDIENTES
        except ImportError:
            base = os.path.join(os.path.expanduser("~"), "Documents", "CEA_PRACTICAR", "expedientes")
        doc = str(self.alumno.get("numero_documento", "sin_doc"))
        carpeta = os.path.join(base, doc)
        os.makedirs(carpeta, exist_ok=True)
        return carpeta

    def _ruta_pdf(self) -> str | None:
        carpeta = self._carpeta_expediente()
        doc = str(self.alumno.get("numero_documento", "sin_doc"))
        for nombre in [f"{doc}.pdf", "expediente.pdf"]:
            ruta = os.path.join(carpeta, nombre)
            if os.path.exists(ruta):
                return ruta
        return None

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──
        header = QWidget()
        header.setFixedHeight(72)
        header.setStyleSheet(f"background: {PAL['blue']}; border-bottom: 3px solid {PAL['coral']};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 0, 24, 0)
        lbl_t = QLabel("📁  Expediente Digital")
        lbl_t.setStyleSheet("font-size: 17px; font-weight: 700; color: #FFF;")
        hl.addWidget(lbl_t)
        hl.addStretch()
        nombre = f"{self.alumno.get('nombres','')} {self.alumno.get('apellidos','')}".strip()
        doc    = str(self.alumno.get("numero_documento",""))
        lbl_n = QLabel(f"{nombre}  ·  C.C. {doc}")
        lbl_n.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.75); font-weight: 600;")
        hl.addWidget(lbl_n)
        root.addWidget(header)

        # ── Tabs ──
        tabs = QTabWidget()
        tabs.setStyleSheet(GLOBAL_QSS)

        # ══ TAB 1: EXPEDIENTE ══
        tab_exp = QWidget()
        tab_exp.setStyleSheet(f"background: {PAL['bg']};")
        exp_lay = QVBoxLayout(tab_exp)
        exp_lay.setContentsMargins(32, 28, 32, 28)
        exp_lay.setSpacing(20)

        exp_lay.addWidget(_section_lbl("Expediente del alumno"))

        lbl_info = QLabel(
            "Sube el PDF con todos los documentos escaneados del alumno "
            "(cédula, recibo, contrato, evaluaciones, etc.) en un solo archivo."
        )
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet(f"font-size: 12px; color: {PAL['text_2']}; padding: 4px 0;")
        exp_lay.addWidget(lbl_info)

        # Tarjeta principal del PDF
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {PAL['surface']};
                border: 2px dashed {PAL['border']};
                border-radius: 14px;
            }}
        """)
        card.setMinimumHeight(200)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(32, 32, 32, 32)
        card_lay.setSpacing(16)
        card_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ruta = self._ruta_pdf()
        self.lbl_pdf_icono = QLabel("📄" if ruta else "📂")
        self.lbl_pdf_icono.setStyleSheet("font-size: 48px; background: transparent;")
        self.lbl_pdf_icono.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(self.lbl_pdf_icono)

        self.lbl_pdf_estado = QLabel(os.path.basename(ruta) if ruta else "Sin expediente subido")
        self.lbl_pdf_estado.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_pdf_estado.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {PAL['teal'] if ruta else PAL['text_3']}; background: transparent;"
        )
        card_lay.addWidget(self.lbl_pdf_estado)

        if ruta:
            import os as _os
            size_kb = _os.path.getsize(ruta) // 1024
            lbl_size = QLabel(f"{size_kb} KB")
            lbl_size.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_size.setStyleSheet(f"font-size: 11px; color: {PAL['text_3']}; background: transparent;")
            card_lay.addWidget(lbl_size)

        exp_lay.addWidget(card, 1)

        # Botones de acción
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_subir = QPushButton("⬆  Subir PDF del expediente")
        self.btn_subir.setFixedHeight(42)
        self.btn_subir.setStyleSheet(f"""
            QPushButton {{
                background: {PAL['blue']}; color: #FFF; border: none;
                border-radius: 9px; font-size: 13px; font-weight: 700; padding: 0 24px;
            }}
            QPushButton:hover {{ background: {PAL['blue_dark']}; }}
        """)
        self.btn_subir.clicked.connect(self._subir_pdf)
        btn_row.addWidget(self.btn_subir)

        self.btn_ver = QPushButton("👁  Ver expediente")
        self.btn_ver.setFixedHeight(42)
        self.btn_ver.setEnabled(ruta is not None)
        self.btn_ver.setStyleSheet(f"""
            QPushButton {{
                background: {PAL['teal_bg']}; color: {PAL['teal']};
                border: 1.5px solid {PAL['teal']}; border-radius: 9px;
                font-size: 13px; font-weight: 700; padding: 0 24px;
            }}
            QPushButton:hover {{ background: #C5EAE0; }}
            QPushButton:disabled {{ background: {PAL['border_lt']}; color: {PAL['text_3']}; border-color: {PAL['border_lt']}; }}
        """)
        self.btn_ver.clicked.connect(self._ver_pdf)
        btn_row.addWidget(self.btn_ver)

        self.btn_eliminar = QPushButton("🗑  Eliminar")
        self.btn_eliminar.setFixedHeight(42)
        self.btn_eliminar.setEnabled(ruta is not None)
        self.btn_eliminar.setStyleSheet(f"""
            QPushButton {{
                background: {PAL['coral_bg']}; color: {PAL['coral']};
                border: 1.5px solid {PAL['coral']}; border-radius: 9px;
                font-size: 13px; font-weight: 700; padding: 0 24px;
            }}
            QPushButton:hover {{ background: #FDDEDE; }}
            QPushButton:disabled {{ background: {PAL['border_lt']}; color: {PAL['text_3']}; border-color: {PAL['border_lt']}; }}
        """)
        self.btn_eliminar.clicked.connect(self._eliminar_pdf)
        btn_row.addWidget(self.btn_eliminar)
        btn_row.addStretch()

        exp_lay.addLayout(btn_row)

        # Ruta de almacenamiento
        try:
            from database import RUTA_EXPEDIENTES
            ruta_base = RUTA_EXPEDIENTES
        except ImportError:
            ruta_base = "~/Documents/CEA_PRACTICAR/expedientes"
        lbl_ruta = QLabel(f"📂  Guardado en: {ruta_base}/{self.alumno.get('numero_documento','')}/")
        lbl_ruta.setStyleSheet(f"font-size: 10px; color: {PAL['text_3']};")
        exp_lay.addWidget(lbl_ruta)

        tabs.addTab(tab_exp, "📁  Expediente")

        # ══ TAB 2: EVALUACIONES ══
        tab_eval = QWidget()
        tab_eval.setStyleSheet(f"background: {PAL['bg']};")
        ev_lay = QVBoxLayout(tab_eval)
        ev_lay.setContentsMargins(28, 24, 28, 24)
        ev_lay.setSpacing(14)
        ev_lay.addWidget(_section_lbl("Evaluaciones del alumno"))

        self.tbl_eval = QTableWidget()
        self.tbl_eval.setColumnCount(5)
        self.tbl_eval.setHorizontalHeaderLabels(["Tipo","Fecha","Nota","Resultado","Observaciones"])
        self.tbl_eval.horizontalHeader().setStretchLastSection(True)
        self.tbl_eval.verticalHeader().setVisible(False)
        self.tbl_eval.setShowGrid(False)
        self.tbl_eval.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tbl_eval.verticalHeader().setDefaultSectionSize(44)
        _shadow(self.tbl_eval, blur=10, dy=2, opacity=0.04)
        ev_lay.addWidget(self.tbl_eval)
        tabs.addTab(tab_eval, "📝  Evaluaciones")

        root.addWidget(tabs, 1)

        # ── Footer ──
        footer = QWidget()
        footer.setFixedHeight(60)
        footer.setStyleSheet(f"background: {PAL['surface']}; border-top: 1.5px solid {PAL['border_lt']};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 0, 24, 0)
        fl.addStretch()
        btn_cerrar = _btn_secondary("Cerrar")
        btn_cerrar.clicked.connect(self.accept)
        fl.addWidget(btn_cerrar)
        root.addWidget(footer)

        self._cargar_evaluaciones()

    # ── Lógica PDF ──────────────────────────────────────────────

    def _subir_pdf(self):
        ruta_src, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar PDF del expediente",
            os.path.expanduser("~"),
            "PDF (*.pdf);;Imágenes (*.jpg *.jpeg *.png)"
        )
        if not ruta_src:
            return
        ext     = os.path.splitext(ruta_src)[1].lower().lstrip(".")
        carpeta = self._carpeta_expediente()
        doc     = str(self.alumno.get("numero_documento", "sin_doc"))
        # Eliminar anterior
        for e in ["pdf","jpg","jpeg","png"]:
            ant = os.path.join(carpeta, f"{doc}.{e}")
            if os.path.exists(ant): os.remove(ant)
        ruta_dest = os.path.join(carpeta, f"{doc}.{ext}")
        shutil.copy2(ruta_src, ruta_dest)

        # Actualizar UI
        self.lbl_pdf_icono.setText("📄")
        self.lbl_pdf_estado.setText(os.path.basename(ruta_dest))
        self.lbl_pdf_estado.setStyleSheet(f"font-size:14px; font-weight:700; color:{PAL['teal']}; background:transparent;")
        self.btn_ver.setEnabled(True)
        self.btn_eliminar.setEnabled(True)
        QMessageBox.information(self, "Expediente subido", f"✓ Expediente guardado correctamente.")

    def _ver_pdf(self):
        ruta = self._ruta_pdf()
        if not ruta:
            QMessageBox.warning(self, "Sin expediente", "No hay expediente subido para este alumno.")
            return
        try:
            import subprocess, sys
            if sys.platform == "win32":
                os.startfile(ruta)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", ruta])
            else:
                subprocess.Popen(["xdg-open", ruta])
        except Exception as e:
            QMessageBox.warning(self, "Error al abrir", str(e))

    def _eliminar_pdf(self):
        resp = QMessageBox.question(
            self, "Eliminar expediente",
            "¿Eliminar el PDF del expediente de este alumno?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        ruta = self._ruta_pdf()
        if ruta and os.path.exists(ruta):
            os.remove(ruta)
        self.lbl_pdf_icono.setText("📂")
        self.lbl_pdf_estado.setText("Sin expediente subido")
        self.lbl_pdf_estado.setStyleSheet(f"font-size:14px; font-weight:700; color:{PAL['text_3']}; background:transparent;")
        self.btn_ver.setEnabled(False)
        self.btn_eliminar.setEnabled(False)

    # ── Evaluaciones ────────────────────────────────────────────

    def _cargar_evaluaciones(self):
        try:
            db = Database.get_instance()
            evals = db.fetchall(
                "SELECT tipo, DATE_FORMAT(fecha,'%Y-%m-%d') AS fecha, nota, resultado, observaciones "
                "FROM evaluaciones WHERE id_matricula = %s ORDER BY fecha DESC",
                (self.alumno.get("id"),)  # ← "id" aquí es matricula_id
            )
            self.tbl_eval.setRowCount(len(evals))
            for i, e in enumerate(evals):
                for col, val in enumerate([e.get("tipo"),e.get("fecha"),e.get("nota"),e.get("resultado"),e.get("observaciones")]):
                    item = QTableWidgetItem(str(val) if val is not None else "—")
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col == 3:
                        res = str(val or "")
                        if "aprobado" in res.lower(): item.setForeground(QColor(PAL["teal"]))
                        elif "reprobado" in res.lower(): item.setForeground(QColor(PAL["coral"]))
                    self.tbl_eval.setItem(i, col, item)
            if not evals:
                self.tbl_eval.setRowCount(1)
                item = QTableWidgetItem("Sin evaluaciones registradas.")
                item.setForeground(QColor(PAL["text_3"]))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tbl_eval.setItem(0, 0, item)
                self.tbl_eval.setSpan(0, 0, 1, 5)
        except Exception:
            pass
# ══════════════════════════════════════════════════════════════════════════════
#  VISTA PRINCIPAL: BASE DE DATOS / ARCHIVO HISTÓRICO
# ══════════════════════════════════════════════════════════════════════════════

class HistoricoView(QWidget):
    """
    Vista de Base de Datos.
    Permite buscar alumnos por nombre, documento o categoría,
    ver su ficha completa y exportar.
    """
    ficha_abierta = pyqtSignal()
    
    ESTADO_STYLES = {
        "Activo":         (PAL["teal_bg"],  PAL["teal"]),
        "Completado":     (PAL["blue_bg"],  PAL["blue"]),
        "Pendiente Pago": (PAL["amber_bg"], PAL["amber"]),
        "Cancelado":      (PAL["coral_bg"], PAL["coral"]),
    }

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {PAL['bg']};" + GLOBAL_QSS)
        self.all_data = []
        self._build_ui()
        self._load()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(20)

        # ── Header ──
        header = QHBoxLayout()
        header.setSpacing(14)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_title = QLabel("Base de Datos")
        lbl_title.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {PAL['text_1']};")
        title_col.addWidget(lbl_title)
        lbl_sub = QLabel("Historial completo de alumnos — datos, pagos, clases y evaluaciones")
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {PAL['text_2']};")
        title_col.addWidget(lbl_sub)
        header.addLayout(title_col)
        header.addStretch()

        # Búsqueda
        search_wrap = QWidget()
        search_wrap.setMaximumWidth(380)
        search_wrap.setStyleSheet(f"""
            QWidget {{
                background: {PAL['surface']}; border: 1.5px solid {PAL['border']}; border-radius: 9px;
            }}
        """)
        si = QHBoxLayout(search_wrap)
        si.setContentsMargins(12, 0, 12, 0)
        si.setSpacing(8)
        lbl_ico = QLabel("🔍")
        lbl_ico.setStyleSheet("background: transparent; border: none; font-size: 14px;")
        si.addWidget(lbl_ico)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por nombre, cédula o categoría...")
        self.search_input.setStyleSheet("QLineEdit { border: none; background: transparent; font-size: 13px; padding: 10px 0; } QLineEdit:focus { border: none; }")
        self.search_input.textChanged.connect(self._filter)
        si.addWidget(self.search_input)
        header.addWidget(search_wrap)

        btn_reload = _btn_secondary("↻  Recargar")
        btn_reload.setFixedHeight(42)
        btn_reload.clicked.connect(self._load)
        header.addWidget(btn_reload)

        root.addLayout(header)

        # ── Stats ──
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self.stat_labels = {}
        for key, label, color, bg in [
            ("total",    "Total alumnos",    PAL["blue"],  PAL["blue_bg"]),
            ("activos",  "Activos",           PAL["teal"],  PAL["teal_bg"]),
            ("pendiente","Pendiente pago",    PAL["amber"], PAL["amber_bg"]),
            ("cancelado","Cancelados",        PAL["coral"], PAL["coral_bg"]),
        ]:
            w = QWidget()
            w.setStyleSheet(f"""
                QWidget {{
                    background-color: {PAL['surface']}; border-radius: 10px;
                    border: 1px solid {PAL['border_lt']};
                }}
            """)
            _shadow(w, blur=10, dy=2, opacity=0.05)
            wl = QHBoxLayout(w)
            wl.setContentsMargins(16, 14, 16, 14)
            wl.setSpacing(14)
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"background: {color}; border-radius: 5px; border: none;")
            wl.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
            tc = QVBoxLayout()
            tc.setSpacing(2)
            
            # FIX: Guardar referencia al QLabel en vez de usar children()[0]
            lbl_stat = QLabel(label)
            lbl_stat.setStyleSheet(f"font-size: 11px; color: {PAL['text_2']};")
            tc.addWidget(lbl_stat)
            
            vl = QLabel("0")
            vl.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {PAL['text_1']};")
            tc.addWidget(vl)
            self.stat_labels[key] = vl
            wl.addLayout(tc)
            wl.addStretch()
            stats_row.addWidget(w)
        root.addLayout(stats_row)

        # ── Tabla ──
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Código", "Documento", "Nombres", "Apellidos", "Categoría",
            "Estado", "Fecha Registro", "Clases", "Acciones"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setDefaultSectionSize(56)
        self.table.setColumnWidth(7, 180)
        _shadow(self.table, blur=14, dy=3, opacity=0.05)
        root.addWidget(self.table)

        # Footer
        foot = QHBoxLayout()
        self.lbl_count = QLabel("Mostrando 0 registros")
        self.lbl_count.setStyleSheet(f"font-size: 12px; color: {PAL['text_3']};")
        foot.addWidget(self.lbl_count)
        foot.addStretch()
        root.addLayout(foot)                

    def _load(self):
        try:
            db = Database.get_instance()
            rows = db.fetchall("""
                SELECT
                    m.id AS matricula_id,
                    m.numero_orden,
                    m.anio,
                    a.numero_documento,
                    a.nombres,
                    a.apellidos,
                    m.categoria,
                    m.estado,
                    DATE_FORMAT(m.fecha_registro, '%Y-%m-%d') AS fecha_registro,
                    COUNT(c.id) AS total_clases
                FROM matriculas m
                JOIN alumnos a ON a.numero_documento = m.numero_documento
                LEFT JOIN clases c ON c.id_matricula = m.id
                GROUP BY m.id
                ORDER BY m.fecha_registro DESC
            """)
            self.all_data = [
            (
                r["matricula_id"],
                f"{r['numero_orden']}-{str(r['anio'])[-2:]}",
                r["numero_documento"],
                r["nombres"],
                r["apellidos"],
                r["categoria"],
                r["estado"],
                r["fecha_registro"] or "",
                r["total_clases"],
            )
            for r in rows
        ]
        except (ConnectionError, RuntimeError) as e:
            QMessageBox.critical(self, "Error de conexión", str(e))
            self.all_data = []

        self._render(self.all_data)
        self._update_stats(self.all_data)

    def _render(self, data):
        self.table.setRowCount(len(data))
        for i, row in enumerate(data):
            alumno_id, codigo, doc, nom, ape, cat, estado, fecha, clases = row

            for col, val in enumerate([codigo, doc, nom, ape, cat, estado, fecha, str(clases)]):
                item = QTableWidgetItem(str(val) if val else "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 0:
                    item.setForeground(QColor(PAL["blue"]))
                    item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                if col == 5:
                    _, fg = self.ESTADO_STYLES.get(val, (PAL["bg"], PAL["text_2"]))
                    item.setForeground(QColor(fg))
                    item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                self.table.setItem(i, col, item)

            # Botón Ver Ficha
            act_w = QWidget()
            act_w.setStyleSheet("background: transparent;")
            al = QHBoxLayout(act_w)
            al.setContentsMargins(8, 8, 8, 8)
            al.setSpacing(6)

            btn_ver = QPushButton("📋  Ver Ficha")
            btn_ver.setFixedHeight(34)
            btn_ver.setMinimumWidth(110)
            btn_ver.setStyleSheet(f"""
                QPushButton {{
                    font-size: 12px; font-weight: 600;
                    background-color: {PAL['blue_bg']}; color: {PAL['blue']};
                    border: 1.5px solid transparent; border-radius: 7px; padding: 0 10px;
                }}
                QPushButton:hover {{ border: 1.5px solid {PAL['blue']}; }}
            """)
            btn_ver.clicked.connect(lambda _, aid=alumno_id: self._ver_ficha(aid))
            al.addWidget(btn_ver)
            al.addStretch()
            self.table.setCellWidget(i, 8, act_w)

        self.lbl_count.setText(f"Mostrando {len(data)} registro{'s' if len(data) != 1 else ''}")

    def _update_stats(self, data):
        conteos = {"total": len(data), "activos": 0, "pendiente": 0, "cancelado": 0}
        for row in data:
            estado = row[6]
            if estado == "Activo":
                conteos["activos"] += 1
            elif estado == "Pendiente Pago":
                conteos["pendiente"] += 1
            elif estado == "Cancelado":
                conteos["cancelado"] += 1
        for key, lbl in self.stat_labels.items():
            lbl.setText(str(conteos.get(key, 0)))

    def _filter(self, text):
        text = text.lower()
        if not text:
            self._render(self.all_data)
            self._update_stats(self.all_data)
            return
        filtered = [r for r in self.all_data if any(text in str(c).lower() for c in r)]
        self._render(filtered)
        self._update_stats(filtered)

    def _ver_ficha(self, alumno_id):
        dlg = FichaAlumnoDialog(alumno_id=alumno_id, parent=self)
        dlg.exec()
    
    def showEvent(self, event):
        super().showEvent(event)
        self._load()