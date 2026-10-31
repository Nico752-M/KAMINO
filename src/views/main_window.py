#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ventana Principal del Sistema CEA PRACTICAR
Estética: sidebar #111827, rojo #C8252A, azul #1A2B6B, Nunito/Bebas Neue
Sidebar: toggle hamburguesa — se oculta/muestra con animación suave
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame,
    QApplication
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QPen, QColor

from views.login_view import LoginView
from views.dashboard_view import DashboardView
from views.alumnos_view import AlumnosView  # señal: alumno_registrado
from views.pagos_view import PagosView
from views.reportes_view import ReportesView
from views.historico_view import HistoricoView
from views.renovaciones_view import RenovacionesView
from views.recordatorios_view import RecordatoriosView, get_pendientes_runt   # ← NUEVO

# ── Paleta PRACTICAR ────────────────────────────────────────────
C_ROJO        = "#C8252A"
C_ROJO_DARK   = "#9E1C20"
C_ROJO_LIGHT  = "#f9e8e8"
C_AZUL        = "#1A2B6B"
C_AZUL_LIGHT  = "#e8ecf9"
C_GRIS_FONDO  = "#F3F4F8"
C_GRIS_BORDE  = "#E0E3EE"
C_GRIS_TEXTO  = "#6B7080"
C_BLANCO      = "#FFFFFF"
C_SIDEBAR     = "#111827"
C_SIDEBAR_HOV = "#1f2a40"
C_SIDEBAR_TXT = "#9CA3AF"

SIDEBAR_W = 220   # ancho visible
SIDEBAR_ANIM_MS = 220   # duración animación en ms


# ════════════════════════════════════════════════════════════════
#  SIDEBAR BUTTON
# ════════════════════════════════════════════════════════════════


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
    
