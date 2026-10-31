"""Acceso a MySQL con pool de conexiones.

A diferencia de la versión de escritorio (una sola conexión compartida),
aquí cada consulta toma una conexión del pool y la devuelve al terminar,
así varios usuarios pueden trabajar a la vez sin pisarse.
"""
from contextlib import contextmanager

from mysql.connector import pooling

from config import Config

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="cea_pool",
            pool_size=Config.DB_POOL_SIZE,
            pool_reset_session=True,
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            charset="utf8mb4",
            time_zone=Config.DB_TIMEZONE,
            autocommit=False,
            connection_timeout=10,
        )
    return _pool


@contextmanager
def _conexion():
    cnx = _get_pool().get_connection()
    try:
        yield cnx
    finally:
        cnx.close()  # devuelve la conexión al pool


def fetchall(sql: str, params: tuple = ()) -> list[dict]:
    with _conexion() as cnx:
        cur = cnx.cursor(dictionary=True)
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()


def fetchone(sql: str, params: tuple = ()) -> dict | None:
    with _conexion() as cnx:
        cur = cnx.cursor(dictionary=True)
        try:
            cur.execute(sql, params)
            return cur.fetchone()
        finally:
            cur.close()


def execute(sql: str, params: tuple = ()) -> int:
    """INSERT/UPDATE/DELETE de una sola sentencia. Devuelve lastrowid."""
    with transaccion() as cur:
        cur.execute(sql, params)
        return cur.lastrowid


@contextmanager
def transaccion():
    """Varias sentencias que deben guardarse juntas o ninguna.

        with db.transaccion() as cur:
            cur.execute(...)
            cur.execute(...)
    Si ocurre un error dentro del bloque se hace rollback automático.
    """
    cnx = _get_pool().get_connection()
    cur = cnx.cursor(dictionary=True)
    try:
        yield cur
        cnx.commit()
    except Exception:
        cnx.rollback()
        raise
    finally:
        cur.close()
        cnx.close()
