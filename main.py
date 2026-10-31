#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Gestión CEA PRACTICAR
Flujo: Login → Menú Principal → App con Sidebar
"""

import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from PyQt6.QtWidgets import QApplication
from database import Database

db = Database.get_instance()

print("Iniciando Sistema CEA PRACTICAR...")
print("Directorio base: " + BASE_DIR)

try:
    from views.main_window import MainWindow
    from practicar_style import setup_app_style
    
    print("MainWindow y estilo importados")
except Exception as e:
    print("Error en imports: " + str(e))
    import traceback
    traceback.print_exc()
    input("Presiona Enter para salir...")
    sys.exit(1)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CEA PRACTICAR")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("CEAPracticar")
    from PyQt6.QtWidgets import QStyleFactory  
    app.setStyle(QStyleFactory.create("Fusion"))
    print("QApplication creada")

    setup_app_style(app)
    print("Estilo PRACTICAR aplicado")

    print("Creando ventana principal...")
    window = MainWindow()
    print("Ventana principal creada")

    window.show()
    print("Ventana mostrada")
    print("Sistema listo!")

    result = app.exec()
    print("Aplicacion cerrada con codigo: " + str(result))
    sys.exit(result)


if __name__ == "__main__":
    main()

