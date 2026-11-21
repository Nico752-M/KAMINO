"""Lógica de la tienda: productos, ventas con descuento automático de inventario y ganancias."""
from datetime import date, timedelta

from utils import hoy

from . import datos

METODOS = ("Efectivo", "Nequi", "Tarjeta")
TOPE = 999_999_999
MOTIVOS_MERMA = ("Dañado", "Vencido", "Consumo propio", "Pérdida", "Otro")

AJUSTES_BASE = {
    "gastosMes": 0, "usarGastos": True,
    "comision": 2.5, "usarComision": False,
    "impuesto": 0.0, "usarImpuesto": False,
    "reserva": 20.0, "usarReserva": False,
}


class TiendaError(Exception):
    """Error de negocio: el mensaje se muestra tal cual al usuario."""


def _entero(valor, nombre, minimo=0, maximo=TOPE):
    try:
        if isinstance(valor, bool):
            raise ValueError
        n = int(str(valor).replace(".", "").strip()) if isinstance(valor, str) else int(valor)
    except (TypeError, ValueError):
        raise TiendaError(f"{nombre}: escribe un número entero.")
    if n < minimo or n > maximo:
        raise TiendaError(f"{nombre}: debe estar entre {minimo:,} y {maximo:,}.".replace(",", "."))
    return n


def _marcadores(n):
    return ", ".join(["%s"] * n)


# ═════════════════ Productos ═════════════════
def listar_productos():
    filas = datos.fetchall("""
        SELECT id, nombre, categoria, costo, precio, stock, stock_minimo
        FROM t_productos WHERE activo = 1 ORDER BY categoria, nombre""")
    return [{"id": int(f["id"]), "nombre": f["nombre"], "cat": f["categoria"],
             "costo": int(f["costo"]), "precio": int(f["precio"]),
             "stock": int(f["stock"]), "minimo": int(f["stock_minimo"])} for f in filas]


def guardar_producto(d, usuario):
    nombre = " ".join(str(d.get("nombre", "")).split())
    categoria = " ".join(str(d.get("categoria", "")).split()) or "General"
    if not nombre or len(nombre) > 80:
        raise TiendaError("El nombre es obligatorio (máximo 80 caracteres).")
    if len(categoria) > 40:
        raise TiendaError("La categoría admite hasta 40 caracteres.")
    costo = _entero(d.get("costo", 0), "Costo")
    precio = _entero(d.get("precio"), "Precio", minimo=1)
    stock = _entero(d.get("stock", 0), "Stock")
    minimo = _entero(d.get("minimo", 0), "Aviso de stock bajo")
    if costo > precio:
        raise TiendaError("El costo es mayor que el precio: venderías con pérdida.")
    pid = d.get("id")
    pid = _entero(pid, "Producto", minimo=1) if pid not in (None, "", 0) else None

    with datos.transaccion() as cur:
        repetido = cur.execute(
            "SELECT id FROM t_productos WHERE activo = 1 AND LOWER(nombre) = LOWER(%s)", (nombre,)
        ).fetchall()
        if any(int(r["id"]) != (pid or 0) for r in repetido):
            raise TiendaError("Ya existe un producto con ese nombre.")
        if pid:
            fila = cur.execute(
                "SELECT stock FROM t_productos WHERE id = %s AND activo = 1 FOR UPDATE", (pid,)
            ).fetchone()
            if not fila:
                raise TiendaError("El producto ya no existe.")
            cur.execute("""UPDATE t_productos SET nombre = %s, categoria = %s, costo = %s, precio = %s,
                                  stock = %s, stock_minimo = %s WHERE id = %s""",
                        (nombre, categoria, costo, precio, stock, minimo, pid))
            diferencia = stock - int(fila["stock"])
            if diferencia:
                cur.execute("""INSERT INTO t_movimientos
                                 (producto_id, tipo, cantidad, stock_resultante, usuario_id, nota)
                               VALUES (%s, 'AJUSTE', %s, %s, %s, 'Corrección al editar el producto')""",
                            (pid, diferencia, stock, usuario["id"]))
        else:
            cur.execute("""INSERT INTO t_productos (id, nombre, categoria, costo, precio, stock, stock_minimo)
                           VALUES (t_seq_productos.NEXTVAL, %s, %s, %s, %s, %s, %s)""",
                        (nombre, categoria, costo, precio, stock, minimo))
            if stock:
                nuevo = cur.execute("SELECT t_seq_productos.CURRVAL AS id FROM dual").fetchone()
                cur.execute("""INSERT INTO t_movimientos
                                 (producto_id, tipo, cantidad, stock_resultante, usuario_id, nota)
                               VALUES (%s, 'INICIAL', %s, %s, %s, 'Stock inicial')""",
                            (int(nuevo["id"]), stock, stock, usuario["id"]))


