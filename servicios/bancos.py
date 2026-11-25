"""Bancos y bolsillos. El saldo sale del libro de movimientos (entradas - salidas no anuladas)."""
import db
from servicios.recibos import numero_recibo
from utils import cop


class BancoError(ValueError):
    """Mensaje claro para mostrar a la persona."""


def parsear_destino(texto):
    """'3:0' -> (3, None) banco sin bolsillo;  '3:7' -> (3, 7);  '' -> None."""
    texto = (texto or "").strip()
    if not texto:
        return None
    try:
        banco, bolsillo = (int(x) for x in texto.split(":"))
    except ValueError:
        raise BancoError("El destino bancario no es válido.")
    if banco <= 0 or bolsillo < 0:
        raise BancoError("El destino bancario no es válido.")
    return banco, (bolsillo or None)


def catalogo_destinos():
    """Lista plana para los selectores: [{valor: '3:0', texto: 'Bancolombia · Sin bolsillo'}, ...]."""
    filas = db.fetchall("""
        SELECT b.id AS banco_id, b.nombre AS banco, p.id AS bolsillo_id, p.nombre AS bolsillo
        FROM bancos b
        LEFT JOIN bolsillos p ON p.banco_id = b.id AND p.activo = 1
        WHERE b.activo = 1
        ORDER BY b.nombre, p.nombre
    """)
    destinos, vistos = [], set()
    for f in filas:
        if f["banco_id"] not in vistos:
            vistos.add(f["banco_id"])
            destinos.append({"valor": f"{f['banco_id']}:0", "texto": f"{f['banco']} · Sin bolsillo"})
        if f["bolsillo_id"]:
            destinos.append({"valor": f"{f['banco_id']}:{f['bolsillo_id']}",
                             "texto": f"{f['banco']} · {f['bolsillo']}"})
    return destinos


def validar_destino(cur, destino, bloquear=False):
    """Comprueba que banco y bolsillo existan y estén activos. Con bloquear=True bloquea el banco
    para que dos salidas simultáneas no dejen el saldo en negativo."""
    banco_id, bolsillo_id = destino
    banco = cur.execute(
        "SELECT id, nombre FROM bancos WHERE id = %s AND activo = 1" + (" FOR UPDATE" if bloquear else ""),
        (banco_id,),
    ).fetchone()
    if not banco:
        raise BancoError("El banco elegido no existe o está desactivado.")
    bolsillo = None
    if bolsillo_id:
        bolsillo = cur.execute(
            "SELECT id, nombre FROM bolsillos WHERE id = %s AND banco_id = %s AND activo = 1",
            (bolsillo_id, banco_id),
        ).fetchone()
        if not bolsillo:
            raise BancoError("El bolsillo elegido no existe, está desactivado o no es de ese banco.")
    return {"banco_id": int(banco["id"]),
            "bolsillo_id": int(bolsillo["id"]) if bolsillo else None,
            "texto": banco["nombre"] + (f" · {bolsillo['nombre']}" if bolsillo else "")}


def saldo(cur, d) -> int:
    filtro = "bolsillo_id = %s" if d["bolsillo_id"] else "bolsillo_id IS NULL"
    params = (d["banco_id"],) + ((d["bolsillo_id"],) if d["bolsillo_id"] else ())
    fila = cur.execute(
        "SELECT NVL(SUM(CASE WHEN tipo = 'ENTRADA' THEN valor ELSE -valor END), 0) AS s "
        f"FROM movimientos_banco WHERE anulado = 0 AND banco_id = %s AND {filtro}", params,
    ).fetchone()
    return int(fila["s"])


def exigir_saldo(cur, d, valor):
    actual = saldo(cur, d)
    if actual < valor:
        raise BancoError(f"Saldo insuficiente en {d['texto']}: hay {cop(actual)}.")


def registrar(cur, d, tipo, valor, concepto, origen, referencia, usuario_id, categoria=None):
    cur.execute(
        """INSERT INTO movimientos_banco
           (banco_id, bolsillo_id, tipo, valor, concepto, origen, referencia, categoria, usuario_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (d["banco_id"], d["bolsillo_id"], tipo, valor, concepto[:200], origen,
         referencia, categoria, usuario_id),
    )


def movimiento_manual(cur, tipo, destino, valor, concepto, categoria, usuario_id) -> str:
    """Ingreso (ENTRADA) o egreso (SALIDA) directo en un banco. Devuelve el número de recibo."""
    d = validar_destino(cur, destino, bloquear=(tipo == "SALIDA"))
    if tipo == "SALIDA":
        exigir_saldo(cur, d, valor)
    recibo = numero_recibo(cur)
    registrar(cur, d, tipo, valor, concepto, "MANUAL", recibo, usuario_id, categoria)
    return recibo