from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSpinBox, 
    QFrame, QPushButton, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal

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
    # (valor, etiqueta, color_indicador, tipo)
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

def _separador():
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"color: {C_GRIS_BORDE}; background: {C_GRIS_BORDE}; max-height:1px;")
    return sep

def _lbl_seccion(texto: str) -> QLabel:
    lbl = QLabel(texto.upper())
    lbl.setStyleSheet(f"""
        font-size: 9px; font-weight: 700;
        letter-spacing: 0.12em; color: {C_GRIS_MED}; padding-bottom: 2px;
    """)
    return lbl

class CalculadoraBilletes(QWidget):
    total_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._spinners: list[tuple[int, QSpinBox, QLabel]] = []
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: transparent;")
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(16)

        # ── Panel Billetes (izquierda) ──
        panel_billetes = QFrame()
        panel_billetes.setStyleSheet(f"""
            QFrame {{
                background: {C_BLANCO};
                border: 1px solid {C_GRIS_BORDE};
                border-radius: 12px;
            }}
        """)
        lay_b = QVBoxLayout(panel_billetes)
        lay_b.setContentsMargins(14, 14, 14, 14)
        lay_b.setSpacing(10)

        lbl_b = QLabel("💵  BILLETES")
        lbl_b.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {C_NEGRO}; font-family: 'Inter', 'Segoe UI', sans-serif;")
        lay_b.addWidget(lbl_b)

        grid_b = QGridLayout()
        grid_b.setSpacing(8)
        grid_b.setColumnStretch(0, 1)
        grid_b.setColumnStretch(1, 1)

        # ── Panel Monedas (derecha) ──
        panel_monedas = QFrame()
        panel_monedas.setStyleSheet(f"""
            QFrame {{
                background: {C_BLANCO};
                border: 1px solid {C_GRIS_BORDE};
                border-radius: 12px;
            }}
        """)
        lay_m = QVBoxLayout(panel_monedas)
        lay_m.setContentsMargins(14, 14, 14, 14)
        lay_m.setSpacing(10)

        lbl_m = QLabel("🪙  MONEDAS")
        lbl_m.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {C_NEGRO}; font-family: 'Inter', 'Segoe UI', sans-serif;")
        lay_m.addWidget(lbl_m)

        grid_m = QGridLayout()
        grid_m.setSpacing(8)
        grid_m.setColumnStretch(0, 1)
        grid_m.setColumnStretch(1, 1)

        # Separar billetes y monedas
        b_idx, m_idx = 0, 0
        for valor, etiqueta, color, tipo in DENOMINACIONES:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {C_BLANCO};
                    border: 1px solid #E2E8F0;
                    border-radius: 10px;
                }}
            """)
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(10, 8, 10, 8)
            card_lay.setSpacing(4)

            # Fila superior: indicador de color + denominación
            top = QHBoxLayout()
            top.setSpacing(6)

            # Indicador de color (rectángulo redondeado para billetes, círculo para monedas)
            indicador = QFrame()
            if tipo == "billete":
                indicador.setFixedSize(24, 16)
                indicador.setStyleSheet(f"""
                    background: {color};
                    border-radius: 4px;
                """)
            else:
                indicador.setFixedSize(16, 16)
                indicador.setStyleSheet(f"""
                    background: {color};
                    border-radius: 8px;
                """)
            top.addWidget(indicador)

            lbl_den = QLabel(etiqueta)
            lbl_den.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {C_NEGRO};")
            top.addWidget(lbl_den)
            top.addStretch()
            card_lay.addLayout(top)

            # Fila central: botones + cantidad
            mid = QHBoxLayout()
            mid.setSpacing(4)

            btn_menos = QPushButton("−")
            btn_menos.setFixedSize(32, 32)
            btn_menos.setStyleSheet(f"""
                QPushButton {{
                    background: #E2E8F0;
                    color: #475569;
                    border: none;
                    border-radius: 6px;
                    font-size: 16px;
                    font-weight: 700;
                }}
                QPushButton:hover {{ background: #CBD5E1; }}
            """)

            spin = QSpinBox()
            spin.setMinimum(0)
            spin.setMaximum(999)
            spin.setValue(0)
            spin.setFixedWidth(72)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            spin.wheelEvent = lambda event: None
            spin.valueChanged.connect(self._recalcular)

            btn_mas = QPushButton("+")
            btn_mas.setFixedSize(32, 32)
            btn_mas.setStyleSheet(f"""
                QPushButton {{
                    background: #E2E8F0;
                    color: #475569;
                    border: none;
                    border-radius: 6px;
                    font-size: 16px;
                    font-weight: 700;
                }}
                QPushButton:hover {{ background: #CBD5E1; }}
            """)

            # Conectar botones
            btn_menos.clicked.connect(lambda checked, s=spin: s.setValue(max(0, s.value() - 1)))
            btn_mas.clicked.connect(lambda checked, s=spin: s.setValue(s.value() + 1))

            mid.addWidget(btn_menos)
            mid.addStretch()
            mid.addWidget(spin)
            mid.addStretch()
            mid.addWidget(btn_mas)
            card_lay.addLayout(mid)

            # Subtotal
            lbl_sub = QLabel("$0")
            lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_sub.setStyleSheet(f"font-size: 11px; color: {C_GRIS_MED}; font-weight: 500;")
            card_lay.addWidget(lbl_sub)

            self._spinners.append((valor, spin, lbl_sub))

            # Agregar al grid correspondiente
            if tipo == "billete":
                row, col = divmod(b_idx, 2)
                grid_b.addWidget(card, row, col)
                b_idx += 1
            else:
                row, col = divmod(m_idx, 2)
                grid_m.addWidget(card, row, col)
                m_idx += 1

        lay_b.addLayout(grid_b)
        lay_m.addLayout(grid_m)
        main.addWidget(panel_billetes, 1)
        main.addWidget(panel_monedas, 1)

    def _recalcular(self):
        total = 0.0
        for valor, spin, lbl_sub in self._spinners:
            sub = valor * spin.value()
            total += sub
            lbl_sub.setText(f"${sub:,.0f}" if sub > 0 else "$0")
        self.total_changed.emit(total)

    def total(self) -> float:
        return sum(v * s.value() for v, s, _ in self._spinners)

    def reset(self):
        for _, spin, lbl in self._spinners:
            spin.setValue(0)
            lbl.setText("$0")