def entrada_stock(pid, cantidad, nota, usuario):
    cantidad = _entero(cantidad, "Cantidad", minimo=1, maximo=1_000_000)
    nota = " ".join(str(nota or "").split())[:200] or "Entrada de mercancía"
    with datos.transaccion() as cur:
        fila = cur.execute(
            "SELECT stock FROM t_productos WHERE id = %s AND activo = 1 FOR UPDATE", (pid,)
        ).fetchone()
        if not fila:
            raise TiendaError("El producto ya no existe.")
        nuevo = int(fila["stock"]) + cantidad
        cur.execute("UPDATE t_productos SET stock = %s WHERE id = %s", (nuevo, pid))
        cur.execute("""INSERT INTO t_movimientos (producto_id, tipo, cantidad, stock_resultante, usuario_id, nota)
                       VALUES (%s, 'ENTRADA', %s, %s, %s, %s)""",
                    (pid, cantidad, nuevo, usuario["id"], nota))
    return nuevo


def quitar_producto(pid):
    """Lo oculta (no se borra) para conservar el historial de ventas."""
    n = datos.execute_rowcount("UPDATE t_productos SET activo = 0 WHERE id = %s AND activo = 1", (pid,))
    if not n:
        raise TiendaError("El producto ya no existe.")


# ═════════════════ Ventas ═════════════════
def _descuento(d, subtotal):
    """Descuento en $ o % ya convertido a pesos. 0 si no hay."""
    if not isinstance(d, dict):
        return 0
    v = _entero(d.get("valor") or 0, "Descuento")
    if d.get("tipo") == "pct":
        if v > 100:
            raise TiendaError("El descuento no puede pasar de 100 %.")
        v = round(subtotal * v / 100)
    if v >= subtotal and v > 0:
        raise TiendaError("El descuento debe ser menor que el total de la venta.")
    return v


def caja_abierta():
    """La caja está abierta si hay una base vigente desde el último cierre."""
    ultimo = datos.fetchone("SELECT MAX(creado) AS c FROM t_cierres")
    if ultimo and ultimo["c"]:
        cond, par = "fecha > %s", (ultimo["c"],)
    else:
        cond, par = "fecha >= TRUNC(CURRENT_TIMESTAMP)", ()
    f = datos.fetchone(
        f"SELECT COUNT(*) AS n FROM t_caja_mov WHERE tipo = 'BASE' AND anulado = 0 AND {cond}", par)
    return int(f["n"]) > 0


