#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vista de Documentos y Trámites
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

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
    
class DocumentosView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel("📄 Documentos y Trámites")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: #2d3748;")
        layout.addWidget(title)

        subtitle = QLabel("Autorización de datos, contratos y firmas digitales")
        subtitle.setStyleSheet("font-size: 14px; color: #718096; margin-bottom: 20px;")
        layout.addWidget(subtitle)

        placeholder = QLabel("🚧 Módulo en desarrollo\n\nAquí irá:\n• Generación de autorización de datos (GSE)\n• Contrato del alumno (FOR 35)\n• Firma digital en pantalla\n• Exportación a PDF")
        placeholder.setStyleSheet("font-size: 16px; color: #a0aec0; padding: 50px;")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(placeholder)
        layout.addStretch()
