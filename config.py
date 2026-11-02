"""Configuración central. Todo lo sensible viene de variables de entorno (.env)."""
import os
from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.environ.get("APP_ENV", "development")
EN_PRODUCCION = APP_ENV == "production"


def _secret_key() -> str:
    clave = os.environ.get("SECRET_KEY")
    if clave:
        return clave
    if EN_PRODUCCION:
        raise RuntimeError("Falta SECRET_KEY en las variables de entorno.")
    return "clave-solo-para-desarrollo"


class Config:
    SECRET_KEY = _secret_key()

    # Cookies de sesión
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = EN_PRODUCCION      # solo por HTTPS en producción
    SESSION_HOURS = 12

    # Base de datos (Oracle Autonomous)
    DB_USER = os.environ.get("DB_USER", "")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_DSN = os.environ.get("DB_DSN", "kamino_low")
    DB_SCHEMA = os.environ.get("DB_SCHEMA", "CEA_APP")
    DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "5"))
    WALLET_DIR = os.environ.get("WALLET_DIR", "./Wallet")
    WALLET_PASSWORD = os.environ.get("WALLET_PASSWORD", "")

    # Colombia (UTC-5, sin horario de verano). El servidor en la nube suele estar en UTC.
    ZONA_HORARIA = "America/Bogota"
    DB_TIMEZONE = "-05:00"

    TRUST_PROXY = os.environ.get("TRUST_PROXY", "0") == "1"

    # Súbelo cuando cambies CSS/JS para forzar recarga en los celulares
    ASSET_V = "2"