def registrar_venta(items, metodo, recibido, usuario, resto=None, descuento=None):
    if metodo not in METODOS:
        raise TiendaError("Elige un método de pago válido.")
    if not isinstance(items, list) or not items or len(items) > 60:
        raise TiendaError("Agrega al menos un producto a la venta.")
    pedido = {}
    for it in items:
        if not isinstance(it, dict):
            raise TiendaError("La venta no es válida.")
        pid = _entero(it.get("id"), "Producto", minimo=1)
        pedido[pid] = pedido.get(pid, 0) + _entero(it.get("cant"), "Cantidad", minimo=1, maximo=9999)
    recibido = _entero(recibido or 0, "Recibido") if metodo == "Efectivo" else 0
    if not caja_abierta():
        raise TiendaError("La caja está cerrada. Ve a Ventas y pon la base para poder vender.")

    ids = sorted(pedido)
    with datos.transaccion() as cur:
        filas = cur.execute(f"""
            SELECT id, nombre, costo, precio, stock, stock_minimo FROM t_productos
            WHERE activo = 1 AND id IN ({_marcadores(len(ids))}) ORDER BY id FOR UPDATE""",
            tuple(ids)).fetchall()
        if len(filas) != len(ids):
            raise TiendaError("Un producto de la venta ya no está disponible. Recarga la pantalla.")
        total = costo_total = 0
        lineas = []
        for f in filas:                      # precios y costos salen de la base, no del navegador
            cant = pedido[int(f["id"])]
            if cant > int(f["stock"]):
                raise TiendaError(f"«{f['nombre']}» solo tiene {int(f['stock'])} en stock.")
            total += cant * int(f["precio"])
            costo_total += cant * int(f["costo"])
            lineas.append((f, cant))
        desc = _descuento(descuento, total)
        total -= desc
        metodo2, monto2 = None, 0
        if metodo == "Efectivo":
            if recibido <= 0:
                raise TiendaError("Escribe el efectivo recibido.")
            if recibido < total:      # pago mixto: el resto va por otro método
                if resto not in ("Nequi", "Tarjeta"):
                    raise TiendaError("El efectivo no alcanza: elige con qué se paga el resto.")
                metodo2, monto2 = resto, total - recibido
        cambio = recibido - total if metodo == "Efectivo" and recibido > total else 0

        cur.execute("""INSERT INTO t_ventas (id, metodo, total, costo_total, recibido, cambio, usuario_id, usuario_nombre,
                                             metodo2, monto_metodo2, descuento)
                       VALUES (t_seq_ventas.NEXTVAL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (metodo, total, costo_total, recibido, cambio, usuario["id"], usuario["nombre"][:100],
                     metodo2, monto2, desc))
        vid = int(cur.execute("SELECT t_seq_ventas.CURRVAL AS id FROM dual").fetchone()["id"])
        cur.executemany("UPDATE t_productos SET stock = stock - %s WHERE id = %s",
                        [(c, int(f["id"])) for f, c in lineas])
        cur.executemany("""INSERT INTO t_venta_items (venta_id, producto_id, nombre, cantidad, precio, costo)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        [(vid, int(f["id"]), f["nombre"], c, int(f["precio"]), int(f["costo"])) for f, c in lineas])
        cur.executemany("""INSERT INTO t_movimientos
                             (producto_id, tipo, cantidad, stock_resultante, venta_id, usuario_id)
                           VALUES (%s, 'VENTA', %s, %s, %s, %s)""",
                        [(int(f["id"]), -c, int(f["stock"]) - c, vid, usuario["id"]) for f, c in lineas])

    bajos = [{"nombre": f["nombre"], "stock": int(f["stock"]) - c}
             for f, c in lineas if int(f["stock"]) - c <= int(f["stock_minimo"])]
    return {
        "venta": {"id": vid, "metodo": metodo, "total": total, "metodo2": metodo2, "monto2": monto2,
                  "descuento": desc,
                  "items": [{"nombre": f["nombre"], "cant": c, "precio": int(f["precio"])} for f, c in lineas]},
        "devuelta": cambio, "bajos": bajos,
        "stocks": [{"id": int(f["id"]), "stock": int(f["stock"]) - c} for f, c in lineas],
    }


def listar_ventas(limite=60):
    ventas = datos.fetchall(f"""
        SELECT id, fecha, metodo, metodo2, monto_metodo2, total, descuento, usuario_nombre, anulada, motivo_anulacion
        FROM t_ventas ORDER BY id DESC FETCH FIRST {int(limite)} ROWS ONLY""")
    if not ventas:
        return []
    ids = [int(v["id"]) for v in ventas]
    items = datos.fetchall(f"""
        SELECT venta_id, nombre, cantidad, precio FROM t_venta_items
        WHERE venta_id IN ({_marcadores(len(ids))}) ORDER BY id""", tuple(ids))
    por_venta = {}
    for it in items:
        por_venta.setdefault(int(it["venta_id"]), []).append(
            {"nombre": it["nombre"], "cant": int(it["cantidad"]), "precio": int(it["precio"])})
    return [{"id": int(v["id"]), "fecha": v["fecha"].isoformat() if v["fecha"] else None,
             "metodo": v["metodo"], "metodo2": v["metodo2"], "total": int(v["total"]),
             "descuento": int(v["descuento"]), "cajero": v["usuario_nombre"],
             "anulada": int(v["anulada"]) == 1, "motivo": v["motivo_anulacion"],
             "items": por_venta.get(int(v["id"]), [])} for v in ventas]


