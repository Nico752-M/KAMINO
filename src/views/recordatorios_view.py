#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vista de Recordatorios RUNT - CEA PRACTICAR
Muestra alumnos nuevos de la semana que deben ser registrados en el RUNT.
Los recordatorios se generan automáticamente cada sábado.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFrame, QGraphicsDropShadowEffect,
    QDialog, QScrollArea, QGridLayout,
    QApplication  
)
from PyQt6.QtCore import Qt, QTimer, QDate, pyqtSignal, QPropertyAnimation, QEasingCurve  
from PyQt6.QtGui import QColor, QFont

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database import Database

# ─── Paleta PRACTICAR ──────────────────────────────────────────────────────
PAL = {
    "bg":         "#F4F3EF",
    "surface":    "#FDFCF9",
    "border":     "#DDD9D0",
    "border_lt":  "#EAE7E0",
    "text_1":     "#1A1916",
    "text_2":     "#5A5650",
    "text_3":     "#9A9690",
    "blue":       "#1A2B6B",
    "blue_dark":  "#0f1d4d",
    "blue_bg":    "#EAF1FB",
    "teal":       "#0D6E55",
    "teal_bg":    "#E0F4EE",
    "amber":      "#8A5210",
    "amber_bg":   "#FAF0DC",
    "coral":      "#C8252A",
    "coral_bg":   "#FAECE6",
    "green":      "#1D9E75",
    "green_bg":   "#E0F4EE",
    "rojo":       "#C8252A",
    "rojo_dark":  "#9E1C20",
    "rojo_bg":    "#f9e8e8",
}

GLOBAL_QSS = f"""
    QLabel {{ background: transparent; }}
    QTableWidget {{
        background-color: {PAL['surface']}; border-radius: 12px;
        border: 1.5px solid {PAL['border_lt']}; gridline-color: {PAL['border_lt']}; outline: none;
    }}
    QTableWidget::item {{
        padding: 0 14px; border-bottom: 1px solid {PAL['border_lt']}; color: {PAL['text_1']};
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


def _btn_primary(text, color=None, color_dark=None):
    c = color or PAL['blue']
    cd = color_dark or PAL['blue_dark']
    b = QPushButton(text)
    b.setStyleSheet(f"""
        QPushButton {{
            background-color: {c}; color: #FFF; border: none;
            border-radius: 9px; padding: 11px 22px; font-size: 13px; font-weight: 600;
        }}
        QPushButton:hover {{ background-color: {cd}; }}
        QPushButton:pressed {{ background-color: {cd}; }}
    """)
    return b


def _btn_secondary(text):
    b = QPushButton(text)
    b.setStyleSheet(f"""
        QPushButton {{
            background-color: {PAL['bg']}; color: {PAL['text_1']};
            border: 1.5px solid {PAL['border']}; border-radius: 9px;
            padding: 11px 22px; font-size: 13px; font-weight: 500;
        }}
        QPushButton:hover {{ background-color: {PAL['border_lt']}; }}
    """)
    return b


# ══════════════════════════════════════════════════════════════════════════════
#  TOAST NOTIFICACIÓN FLOTANTE
# ══════════════════════════════════════════════════════════════════════════════
# 

class ToastNotificacion(QFrame):
    """
    Notificación flotante tipo toast con fondo opaco.
    Permanece visible hasta que el usuario la cierre (X o botón).
    """

    def __init__(self, parent=None, titulo="Aviso", mensaje="", tipo="critico"):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # Colores según tipo — fondos OPACOS, no transparentes
        if tipo == "critico":
            self.color_bg = "#FFFFFF"
            self.color_header_bg = "#DC2626"
            self.color_border = "#DC2626"
            self.color_header_text = "#FFFFFF"
            self.icono = "🔴"
        elif tipo == "advertencia":
            self.color_bg = "#FFFFFF"
            self.color_header_bg = "#D97706"
            self.color_border = "#D97706"
            self.color_header_text = "#FFFFFF"
            self.icono = "🟠"
        else:
            self.color_bg = "#FFFFFF"
            self.color_header_bg = "#059669"
            self.color_border = "#059669"
            self.color_header_text = "#FFFFFF"
            self.icono = "🟢"

        self._build_ui(titulo, mensaje)
        self._posicionar()

        # Animación de entrada
        self.setWindowOpacity(0.0)
        self._anim_opacity = QPropertyAnimation(self, b"windowOpacity")
        self._anim_opacity.setDuration(400)
        self._anim_opacity.setStartValue(0.0)
        self._anim_opacity.setEndValue(1.0)
        self._anim_opacity.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim_opacity.start()

        # NO hay auto-cerrar — se queda hasta que el usuario cierre

    def _build_ui(self, titulo, mensaje):
        self.setStyleSheet(f"""
            QFrame#toastFrame {{
                background-color: {self.color_bg};
                border: 3px solid {self.color_border};
                border-radius: 14px;
            }}
            QLabel {{ background: transparent; }}
        """)
        self.setObjectName("toastFrame")
        self.setFixedWidth(400)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header con fondo de color sólido ──
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {self.color_header_bg};
                border-top-left-radius: 11px;
                border-top-right-radius: 11px;
            }}
        """)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 12, 12, 12)
        hl.setSpacing(10)

        lbl_icon = QLabel(self.icono)
        lbl_icon.setStyleSheet("font-size: 18px; background: transparent;")
        hl.addWidget(lbl_icon)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            font-size: 14px; font-weight: 700; color: {self.color_header_text};
            background: transparent;
        """)
        hl.addWidget(lbl_titulo)
        hl.addStretch()

        btn_cerrar = QLabel("✕")
        btn_cerrar.setFixedSize(32, 32)
        btn_cerrar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cerrar.setStyleSheet("""
            QLabel {
                background-color: rgba(0,0,0,0.25);
                color: #FFFFFF;
                border-radius: 16px;
                font-size: 16px;
                font-weight: 800;
            }
        """)
        btn_cerrar.mousePressEvent = lambda e: self._cerrar_animado()
        hl.addWidget(btn_cerrar)

        root.addWidget(header)

        # ── Cuerpo del mensaje ──
        body = QFrame()
        body.setStyleSheet(f"""
            QFrame {{
                background-color: {self.color_bg};
                border-bottom-left-radius: 11px;
                border-bottom-right-radius: 11px;
            }}
        """)
        bl = QVBoxLayout(body)
        bl.setContentsMargins(18, 16, 18, 18)
        bl.setSpacing(14)

        lbl_mensaje = QLabel(mensaje)
        lbl_mensaje.setWordWrap(True)
        lbl_mensaje.setStyleSheet("""
            font-size: 13px; color: #374151; line-height: 1.5;
            background: transparent;
        """)
        bl.addWidget(lbl_mensaje)

        # Botón de acción
        btn_ir = QPushButton("Ir a Recordatorios →")
        btn_ir.setFixedHeight(38)
        btn_ir.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ir.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.color_header_bg}; color: #FFF;
                border: none; border-radius: 8px;
                font-size: 12px; font-weight: 600; padding: 0 20px;
            }}
            QPushButton:hover {{
                background-color: {self.color_header_bg}DD;
            }}
        """)
        btn_ir.clicked.connect(self._ir_a_recordatorios)
        bl.addWidget(btn_ir, 0, Qt.AlignmentFlag.AlignRight)

        root.addWidget(body)

        _shadow(body, blur=24, dy=8, opacity=0.20)  # ← aquí, no al self
        root.addWidget(body)

    def _posicionar(self):
        """Posiciona el toast en la esquina inferior derecha."""
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.width() - self.width() - 24,
            screen.height() - 280
        )

    def _cerrar_animado(self):
        """Cierra el toast con animación."""
        self._anim_salida = QPropertyAnimation(self, b"windowOpacity")
        self._anim_salida.setDuration(250)
        self._anim_salida.setStartValue(1.0)
        self._anim_salida.setEndValue(0.0)
        self._anim_salida.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim_salida.finished.connect(self.close)
        self._anim_salida.start()

    def _ir_a_recordatorios(self):
        """Cierra el toast y navega a recordatorios."""
        self._cerrar_animado()
        if hasattr(self, 'on_ir_clicked') and self.on_ir_clicked:
            self.on_ir_clicked()

