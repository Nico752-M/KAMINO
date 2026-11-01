"""Acceso a Oracle Autonomous Database (oracledb, modo thin) con pool de conexiones.

Cada consulta toma una conexión del pool y la devuelve al terminar.
Se conserva el estilo %s de los parámetros: aquí se convierten a :1, :2, ...
Las filas se devuelven como dict con las claves en minúscula.
"""
import re
from contextlib import contextmanager

import oracledb

from config import Config

_pool = None


def _pos(sql: str) -> str:
    """%s (estilo MySQL) -> :1, :2, ... (estilo Oracle)."""
    n = 0

    def reemplazo(_):
        nonlocal n
        n += 1
        return f":{n}"

    return re.sub(r"%s", reemplazo, sql)


def _get_pool():
    global _pool
    if _pool is None:
        _pool = oracledb.create_pool(
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            dsn=Config.DB_DSN,
            config_dir=Config.WALLET_DIR,
            wallet_location=Config.WALLET_DIR,
            wallet_password=Config.WALLET_PASSWORD,
            min=1,
            max=Config.DB_POOL_SIZE,
            increment=1,
            timeout=300,
            tcp_connect_timeout=15,
            retry_count=0,
            getmode=oracledb.POOL_GETMODE_WAIT,
        )
    return _pool


def _conectar():
    cnx = _get_pool().acquire()
    with cnx.cursor() as c:
        if Config.DB_SCHEMA:
            c.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {Config.DB_SCHEMA}")
        c.execute(f"ALTER SESSION SET TIME_ZONE = '{Config.DB_TIMEZONE}'")
        # Búsquedas sin distinguir mayúsculas ni tildes (como en MySQL)
        c.execute("ALTER SESSION SET NLS_COMP = LINGUISTIC")
        c.execute("ALTER SESSION SET NLS_SORT = BINARY_AI")
    return cnx


class _Cursor:
    """Envuelve el cursor para recibir %s y devolver dicts."""

    def __init__(self, cur):
        self._c = cur

    def execute(self, sql: str, params: tuple = ()):
        self._c.execute(_pos(sql), list(params))
        if self._c.description:
            cols = [d[0].lower() for d in self._c.description]
            self._c.rowfactory = lambda *v: dict(zip(cols, v))
        return self

    def fetchone(self):
        return self._c.fetchone()

    def fetchall(self):
        return self._c.fetchall()

    @property
    def rowcount(self):
        return self._c.rowcount

    def close(self):
        self._c.close()


@contextmanager
def _conexion():
    cnx = _conectar()
    try:
        yield cnx
    finally:
        cnx.close()  # devuelve la conexión al pool


def fetchall(sql: str, params: tuple = ()) -> list[dict]:
    with _conexion() as cnx:
        cur = _Cursor(cnx.cursor())
        try:
            return cur.execute(sql, params).fetchall()
        finally:
            cur.close()


def fetchone(sql: str, params: tuple = ()) -> dict | None:
    with _conexion() as cnx:
        cur = _Cursor(cnx.cursor())
        try:
            return cur.execute(sql, params).fetchone()
        finally:
            cur.close()


def execute(sql: str, params: tuple = ()) -> int:
    """INSERT/UPDATE/DELETE de una sola sentencia. Devuelve filas afectadas."""
    with transaccion() as cur:
        cur.execute(sql, params)
        return cur.rowcount


@contextmanager
def transaccion():
    """Varias sentencias que deben guardarse juntas o ninguna.

        with db.transaccion() as cur:
            cur.execute(...)
            cur.execute(...)
    Si ocurre un error dentro del bloque se hace rollback automático.
    """
    cnx = _conectar()
    cur = _Cursor(cnx.cursor())
    try:
        yield cur
        cnx.commit()
    except Exception:
        cnx.rollback()
        raise
    finally:
        cur.close()
        cnx.close()