def obtener_venta(vid):
    v = datos.fetchone("""SELECT id, fecha, metodo, metodo2, monto_metodo2, total, descuento, recibido, cambio,
                                 usuario_nombre, anulada FROM t_ventas WHERE id = %s""", (vid,))
    if not v:
        raise TiendaError("La venta no existe.")
    items = datos.fetchall(
        "SELECT nombre, cantidad, precio FROM t_venta_items WHERE venta_id = %s ORDER BY id", (vid,))
    return v, items


def anular_venta(vid, motivo, usuario):
    motivo = " ".join(str(motivo or "").split())
    if not motivo or len(motivo) > 500:
        raise TiendaError("El motivo es obligatorio (máximo 500 caracteres).")
    with datos.transaccion() as cur:
        venta = cur.execute("SELECT anulada FROM t_ventas WHERE id = %s FOR UPDATE", (vid,)).fetchone()
        if not venta:
            raise TiendaError("La venta no existe.")
        if int(venta["anulada"]) == 1:
            raise TiendaError("Esa venta ya estaba anulada.")
        items = cur.execute("SELECT producto_id, cantidad FROM t_venta_items WHERE venta_id = %s", (vid,)).fetchall()
        pids = sorted({int(i["producto_id"]) for i in items})
        stock = {int(f["id"]): int(f["stock"]) for f in cur.execute(
            f"SELECT id, stock FROM t_productos WHERE id IN ({_marcadores(len(pids))}) ORDER BY id FOR UPDATE",
            tuple(pids)).fetchall()}
        movimientos, cambios = [], []
        for i in items:
            pid, cant = int(i["producto_id"]), int(i["cantidad"])
            stock[pid] += cant
            cambios.append((cant, pid))
            movimientos.append((pid, cant, stock[pid], vid, usuario["id"]))
        cur.executemany("UPDATE t_productos SET stock = stock + %s WHERE id = %s", cambios)
        cur.executemany("""INSERT INTO t_movimientos
                             (producto_id, tipo, cantidad, stock_resultante, venta_id, usuario_id, nota)
                           VALUES (%s, 'ANULACION', %s, %s, %s, %s, 'Venta anulada: el producto regresa al stock')""",
                        movimientos)
        cur.execute("""UPDATE t_ventas SET anulada = 1, motivo_anulacion = %s, fecha_anulacion = CURRENT_TIMESTAMP,
                              anulada_por = %s WHERE id = %s""", (motivo, usuario["nombre"][:100], vid))