class SidebarButton(QPushButton):
    """
    Botón de navegación del sidebar.
    Normal  → texto gris
    Hover   → fondo #1f2a40, texto blanco
    Checked → fondo rojo translúcido, borde-izq rojo, texto blanco
    """

    def __init__(self, icon_text: str, label: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(10)

        self.lbl_icon = QLabel(icon_text)
        self.lbl_icon.setFixedWidth(20)
        self.lbl_icon.setStyleSheet("font-size: 16px; background: transparent; color: #9CA3AF;")
        row.addWidget(self.lbl_icon)

        self.lbl_text = QLabel(label)
        self.lbl_text.setStyleSheet(
            "font-size: 13px; font-weight: 600; background: transparent; color: #9CA3AF;"
        )
        row.addWidget(self.lbl_text)
        row.addStretch()

        # Badge para recordatorios
        self.badge = QLabel("")
        self.badge.setFixedSize(20, 20)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setStyleSheet(f"""
            background: {C_ROJO}; color: white; border-radius: 10px;
            font-size: 10px; font-weight: 800;
        """)
        self.badge.setVisible(False)
        row.addWidget(self.badge)

        self.setStyleSheet(f"""
            SidebarButton {{
                background-color: transparent;
                border: none;
                border-left: 3px solid transparent;
                border-radius: 0px;
                text-align: left;
            }}
            SidebarButton:hover {{
                background-color: {C_SIDEBAR_HOV};
            }}
            SidebarButton:checked {{
                background-color: rgba(200, 37, 42, 0.15);
                border-left: 3px solid {C_ROJO};
            }}
        """)

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        color = "#FFFFFF" if checked else C_SIDEBAR_TXT
        self.lbl_icon.setStyleSheet(f"font-size: 16px; background: transparent; color: {color};")
        self.lbl_text.setStyleSheet(
            f"font-size: 13px; font-weight: 600; background: transparent; color: {color};"
        )

    def set_badge(self, count: int):
        """Muestra u oculta el badge con el número de pendientes."""
        if count > 0:
            self.badge.setText(str(count) if count < 100 else "99+")
            self.badge.setVisible(True)
        else:
            self.badge.setVisible(False)


# ════════════════════════════════════════════════════════════════
#  SIDEBAR LABEL DE SECCIÓN
# ════════════════════════════════════════════════════════════════

def _section_label(texto: str) -> QLabel:
    lbl = QLabel(texto.upper())
    lbl.setStyleSheet("""
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.12em;
        color: rgba(255,255,255,0.25);
        padding: 16px 16px 6px 16px;
        background: transparent;
    """)
    return lbl


# ════════════════════════════════════════════════════════════════
#  BOTÓN HAMBURGUESA
# ════════════════════════════════════════════════════════════════

def _ham_button() -> QPushButton:
    """Botón hamburguesa ≡ para la topbar — tres líneas oscuras, siempre visible."""
    btn = QPushButton()
    btn.setFixedSize(38, 38)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip("Mostrar / ocultar menú")

    inner = QHBoxLayout(btn)
    inner.setContentsMargins(0, 0, 0, 0)

    icon_lbl = QLabel()
    icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_lbl.setStyleSheet("background: transparent;")

    pix = QPixmap(24, 18)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(C_AZUL))
    pen.setWidth(2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(0, 2,  24, 2)
    p.drawLine(0, 9,  24, 9)
    p.drawLine(0, 16, 24, 16)
    p.end()
    icon_lbl.setPixmap(pix)
    inner.addWidget(icon_lbl)

    btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            border: 1.5px solid {C_GRIS_BORDE};
            border-radius: 8px;
        }}
        QPushButton:hover {{
            background: {C_AZUL_LIGHT};
            border-color: {C_AZUL};
        }}
        QPushButton:pressed {{
            background: {C_GRIS_BORDE};
        }}
    """)
    return btn


# ════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CEA PRACTICAR — Sistema de Gestión")
        self.setMinimumSize(1024, 700)
        self.showMaximized()

        self._sidebar_visible = True
        # Índice del botón Recordatorios en la lista sidebar_buttons (se asigna en _build_sidebar)
        self._idx_recordatorios = None

        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)

        # 1 — LOGIN (índice 0)
        self.login_view = LoginView()
        self.login_view.login_successful.connect(self.show_app)
        self.central_stack.addWidget(self.login_view)

        # 2 — APP CON SIDEBAR (índice 1)
        self.app_widget = QWidget()
        self._build_app_ui()
        self.central_stack.addWidget(self.app_widget)

        self.central_stack.setCurrentIndex(0)

    # ── NAVEGACIÓN ────────────────────────────────────────────

    def show_app(self):
        self.central_stack.setCurrentIndex(1)
        self.on_menu_clicked(0)
        # Mostrar notificación de RUNT al abrir la app
        QTimer.singleShot(1200, self._notificar_runt_al_inicio)
        # Verificar críticos y mostrar toast flotante
        QTimer.singleShot(2000, self._mostrar_toast_runt)

    def logout(self):
        self.central_stack.setCurrentIndex(0)

    def on_menu_clicked(self, index: int):
        for i, btn in enumerate(self.sidebar_buttons):
            btn.setChecked(i == index)
        self.lbl_page_title.setText(self.menu_items[index][1])
        self.content_stack.setCurrentIndex(index)

    def _on_pago_registrado(self):
        """Recarga la vista de alumnos cuando se registra un pago."""
        if self.vista_alumnos:
            self.vista_alumnos.load_alumnos()
    # ── TOGGLE SIDEBAR ─────────────────────────────────────────

    def toggle_sidebar(self):
        self._sidebar_visible = not self._sidebar_visible

        anim = QPropertyAnimation(self.sidebar_frame, b"maximumWidth")
        anim.setDuration(SIDEBAR_ANIM_MS)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuart)

        if self._sidebar_visible:
            anim.setStartValue(0)
            anim.setEndValue(SIDEBAR_W)
            self.sidebar_frame.setVisible(True)
        else:
            anim.setStartValue(SIDEBAR_W)
            anim.setEndValue(0)
            anim.finished.connect(lambda: self.sidebar_frame.setVisible(False))

        self._sidebar_anim = anim
        anim.start()

    # ── BUILD UI ──────────────────────────────────────────────

    def _build_app_ui(self):
        root = QHBoxLayout(self.app_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar_frame = self._build_sidebar()
        root.addWidget(self.sidebar_frame)
        root.addWidget(self._build_content_area(), 1)

    # ── SIDEBAR ───────────────────────────────────────────────

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(SIDEBAR_W)
        sidebar.setMinimumWidth(0)
        sidebar.setMaximumWidth(SIDEBAR_W)
        sidebar.setStyleSheet(f"QFrame {{ background-color: {C_SIDEBAR}; border: none; }}")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Cabecera / Brand ──
        header = QFrame()
        header.setFixedHeight(64)
        header.setStyleSheet(
            f"background: {C_SIDEBAR}; border-bottom: 1px solid rgba(255,255,255,0.07);"
        )
        h_row = QHBoxLayout(header)
        h_row.setContentsMargins(16, 0, 16, 0)
        h_row.setSpacing(10)

        logo_box = QLabel()
        logo_box.setFixedSize(36, 36)
        logo_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        import os as _os
        _logo_path = _os.path.normpath(_os.path.join(
            _os.path.dirname(_os.path.abspath(__file__)),
            "..", "assets", "logo_practicar.png"
        ))

        if _os.path.exists(_logo_path):
            _pix = QPixmap(_logo_path).scaled(
                36, 36,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            logo_box.setPixmap(_pix)
            logo_box.setStyleSheet("border-radius: 9px; background: transparent;")
            self.setWindowIcon(QIcon(_logo_path))
        else:
            logo_box.setText("P")
            logo_box.setStyleSheet(f"""
                background: {C_AZUL};
                border-radius: 9px;
                border: 2px solid {C_ROJO};
                font-size: 16px;
                font-weight: 800;
                color: #FFFFFF;
            """)

        h_row.addWidget(logo_box)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(1)

        lbl_brand = QLabel("PRACTICAR")
        lbl_brand.setStyleSheet(f"""
            font-family: 'Bebas Neue', 'Nunito', sans-serif;
            font-size: 17px;
            letter-spacing: 0.06em;
            color: #FFFFFF;
            background: transparent;
        """)
        brand_col.addWidget(lbl_brand)

        lbl_sub = QLabel("Gestión Alumnos")
        lbl_sub.setStyleSheet(
            f"font-size: 10px; color: {C_SIDEBAR_TXT}; background: transparent;"
        )
        brand_col.addWidget(lbl_sub)

        h_row.addLayout(brand_col)
        h_row.addStretch()
        layout.addWidget(header)

        # ── Sección Principal ──
        layout.addWidget(_section_label("Principal"))

        self.menu_items = [
            ("📊", "Dashboard",        DashboardView),
            ("👨‍🎓", "Alumnos",          AlumnosView),
            ("💳", "Control de Pagos", PagosView),
            ("🔄", "Renovaciones",     RenovacionesView),
        ]
        self.sidebar_buttons = []
        for icon, label, _ in self.menu_items:
            btn = SidebarButton(icon, label)
            btn.clicked.connect(
                lambda checked, idx=len(self.sidebar_buttons): self.on_menu_clicked(idx)
            )
            self.sidebar_buttons.append(btn)
            layout.addWidget(btn)

        # ── Sección Operaciones ──
        layout.addWidget(_section_label("Operaciones"))

        ops_items = [
            ("📁", "Base de Datos",    HistoricoView),
            ("🔔", "Recordatorios",    RecordatoriosView),   
            ("💰", "Cierre de Caja",   ReportesView),
        ]
        for icon, label, view_class in ops_items:
            self.menu_items.append((icon, label, view_class))
            btn = SidebarButton(icon, label)
            idx_actual = len(self.sidebar_buttons)
            btn.clicked.connect(
                lambda checked, idx=idx_actual: self.on_menu_clicked(idx)
            )
            # Guardar referencia al botón de recordatorios para su badge
            if label == "Recordatorios":
                self._idx_recordatorios = idx_actual
                self._btn_recordatorios = btn
            self.sidebar_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # ── Footer usuario ──
        footer = QFrame()
        footer.setStyleSheet(
            "background: transparent; border-top: 1px solid rgba(255,255,255,0.07);"
        )
        f_row = QHBoxLayout(footer)
        f_row.setContentsMargins(16, 12, 16, 14)
        f_row.setSpacing(10)

        avatar = QLabel("A")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(f"""
            background: {C_ROJO};
            color: #fff;
            border-radius: 16px;
            font-size: 13px;
            font-weight: 700;
        """)
        f_row.addWidget(avatar)

        user_col = QVBoxLayout()
        user_col.setSpacing(1)
        lbl_user = QLabel("Administrador")
        lbl_user.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #fff; background: transparent;"
        )
        lbl_role = QLabel("admin@practicar.co")
        lbl_role.setStyleSheet(
            f"font-size: 10px; color: {C_SIDEBAR_TXT}; background: transparent;"
        )
        user_col.addWidget(lbl_user)
        user_col.addWidget(lbl_role)
        f_row.addLayout(user_col)
        f_row.addStretch()

        btn_logout = QPushButton()
        btn_logout.setFixedSize(32, 32)
        btn_logout.setToolTip("Cerrar sesión")
        btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)

        pix_out = QPixmap(18, 18)
        pix_out.fill(Qt.GlobalColor.transparent)
        pp = QPainter(pix_out)
        pp.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen2 = QPen(QColor("#9CA3AF"))
        pen2.setWidth(2)
        pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pp.setPen(pen2)
        pp.drawLine(7, 1, 1, 1)
        pp.drawLine(1, 1, 1, 17)
        pp.drawLine(1, 17, 7, 17)
        pp.drawLine(6, 9, 17, 9)
        pp.drawLine(13, 5, 17, 9)
        pp.drawLine(13, 13, 17, 9)
        pp.end()

        btn_logout_inner = QHBoxLayout(btn_logout)
        btn_logout_inner.setContentsMargins(0, 0, 0, 0)
        lbl_exit = QLabel()
        lbl_exit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_exit.setStyleSheet("background: transparent;")
        lbl_exit.setPixmap(pix_out)
        btn_logout_inner.addWidget(lbl_exit)

        btn_logout.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.08);
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {C_ROJO};
            }}
        """)
        btn_logout.clicked.connect(self.logout)
        f_row.addWidget(btn_logout)

        layout.addWidget(footer)
        return sidebar

    # ── CONTENT AREA ──────────────────────────────────────────

    def _build_content_area(self) -> QFrame:
        area = QFrame()
        area.setStyleSheet(f"QFrame {{ background: {C_GRIS_FONDO}; }}")
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Topbar ──
        topbar = QFrame()
        topbar.setFixedHeight(56)
        topbar.setStyleSheet(f"""
            QFrame {{
                background: {C_BLANCO};
                border-bottom: 1px solid {C_GRIS_BORDE};
            }}
        """)
        tb_row = QHBoxLayout(topbar)
        tb_row.setContentsMargins(16, 0, 24, 0)
        tb_row.setSpacing(12)

        btn_ham = _ham_button()
        btn_ham.clicked.connect(self.toggle_sidebar)
        tb_row.addWidget(btn_ham)

        sep = QFrame()
        sep.setFixedSize(1, 28)
        sep.setStyleSheet(f"background: {C_GRIS_BORDE};")
        tb_row.addWidget(sep)

        self.lbl_page_title = QLabel("Dashboard")
        self.lbl_page_title.setStyleSheet(
            f"font-size: 18px; font-weight: 800; color: {C_AZUL}; background: transparent;"
        )
        tb_row.addWidget(self.lbl_page_title)
        tb_row.addStretch()

        # Notificaciones campana
        notif_wrap = QFrame()
        notif_wrap.setFixedSize(44, 40)
        notif_wrap.setStyleSheet("background: transparent; border: none;")
        notif_wrap_lay = QHBoxLayout(notif_wrap)
        notif_wrap_lay.setContentsMargins(0, 0, 0, 0)
        notif_wrap_lay.setSpacing(0)

        notif = QFrame()
        notif.setFixedSize(34, 34)
        notif.setStyleSheet(f"""
            QFrame {{
                background: {C_ROJO_LIGHT};
                border-radius: 17px;
            }}
        """)
        notif_layout = QHBoxLayout(notif)
        notif_layout.setContentsMargins(0, 0, 0, 0)
        notif_icon = QLabel("🔔")
        notif_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        notif_icon.setStyleSheet("font-size: 14px; background: transparent;")
        notif_layout.addWidget(notif_icon)
        notif_wrap_lay.addWidget(notif)

        self.notif_badge = QLabel("0")
        self.notif_badge.setFixedSize(16, 16)
        self.notif_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notif_badge.setStyleSheet(f"""
            background: {C_ROJO};
            color: white;
            border-radius: 8px;
            font-size: 9px;
            font-weight: 800;
        """)
        self.notif_badge.setVisible(False)
        self.notif_badge.setParent(notif_wrap)
        self.notif_badge.move(26, 2)
        tb_row.addWidget(notif_wrap)

        # Timer refresco automático badge (cada minuto)
        self._notif_timer = QTimer(self)
        self._notif_timer.timeout.connect(self._refresh_badge)
        self._notif_timer.start(60_000)
        QTimer.singleShot(800, self._refresh_badge)

        # Avatar usuario
        avatar_tb = QLabel("A")
        avatar_tb.setFixedSize(34, 34)
        avatar_tb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_tb.setStyleSheet(f"""
            background: {C_ROJO};
            color: #fff;
            border-radius: 17px;
            font-size: 13px;
            font-weight: 700;
        """)
        tb_row.addWidget(avatar_tb)

        layout.addWidget(topbar)

        # ── Vistas ──
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet(f"background: {C_GRIS_FONDO};")

        self.views = []
        self.vista_alumnos = None
        self.vista_pagos = None
        for _, _, view_class in self.menu_items:
            view = view_class()
            # Guardar referencias a vistas específicas
            if isinstance(view, AlumnosView):
                self.vista_alumnos = view
                view.alumno_registrado.connect(self._refresh_badge)
            if isinstance(view, HistoricoView):
                self.vista_historico = view
            if isinstance(view, PagosView):
                self.vista_pagos = view
            # Conectar señal de RecordatoriosView → actualiza badge
            if isinstance(view, RecordatoriosView):
                view.badge_actualizado.connect(self._on_badge_runt)
            self.views.append(view)
            self.content_stack.addWidget(view)

        # Conectar pago registrado → recargar alumnos
        # Conectar pago registrado → recargar alumnos
        if self.vista_pagos and self.vista_alumnos:
            self.vista_pagos.pago_registrado.connect(self._on_pago_registrado)
            self.vista_pagos.pago_registrado.connect(self.views[0].load_data)
                # Conectar alumno registrado → recargar histórico
        if self.vista_alumnos and hasattr(self, 'vista_historico'):
            self.vista_alumnos.alumno_registrado.connect(self.vista_historico._load)

        layout.addWidget(self.content_stack)

        # ── Footer ──
        self.footer_bar = QFrame()
        self.footer_bar.setFixedHeight(26)
        self.footer_bar.setStyleSheet(f"""
            QFrame {{
                background: {C_BLANCO};
                border-top: 1px solid {C_GRIS_BORDE};
            }}
        """)
        fb_row = QHBoxLayout(self.footer_bar)
        fb_row.setContentsMargins(16, 0, 16, 0)
        fb_row.setSpacing(6)

        self.footer_dot = QLabel("●")
        self.footer_dot.setStyleSheet("font-size: 10px; color: #38a169; background: transparent;")
        self.footer_db_lbl = QLabel("Conectado a cea_p")
        self.footer_db_lbl.setStyleSheet(f"font-size: 11px; color: {C_GRIS_TEXTO}; background: transparent;")
        fb_row.addWidget(self.footer_dot)
        fb_row.addWidget(self.footer_db_lbl)
        fb_row.addStretch()

        from datetime import date as _date
        _hoy = _date.today()
        _M = ["","ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
        lbl_ver = QLabel(f"v1.0.0  ·  {_hoy.day} {_M[_hoy.month]} {_hoy.year}")
        lbl_ver.setStyleSheet(f"font-size: 11px; color: {C_GRIS_TEXTO}; background: transparent;")
        fb_row.addWidget(lbl_ver)

        layout.addWidget(self.footer_bar)

        return area

    # ── BADGE NOTIFICACIONES ──────────────────────────────────────

    def _refresh_badge(self):
        """Consulta pendientes RUNT y actualiza badge campana + sidebar."""
        try:
            total_runt = get_pendientes_runt()
            if hasattr(self, "footer_dot"):
                self.footer_dot.setStyleSheet("font-size: 10px; color: #38a169; background: transparent;")
                self.footer_db_lbl.setText("Conectado a cea_p")
        except Exception:
            total_runt = 0
            if hasattr(self, "footer_dot"):
                self.footer_dot.setStyleSheet("font-size: 10px; color: #e53e3e; background: transparent;")
                self.footer_db_lbl.setText("Sin conexión a BD")

        self._on_badge_runt(total_runt)

    def _on_badge_runt(self, total: int):
        """Actualiza el badge de la campana y el badge del botón Recordatorios en sidebar."""
        # Badge campana topbar
        if hasattr(self, "notif_badge"):
            if total > 0:
                self.notif_badge.setText(str(total) if total < 100 else "99+")
                self.notif_badge.setVisible(True)
            else:
                self.notif_badge.setVisible(False)

        # Badge en botón sidebar
        if hasattr(self, "_btn_recordatorios"):
            self._btn_recordatorios.set_badge(total)

    def _notificar_runt_al_inicio(self):
        """Al abrir la app, si hay pendientes RUNT muestra un aviso en la campana."""
        total = get_pendientes_runt()
        self._on_badge_runt(total)
        # Si hay pendientes, parpadear la campana brevemente para llamar la atención
        if total > 0 and hasattr(self, "notif_badge"):
            self._parpadeo_count = 0
            self._parpadeo_timer = QTimer(self)
            self._parpadeo_timer.timeout.connect(self._parpadear_badge)
            self._parpadeo_timer.start(350)

    def _mostrar_toast_runt(self):
        """Muestra toast flotante si hay alumnos críticos de RUNT."""
        # Encontrar la vista de recordatorios
        for view in self.views:
            if isinstance(view, RecordatoriosView):
                # Conectar señal para navegar a recordatorios
                view.mostrar_recordatorios.connect(self._ir_a_recordatorios)
                view.verificar_y_notificar(parent_window=self)
                break

    def _ir_a_recordatorios(self):
        """Navega a la vista de Recordatorios cuando se clickea el toast."""
        if hasattr(self, '_idx_recordatorios') and self._idx_recordatorios is not None:
            self.on_menu_clicked(self._idx_recordatorios)

    def _parpadear_badge(self):
        """Hace parpadear el badge de la campana 6 veces al iniciar."""
        if not hasattr(self, "_parpadeo_count"):
            return
        self._parpadeo_count += 1
        visible = (self._parpadeo_count % 2 == 0)
        if hasattr(self, "notif_badge"):
            self.notif_badge.setVisible(visible)
        if self._parpadeo_count >= 12:
            self._parpadeo_timer.stop()
            if hasattr(self, "notif_badge"):
                total = get_pendientes_runt()
                self.notif_badge.setVisible(total > 0)
