"""Conexión de la tienda a Oracle con SU PROPIO usuario (no toca el esquema del CEA).

Variables de entorno (las mismas del wallet y del DSN que ya usa el CEA, más estas):
    TIENDA_DB_USER       usuario de Oracle creado para la tienda
    TIENDA_DB_PASSWORD   su contraseña
    TIENDA_DB_SCHEMA     (opcional) solo si las tablas viven en otro esquema distinto al usuario
"""
import os
import time
from contextlib import contextmanager

import oracledb
from flask import g, has_request_context

from config import Config
from db import _pos, _wallet_dir  # mismos ayudantes del CEA: wallet y parámetros %s

_pool = None


class TiendaNoConfigurada(RuntimeError):
    pass


def _init_sesion(cnx, requested_tag):
    esquema = os.environ.get("TIENDA_DB_SCHEMA", "").strip()
    with cnx.cursor() as c:
        c.execute(f"ALTER SESSION SET {f'CURRENT_SCHEMA = {esquema} ' if esquema else ''}"
                  f"TIME_ZONE = '{Config.DB_TIMEZONE}'")


def _get_pool():
    global _pool
    if _pool is None:
        usuario = os.environ.get("TIENDA_DB_USER", "").strip()
        clave = os.environ.get("TIENDA_DB_PASSWORD", "")
        if not usuario or not clave or not Config.WALLET_PASSWORD:
            raise TiendaNoConfigurada(
                "La tienda aún no está conectada a su base de datos: faltan las variables "
                "TIENDA_DB_USER y TIENDA_DB_PASSWORD.")
        carpeta = _wallet_dir()
        _pool = oracledb.create_pool(
            user=usuario, password=clave, dsn=Config.DB_DSN,
            config_dir=carpeta, wallet_location=carpeta, wallet_password=Config.WALLET_PASSWORD,
            min=1, max=3, increment=1, timeout=300, ping_interval=60,
            tcp_connect_timeout=60, retry_count=3, retry_delay=2,
            getmode=oracledb.POOL_GETMODE_WAIT, session_callback=_init_sesion,
        )
    return _pool


def _obtener():
    """Una sola conexión por petición. Devuelve (conexión, es_propia)."""
    if has_request_context():
        cnx = getattr(g, "tienda_cnx", None)
        if cnx is None:
            cnx = g.tienda_cnx = _get_pool().acquire()
        return cnx, False
    return _get_pool().acquire(), True


def cerrar_conexion(exc=None):
    cnx = g.pop("tienda_cnx", None)
    if cnx is not None:
        try:
            cnx.close()
        except Exception:
            pass


class _Cursor:
    """Envuelve el cursor: acepta %s, devuelve dicts con claves en minúscula."""

    def __init__(self, cur):
        self._c = cur

    def execute(self, sql, params=()):
        self._c.execute(_pos(sql), list(params))
        if self._c.description:
            cols = [d[0].lower() for d in self._c.description]
            self._c.rowfactory = lambda *v: dict(zip(cols, v))
        return self

    def executemany(self, sql, filas):
        """Varias filas en un solo viaje a la base de datos."""
        filas = [list(f) for f in filas]
        if filas:
            self._c.executemany(_pos(sql), filas)
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
def transaccion():
    """Varias sentencias que se guardan juntas o ninguna (rollback automático si algo falla)."""
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


def fetchall(sql, params=()):
    with transaccion() as cur:
        return cur.execute(sql, params).fetchall()


def fetchone(sql, params=()):
    with transaccion() as cur:
        return cur.execute(sql, params).fetchone()


def execute_rowcount(sql, params=()):
    """INSERT/UPDATE/DELETE de una sola sentencia. Devuelve las filas afectadas."""
    with transaccion() as cur:
        cur.execute(sql, params)
        return cur.rowcount