# ═════════════════ Ganancias ═════════════════
def ganancias(periodo):
    if periodo not in ("hoy", "7", "30"):
        raise TiendaError("Periodo no válido.")
    dias = 1 if periodo == "hoy" else int(periodo)
    hoy_ = hoy()
    desde = hoy_ - timedelta(days=dias - 1)
    ant_desde = hoy_ - timedelta(days=2 * dias - 1)

    ventas = datos.fetchall("""
        SELECT fecha, total, costo_total, metodo, metodo2, monto_metodo2
        FROM t_ventas WHERE anulada = 0 AND fecha >= %s""", (ant_desde,))
    top = datos.fetchall("""
        SELECT i.nombre, SUM(i.cantidad) AS unidades, SUM(i.cantidad * (i.precio - i.costo)) AS ganancia
        FROM t_venta_items i JOIN t_ventas v ON v.id = i.venta_id
        WHERE v.anulada = 0 AND v.fecha >= %s
        GROUP BY i.nombre ORDER BY SUM(i.cantidad * (i.precio - i.costo)) DESC FETCH FIRST 6 ROWS ONLY""",
        (desde,))
    perdidas = datos.fetchall("""
        SELECT 'g' AS k, fecha, monto AS valor FROM t_caja_mov
        WHERE tipo = 'EGRESO' AND gasto = 1 AND anulado = 0 AND fecha >= %s
        UNION ALL
        SELECT 'm', fecha, cantidad * costo FROM t_mermas WHERE anulada = 0 AND fecha >= %s""",
        (desde, desde))
    quietos = datos.fetchall("""
        SELECT p.nombre, p.stock, p.stock * p.costo AS parado FROM t_productos p
        WHERE p.activo = 1 AND p.stock > 0 AND NOT EXISTS (
            SELECT 1 FROM t_venta_items i JOIN t_ventas v ON v.id = i.venta_id
            WHERE i.producto_id = p.id AND v.anulada = 0 AND v.fecha >= %s)
        ORDER BY parado DESC FETCH FIRST 8 ROWS ONLY""", (hoy_ - timedelta(days=29),))

    nuevo = lambda: {"n": 0, "ventas": 0, "costo": 0, "noEfectivo": 0, "gastos": 0, "mermas": 0}
    por_fecha, metodos, horas = {}, {}, {}
    ant = {"n": 0, "ventas": 0, "bruta": 0}
    for v in ventas:
        total, costo, monto2 = int(v["total"]), int(v["costo_total"]), int(v["monto_metodo2"])
        d = v["fecha"].date()
        if d < desde:                      # período anterior, solo para comparar
            ant["n"] += 1
            ant["ventas"] += total
            ant["bruta"] += total - costo
            continue
        x = por_fecha.setdefault(d, nuevo())
        x["n"] += 1
        x["ventas"] += total
        x["costo"] += costo
        x["noEfectivo"] += total if v["metodo"] != "Efectivo" else monto2
        metodos[v["metodo"]] = metodos.get(v["metodo"], 0) + total - monto2
        if v["metodo2"]:
            metodos[v["metodo2"]] = metodos.get(v["metodo2"], 0) + monto2
        h = horas.setdefault(v["fecha"].hour, {"n": 0, "ventas": 0})
        h["n"] += 1
        h["ventas"] += total
    for p in perdidas:
        por_fecha.setdefault(p["fecha"].date(), nuevo())["gastos" if p["k"] == "g" else "mermas"] += int(p["valor"])

    por_dia = []
    for i in range(dias):
        d = hoy_ - timedelta(days=dias - 1 - i)
        por_dia.append({"fecha": d.isoformat(), **por_fecha.get(d, nuevo())})
    return {"dias": dias, "porDia": por_dia,
            "top": [{"nombre": t["nombre"], "unidades": int(t["unidades"]), "ganancia": int(t["ganancia"])} for t in top],
            "anterior": ant,
            "metodos": [{"metodo": m, "valor": val} for m, val in sorted(metodos.items(), key=lambda kv: -kv[1])],
            "horas": [{"h": h, **horas[h]} for h in sorted(horas)],
            "quietos": [{"nombre": q["nombre"], "stock": int(q["stock"]), "parado": int(q["parado"])} for q in quietos]}



# ═════════════════ Preferencias de cálculo ═════════════════
def leer_ajustes():
    ajustes = dict(AJUSTES_BASE)
    for f in datos.fetchall("SELECT clave, valor FROM t_ajustes"):
        k, v = f["clave"], f["valor"]
        if k not in AJUSTES_BASE:
            continue
        base = AJUSTES_BASE[k]
        try:
            ajustes[k] = (v == "1") if isinstance(base, bool) else int(float(v)) if k == "gastosMes" else float(v)
        except (TypeError, ValueError):
            pass
    return ajustes


def guardar_ajustes(d):
    limpio = {
        "gastosMes": _entero(d.get("gastosMes", 0), "Gastos fijos del mes"),
        "comision": _porcentaje(d.get("comision"), "Comisión", 20),
        "impuesto": _porcentaje(d.get("impuesto"), "Impuesto", 30),
        "reserva": _porcentaje(d.get("reserva"), "Reinversión", 100),
    }
    for k in ("usarGastos", "usarComision", "usarImpuesto", "usarReserva"):
        limpio[k] = bool(d.get(k))
    filas = [(k, ("1" if v else "0") if isinstance(v, bool) else str(v)) for k, v in limpio.items()]
    with datos.transaccion() as cur:
        cur.execute("DELETE FROM t_ajustes")
        cur.executemany("INSERT INTO t_ajustes (clave, valor) VALUES (%s, %s)", filas)
    return limpio


def _porcentaje(valor, nombre, maximo):
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        raise TiendaError(f"{nombre}: escribe un número.")
    if n < 0 or n > maximo:
        raise TiendaError(f"{nombre}: debe estar entre 0 y {maximo}.")
    return round(n, 2)


