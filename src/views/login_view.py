#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pantalla de Login - CEA PRACTICAR
Estética: fondo azul #1A2B6B, card blanca con borde rojo arriba,
círculos decorativos, Bebas Neue + Nunito.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap

# ── Paleta ───────────────────────────────────────────────────────
C_ROJO      = "#C8252A"
C_ROJO_DARK = "#9E1C20"
C_AZUL      = "#1A2B6B"
C_AZUL_MID  = "#263894"
C_GRIS_FONDO= "#F3F4F8"
C_GRIS_BORDE= "#E0E3EE"
C_GRIS_TEXT = "#6B7080"
C_BLANCO    = "#FFFFFF"

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
    
class LoginBackground(QWidget):
    """Widget de fondo azul con círculos decorativos pintados."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fondo azul sólido
        painter.fillRect(self.rect(), QColor(C_AZUL))

        # Círculos decorativos (igual que el HTML)
        pen = QPen()
        pen.setWidth(2)

        # Círculo grande — arriba derecha, rojo translúcido
        c = QColor(C_ROJO)
        c.setAlpha(38)   # ~0.15 opacity
        pen.setColor(c)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(self.width() - 400, -200, 600, 600)

        # Círculo medio — abajo izquierda, blanco muy transparente
        c2 = QColor("#FFFFFF")
        c2.setAlpha(15)
        pen.setColor(c2)
        painter.setPen(pen)
        painter.drawEllipse(-100, self.height() - 250, 400, 400)

        # Círculo pequeño — centro izquierda, rojo más transparente
        c3 = QColor(C_ROJO)
        c3.setAlpha(25)
        pen.setColor(c3)
        painter.setPen(pen)
        painter.drawEllipse(int(self.width() * 0.08),
                            int(self.height() * 0.4),
                            200, 200)
        painter.end()


class LoginView(QWidget):
    login_successful = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        # Fondo con círculos
        self.bg = LoginBackground(self)
        self.bg.setGeometry(self.rect())

        # Layout centrado sobre el fondo
        main = QVBoxLayout(self)
        main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main.setContentsMargins(0, 0, 0, 0)

        card = self._build_card()
        main.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)

    def _build_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(380)
        card.setStyleSheet(f"""
            QFrame#loginCard {{
                background-color: {C_BLANCO};
                border-radius: 20px;
                border-top: 5px solid {C_ROJO};
            }}
            QFrame#loginCard QFrame {{
                border: none;
            }}
            QFrame#loginCard QLabel {{
                border: none;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(40, 40, 40, 32)
        layout.setSpacing(0)

        # ── Logo ──
        logo_wrap = QHBoxLayout()
        logo_wrap.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_box = QFrame()
        logo_box.setObjectName("logoBox")
        logo_box.setFixedSize(72, 72)
        logo_box.setStyleSheet(f"""
            QFrame#logoBox {{
                background: {C_AZUL};
                border-radius: 16px;
                border: 3px solid {C_ROJO};
            }}
        """)
        logo_inner = QVBoxLayout(logo_box)
        logo_inner.setContentsMargins(0, 0, 0, 0)

        import os as _os
        _logo_path = _os.path.normpath(_os.path.join(
            _os.path.dirname(_os.path.abspath(__file__)),
            "..", "assets", "logo_practicar.png"
        ))

        if _os.path.exists(_logo_path):
            logo_icon = QLabel()
            logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _pix = QPixmap(_logo_path).scaled(
                56, 56,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            logo_icon.setPixmap(_pix)
            logo_icon.setStyleSheet("background: transparent;")
        else:
            logo_icon = QLabel("P")
            logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_icon.setStyleSheet("font-size: 30px; font-weight: 800; color: #FFFFFF; background: transparent;")

        logo_inner.addWidget(logo_icon)
        logo_wrap.addWidget(logo_box)
        layout.addLayout(logo_wrap)

        layout.addSpacing(12)

        # ── Nombre ──
        lbl_name = QLabel("PRACTI<span style='color:#C8252A;'>CAR</span>")
        lbl_name.setTextFormat(Qt.TextFormat.RichText)
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_name.setStyleSheet(f"""
            font-family: 'Bebas Neue', 'Nunito', sans-serif;
            font-size: 32px;
            letter-spacing: 0.06em;
            color: {C_AZUL};
            background: transparent;
        """)
        layout.addWidget(lbl_name)

        lbl_sub = QLabel("Centro de Enseñanza Automovilística")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setStyleSheet(f"""
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.10em;
            color: {C_GRIS_TEXT};
            background: transparent;
        """)
        layout.addWidget(lbl_sub)

        layout.addSpacing(24)

        # ── Campos ──
        lbl_user = QLabel("USUARIO")
        lbl_user.setStyleSheet(self._label_style())
        layout.addWidget(lbl_user)

        self.user_input = QLineEdit()
        self.user_input.setObjectName("loginInput")
        self.user_input.setPlaceholderText("Ingresa tu usuario")
        self.user_input.setFixedHeight(44)
        self.user_input.setStyleSheet(self._input_style())
        layout.addWidget(self.user_input)

        layout.addSpacing(12)

        lbl_pass = QLabel("CONTRASEÑA")
        lbl_pass.setStyleSheet(self._label_style())
        layout.addWidget(lbl_pass)

        self.pass_input = QLineEdit()
        self.pass_input.setObjectName("loginInput")
        self.pass_input.setPlaceholderText("••••••••")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_input.setFixedHeight(44)
        self.pass_input.setStyleSheet(self._input_style())
        layout.addWidget(self.pass_input)

        layout.addSpacing(20)

        # ── Botón ──
        self.btn_login = QPushButton("INGRESAR AL SISTEMA")
        self.btn_login.setFixedHeight(48)
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_ROJO};
                color: white;
                border: none;
                border-radius: 10px;
                font-family: 'Bebas Neue', 'Nunito', sans-serif;
                font-size: 18px;
                letter-spacing: 0.1em;
            }}
            QPushButton:hover   {{ background-color: {C_ROJO_DARK}; }}
            QPushButton:pressed {{ background-color: #7a1418; }}
        """)
        self.btn_login.clicked.connect(self._attempt_login)
        layout.addWidget(self.btn_login)

        layout.addSpacing(16)

        # ── Footer ──
        footer = QLabel("v2.0.0  ·  Sistema de Gestión Practicar")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(f"font-size: 11px; color: {C_GRIS_TEXT}; background: transparent;")
        layout.addWidget(footer)

        return card

    def _label_style(self) -> str:
        return f"""
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.05em;
            color: {C_AZUL};
            background: transparent;
            margin-bottom: 4px;
        """

    def _input_style(self) -> str:
        return f"""
            QLineEdit#loginInput {{
                border: 1.5px solid {C_GRIS_BORDE};
                border-radius: 10px;
                padding: 10px 14px;
                background: {C_GRIS_FONDO};
                font-size: 14px;
                color: {C_AZUL};
            }}
            QLineEdit#loginInput:focus {{
                border: 1.5px solid {C_GRIS_BORDE};
                background: {C_BLANCO};
                outline: none;
            }}
        """

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.bg.setGeometry(self.rect())

    def _attempt_login(self):
        user = self.user_input.text().strip()
        pwd  = self.pass_input.text().strip()
        if user == "admin" and pwd == "admin123":
            self.login_successful.emit()
        else:
            QMessageBox.warning(
                self, "Acceso denegado",
                "Usuario o contraseña incorrectos.\n\nDemo:\nUsuario: admin\nContraseña: admin123"
            )

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._attempt_login()
        else:
            super().keyPressEvent(event)