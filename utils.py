"""Helpers pequeños compartidos."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from config import Config

_TZ = ZoneInfo(Config.ZONA_HORARIA)

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def ahora() -> datetime:
    return datetime.now(_TZ)


def hoy() -> date:
    return ahora().date()


def fecha_larga(d: date | None = None) -> str:
    d = d or hoy()
    return f"{DIAS[d.weekday()].capitalize()}, {d.day} de {MESES[d.month]} de {d.year}"


def cop(valor) -> str:
    """1065000 -> '$ 1.065.000'"""
    try:
        return "$ " + f"{int(round(float(valor or 0))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "$ 0"


def entero(valor, defecto: int = 0) -> int:
    """Convierte '150.000', 150000, '150000.0' a int. Si no se puede, devuelve defecto."""
    try:
        if isinstance(valor, str):
            valor = valor.replace(".", "").replace(",", "").replace("$", "").strip()
        return int(float(valor))
    except (TypeError, ValueError):
        return defecto


def a_fecha(valor) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None