# ═════════════════ Extras ═════════════════
def texto_pago(v):
    return v["metodo"] + (f" + {v['metodo2']}" if v.get("metodo2") else "")


def movimientos_producto(pid):
    filas = datos.fetchall("""
        SELECT fecha, tipo, cantidad, stock_resultante, venta_id FROM t_movimientos
        WHERE producto_id = %s ORDER BY id DESC FETCH FIRST 50 ROWS ONLY""", (pid,))
    return [{"fecha": f["fecha"].isoformat(), "tipo": f["tipo"], "cant": int(f["cantidad"]),
             "stock": int(f["stock_resultante"]), "venta": f["venta_id"]} for f in filas]


def cierre_hoy():
    """Caja abierta: todo lo ocurrido desde el último cierre (o desde las 00:00 si nunca se cerró)."""
    cierres = datos.fetchall("""
        SELECT creado, esperado, contado, diferencia, usuario_nombre FROM t_cierres
        ORDER BY id DESC FETCH FIRST 8 ROWS ONLY""")
    cond, par = (("fecha > %s", (cierres[0]["creado"],)) if cierres
                 else ("fecha >= TRUNC(CURRENT_TIMESTAMP)", ()))
    v = datos.fetchone(f"""
        SELECT NVL(SUM(CASE WHEN metodo = 'Efectivo' THEN total - monto_metodo2 END), 0) AS efectivo,
               NVL(SUM(CASE WHEN metodo = 'Efectivo' THEN monto_metodo2 ELSE total END), 0) AS otros
        FROM t_ventas WHERE anulada = 0 AND {cond}""", par)
    movs = datos.fetchall(f"""
        SELECT id, fecha, tipo, monto, motivo, gasto, usuario_nombre FROM t_caja_mov
        WHERE anulado = 0 AND {cond} ORDER BY id DESC""", par)
    suma = lambda t: sum(int(m["monto"]) for m in movs if m["tipo"] == t)
    base, ingresos, egresos, efectivo = suma("BASE"), suma("INGRESO"), suma("EGRESO"), int(v["efectivo"])
    return {"abierta": any(m["tipo"] == "BASE" for m in movs),
            "base": base, "efectivo": efectivo, "otros": int(v["otros"]),
            "ingresos": ingresos, "egresos": egresos,
            "esperado": base + efectivo + ingresos - egresos,
            "movs": [{"id": int(m["id"]), "fecha": m["fecha"].isoformat(), "tipo": m["tipo"],
                      "monto": int(m["monto"]), "motivo": m["motivo"], "gasto": int(m["gasto"]) == 1,
                      "usuario": m["usuario_nombre"]} for m in movs],
            "cierres": [{"fecha": c["creado"].isoformat(), "esperado": int(c["esperado"]),
                         "contado": int(c["contado"]), "diferencia": int(c["diferencia"]),
                         "usuario": c["usuario_nombre"]} for c in cierres]}


