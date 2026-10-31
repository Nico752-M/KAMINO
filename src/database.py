#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de conexión a MySQL - CEA PRACTICAR
Ubicación sugerida: src/database.py

Uso desde cualquier vista:
    from database import Database
    db = Database.get_instance()
    resultados = db.fetchall("SELECT * FROM alumnos")
"""
from PyQt6 import QtCore, QtGui, QtWidgets

import mysql.connector
from mysql.connector import Error
from typing import Optional, List, Dict, Any
import os as _os
import sys
import configparser


# ─── Ruta de expedientes (archivos escaneados) ───────────────────────────────
# Local por ahora. Cuando tengan servidor, cambiar a la ruta de red:
# Windows red: r"\\192.168.1.X\CEA_PRACTICAR\expedientes"
# Linux/Mac red: "/mnt/servidor/CEA_PRACTICAR/expedientes"
RUTA_EXPEDIENTES = _os.path.join(_os.path.expanduser("~"), "Documents", "CEA_PRACTICAR", "expedientes")

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

def _cargar_config():
    config = configparser.ConfigParser()

    # Rutas donde buscar config.ini (en orden)
    posibles_rutas = [
        _os.path.join(_os.path.dirname(sys.executable), 'config.ini'),                        # Misma carpeta del .exe
        _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'config.ini'),       # Carpeta padre de database.py
        _os.path.join(_os.getcwd(), 'config.ini'),                                             # Carpeta actual
    ]

    for ruta in posibles_rutas:
        if _os.path.exists(ruta):
            config.read(ruta, encoding='utf-8')
            break

    return {
        "host":               config.get('database', 'host',     fallback='127.0.0.1'),
        "port":               config.getint('database', 'port',  fallback=3306),
        "database":           config.get('database', 'database', fallback='cea_p'),
        "user":               config.get('database', 'user',     fallback='PRACTICAR'),
        "password":           config.get('database', 'password', fallback='PRACTICAR123'),
        "charset":            "utf8mb4",
        "autocommit":         True,
        "connection_timeout": 10
    }

DB_CONFIG = _cargar_config()


# ══════════════════════════════════════════════════════════════════════════════
#  CLASE DATABASE — Singleton para reutilizar la conexión
# ══════════════════════════════════════════════════════════════════════════════

class Database:
    """
    Singleton de conexión a MySQL.
    Una sola instancia compartida por toda la aplicación.
    """

    _instance: Optional["Database"] = None

    def __init__(self):
        self._connection: Optional[mysql.connector.MySQLConnection] = None
        self._connect()

    # ── Singleton ─────────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "Database":
        """Retorna la instancia única. La crea si no existe."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Cierra la conexión y elimina la instancia (útil para reconectar)."""
        if cls._instance and cls._instance._connection:
            try:
                cls._instance._connection.close()
            except Exception:
                pass
        cls._instance = None

    # ── Conexión ──────────────────────────────────────────────────────────────

    def _connect(self):
        """Establece la conexión con el servidor MySQL."""
        try:
            self._connection = mysql.connector.connect(**DB_CONFIG)
            print(f"[DB] Conectado a {DB_CONFIG['host']}:{DB_CONFIG['port']} — {DB_CONFIG['database']}")
        except Error as e:
            self._connection = None
            raise ConnectionError(f"No se pudo conectar a la base de datos:\n{e}")

    def _ensure_connection(self):
        """Reconecta automáticamente si la conexión se perdió."""
        try:
            if self._connection is None or not self._connection.is_connected():
                print("[DB] Reconectando...")
                self._connect()
        except Error as e:
            raise ConnectionError(f"Error al reconectar: {e}")

    def is_connected(self) -> bool:
        """Retorna True si la conexión está activa."""
        try:
            return self._connection is not None and self._connection.is_connected()
        except Exception:
            return False

    # ── Métodos de consulta ───────────────────────────────────────────────────

    def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Ejecuta un SELECT y retorna todos los resultados como lista de dicts.

        Ejemplo:
            rows = db.fetchall("SELECT * FROM alumnos WHERE estado = %s", ("Activo",))
            for row in rows:
                print(row["nombres"])
        """
        self._ensure_connection()
        cursor = self._connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            return cursor.fetchall()
        except Error as e:
            raise RuntimeError(f"Error en consulta:\n{query}\n{e}")
        finally:
            cursor.close()

    def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """
        Ejecuta un SELECT y retorna solo el primer resultado como dict.

        Ejemplo:
            alumno = db.fetchone(
                "SELECT * FROM alumnos WHERE numero_documento = %s",
                ("94427466",)
            )
        """
        self._ensure_connection()
        cursor = self._connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            return cursor.fetchone()
        except Error as e:
            raise RuntimeError(f"Error en consulta:\n{query}\n{e}")
        finally:
            cursor.close()

    def execute(self, query: str, params: tuple = ()) -> int:
        """
        Ejecuta INSERT, UPDATE o DELETE.
        Retorna el ID del último registro insertado (útil para INSERTs).

        Ejemplo:
            nuevo_id = db.execute(
                "INSERT INTO alumnos (nombres, apellidos) VALUES (%s, %s)",
                ("Carlos", "Hoyos")
            )
        """
        self._ensure_connection()
        cursor = self._connection.cursor()
        try:
            cursor.execute(query, params)
            self._connection.commit()
            return cursor.lastrowid
        except Error as e:
            self._connection.rollback()
            raise RuntimeError(f"Error al ejecutar:\n{query}\n{e}")
        finally:
            cursor.close()

    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """
        Ejecuta el mismo INSERT/UPDATE para múltiples filas de una vez.
        Más eficiente que llamar execute() en un loop.

        Ejemplo:
            db.execute_many(
                "INSERT INTO clases (id_matricula, tipo, numero_clase, fecha) VALUES (%s, %s, %s, %s)",
                [(1, "Practica", 1, "2026-05-16"), (1, "Practica", 2, "2026-05-17")]
            )
        """
        self._ensure_connection()
        cursor = self._connection.cursor()
        try:
            cursor.executemany(query, params_list)
            self._connection.commit()
            return cursor.rowcount
        except Error as e:
            self._connection.rollback()
            raise RuntimeError(f"Error en execute_many:\n{e}")
        finally:
            cursor.close()

    # ── Métodos nuevos para código de alumno ──────────────────────────────────

    def generar_codigo_alumno(self) -> str:
        """
        Genera un código único tipo 001-26, 002-26, etc.
        El consecutivo es por año (reinicia cada año).
        """
        from datetime import datetime
        anio_actual = datetime.now().year
        anio_corto = str(anio_actual)[-2:]

        row = self.fetchone(
            "SELECT codigo_alumno FROM alumnos WHERE codigo_alumno LIKE %s ORDER BY codigo_alumno DESC LIMIT 1",
            (f"%-{anio_corto}",)
        )
        if row and row.get("codigo_alumno"):
            try:
                ultimo_num = int(row["codigo_alumno"].split("-")[0])
                nuevo_num = ultimo_num + 1
            except (ValueError, IndexError):
                nuevo_num = 1
        else:
            nuevo_num = 1

        return f"{nuevo_num:03d}-{anio_corto}"

    def get_alumnos_por_mes(self, anio: int = None) -> dict:
        """
        Retorna un dict {mes_numero: cantidad_alumnos} para el año dado.
        Si anio es None, usa el año actual.
        """
        from datetime import datetime
        if anio is None:
            anio = datetime.now().year

        rows = self.fetchall(
            "SELECT MONTH(fecha_registro) AS mes, COUNT(*) AS total FROM alumnos WHERE YEAR(fecha_registro) = %s GROUP BY MONTH(fecha_registro)",
            (anio,)
        )
        return {r["mes"]: r["total"] for r in rows}

    def close(self):
        """Cierra la conexión manualmente."""
        if self._connection and self._connection.is_connected():
            self._connection.close()
            print("[DB] Conexión cerrada.")