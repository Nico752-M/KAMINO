```markdown
```markdown
# 🚗 Sistema CEA PRACTICAR
Sistema de gestión de escritorio para Centros de Enseñanza Automovilística (CEA).
## 📋 Descripción
Aplicación de escritorio desarrollada en Python + PyQt6 para automatizar la gestión de escuelas de conducción en Colombia. Reemplaza el registro manual en cuadernos y carpetas físicas por un sistema digital completo.
## 🏗️ Arquitectura
```
CEA_Practicar_System/
├── main.py                    # Punto de entrada
├── requirements.txt           # Dependencias
├── database/
│   ├── schema.sql             # Schema completo de la BD
│   └── cea_practicar.db       # Base de datos SQLite (auto-generada)
├── src/
│   ├── models/
│   │   └── database.py        # Gestor de base de datos (CRUD completo)
│   ├── views/
│   │   ├── main_window.py     # Ventana principal con sidebar
│   │   ├── dashboard_view.py  # Dashboard con estadísticas
│   │   ├── alumnos_view.py    # Gestión de alumnos
│   │   ├── pagos_view.py      # Control de pagos
│   │   ├── clases_view.py     # Registro de clases
│   │   ├── evaluaciones_view.py # Evaluaciones teóricas/prácticas
│   │   ├── documentos_view.py # Documentos y trámites
│   │   ├── reportes_view.py   # Reportes y estadísticas
│   │   └── historico_view.py  # Archivo histórico
│   ├── controllers/           # Controladores (futuro)
│   └── utils/                 # Utilidades (OCR, PDF, etc.)
├── exports/                   # PDFs generados por el sistema
└── temp/                      # Archivos temporales
```
## 🚀 Instalación
1. Clonar o descargar el proyecto
2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Ejecutar:
   ```bash
   python main.py
   ```
## 🎯 Módulos Implementados
| Módulo | Estado | Descripción |
|--------|--------|-------------|
| Dashboard | ✅ Funcional | Estadísticas en tiempo real, alumnos recientes, clases del día |
| Alumnos | ✅ Funcional | Registro con formulario completo, búsqueda, tabla con acciones |
| Pagos | 🚧 Placeholder | Recibos, cuotas, estados de cuenta |
| Clases | 🚧 Placeholder | Asistencia, firmas, control de horas |
| Evaluaciones | 🚧 Placeholder | FOR 06 (teórica) y FOR 04 (práctica) |
| Documentos | 🚧 Placeholder | Autorización, contrato, firmas digitales |
| Reportes | 🚧 Placeholder | Estadísticas, exportación PDF |
| Histórico | 🚧 Placeholder | PDFs escaneados, búsqueda unificada |
## 📝 Credenciales por Defecto
- **Usuario:** admin
- **Contraseña:** admin123
## 🔧 Stack Tecnológico
- **Frontend:** PyQt6 (Python)
- **Base de Datos:** SQLite3 (archivo local)
- **OCR:** Tesseract + OpenCV
- **PDFs:** ReportLab + PyPDF2
- **Estilo:** CSS-like con QSS (Qt Style Sheets)