def guardar_cierre(contado, usuario):
    contado = _entero(contado, "Efectivo contado")
    c = cierre_hoy()
    if not c["abierta"]:
        raise TiendaError("No hay una caja abierta para cerrar.")
    datos.execute_rowcount("""
        INSERT INTO t_cierres (fecha, esperado, contado, diferencia, usuario_nombre,
                               base, efectivo, ingresos, egresos, otros)
        VALUES (TRUNC(CURRENT_TIMESTAMP), %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (c["esperado"], contado, contado - c["esperado"], usuario["nombre"][:100],
         c["base"], c["efectivo"], c["ingresos"], c["egresos"], c["otros"]))


# ═════════════════ Movimientos de caja ═════════════════
def registrar_mov(d, usuario):
    tipo = d.get("tipo")
    if tipo not in ("BASE", "INGRESO", "EGRESO"):
        raise TiendaError("Tipo de movimiento no válido.")
    monto = _entero(d.get("monto"), "Valor", minimo=1, maximo=100_000_000)
    motivo = " ".join(str(d.get("motivo") or "").split())[:200]
    if tipo == "BASE":
        motivo = motivo or "Base inicial"
    if not motivo:
        raise TiendaError("Escribe el motivo.")
    gasto = 1 if tipo == "EGRESO" and d.get("gasto") else 0
    abierta = caja_abierta()
    if tipo == "BASE" and abierta:
        raise TiendaError("La caja ya tiene base. Quítala si te equivocaste, o cierra la caja para abrir otra.")
    if tipo != "BASE" and not abierta:
        raise TiendaError("Primero abre la caja poniendo la base.")
    datos.execute_rowcount(
        "INSERT INTO t_caja_mov (tipo, monto, motivo, gasto, usuario_nombre) VALUES (%s, %s, %s, %s, %s)",
        (tipo, monto, motivo, gasto, usuario["nombre"][:100]))


def quitar_mov(mid):
    """Solo los movimientos de la caja abierta; los ya cerrados no se tocan."""
    n = datos.execute_rowcount(
        "UPDATE t_caja_mov SET anulado = 1 WHERE id = %s AND anulado = 0 "
        "AND fecha > NVL((SELECT MAX(creado) FROM t_cierres), TIMESTAMP '1900-01-01 00:00:00')", (mid,))
    if not n:
        raise TiendaError("No se puede quitar: ya fue cerrado o no existe.")


# ═════════════════ Mermas (bajas de inventario) ═════════════════
def registrar_merma(pid, cantidad, motivo, nota, usuario):
    cantidad = _entero(cantidad, "Cantidad", minimo=1, maximo=1_000_000)
    if motivo not in MOTIVOS_MERMA:
        raise TiendaError("Elige el motivo de la baja.")
    nota = " ".join(str(nota or "").split())[:200] or None
    with datos.transaccion() as cur:
        p = cur.execute("SELECT nombre, costo, stock FROM t_productos WHERE id = %s AND activo = 1 FOR UPDATE",
                        (pid,)).fetchone()
        if not p:
            raise TiendaError("El producto ya no existe.")
        if cantidad > int(p["stock"]):
            raise TiendaError(f"«{p['nombre']}» solo tiene {int(p['stock'])} en stock.")
        nuevo = int(p["stock"]) - cantidad
        cur.execute("UPDATE t_productos SET stock = %s WHERE id = %s", (nuevo, pid))
        cur.execute("""INSERT INTO t_mermas (producto_id, nombre, cantidad, costo, motivo, nota, usuario_nombre)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (pid, p["nombre"], cantidad, int(p["costo"]), motivo, nota, usuario["nombre"][:100]))
        cur.execute("""INSERT INTO t_movimientos (producto_id, tipo, cantidad, stock_resultante, usuario_id, nota)
                       VALUES (%s, 'MERMA', %s, %s, %s, %s)""", (pid, -cantidad, nuevo, usuario["id"], motivo))


def listar_mermas():
    filas = datos.fetchall("""
        SELECT id, fecha, nombre, cantidad, costo, motivo, nota, anulada FROM t_mermas
        ORDER BY id DESC FETCH FIRST 40 ROWS ONLY""")
    return [{"id": int(f["id"]), "fecha": f["fecha"].isoformat(), "nombre": f["nombre"],
             "cant": int(f["cantidad"]), "costo": int(f["costo"]), "motivo": f["motivo"],
             "nota": f["nota"], "anulada": int(f["anulada"]) == 1} for f in filas]


def anular_merma(mid, usuario):
    with datos.transaccion() as cur:
        m = cur.execute("SELECT producto_id, cantidad, anulada FROM t_mermas WHERE id = %s FOR UPDATE",
                        (mid,)).fetchone()
        if not m:
            raise TiendaError("La baja no existe.")
        if int(m["anulada"]) == 1:
            raise TiendaError("Esa baja ya estaba anulada.")
        pid, cant = int(m["producto_id"]), int(m["cantidad"])
        nuevo = int(cur.execute("SELECT stock FROM t_productos WHERE id = %s FOR UPDATE",
                                (pid,)).fetchone()["stock"]) + cant
        cur.execute("UPDATE t_productos SET stock = %s WHERE id = %s", (nuevo, pid))
        cur.execute("UPDATE t_mermas SET anulada = 1 WHERE id = %s", (mid,))
        cur.execute("""INSERT INTO t_movimientos (producto_id, tipo, cantidad, stock_resultante, usuario_id, nota)
                       VALUES (%s, 'ANULACION', %s, %s, %s, 'Baja anulada: el producto regresa al stock')""",
                    (pid, cant, nuevo, usuario["id"]))