# ══════════════════════════════════════════════════════════════════════════════
#  FUNCIÓN PÚBLICA: cuántos alumnos pendientes de RUNT hay esta semana
# ══════════════════════════════════════════════════════════════════════════════

def get_pendientes_runt() -> int:
    """Devuelve el TOTAL de alumnos pendientes de RUNT (todas las prioridades)."""
    try:
        criticos, medios, normales = get_alumnos_pendientes_runt()
        return len(criticos) + len(medios) + len(normales)
    except Exception:
        return 0


def get_alumnos_pendientes_runt():
    """Devuelve 3 listas: [criticos, medios, normales]"""
    try:
        db = Database.get_instance()
        hoy = QDate.currentDate()

        # Fechas límite
        fecha_90 = hoy.addDays(-90).toString("yyyy-MM-dd")   # 3 meses (crítico)
        fecha_60 = hoy.addDays(-60).toString("yyyy-MM-dd")   # 2 meses (medio)
        fecha_30 = hoy.addDays(-30).toString("yyyy-MM-dd")   # 1 mes (normal)

        # Todos los pendientes de los últimos 3 meses
        rows = db.fetchall("""
            SELECT m.id, a.nombres, a.apellidos, a.numero_documento, a.tipo_documento,
                   m.categoria, m.fecha_registro, m.estado, a.celular, a.email,
                   a.fecha_nacimiento, a.lugar_nacimiento, a.sexo, a.estado_civil,
                   a.grupo_sanguineo, m.observaciones
            FROM matriculas m
            JOIN alumnos a ON a.numero_documento = m.numero_documento
            WHERE DATE(m.fecha_registro) >= %s
              AND (m.runt_registrado IS NULL OR m.runt_registrado = 0)
              AND m.estado != 'Histórico'
            ORDER BY m.fecha_registro ASC
        """, (fecha_90,))

        criticos, medios, normales = [], [], []

        for r in rows:
            fecha_reg = QDate.fromString(str(r.get("fecha_registro", ""))[:10], "yyyy-MM-dd")
            dias = fecha_reg.daysTo(hoy)

            if dias >= 60:          # 2+ meses → CRÍTICO
                criticos.append(r)
            elif dias >= 30:        # 1-2 meses → MEDIO
                medios.append(r)
            else:                   # <1 mes → NORMAL
                normales.append(r)

        return criticos, medios, normales

    except Exception:
        return [], [], []

# ══════════════════════════════════════════════════════════════════════════════
#  DIÁLOGO: CONFIRMACIÓN PERSONALIZADA (sin botones blancos del sistema)
# ══════════════════════════════════════════════════════════════════════════════

