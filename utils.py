"""Helpers pequeños compartidos."""
from datetime import date, datetime
import re
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


def parsear_pesos(valor: str | int | None) -> int | None:
    """Convierte pesos enteros (dígitos o grupos con puntos) sin aceptar decimales."""
    texto = str("" if valor is None else valor).strip()
    if (not texto.isascii()
            or not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)", texto)):
        return None
    return int(texto.replace(".", ""))


def a_fecha(valor) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None

import time as _time

_CACHE: dict = {}


def cacheado(clave: str, ttl: int, consulta):
    """Devuelve el resultado guardado si tiene menos de `ttl` segundos."""
    guardado = _CACHE.get(clave)
    if guardado and _time.monotonic() - guardado[0] < ttl:
        return guardado[1]
    valor = consulta()
    _CACHE[clave] = (_time.monotonic(), valor)
    return valor


def invalidar_cache(*claves: str) -> None:
    for clave in claves:
        _CACHE.pop(clave, None)