"""Crea o resetea un usuario con contraseña segura.

    python crear_usuario.py admin --nombre "Administrador" --rol admin
"""
import argparse
import getpass
import sys

from werkzeug.security import generate_password_hash

import db

ROLES = ("admin", "cajera", "secretaria", "contadora")

p = argparse.ArgumentParser()
p.add_argument("usuario")
p.add_argument("--nombre", default=None)
p.add_argument("--rol", choices=ROLES, default="cajera")
a = p.parse_args()

usuario = a.usuario.strip().lower()
clave = getpass.getpass("Contraseña (mínimo 8 caracteres): ")
if len(clave) < 8:
    sys.exit("La contraseña es muy corta.")
if clave != getpass.getpass("Repite la contraseña: "):
    sys.exit("No coinciden.")

hash_ = generate_password_hash(clave)
existe = db.fetchone("SELECT id FROM usuarios WHERE usuario = %s", (usuario,))
if existe:
    db.execute("UPDATE usuarios SET password_hash=%s, rol=%s, activo=1"
               + (", nombre=%s" if a.nombre else "") + " WHERE id=%s",
               (hash_, a.rol) + ((a.nombre,) if a.nombre else ()) + (existe["id"],))
    print(f"Usuario '{usuario}' actualizado.")
else:
    db.execute("INSERT INTO usuarios (nombre, usuario, password_hash, rol, activo) "
               "VALUES (%s, %s, %s, %s, 1)", (a.nombre or usuario, usuario, hash_, a.rol))
    print(f"Usuario '{usuario}' creado.")
