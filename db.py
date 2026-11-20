"""Acceso a Oracle Autonomous Database (oracledb, modo thin) con pool de conexiones.

Cada consulta toma una conexión del pool y la devuelve al terminar.
Se conserva el estilo %s de los parámetros: aquí se convierten a :1, :2, ...
Las filas se devuelven como dict con las claves en minúscula.
"""
import base64
import os
import pathlib
import re
import time
from contextlib import contextmanager

import oracledb
from flask import g, has_request_context

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


def _wallet_dir() -> str:
    pem = os.environ.get("WALLET_PEM_B64")
    tns = os.environ.get("WALLET_TNS_B64")
    if bool(pem) != bool(tns):
        raise RuntimeError("WALLET_PEM_B64 y WALLET_TNS_B64 deben configurarse juntos.")
    if not pem:
        if not pathlib.Path(Config.WALLET_DIR).is_dir():
            raise FileNotFoundError(f"No se encontró el wallet Oracle en {Config.WALLET_DIR}.")
        return Config.WALLET_DIR
    d = pathlib.Path("/tmp/wallet")
    d.mkdir(exist_ok=True)
    (d / "ewallet.pem").write_bytes(base64.b64decode(pem, validate=True))
    (d / "tnsnames.ora").write_bytes(base64.b64decode(tns, validate=True))
    return str(d)


def _init_sesion(cnx, requested_tag):
    with cnx.cursor() as c:
        esquema = f"CURRENT_SCHEMA = {Config.DB_SCHEMA} " if Config.DB_SCHEMA else ""
        c.execute(f"ALTER SESSION SET {esquema}TIME_ZONE = '{Config.DB_TIMEZONE}'")


def _get_pool():
    global _pool
    if _pool is None:
        if not Config.DB_USER or not Config.DB_PASSWORD or not Config.WALLET_PASSWORD:
            raise RuntimeError("Faltan DB_USER, DB_PASSWORD o WALLET_PASSWORD.")
        carpeta = _wallet_dir()
        _pool = oracledb.create_pool(
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            dsn=Config.DB_DSN,
            config_dir=carpeta,
            wallet_location=carpeta,
            wallet_password=Config.WALLET_PASSWORD,
            min=1,
            max=max(Config.DB_POOL_SIZE, 5),
            increment=1,
            timeout=300,
            ping_interval=60,
            tcp_connect_timeout=60,
            retry_count=3,
            retry_delay=2,
            getmode=oracledb.POOL_GETMODE_WAIT,
            session_callback=_init_sesion,
        )
    return _pool


def _conectar():
    inicio = time.perf_counter()
    try:
        return _get_pool().acquire()
    finally:
        _registrar_medicion(inicio)


def _obtener():
    """Una sola conexión por petición.Devuelve (conexión, es_propia)."""
    if has_request_context():
        cnx = getattr(g, "db_cnx", None)
        if cnx is None:
            cnx = g.db_cnx = _conectar()
        return cnx, False
    return _conectar(), True


def cerrar_conexion_request(exc=None):
    cnx = g.pop("db_cnx", None)
    if cnx is not None:
        try:
            cnx.close()
        except Exception:
            pass


def _registrar_medicion(inicio: float, consulta: bool = False) -> None:
    if not has_request_context():
        return
    if consulta:
        g.db_query_count = getattr(g, "db_query_count", 0) + 1
    g.db_query_ms = getattr(g, "db_query_ms", 0.0) + (
        time.perf_counter() - inicio
    ) * 1000


class _Cursor:
    """Envuelve el cursor para recibir %s y devolver dicts."""

    def __init__(self, cur):
        self._c = cur

    def execute(self, sql: str, params: tuple = ()):
        started = time.perf_counter()
        try:
            self._c.execute(_pos(sql), list(params))
        finally:
            _registrar_medicion(started, consulta=True)
        if self._c.description:
            cols = [d[0].lower() for d in self._c.description]
            self._c.rowfactory = lambda *v: dict(zip(cols, v))
        return self

    def fetchone(self):
        started = time.perf_counter()
        try:
            return self._c.fetchone()
        finally:
            _registrar_medicion(started)

    def fetchall(self):
        started = time.perf_counter()
        try:
            return self._c.fetchall()
        finally:
            _registrar_medicion(started)

    @property
    def rowcount(self):
        return self._c.rowcount

    def close(self):
        self._c.close()


@contextmanager
def _conexion():
    cnx, propia = _obtener()
    try:
        yield cnx
    finally:
        if propia:
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
    cnx, propia = _obtener()
    cur = _Cursor(cnx.cursor())
    try:
        yield cur
        cnx.commit()
    except Exception:
        cnx.rollback()
        raise
    finally:
        cur.close()
        if propia:
            cnx.close()