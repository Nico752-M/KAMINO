#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard Principal - CEA PRACTICAR
Datos reales desde MySQL + estética mejorada completa.
"""

from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QScrollArea, QPushButton, QProgressBar,
    QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database import Database

# ─── Paleta ────────────────────────────────────────────────────────────────────
PAL = {
    "bg":        "#F4F3EF",
    "surface":   "#FDFCF9",
    "border":    "#DDD9D0",
    "border_lt": "#EAE7E0",
    "text_1":    "#1A1916",
    "text_2":    "#5A5650",
    "text_3":    "#9A9690",
    "blue":      "#0033A0",
    "blue_dk":   "#002880",
    "blue_bg":   "#EAF1FB",
    "teal":      "#0D6E55",
    "teal_bg":   "#E0F4EE",
    "amber":     "#8A5210",
    "amber_bg":  "#FAF0DC",
    "coral":     "#E31937",
    "coral_bg":  "#FAECE6",
    "green":     "#1D9E75",
}

MESES = ["", "Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

DIAS = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]

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

def _shadow(w, blur=16, dy=4, alpha=20):
    s = QGraphicsDropShadowEffect()
    s.setBlurRadius(blur)
    s.setOffset(0, dy)
    s.setColor(QColor(26, 25, 22, alpha))
    w.setGraphicsEffect(s)


def _card(radius=14):
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame {{
            background: {PAL['surface']};
            border-radius: {radius}px;
            border: 1px solid {PAL['border_lt']};
        }}
    """)
    _shadow(f)
    return f


