"""Cierres de caja ya hechos: recalcular el esperado y la diferencia cuando se corrige un movimiento."""
import json


def registrar_auditoria(cur, entidad, entidad_id, accion, usuario_id, antes, despues, motivo=None):
    cur.execute(
        """INSERT INTO auditoria_cambios
           (entidad, entidad_id, accion, usuario_id, antes, despues, motivo)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (entidad, entidad_id, accion, usuario_id,
         json.dumps(antes, ensure_ascii=False, default=str) if antes is not None else None,
         json.dumps(despues, ensure_ascii=False, default=str) if despues is not None else None,
         motivo),
    )


def caja_cerrada(cur, caja_id) -> bool:
    """Un movimiento sin caja (datos históricos) se trata como de un cierre anterior."""
    if not caja_id:
        return True
    caja = cur.execute("SELECT estado FROM cajas WHERE id = %s FOR UPDATE", (caja_id,)).fetchone()
    return not caja or caja["estado"] != "ABIERTA"


def recalcular_cierre(cur, caja_id, usuario_id, motivo):
    """Recalcula efectivo esperado y diferencia de una caja CERRADA.

    El efectivo contado no cambia (ya se contó el dinero real); cambia el esperado,
    y por eso la diferencia. Deja la caja marcada como «modificada después del cierre»
    y guarda el esperado original la primera vez. Si la caja está abierta o no existe,
    no hace nada: una caja abierta se calcula sola.
    """
    if not caja_id:
        return None
    caja = cur.execute("""
        SELECT id, estado, monto_apertura, monto_cierre, efectivo_esperado, diferencia
        FROM cajas WHERE id = %s FOR UPDATE
    """, (caja_id,)).fetchone()
    if not caja or caja["estado"] != "CERRADA":
        return None
    pagos = cur.execute("""
        SELECT COALESCE(SUM(valor), 0) AS total FROM pagos
        WHERE caja_id = %s AND metodo_pago = 'Efectivo'
          AND concepto <> 'Abono histórico previo' AND anulado = 0
    """, (caja_id,)).fetchone()["total"]
    ingresos = cur.execute(
        "SELECT COALESCE(SUM(valor), 0) AS total FROM ingresos_caja WHERE caja_id = %s AND anulado = 0",
        (caja_id,)).fetchone()["total"]
    salidas = cur.execute(
        "SELECT COALESCE(SUM(valor), 0) AS total FROM salidas_caja WHERE caja_id = %s AND anulado = 0",
        (caja_id,)).fetchone()["total"]
    esperado = int(caja["monto_apertura"]) + int(pagos) + int(ingresos) - int(salidas)
    diferencia = int(caja["monto_cierre"] or 0) - esperado
    cur.execute("""
        UPDATE cajas
        SET efectivo_esperado_original = NVL(efectivo_esperado_original, efectivo_esperado),
            efectivo_esperado = %s, diferencia = %s, modificada_despues = 1,
            fecha_ultima_modificacion = CURRENT_TIMESTAMP, modificada_por = %s
        WHERE id = %s
    """, (esperado, diferencia, usuario_id, caja_id))
    antes = {"efectivo_esperado": caja["efectivo_esperado"], "diferencia": caja["diferencia"]}
    despues = {"efectivo_esperado": esperado, "diferencia": diferencia}
    registrar_auditoria(cur, "CAJA", caja_id, "RECALCULO_CIERRE", usuario_id, antes, despues, motivo)
    return despues
