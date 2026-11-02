"""Crea o resetea un usuario con contraseña segura.

    python crear_usuario.py admin --nombre "Administrador" --rol admin

Se conecta como el dueño de las tablas (cea_app), porque la app web (cea_web)
no tiene permiso de crear usuarios ni cambiar contraseñas.
"""
import argparse
import getpass
import os
import sys

from werkzeug.security import generate_password_hash
from permisos import PERMISOS_POR_ROL, ROLES

p = argparse.ArgumentParser()
p.add_argument("usuario")
p.add_argument("--nombre", default=None)
p.add_argument("--rol", choices=ROLES, default="cajera")
a = p.parse_args()

usuario = a.usuario.strip().lower()
clave = getpass.getpass("Contraseña del nuevo usuario (mínimo 8 caracteres): ")
if len(clave) < 8:
    sys.exit("La contraseña es muy corta.")
if clave != getpass.getpass("Repite la contraseña: "):
    sys.exit("No coinciden.")

# Conexión como dueño (antes de importar db/config)
os.environ["DB_USER"] = os.environ.get("DB_OWNER_USER", "cea_app")
os.environ["DB_PASSWORD"] = os.environ.get("DB_OWNER_PASSWORD") or getpass.getpass("Contraseña de cea_app (Oracle): ")
os.environ["DB_SCHEMA"] = ""

import db  # noqa: E402

hash_ = generate_password_hash(clave)
existe = db.fetchone("SELECT id FROM usuarios WHERE usuario = %s", (usuario,))
if existe:
    with db.transaccion() as cur:
        cur.execute("UPDATE usuarios SET password_hash=%s, rol=%s, activo=1"
                    + (", nombre=%s" if a.nombre else "") + " WHERE id=%s",
                    (hash_, a.rol) + ((a.nombre,) if a.nombre else ()) + (existe["id"],))
        perfil = cur.execute(
            "SELECT id FROM perfiles WHERE usuario_id = %s", (existe["id"],)
        ).fetchone()
        if not perfil:
            cur.execute(
                "INSERT INTO perfiles (usuario_id, nombre) VALUES (%s, %s)",
                (existe["id"], f"{a.nombre or usuario} - {a.rol}"),
            )
            perfil = cur.execute(
                "SELECT id FROM perfiles WHERE usuario_id = %s", (existe["id"],)
            ).fetchone()
            for codigo in sorted(PERMISOS_POR_ROL[a.rol]):
                cur.execute(
                    "INSERT INTO perfil_permisos (perfil_id, codigo) VALUES (%s, %s)",
                    (perfil["id"], codigo),
                )
    print(f"Usuario '{usuario}' actualizado.")
else:
    with db.transaccion() as cur:
        cur.execute("INSERT INTO usuarios (nombre, usuario, password_hash, rol, activo) "
                    "VALUES (%s, %s, %s, %s, 1)", (a.nombre or usuario, usuario, hash_, a.rol))
        user_id = cur.execute(
            "SELECT id FROM usuarios WHERE usuario = %s", (usuario,)
        ).fetchone()["id"]
        cur.execute(
            "INSERT INTO perfiles (usuario_id, nombre) VALUES (%s, %s)",
            (user_id, f"{a.nombre or usuario} - {a.rol}"),
        )
        profile_id = cur.execute(
            "SELECT id FROM perfiles WHERE usuario_id = %s", (user_id,)
        ).fetchone()["id"]
        for codigo in sorted(PERMISOS_POR_ROL[a.rol]):
            cur.execute(
                "INSERT INTO perfil_permisos (perfil_id, codigo) VALUES (%s, %s)",
                (profile_id, codigo),
            )
    print(f"Usuario '{usuario}' creado.")