# ═════════════════ Reporte por fechas ═════════════════
def reporte(desde, hasta):
    try:
        d0, d1 = date.fromisoformat(desde or ""), date.fromisoformat(hasta or "")
    except ValueError:
        raise TiendaError("Escribe las dos fechas del reporte.")
    if d1 < d0 or (d1 - d0).days > 366:
        raise TiendaError("Rango no válido (máximo 1 año).")
    par = (d0, d1 + timedelta(days=1))
    ventas = datos.fetchall("""
        SELECT fecha, total, descuento, costo_total, metodo, metodo2, monto_metodo2 FROM t_ventas
        WHERE anulada = 0 AND fecha >= %s AND fecha < %s""", par)
    movs = datos.fetchall("""
        SELECT fecha, tipo, monto, motivo, gasto, usuario_nombre FROM t_caja_mov
        WHERE anulado = 0 AND fecha >= %s AND fecha < %s ORDER BY fecha""", par)
    mermas = datos.fetchall("""
        SELECT fecha, nombre, cantidad, costo, motivo FROM t_mermas
        WHERE anulada = 0 AND fecha >= %s AND fecha < %s ORDER BY fecha""", par)
    prods = datos.fetchall("""
        SELECT i.nombre, SUM(i.cantidad) AS unidades, SUM(i.cantidad * i.precio) AS vendido,
               SUM(i.cantidad * (i.precio - i.costo)) AS ganancia
        FROM t_venta_items i JOIN t_ventas v ON v.id = i.venta_id
        WHERE v.anulada = 0 AND v.fecha >= %s AND v.fecha < %s
        GROUP BY i.nombre ORDER BY SUM(i.cantidad) DESC""", par)
    cierres = datos.fetchall("""
        SELECT creado, contado, diferencia FROM t_cierres WHERE creado >= %s AND creado < %s""", par)

    dias = {}
    dia = lambda d: dias.setdefault(d, {"n": 0, "ventas": 0, "desc": 0, "costo": 0, "Efectivo": 0, "Nequi": 0,
                                        "Tarjeta": 0, "ing": 0, "egr": 0, "mer": 0, "contado": None, "dif": None})
    for v in ventas:
        x, total, m2 = dia(v["fecha"].date()), int(v["total"]), int(v["monto_metodo2"])
        x["n"] += 1
        x["ventas"] += total
        x["desc"] += int(v["descuento"])
        x["costo"] += int(v["costo_total"])
        x[v["metodo"]] += total - m2
        if v["metodo2"]:
            x[v["metodo2"]] += m2
    for m in movs:
        if m["tipo"] != "BASE":
            dia(m["fecha"].date())["ing" if m["tipo"] == "INGRESO" else "egr"] += int(m["monto"])
    for m in mermas:
        dia(m["fecha"].date())["mer"] += int(m["cantidad"]) * int(m["costo"])
    for c in cierres:
        x = dia(c["creado"].date())
        x["contado"] = (x["contado"] or 0) + int(c["contado"])
        x["dif"] = (x["dif"] or 0) + int(c["diferencia"])
    filas = [{"fecha": d.isoformat(), **dias[d]} for d in sorted(dias)]
    tot = {k: sum(f[k] for f in filas) for k in ("n", "ventas", "desc", "costo", "Efectivo", "Nequi", "Tarjeta", "ing", "egr", "mer")}
    etiqueta = {"BASE": "Base", "INGRESO": "Entrada", "EGRESO": "Salida"}
    return {
        "desde": d0.isoformat(), "hasta": d1.isoformat(), "dias": filas, "tot": tot,
        "movs": [(m["fecha"].strftime("%Y-%m-%d"), m["fecha"].strftime("%H:%M"),
                  etiqueta[m["tipo"]] + (" (gasto)" if int(m["gasto"]) else ""), m["motivo"],
                  int(m["monto"]), m["usuario_nombre"]) for m in movs],
        "mermas": [(m["fecha"].strftime("%Y-%m-%d"), m["nombre"], int(m["cantidad"]), int(m["costo"]),
                    int(m["cantidad"]) * int(m["costo"]), m["motivo"]) for m in mermas],
        "productos": [(p["nombre"], int(p["unidades"]), int(p["vendido"]), int(p["ganancia"])) for p in prods],
    }