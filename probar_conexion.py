"""Prueba rápida:  python probar_conexion.py"""
import db

print(db.fetchone("SELECT USER AS usuario, SYS_CONTEXT('USERENV','CURRENT_SCHEMA') AS esquema FROM dual"))
for t in ("alumnos", "matriculas", "pagos", "usuarios"):
    print(t, db.fetchone(f"SELECT COUNT(*) AS n FROM {t}")["n"])
print("Conexión OK")