def _initials(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if name else "??"


AVATAR_COLORS = [
    ("#EAF1FB", "#0033A0"), ("#E0F4EE", "#0D6E55"),
    ("#FAF0DC", "#8A5210"), ("#FAECE6", "#E31937"),
    ("#F3E5F5", "#7B1FA2"), ("#E8F5E9", "#388E3C"),
]


def _avatar_label(name: str, size=36, idx=0) -> QLabel:
    bg, fg = AVATAR_COLORS[idx % len(AVATAR_COLORS)]
    lbl = QLabel(_initials(name))
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(f"""
        background: {bg}; color: {fg};
        border-radius: {size//2}px;
        font-size: {size//2 - 2}px; font-weight: 700;
    """)
    return lbl


# ══════════════════════════════════════════════════════════════════════════════
#  STAT CARD — con animación de número
# ══════════════════════════════════════════════════════════════════════════════

class StatCard(QFrame):
    def __init__(self, icon, title, color, parent=None):
        super().__init__(parent)
        self.color = color
        self._target = 0
        self._current = 0
        self.setFixedHeight(118)
        self.setStyleSheet(f"""
            StatCard {{
                background: {PAL['surface']};
                border-radius: 14px;
                border: 1px solid {PAL['border_lt']};
            }}
            StatCard:hover {{
                border: 1.5px solid {color};
            }}
        """)
        _shadow(self)

        row = QHBoxLayout(self)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(14)

        # Ícono
        ic = QFrame()
        ic.setFixedSize(46, 46)
        ic.setStyleSheet(f"""
            QFrame {{
                background: {color}18;
                border-radius: 12px;
                border: none;
            }}
        """)
        il = QVBoxLayout(ic)
        il.setContentsMargins(0, 0, 0, 0)
        lbl_ic = QLabel(icon)
        lbl_ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_ic.setStyleSheet("font-size: 20px; background: transparent;")
        il.addWidget(lbl_ic)
        row.addWidget(ic)

        # Texto
        col = QVBoxLayout()
        col.setSpacing(3)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet(f"font-size: 11px; color: {PAL['text_2']}; font-weight: 500;")
        col.addWidget(self.lbl_title)

        self.lbl_value = QLabel("—")
        self.lbl_value.setStyleSheet(f"font-size: 26px; font-weight: 700; color: {PAL['text_1']};")
        col.addWidget(self.lbl_value)

        self.lbl_sub = QLabel("")
        self.lbl_sub.setStyleSheet(f"font-size: 11px; color: {PAL['green']};")
        col.addWidget(self.lbl_sub)

        row.addLayout(col, 1)

    def set_data(self, value_str: str, subtitle: str = ""):
        self.lbl_value.setText(value_str)
        self.lbl_sub.setText(subtitle)


# ══════════════════════════════════════════════════════════════════════════════
#  BARRA DE CATEGORÍAS — dibujada con QPainter
# ══════════════════════════════════════════════════════════════════════════════

class CatBarChart(QWidget):
    """Gráfico de barras horizontal para distribución por categoría."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = []   # [(label, count, color)]
        self.setMinimumHeight(140)

    def set_data(self, data):
        self.data = data
        self.update()

    def paintEvent(self, event):
        if not self.data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        total = sum(d[1] for d in self.data) or 1
        w = self.width() - 24
        bar_h = 18
        gap = 22
        y = 12

        for label, count, color in self.data:
            pct = count / total
            bar_w = int(w * pct)

            # Fondo barra
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(PAL['border_lt'])))
            p.drawRoundedRect(12, y, w, bar_h, 6, 6)

            # Barra rellena
            if bar_w > 0:
                p.setBrush(QBrush(QColor(color)))
                p.drawRoundedRect(12, y, bar_w, bar_h, 6, 6)

            # Etiqueta izquierda
            p.setPen(QPen(QColor(PAL['text_2'])))
            font = p.font()
            font.setPointSize(9)
            font.setBold(False)
            p.setFont(font)
            p.drawText(12, y - 3, f"{label}")

            # Porcentaje derecha
            font.setBold(True)
            p.setFont(font)
            p.setPen(QPen(QColor(PAL['text_1'])))
            pct_str = f"{pct*100:.0f}%  ({count})"
            p.drawText(12 + bar_w + 6, y + bar_h - 3, pct_str)

            y += bar_h + gap

        p.end()


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD VIEW
# ══════════════════════════════════════════════════════════════════════════════

class DashboardView(QWidget):

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background: {PAL['bg']};")
        self._build_ui()
        # Cargar datos reales al iniciar
        QTimer.singleShot(100, self.load_data)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 26, 26, 26)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(22)

        # ── Header ──
        hdr = QHBoxLayout()
        hoy = datetime.now()
        dia_semana = DIAS[hoy.weekday()]
        lbl_title = QLabel("Dashboard")
        lbl_title.setStyleSheet(f"font-size: 26px; font-weight: 700; color: {PAL['text_1']};")
        hdr.addWidget(lbl_title)
        hdr.addStretch()
        lbl_fecha = QLabel(f"{dia_semana.capitalize()}, {hoy.day} de {MESES[hoy.month]} de {hoy.year}")
        lbl_fecha.setStyleSheet(f"font-size: 13px; color: {PAL['text_2']};")
        hdr.addWidget(lbl_fecha)


        bl.addLayout(hdr)

        # ── Stat Cards ──
        stats_grid = QGridLayout()
        stats_grid.setSpacing(14)

        self.card_alumnos   = StatCard("👨‍🎓", "Alumnos Activos",    PAL['blue'])
        self.card_ingresos  = StatCard("💰",   "Ingresos del Mes",   PAL['amber'])

        for i, c in enumerate([self.card_alumnos, self.card_ingresos]):
            stats_grid.addWidget(c, 0, i)

        bl.addLayout(stats_grid)

        # ── Cuerpo 2 columnas ──
        body_row = QHBoxLayout()
        body_row.setSpacing(18)

        # Columna izquierda
        left = QVBoxLayout()
        left.setSpacing(18)

        # Panel alumnos recientes
        card_rec = _card()
        rl = QVBoxLayout(card_rec)
        rl.setContentsMargins(20, 18, 20, 18)
        rl.setSpacing(14)

        rec_hdr = QHBoxLayout()
        lbl_rec = QLabel("Alumnos Recientes")
        lbl_rec.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {PAL['text_1']};")
        rec_hdr.addWidget(lbl_rec)
        rec_hdr.addStretch()
        self.lbl_rec_count = QLabel("")
        self.lbl_rec_count.setStyleSheet(f"font-size: 11px; color: {PAL['text_3']};")
        rec_hdr.addWidget(self.lbl_rec_count)
        rl.addLayout(rec_hdr)

        self.alumnos_container = QVBoxLayout()
        self.alumnos_container.setSpacing(10)
        rl.addLayout(self.alumnos_container)
        left.addWidget(card_rec)

        # Panel gráfico categorías
        card_cat = _card()
        cl = QVBoxLayout(card_cat)
        cl.setContentsMargins(20, 18, 20, 18)
        cl.setSpacing(12)
        lbl_cat = QLabel("Distribución por Categoría")
        lbl_cat.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {PAL['text_1']};")
        cl.addWidget(lbl_cat)
        self.cat_chart = CatBarChart()
        cl.addWidget(self.cat_chart)
        self.lbl_cat_empty = QLabel("Sin datos suficientes")
        self.lbl_cat_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cat_empty.setStyleSheet(f"font-size: 13px; color: {PAL['text_3']}; padding: 20px;")
        cl.addWidget(self.lbl_cat_empty)
        left.addWidget(card_cat)

        body_row.addLayout(left, 3)

        # Columna derecha
        right = QVBoxLayout()
        right.setSpacing(18)

    

        # Pagos pendientes
        card_pend = _card()
        pl = QVBoxLayout(card_pend)
        pl.setContentsMargins(20, 18, 20, 18)
        pl.setSpacing(12)
        pend_hdr = QHBoxLayout()
        lbl_pend = QLabel("Pagos Pendientes")
        lbl_pend.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {PAL['text_1']};")
        pend_hdr.addWidget(lbl_pend)
        pend_hdr.addStretch()
        self.lbl_pend_total = QLabel("")
        self.lbl_pend_total.setStyleSheet(f"font-size: 11px; color: {PAL['coral']}; font-weight: 600;")
        pend_hdr.addWidget(self.lbl_pend_total)
        pl.addLayout(pend_hdr)
        self.pend_container = QVBoxLayout()
        self.pend_container.setSpacing(0)
        pl.addLayout(self.pend_container)
        right.addWidget(card_pend)

        # Acciones rápidas
        card_acc = _card()
        al = QVBoxLayout(card_acc)
        al.setContentsMargins(20, 18, 20, 18)
        al.setSpacing(12)
        lbl_acc = QLabel("Acciones Rápidas")
        lbl_acc.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {PAL['text_1']};")
        al.addWidget(lbl_acc)
        acc_grid = QGridLayout()
        acc_grid.setSpacing(8)
        acciones = [
            ("👨‍🎓  Nuevo Alumno",    PAL['blue_bg'],  PAL['blue']),
            ("💳  Registrar Pago",   PAL['amber_bg'], PAL['amber']),
            ("📅  Registrar Clase",  PAL['teal_bg'],  PAL['teal']),
            ("📊  Ver Reportes",     PAL['coral_bg'], PAL['coral']),
        ]
        acc_indices = [1, 2, 5, 6]
        for i, (txt, bg, fg) in enumerate(acciones):
            b = QPushButton(txt)
            b.setFixedHeight(44)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {bg}; color: {fg};
                    border: 1.5px solid transparent; border-radius: 10px;
                    font-size: 12px; font-weight: 600;
                    text-align: left; padding-left: 14px;
                }}
                QPushButton:hover {{ border-color: {fg}; }}
                QPushButton:pressed {{ padding-top: 1px; }}
            """)
            target_idx = acc_indices[i]
            b.clicked.connect(lambda _, idx=target_idx: self._navigate(idx))
            acc_grid.addWidget(b, i // 2, i % 2)
        al.addLayout(acc_grid)
        right.addWidget(card_acc)

        body_row.addLayout(right, 2)
        bl.addLayout(body_row)
        bl.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, 1)


    # ── Carga de datos reales ──────────────────────────────────────────────────

    def load_data(self):
        """Consulta MySQL y actualiza todos los paneles."""
        try:
            db = Database.get_instance()
        except Exception as e:
            print(f"[Dashboard] Sin conexión: {e}")
            self.card_alumnos.set_data("—", "Sin conexión")
            self.card_ingresos.set_data("—", "")
            return
        try:
            self._load_stats(db)
        except Exception as e:
            print(f"[Dashboard] Error stats: {e}")
        try:
            self._load_alumnos_recientes(db)
        except Exception as e:
            print(f"[Dashboard] Error alumnos: {e}")
        try:
            self._load_categorias(db)
        except Exception as e:
            print(f"[Dashboard] Error categorias: {e}")
        try:
            self._load_pagos_pendientes(db)
        except Exception as e:
            print(f"[Dashboard] Error pagos pendientes: {e}")

    def _load_stats(self, db):
        hoy = datetime.now()

        # Alumnos activos
        r = db.fetchone("""
            SELECT COUNT(*) AS total FROM matriculas
            WHERE estado NOT IN ('Cancelado', 'Histórico')
        """)
        activos = r['total'] if r else 0

        # Mes anterior para comparar
        r2 = db.fetchone("""
            SELECT COUNT(*) AS total FROM matriculas
            WHERE estado NOT IN ('Cancelado', 'Histórico')
            AND MONTH(fecha_registro) = MONTH(CURDATE() - INTERVAL 1 MONTH)
            AND YEAR(fecha_registro)  = YEAR(CURDATE() - INTERVAL 1 MONTH)
        """)
        ant = r2['total'] if r2 else 0
        diff_txt = ""
        if ant > 0:
            diff = ((activos - ant) / ant) * 100
            diff_txt = f"{'↑' if diff >= 0 else '↓'} {abs(diff):.0f}% vs mes anterior"
        self.card_alumnos.set_data(str(activos), diff_txt)

        # Ingresos del mes
        r4 = db.fetchone("""
            SELECT COALESCE(SUM(valor), 0) AS total FROM pagos
            WHERE MONTH(fecha_pago) = MONTH(CURDATE())
              AND YEAR(fecha_pago)  = YEAR(CURDATE())
        """)
        ing = float(r4['total']) if r4 else 0
        ing_fmt = f"${ing:,.0f}".replace(",", ".")
        self.card_ingresos.set_data(ing_fmt, f"{MESES[hoy.month]} {hoy.year}")

    def _load_alumnos_recientes(self, db):
        # Limpiar
        while self.alumnos_container.count():
            item = self.alumnos_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rows = db.fetchall("""
            SELECT a.nombres, a.apellidos, a.numero_documento,
                m.categoria, m.estado,
                COALESCE(m.precio_total, 0) AS precio_total,
                COALESCE((SELECT SUM(valor) FROM pagos WHERE id_matricula = m.id), 0) AS total_pagado
            FROM matriculas m
            JOIN alumnos a ON a.numero_documento = m.numero_documento
            ORDER BY m.fecha_registro DESC
            LIMIT 6
        """)
        self.lbl_rec_count.setText(f"{len(rows)} más recientes")

        for idx, r in enumerate(rows):
            nombre = f"{r['nombres']} {r['apellidos']}"
            doc    = r['numero_documento']
            cat    = r['categoria'] or ""
            estado = r['estado'] or "Activo"
            precio_total  = int(r['precio_total'] or 0)
            total_pagado  = int(r['total_pagado'] or 0)
            progreso = min(int((total_pagado / precio_total) * 100), 100) if precio_total > 0 else 0

            # Card del alumno
            item = QFrame()
            item.setStyleSheet(f"""
                QFrame {{
                    background: {PAL['bg']};
                    border-radius: 10px;
                    border: 1px solid {PAL['border_lt']};
                }}
                QFrame:hover {{
                    background: {PAL['surface']};
                    border-color: {PAL['border']};
                }}
            """)
            il = QVBoxLayout(item)
            il.setContentsMargins(14, 11, 14, 11)
            il.setSpacing(8)

            # Fila superior
            top = QHBoxLayout()
            top.setSpacing(10)
            top.addWidget(_avatar_label(nombre, size=34, idx=idx))

            name_col = QVBoxLayout()
            name_col.setSpacing(1)
            lbl_n = QLabel(nombre)
            lbl_n.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {PAL['text_1']};")
            name_col.addWidget(lbl_n)
            lbl_d = QLabel(f"CC: {doc}")
            lbl_d.setStyleSheet(f"font-size: 11px; color: {PAL['text_3']};")
            name_col.addWidget(lbl_d)
            top.addLayout(name_col, 1)

            # Badge categoría
            cat_bg, cat_fg = {
                "A": (PAL['teal_bg'],  PAL['teal']),
                "B": (PAL['blue_bg'],  PAL['blue']),
                "C": (PAL['amber_bg'], PAL['amber']),
            }.get(cat[0] if cat else "B", (PAL['bg'], PAL['text_2']))
            lbl_cat = QLabel(cat)
            lbl_cat.setStyleSheet(f"""
                background: {cat_bg}; color: {cat_fg};
                padding: 3px 10px; border-radius: 9px;
                font-size: 11px; font-weight: 600;
            """)
            top.addWidget(lbl_cat)
            il.addLayout(top)

            # Barra de progreso animada
            prog_row = QHBoxLayout()
            prog_row.setSpacing(8)
            bar = QProgressBar()
            bar.setValue(0)           # arranca en 0
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setStyleSheet(f"""
                QProgressBar {{ background: {PAL['border_lt']}; border-radius: 3px; border: none; }}
                QProgressBar::chunk {{ background: {PAL['blue']}; border-radius: 3px; }}
            """)
            prog_row.addWidget(bar, 1)
            lbl_pct = QLabel(f"{progreso}%")
            lbl_pct.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {PAL['blue']};")
            prog_row.addWidget(lbl_pct)
            il.addLayout(prog_row)

            # Animación: de 0 → valor real en 600 ms
            anim = QPropertyAnimation(bar, b"value")
            anim.setDuration(600)
            anim.setStartValue(0)
            anim.setEndValue(progreso)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start()
            # Guardar referencia para que el GC no la destruya
            if not hasattr(self, "_prog_anims"):
                self._prog_anims = []
            self._prog_anims.append(anim)

            # Badge estado
            est_map = {
                "Activo":         (PAL['teal_bg'],  PAL['teal'],  "Activo"),
                "Completado":     (PAL['blue_bg'],  PAL['blue'],  "Completado"),
                "Pendiente Pago": (PAL['amber_bg'], PAL['amber'], "Pendiente Pago"),
                "Cancelado":      (PAL['coral_bg'], PAL['coral'], "Cancelado"),
            }
            eb, ef, et = est_map.get(estado, (PAL['bg'], PAL['text_2'], estado))
            lbl_est = QLabel(et)
            lbl_est.setStyleSheet(f"""
                background: {eb}; color: {ef};
                padding: 3px 12px; border-radius: 9px;
                font-size: 11px; font-weight: 500;
            """)
            il.addWidget(lbl_est)
            self.alumnos_container.addWidget(item)

        if not rows:
            lbl_empty = QLabel("No hay alumnos registrados aún")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_empty.setStyleSheet(f"font-size: 13px; color: {PAL['text_3']}; padding: 20px;")
            self.alumnos_container.addWidget(lbl_empty)

    def _load_categorias(self, db):
        rows = db.fetchall("""
            SELECT categoria, COUNT(*) AS total
            FROM matriculas
            WHERE estado != 'Cancelado'
            GROUP BY categoria
            ORDER BY total DESC
        """)
        COLORES_CAT = [PAL['blue'], PAL['teal'], PAL['amber'], PAL['coral'], "#7B1FA2", "#388E3C"]
        data = [(r['categoria'], int(r['total']), COLORES_CAT[i % len(COLORES_CAT)])
                for i, r in enumerate(rows)]

        if data:
            self.lbl_cat_empty.hide()
            self.cat_chart.set_data(data)
            # Ajustar altura según cantidad de categorías
            self.cat_chart.setMinimumHeight(max(120, len(data) * 42))
        else:
            self.lbl_cat_empty.show()
            self.cat_chart.set_data([])


    def _load_pagos_pendientes(self, db):
        while self.pend_container.count():
            item = self.pend_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Alumnos con estado Pendiente Pago y lo que deben
        rows = db.fetchall("""
            SELECT
                CONCAT(a.nombres, ' ', a.apellidos) AS alumno,
                COALESCE(m.precio_total, 0) AS precio_total,
                COALESCE(SUM(p.valor), 0) AS pagado
            FROM matriculas m
            JOIN alumnos a ON a.numero_documento = m.numero_documento
            LEFT JOIN pagos p ON p.id_matricula = m.id
            WHERE m.estado NOT IN ('Cancelado', 'Histórico')
            GROUP BY m.id
            HAVING COALESCE(precio_total, 0) > COALESCE(SUM(p.valor), 0)
            ORDER BY (precio_total - COALESCE(SUM(p.valor), 0)) DESC
            LIMIT 5
        """)

        total_pend = sum(float(r['precio_total']) - float(r['pagado']) for r in rows)
        if total_pend > 0:
            self.lbl_pend_total.setText(f"${total_pend:,.0f}".replace(",", "."))
        else:
            self.lbl_pend_total.setText("")

        for idx, r in enumerate(rows):
            item = QFrame()
            # Línea separadora entre items
            border_b = f"border-bottom: 1px solid {PAL['border_lt']};" if idx < len(rows) - 1 else ""
            item.setStyleSheet(f"QFrame {{ background: transparent; {border_b} }}")
            row = QHBoxLayout(item)
            row.setContentsMargins(4, 10, 4, 10)
            row.setSpacing(10)

            row.addWidget(_avatar_label(r['alumno'], size=30, idx=idx))

            lbl_n = QLabel(r['alumno'])
            lbl_n.setStyleSheet(f"font-size: 12px; color: {PAL['text_1']}; font-weight: 500;")
            row.addWidget(lbl_n, 1)

            deuda = float(r['precio_total']) - float(r['pagado'])
            lbl_v = QLabel(f"${deuda:,.0f}".replace(",", "."))
            lbl_v.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {PAL['coral']};")
            row.addWidget(lbl_v)
            self.pend_container.addWidget(item)

        if not rows:
            lbl_ok = QLabel("✅  Sin pagos pendientes")
            lbl_ok.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_ok.setStyleSheet(f"font-size: 12px; color: {PAL['teal']}; padding: 14px;")
            self.pend_container.addWidget(lbl_ok)

    def _navigate(self, idx: int):
        from PyQt6.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if hasattr(w, 'on_menu_clicked'):
                w.on_menu_clicked(idx)
                break