class _ConfirmDialog(QDialog):
    """Diálogo de confirmación con botones estilizados PRACTICAR."""

    def __init__(self, titulo: str, mensaje: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        _tamanio_adaptativo(self, 540, 680)
        self.setStyleSheet(f"QDialog {{ background-color: {PAL['surface']}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(18)

        # Ícono + mensaje
        row = QHBoxLayout()
        row.setSpacing(16)
        ic = QLabel("❓")
        ic.setStyleSheet("font-size: 30px; background: transparent;")
        ic.setFixedWidth(40)
        row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        lbl = QLabel(mensaje)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"font-size: 13px; color: {PAL['text_1']}; background: transparent;")
        row.addWidget(lbl, 1)
        root.addLayout(row)

        # Botones
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        btn_no = QPushButton("Cancelar")
        btn_no.setFixedHeight(38)
        btn_no.setMinimumWidth(100)
        btn_no.setStyleSheet(f"""
            QPushButton {{
                background: {PAL['bg']}; color: {PAL['text_1']};
                border: 1.5px solid {PAL['border']}; border-radius: 8px;
                font-size: 13px; font-weight: 500; padding: 0 18px;
            }}
            QPushButton:hover {{ background: {PAL['border_lt']}; }}
        """)
        btn_no.clicked.connect(self.reject)
        btn_row.addWidget(btn_no)

        btn_si = QPushButton("Sí, confirmar")
        btn_si.setFixedHeight(38)
        btn_si.setMinimumWidth(130)
        btn_si.setStyleSheet(f"""
            QPushButton {{
                background: {PAL['rojo']}; color: #FFF;
                border: none; border-radius: 8px;
                font-size: 13px; font-weight: 700; padding: 0 18px;
            }}
            QPushButton:hover {{ background: {PAL['rojo_dark']}; }}
        """)
        btn_si.clicked.connect(self.accept)
        btn_row.addWidget(btn_si)

        root.addLayout(btn_row)


# ══════════════════════════════════════════════════════════════════════════════
#  DIÁLOGO: DETALLE DEL ALUMNO PENDIENTE
# ══════════════════════════════════════════════════════════════════════════════

class DetalleAlumnoDialog(QDialog):
    marcado = pyqtSignal(int)

    def __init__(self, alumno: dict, parent=None):
        super().__init__(parent)
        self.alumno = alumno
        self.setWindowTitle("Detalle Alumno — RUNT")
        self.setMinimumSize(780, 750)
        _tamanio_adaptativo(self, 800, 700)
        self.setStyleSheet(f"QDialog {{ background-color: {PAL['bg']}; }}" + GLOBAL_QSS)
        
        # Ventana flotante siempre visible encima de otras apps
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowCloseButtonHint
        )
    
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Header ──
        header = QWidget()
        header.setFixedHeight(76)
        header.setStyleSheet(
            f"background: {PAL['blue']}; border-bottom: 4px solid {PAL['rojo']};"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 0, 24, 0)
        ic = QLabel("🗂")
        ic.setStyleSheet("font-size: 26px; background: transparent;")
        hl.addWidget(ic)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_t = QLabel("Alumno pendiente de RUNT")
        lbl_t.setStyleSheet("font-size: 17px; font-weight: 700; color: #FFF; background: transparent;")
        title_col.addWidget(lbl_t)
        nombre_completo = f"{self.alumno.get('nombres','')} {self.alumno.get('apellidos','')}".strip()
        lbl_s = QLabel(nombre_completo)
        lbl_s.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.75); background: transparent;")
        title_col.addWidget(lbl_s)
        hl.addLayout(title_col)
        root.addWidget(header)

        # ── Scroll body ──
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        body = QWidget()
        body.setStyleSheet(f"background: {PAL['bg']};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 20, 24, 16)
        bl.setSpacing(14)

        # ── Grid 2x2 de tarjetas ──
        grid = QGridLayout()
        grid.setSpacing(14)

        # Datos de cada tarjeta: (titulo, icono, [(etiqueta, valor), ...])
        tarjetas = [
            ("Identificación", "🪪", [
                ("Nombre completo", f"{self.alumno.get('nombres','')} {self.alumno.get('apellidos','')}".strip()),
                ("Tipo documento",  self.alumno.get('tipo_documento', '—') or '—'),
                ("N° Documento",    self.alumno.get('numero_documento', '—') or '—'),
                ("Categoría",       self.alumno.get('categoria', '—') or '—'),
                ("Estado",          self.alumno.get('estado', '—') or '—'),
                ("Fecha registro",  str(self.alumno.get('fecha_registro', '—') or '—')),
            ]),
            ("Datos Personales", "👤", [
                ("Fecha nacimiento", str(self.alumno.get('fecha_nacimiento', '—') or '—')),
                ("Lugar nacimiento", self.alumno.get('lugar_nacimiento', '—') or '—'),
                ("Sexo",             self.alumno.get('sexo', '—') or '—'),
                ("Estado civil",     self.alumno.get('estado_civil', '—') or '—'),
                ("Grupo sanguíneo",  self.alumno.get('grupo_sanguineo', '—') or '—'),
            ]),
            ("Contacto", "📞", [
                ("Celular", self.alumno.get('celular', '—') or '—'),
                ("Email",   self.alumno.get('email', '—') or '—'),
            ]),
            ("Observaciones", "📝", [
                ("__obs__", self.alumno.get('observaciones', 'Sin observaciones.') or 'Sin observaciones.'),
            ]),
        ]

        posiciones = [(0, 0), (0, 1), (1, 0), (1, 1)]

        for (fila, col), (titulo, icono, campos) in zip(posiciones, tarjetas):
            card = self._make_card(titulo, icono, campos)
            grid.addWidget(card, fila, col)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        bl.addLayout(grid)
        bl.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll)

        # ── Footer ──
        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet(
            f"background: {PAL['surface']}; border-top: 1.5px solid {PAL['border_lt']};"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 0, 24, 0)
        fl.setSpacing(10)
        fl.addStretch()

        btn_cancel = _btn_secondary("Cerrar")
        btn_cancel.clicked.connect(self.reject)
        fl.addWidget(btn_cancel)

        btn_marcar = _btn_primary(
            "✔  Marcar como Registrado en RUNT",
            color=PAL['rojo'], color_dark=PAL['rojo_dark']
        )
        btn_marcar.clicked.connect(self._marcar_runt)
        fl.addWidget(btn_marcar)
        root.addWidget(footer)

    # ── Construcción de tarjeta ──────────────────────────────────────────────

    def _make_card(self, titulo: str, icono: str, campos: list) -> QFrame:
        card = QFrame()
        card.setObjectName("Tarjeta")
        card.setStyleSheet(f"""
            QFrame#Tarjeta {{
                background-color: {PAL['surface']};
                border: 1.5px solid {PAL['border_lt']};
                border-radius: 12px;
            }}
        """)
        _shadow(card, blur=10, dy=2, opacity=0.05)

        vl = QVBoxLayout(card)
        vl.setContentsMargins(16, 14, 16, 16)
        vl.setSpacing(10)

        # Título de tarjeta
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        ic_lbl = QLabel(icono)
        ic_lbl.setStyleSheet(f"""
            font-size: 15px; background: {PAL['blue_bg']};
            border-radius: 8px; padding: 4px 6px;
        """)
        ic_lbl.setFixedSize(32, 32)
        ic_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addWidget(ic_lbl)

        t_lbl = QLabel(titulo)
        t_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {PAL['blue']}; background: transparent;"
        )
        title_row.addWidget(t_lbl)
        title_row.addStretch()
        vl.addLayout(title_row)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {PAL['border_lt']}; border: none; max-height: 1px;")
        vl.addWidget(sep)

        # Campos
        for etq, val in campos:
            # Campo especial: observaciones (texto largo)
            if etq == "__obs__":
                obs_lbl = QLabel(val)
                obs_lbl.setWordWrap(True)
                obs_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
                obs_lbl.setStyleSheet(f"""
                    font-size: 12px; color: {PAL['text_2']};
                    background: {PAL['bg']}; border-radius: 8px;
                    padding: 10px; border: 1px solid {PAL['border_lt']};
                """)
                obs_lbl.setMinimumHeight(80)
                vl.addWidget(obs_lbl)
            else:
                row = QVBoxLayout()
                row.setSpacing(2)

                lbl_key = QLabel(etq)
                lbl_key.setStyleSheet(
                    f"font-size: 10px; font-weight: 600; color: {PAL['text_3']}; "
                    f"letter-spacing: 0.04em; background: transparent;"
                )
                row.addWidget(lbl_key)

                lbl_val = QLabel(str(val))
                lbl_val.setStyleSheet(
                    f"font-size: 13px; font-weight: 600; color: {PAL['text_1']}; background: transparent;"
                )
                lbl_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                row.addWidget(lbl_val)

                vl.addLayout(row)

        vl.addStretch()
        return card

    # ── Acción marcar RUNT ───────────────────────────────────────────────────

    def _marcar_runt(self):
        confirm = _ConfirmDialog(
            titulo="Confirmar registro RUNT",
            mensaje=f"¿Confirma que <b>{self.alumno.get('nombres','')} {self.alumno.get('apellidos','')}</b> ya fue registrado en el RUNT?",
            parent=self
        )
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            db = Database.get_instance()
            db.execute(
                "UPDATE matriculas SET runt_registrado = 1 WHERE id = %s",
                (self.alumno["id"],)
            )
            self.marcado.emit(self.alumno["id"])
            QMessageBox.information(
                self, "Listo",
                f"{self.alumno.get('nombres','')} marcado como registrado en RUNT."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  VISTA PRINCIPAL: RECORDATORIOS RUNT
# ══════════════════════════════════════════════════════════════════════════════

class RecordatoriosView(QWidget):
    badge_actualizado = pyqtSignal(int)
    mostrar_recordatorios = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setStyleSheet(self._global_qss())
        self._pendientes = []
        self._build_ui()
        self._load()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._load)
        self._timer.start(5 * 60 * 1000)

    def showEvent(self, event):
        super().showEvent(event)
        self._load()

    # ── QSS ──────────────────────────────────────────────────────────────────

    def _global_qss(self):
        return f"""
            QWidget {{ background-color: #F4F5F7; font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif; }}
            QLabel  {{ background: transparent; }}
                
            QScrollBar:vertical {{
                width: 6px; background: transparent; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: #CBD5E1; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """

    # ── BUILD UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        
        _scroll_outer = QScrollArea()
        _scroll_outer.setWidgetResizable(True)
        _scroll_outer.setFrameShape(QFrame.Shape.NoFrame)
        _scroll_outer.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        _scroll_outer.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        _scroll_outer.setStyleSheet("background: transparent; border: none;")
        _body = QWidget()
        _body.setStyleSheet("background: transparent;")
        root = QVBoxLayout(_body)          # ← _body, NO self
        root.setContentsMargins(32, 28, 32, 0)
        root.setSpacing(20)

        # ═══════════════════════════════════════════════════════════
        #  HEADER TÍTULO
        # ═══════════════════════════════════════════════════════════
        header_row = QHBoxLayout()
        header_row.setSpacing(14)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        lbl_title = QLabel("Recordatorios RUNT")
        lbl_title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1E293B;")
        title_col.addWidget(lbl_title)
        self.lbl_sub = QLabel("Alumnos pendientes de registro en el RUNT por prioridad")
        self.lbl_sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_col.addWidget(self.lbl_sub)
        header_row.addLayout(title_col)
        header_row.addStretch()

        btn_refrescar = QPushButton("↻  Refrescar")
        btn_refrescar.setFixedHeight(36)
        btn_refrescar.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #1D4ED8;
                border: 1.5px solid #1D4ED8; border-radius: 9px;
                padding: 0 18px; font-size: 12px; font-weight: 600;
            }
            QPushButton:hover  { background-color: #EFF6FF; }
            QPushButton:pressed { background-color: #DBEAFE; }
        """)
        btn_refrescar.clicked.connect(self._load)
        header_row.addWidget(btn_refrescar)
        root.addLayout(header_row)

        # ═══════════════════════════════════════════════════════════
        #  STAT CARD (total general)
        # ═══════════════════════════════════════════════════════════
        self.card_stat = QFrame()
        self.card_stat.setFixedHeight(96)
        self.card_stat.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #E2E8F0;
            }
        """)
        _shadow(self.card_stat, blur=16, dy=4, opacity=0.06)

        stat_row = QHBoxLayout(self.card_stat)
        stat_row.setContentsMargins(20, 0, 24, 0)
        stat_row.setSpacing(16)

        ic_circle = QLabel("🔔")
        ic_circle.setFixedSize(52, 52)
        ic_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic_circle.setStyleSheet("""
            background: #DBEAFE; border-radius: 26px;
            font-size: 22px; border: none;
        """)
        stat_row.addWidget(ic_circle)

        stat_txt = QVBoxLayout()
        stat_txt.setSpacing(2)
        lbl_stat_label = QLabel("Total alumnos pendientes de registro RUNT")
        lbl_stat_label.setStyleSheet("font-size: 11px; color: #64748B; font-weight: 500;")
        stat_txt.addWidget(lbl_stat_label)

        self.lbl_pendientes_count = QLabel("0")
        self.lbl_pendientes_count.setStyleSheet("font-size: 34px; font-weight: 800; color: #1D4ED8;")
        stat_txt.addWidget(self.lbl_pendientes_count)
        stat_row.addLayout(stat_txt)
        stat_row.addStretch()

        self.semana_badge = QFrame()
        self.semana_badge.setObjectName("TarjetaSemana")
        self.semana_badge.setStyleSheet("""
            #TarjetaSemana {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
            #TarjetaSemana QLabel {
                color: #64748B;
                font-size: 12px;
                font-weight: 500;
                background: transparent;
            }
        """)
        badge_layout = QHBoxLayout(self.semana_badge)
        badge_layout.setContentsMargins(14, 8, 14, 8)
        self.lbl_semana = QLabel("Semana: —")
        self.lbl_semana.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        badge_layout.addWidget(self.lbl_semana)
        stat_row.addWidget(self.semana_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self.card_stat)

        # ═══════════════════════════════════════════════════════════
        #  PANEL VACÍO (cuando no hay nada)
        # ══════════════════════════════════════════════
        self.panel_vacio = QWidget()
        vacio_layout = QVBoxLayout(self.panel_vacio)
        vacio_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vacio_layout.setSpacing(12)

        ic_ok = QLabel("✅")
        ic_ok.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic_ok.setStyleSheet("font-size: 52px; background: transparent;")
        vacio_layout.addWidget(ic_ok)

        lbl_ok = QLabel("No hay recordatorios pendientes")
        lbl_ok.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_ok.setStyleSheet("font-size: 18px; font-weight: 700; color: #475569;")
        vacio_layout.addWidget(lbl_ok)

        lbl_ok2 = QLabel("Todos los alumnos nuevos ya fueron registrados en el RUNT\no no hay alumnos pendientes.")
        lbl_ok2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_ok2.setStyleSheet("font-size: 13px; color: #94A3B8;")
        lbl_ok2.setWordWrap(True)
        vacio_layout.addWidget(lbl_ok2)
        root.addWidget(self.panel_vacio)

        # ═══════════════════════════════════════════════════════════
        #  PANEL TABLAS (contiene las 3 tablas por prioridad)
        # ═══════════════════════════════════════════════════════════
        self.panel_tablas = QWidget()
        self.panel_tablas.setStyleSheet("background: transparent;")
        tablas_layout = QVBoxLayout(self.panel_tablas)
        tablas_layout.setContentsMargins(0, 0, 0, 0)
        tablas_layout.setSpacing(24)

                # ── Tabla CRÍTICA (2+ meses) ──
        self._build_tabla_seccion(
            tablas_layout,
            titulo="🔴  URGENTE — Más de 2 meses sin RUNT",
            subtitulo="Estos alumnos están próximos a vencer el plazo de 3 meses. ¡Acción inmediata!",
            color_header="#DC2626",
            color_bg="#FEF2F2",
            color_border="#FECACA",
            nombre_attr="tbl_criticos"
        )

        tablas_layout.addSpacing(24)  # ← ESPACIO ENTRE SECCIONES

        # ── Tabla MEDIA (1-2 meses) ──
        self._build_tabla_seccion(
            tablas_layout,
            titulo="🟠  PRÓXIMOS A VENCER — 1 a 2 meses",
            subtitulo="Deben registrarse en RUNT esta semana para evitar retrasos.",
            color_header="#D97706",
            color_bg="#FFFBEB",
            color_border="#FDE68A",
            nombre_attr="tbl_medios"
        )

        tablas_layout.addSpacing(24)  # ← ESPACIO ENTRE SECCIONES

        # ── Tabla NORMAL (<1 mes) ──
        self._build_tabla_seccion(
            tablas_layout,
            titulo="🟢  PENDIENTES — Menos de 1 mes",
            subtitulo="Registro reciente, aún dentro del tiempo óptimo.",
            color_header="#059669",
            color_bg="#F0FDF4",
            color_border="#BBF7D0",
            nombre_attr="tbl_normales"
        )

        # Botón marcar todos (solo aparece si hay datos)
        foot = QHBoxLayout()
        foot.setContentsMargins(0, 10, 0, 0)
        foot.addStretch()

        btn_marcar_todos = QPushButton("✔  Marcar todos como Registrados")
        btn_marcar_todos.setFixedHeight(42)
        btn_marcar_todos.setStyleSheet("""
            QPushButton {
                background-color: #991B1B; color: #FFF;
                border: none; border-radius: 10px;
                padding: 0 28px; font-size: 13px; font-weight: 700;
            }
            QPushButton:hover  { background-color: #7F1D1D; }
            QPushButton:pressed { background-color: #7F1D1D; }
        """)
        _shadow(btn_marcar_todos, blur=18, dy=5, opacity=0.18)
        btn_marcar_todos.clicked.connect(self._marcar_todos)
        foot.addWidget(btn_marcar_todos)
        tablas_layout.addLayout(foot)

        root.addWidget(self.panel_tablas)

        # ── Pie de página ──
        footer_line = QFrame()
        footer_line.setFrameShape(QFrame.Shape.HLine)
        footer_line.setFixedHeight(1)
        footer_line.setStyleSheet("background: #E2E8F0; border: none;")
        root.addWidget(footer_line)

        foot_bar = QHBoxLayout()
        foot_bar.setContentsMargins(0, 5, 0, 10)
        from PyQt6.QtCore import QDate as _QDate
        hoy_str = _QDate.currentDate().toString("dd 'de' MMMM yyyy")
        lbl_footer = QLabel(f"Conectado a: cea_p  |  Versión 1.0.0  |  {hoy_str}")
        lbl_footer.setStyleSheet("font-size: 10px; color: #CBD5E1;")
        foot_bar.addWidget(lbl_footer)
        foot_bar.addStretch()
        root.addLayout(foot_bar)

        _scroll_outer.setWidget(_body)
        _outer_root = QVBoxLayout(self)
        _outer_root.setContentsMargins(0, 0, 0, 0)
        _outer_root.setSpacing(0)
        _outer_root.addWidget(_scroll_outer, 1)

    # ── CARGA ─────────────────────────────────────────────────────────────────

    def _build_tabla_seccion(self, parent_layout, titulo, subtitulo, color_header, color_bg, color_border, nombre_attr):
        """Crea una sección de tabla con estilo visual único por prioridad."""

        # Contenedor principal con borde de color
        seccion = QFrame()
        seccion.setObjectName(f"seccion_{nombre_attr}")
        seccion.setStyleSheet(f"""
            QFrame#seccion_{nombre_attr} {{
                background-color: #FFFFFF;
                border-radius: 14px;
                border: 2px solid {color_border};
            }}
        """)
        _shadow(seccion, blur=18, dy=4, opacity=0.08)

        sl = QVBoxLayout(seccion)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        # ── Header de sección con color de fondo ──
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {color_bg};
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom: 2px solid {color_border};
            }}
        """)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 14, 20, 14)

        # Icono + texto
        txt_col = QVBoxLayout()
        txt_col.setSpacing(3)

        lbl_t = QLabel(titulo)
        lbl_t.setStyleSheet(f"""
            font-size: 14px; font-weight: 700; color: {color_header};
            background: transparent;
        """)
        txt_col.addWidget(lbl_t)

        lbl_s = QLabel(subtitulo)
        lbl_s.setStyleSheet("""
            font-size: 11px; color: #64748B; background: transparent;
        """)
        txt_col.addWidget(lbl_s)

        hl.addLayout(txt_col)
        hl.addStretch()

        # Contador circular con color
        count_frame = QFrame()
        count_frame.setFixedSize(44, 44)
        count_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {color_header};
                border-radius: 22px;
            }}
        """)
        count_lay = QVBoxLayout(count_frame)
        count_lay.setContentsMargins(0, 0, 0, 0)

        lbl_count = QLabel("0")
        lbl_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_count.setStyleSheet("""
            font-size: 16px; font-weight: 800; color: #FFFFFF;
            background: transparent;
        """)
        count_lay.addWidget(lbl_count)
        hl.addWidget(count_frame)

        sl.addWidget(header)

        # ── Tabla con estilo personalizado ──
        tabla = QTableWidget()
        tabla.setObjectName(f"tabla_{nombre_attr}")
        tabla.setColumnCount(7)
        tabla.setHorizontalHeaderLabels([
            "Nombre Completo", "N° Documento", "Categoría",
            "Fecha Registro", "Estado", "Días Pendiente", "Acción"
        ])

        # Header de tabla con color de la sección
        tabla.setStyleSheet(f"""
            QTableWidget#tabla_{nombre_attr} {{
                background-color: #FFFFFF;
                border: none;
                gridline-color: {color_border};
                outline: none;
            }}
            QTableWidget#tabla_{nombre_attr}::item {{
                padding: 0 14px;
                border-bottom: 1px solid #F1F5F9;
                color: #1E293B;
                font-size: 13px;
            }}
            QTableWidget#tabla_{nombre_attr}::item:selected {{
                background-color: {color_bg};
                color: {color_header};
            }}
            QHeaderView::section {{
                background-color: {color_bg};
                padding: 12px 14px;
                border: none;
                border-bottom: 2px solid {color_border};
                font-weight: 700;
                font-size: 10px;
                letter-spacing: 0.06em;
                color: {color_header};
                text-transform: uppercase;
            }}
        """)

        tabla.horizontalHeader().setStretchLastSection(True)
        tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        
        tabla.verticalHeader().setVisible(False)
        tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tabla.setShowGrid(False)
        tabla.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tabla.verticalHeader().setDefaultSectionSize(52)
        tabla.setFrameShape(QFrame.Shape.NoFrame)
        
        tabla.setColumnWidth(1, 130)
        tabla.setColumnWidth(2, 100)
        tabla.setColumnWidth(3, 130)
        tabla.setColumnWidth(4, 110)
        tabla.setColumnWidth(5, 120)
        tabla.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        tabla.setColumnWidth(6, 170)
        tabla.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Fondo alternado para filas
        tabla.setAlternatingRowColors(True)

        sl.addWidget(tabla)

        # Espaciado inferior redondeado
        bottom = QFrame()
        bottom.setFixedHeight(8)
        bottom.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }}
        """)
        sl.addWidget(bottom)

        parent_layout.addWidget(seccion)

        # Guardar referencias
        setattr(self, nombre_attr, tabla)
        setattr(self, f"lbl_count_{nombre_attr}", lbl_count)
        setattr(self, f"seccion_{nombre_attr}", seccion)

    def _load(self):
        self._criticos, self._medios, self._normales = get_alumnos_pendientes_runt()
        total = len(self._criticos) + len(self._medios) + len(self._normales)

        self.lbl_pendientes_count.setText(str(total))

        hoy = QDate.currentDate()
        dias_lunes = hoy.dayOfWeek() - 1
        lunes = hoy.addDays(-dias_lunes)
        domingo = lunes.addDays(6)
        MESES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        self.lbl_semana.setText(
            f"Semana: {lunes.day()} {MESES[lunes.month()]} — "
            f"{domingo.day()} {MESES[domingo.month()]} {domingo.year()}"
        )

        self.badge_actualizado.emit(total)

        # Mostrar/ocultar paneles
        if total == 0:
            self.panel_vacio.setVisible(True)
            self.panel_tablas.setVisible(False)
        else:
            self.panel_vacio.setVisible(False)
            self.panel_tablas.setVisible(True)

            # Renderizar cada tabla
            self._render_tabla(self.tbl_criticos, self._criticos, "lbl_count_tbl_criticos", "seccion_tbl_criticos", critico=True)
            self._render_tabla(self.tbl_medios, self._medios, "lbl_count_tbl_medios", "seccion_tbl_medios", critico=False)
            self._render_tabla(self.tbl_normales, self._normales, "lbl_count_tbl_normales", "seccion_tbl_normales", critico=False)


    def verificar_y_notificar(self, parent_window=None):
        """
        Verifica si hay alumnos críticos (2+ meses) y muestra toast si los hay.
        Llama esto desde MainWindow después de login.
        """
        criticos, medios, normales = get_alumnos_pendientes_runt()

        if len(criticos) > 0:
            nombres = [f"{a.get('nombres','')} {a.get('apellidos','')}".strip()
                       for a in criticos[:3]]
            lista_nombres = "<br>• ".join([""] + nombres)
            if len(criticos) > 3:
                lista_nombres += f"<br>• ... y {len(criticos) - 3} más"

            mensaje = (f"<b>{len(criticos)} alumno{'s' if len(criticos) > 1 else ''}</b> "
                       f"lleva{'n' if len(criticos) > 1 else ''} más de <b>2 meses</b> "
                       f"sin registro en RUNT.{lista_nombres}")

            self.toast = ToastNotificacion(
                parent=parent_window,
                titulo="⚠️ URGENTE — RUNT",
                mensaje=mensaje,
                tipo="critico"
            )
            # Conectar el botón "Ir a Recordatorios" con la señal
            self.toast.on_ir_clicked = lambda: self.mostrar_recordatorios.emit()
            self.toast.show()

        elif len(medios) > 0:
            mensaje = (f"<b>{len(medios)} alumno{'s' if len(medios) > 1 else ''}</b> "
                       f"está{'n' if len(medios) > 1 else ''} entre 1 y 2 meses "
                       f"sin registro en RUNT. Revisa pronto.")

            self.toast = ToastNotificacion(
                parent=parent_window,
                titulo="⏰ Próximos a vencer — RUNT",
                mensaje=mensaje,
                tipo="advertencia"
            )
            self.toast.on_ir_clicked = lambda: self.mostrar_recordatorios.emit()
            self.toast.show()

    def _render_tabla(self, tabla, datos, lbl_count_attr, seccion_attr, critico=False):
        """Renderiza una tabla de prioridad y controla su visibilidad."""
        # Actualizar contador en header circular
        lbl_count = getattr(self, lbl_count_attr)
        lbl_count.setText(str(len(datos)))

        # Ocultar sección si no hay datos
        seccion = getattr(self, seccion_attr)
        seccion.setVisible(len(datos) > 0)

        if not datos:
            return

        tabla.setRowCount(len(datos))
        hoy = QDate.currentDate()

        # Colores según prioridad para las filas
        if critico:
            bg_alterno = "#FEF2F2"  # Rojo muy pálido
            bg_normal = "#FFFFFF"
            color_dias = "#DC2626"
            color_dias_warn = "#991B1B"
        elif len(datos) > 0 and any(True for _ in datos):  # Medio
            bg_alterno = "#FFFBEB"  # Ámbar muy pálido
            bg_normal = "#FFFFFF"
            color_dias = "#D97706"
            color_dias_warn = "#92400E"
        else:  # Normal
            bg_alterno = "#F0FDF4"  # Verde muy pálido
            bg_normal = "#FFFFFF"
            color_dias = "#059669"
            color_dias_warn = "#047857"

        for i, alumno in enumerate(datos):
            nombre = f"{alumno.get('nombres', '')} {alumno.get('apellidos', '')}".strip()
            doc = str(alumno.get('numero_documento', ''))
            cat = str(alumno.get('categoria', ''))
            fecha = str(alumno.get('fecha_registro', ''))
            estado = str(alumno.get('estado', ''))

            try:
                fecha_q = QDate.fromString(fecha[:10], "yyyy-MM-dd")
                dias = fecha_q.daysTo(hoy)
            except Exception:
                dias = 0

            valores = [
                nombre, doc, cat,
                fecha[:10] if fecha else "",
                estado,
                f"{dias} día{'s' if dias != 1 else ''}"
            ]

            # Fondo alternado
            bg_color = bg_alterno if i % 2 == 1 else bg_normal

            for col, val in enumerate(valores):
                it = QTableWidgetItem(str(val))
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Aplicar fondo a todas las celdas
                it.setBackground(QColor(bg_color))

                if col == 0:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                    it.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
                else:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)

                # Días pendiente — colores según urgencia
                if col == 5:
                    if critico:
                        it.setForeground(QColor(color_dias))
                        it.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
                    elif dias >= 45:
                        it.setForeground(QColor(color_dias))
                        it.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
                    else:
                        it.setForeground(QColor(color_dias))

                # Estado — color según tipo
                if col == 4:
                    estado_lower = str(val).lower()
                    if "cancelado" in estado_lower:
                        it.setForeground(QColor("#DC2626"))
                    elif "pendiente" in estado_lower:
                        it.setForeground(QColor("#D97706"))
                    elif "activo" in estado_lower:
                        it.setForeground(QColor("#059669"))

                tabla.setItem(i, col, it)

            # Botón acción con borde del color de la sección
            act_w = QWidget()
            act_w.setStyleSheet("background: transparent;")
            al = QHBoxLayout(act_w)
            al.setContentsMargins(10, 8, 10, 8)

            btn_ver = QPushButton("✔  Registrado en RUNT")
            btn_ver.setFixedHeight(32)
            btn_ver.setMinimumWidth(150)
            btn_ver.setStyleSheet("""
                QPushButton {
                    font-size: 11px; font-weight: 600;
                    background-color: #EFF6FF; color: #1D4ED8;
                    border: 1.5px solid #BFDBFE;
                    border-radius: 16px; padding: 0 14px;
                }
                QPushButton:hover {
                    background-color: #1D4ED8; color: #FFFFFF;
                    border-color: #1D4ED8;
                }
            """)
            btn_ver.clicked.connect(lambda _, a=alumno: self._abrir_detalle(a))
            al.addWidget(btn_ver)
            al.addStretch()
            tabla.setCellWidget(i, 6, act_w)



    # ── ACCIONES ──────────────────────────────────────────────────────────────

    def _abrir_detalle(self, alumno: dict):
        dlg = DetalleAlumnoDialog(alumno, parent=self)
        dlg.marcado.connect(self._on_marcado)
        dlg.show()  # ← era dlg.exec()

    def _on_marcado(self, alumno_id: int):
        self._load()

    def _marcar_todos(self):
        todos = self._criticos + self._medios + self._normales
        if not todos:
            return

        nombres = "\n".join(
            f"• {a.get('nombres', '')} {a.get('apellidos', '')}"
            for a in todos[:5]
        )
        if len(todos) > 5:
            nombres += f"\n  ... y {len(todos) - 5} más"

        confirm = _ConfirmDialog(
            titulo="Confirmar — Marcar todos",
            mensaje=f"¿Confirma que <b>todos los {len(todos)} alumnos</b> ya fueron registrados en el RUNT?<br><br>{nombres.replace(chr(10), '<br>')}",
            parent=self
        )
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            db = Database.get_instance()
            ids = tuple(a["id"] for a in todos)
            placeholders = ",".join(["%s"] * len(ids))
            db.execute(
                f"UPDATE matriculas SET runt_registrado = 1 WHERE id IN ({placeholders})",
                ids
            )
            QMessageBox.information(
                self, "Listo",
                f"Se marcaron {len(todos)} alumnos como registrados en RUNT."
            )
            self._load()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))