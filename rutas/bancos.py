"""Bancos: saldos por banco y bolsillo, traslados caja <-> banco y movimientos manuales."""
import oracledb
from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for

import db
from auth import login_required, permiso_requerido, permisos_actuales
from rutas.alumnos import _auditar
from rutas.caja import caja_abierta
from servicios.bancos import (BancoError, catalogo_destinos, exigir_saldo, movimiento_manual,
                              parsear_destino, registrar, validar_destino)
from servicios.recibos import numero_recibo
from utils import parsear_pesos

bp = Blueprint("bancos", __name__, url_prefix="/bancos")
MAX_BANCO = 999_999_999_999


def _volver(**args):
    return redirect(url_for("bancos.inicio", **args))


def _duplicado(error) -> bool:
    return getattr(error.args[0] if error.args else None, "code", None) == 1


def _valor_form(nombre="valor"):
    valor = parsear_pesos(request.form.get(nombre, "").strip())
    if valor is None or valor <= 0 or valor > MAX_BANCO:
        raise BancoError("El valor debe ser un entero en pesos mayor a $0.")
    return valor


def _concepto_form(obligatorio=True):
    concepto = " ".join(request.form.get("concepto", "").split())
    if (obligatorio and not concepto) or len(concepto) > 200:
        raise BancoError("El concepto es obligatorio y admite hasta 200 caracteres.")
    return concepto


def _efectivo_caja(cur, caja) -> int:
    fila = cur.execute("""
        SELECT c.monto_apertura
               + NVL((SELECT SUM(p.valor) FROM pagos p WHERE p.caja_id = c.id
                      AND p.metodo_pago = 'Efectivo' AND p.concepto <> 'Abono histórico previo'
                      AND p.anulado = 0), 0)
               + NVL((SELECT SUM(i.valor) FROM ingresos_caja i WHERE i.caja_id = c.id AND i.anulado = 0), 0)
               - NVL((SELECT SUM(s.valor) FROM salidas_caja s WHERE s.caja_id = c.id AND s.anulado = 0), 0)
               AS esperado
        FROM cajas c WHERE c.id = %s
    """, (caja["id"],)).fetchone()
    return int(fila["esperado"])


# ───────── Catálogo para selectores (lo usan Pagos y Caja) ─────────
@bp.route("/destinos")
@login_required
def destinos():
    if not permisos_actuales() & {"registrar_pagos", "ver_bancos", "gestionar_caja"}:
        abort(403)
    try:
        return jsonify(ok=True, destinos=catalogo_destinos())
    except Exception:
        current_app.logger.exception("No se pudo consultar el catálogo de bancos")
        return jsonify(ok=False, error="No se pudieron cargar los bancos."), 500


# ───────── Página ─────────
@bp.route("")
@login_required
@permiso_requerido("ver_bancos")
def inicio():
    error, bancos, movimientos, destinos_lista, categorias = None, [], [], [], []
    caja_ok, total = False, 0
    filtro = request.args.get("banco", "").strip()
    try:
        filas = db.fetchall("""
            SELECT b.id AS banco_id, b.nombre AS banco, b.activo AS banco_activo,
                   p.id AS bolsillo_id, p.nombre AS bolsillo, p.activo AS bolsillo_activo
            FROM bancos b LEFT JOIN bolsillos p ON p.banco_id = b.id
            ORDER BY b.nombre, p.nombre
        """)
        saldos = {(int(f["banco_id"]), int(f["bolsillo_id"] or 0)): int(f["saldo"]) for f in db.fetchall("""
            SELECT banco_id, bolsillo_id,
                   SUM(CASE WHEN tipo = 'ENTRADA' THEN valor ELSE -valor END) AS saldo
            FROM movimientos_banco WHERE anulado = 0 GROUP BY banco_id, bolsillo_id
        """)}
        por_id = {}
        for f in filas:
            bid = int(f["banco_id"])
            b = por_id.setdefault(bid, {"id": bid, "nombre": f["banco"], "activo": bool(f["banco_activo"]),
                                        "general": saldos.get((bid, 0), 0), "bolsillos": []})
            if f["bolsillo_id"]:
                pid = int(f["bolsillo_id"])
                b["bolsillos"].append({"id": pid, "nombre": f["bolsillo"], "activo": bool(f["bolsillo_activo"]),
                                       "saldo": saldos.get((bid, pid), 0)})
        for b in por_id.values():
            b["total"] = b["general"] + sum(x["saldo"] for x in b["bolsillos"])
        bancos = list(por_id.values())
        total = sum(b["total"] for b in bancos)

        filtro_sql, params = "", ()
        if filtro.isdecimal():
            filtro_sql, params = "WHERE m.banco_id = %s", (int(filtro),)
        movimientos = db.fetchall(f"""
            SELECT m.id, m.fecha, b.nombre AS banco, p.nombre AS bolsillo, m.tipo, m.valor, m.concepto,
                   m.origen, m.referencia, m.categoria, m.anulado, m.motivo_anulacion, u.nombre AS usuario
            FROM movimientos_banco m
            JOIN bancos b ON b.id = m.banco_id
            LEFT JOIN bolsillos p ON p.id = m.bolsillo_id
            LEFT JOIN usuarios u ON u.id = m.usuario_id
            {filtro_sql}
            ORDER BY m.fecha DESC, m.id DESC
            FETCH FIRST 100 ROWS ONLY
        """, params)
        destinos_lista = catalogo_destinos()
        categorias = db.fetchall("SELECT categoria FROM categorias_caja WHERE activo = 1 ORDER BY categoria")
        caja_ok = bool(db.fetchone("SELECT id FROM cajas WHERE usuario_id = %s AND estado = 'ABIERTA'",
                                   (session["uid"],)))
    except Exception:
        error = "No se pudo consultar los bancos. ¿Ya se aplicó la migración 013?"
        current_app.logger.exception("No se pudo consultar los bancos")
    return render_template("bancos.html", nav="bancos", bancos=bancos, total=total, movimientos=movimientos,
                           destinos=destinos_lista, categorias=categorias, caja_abierta=caja_ok,
                           filtro=filtro, error=error,
                           recibo_nuevo=request.args.get("recibo_nuevo", "").strip()[:50])


# ───────── Bancos y bolsillos ─────────
@bp.route("/crear", methods=["POST"])
@login_required
@permiso_requerido("gestionar_bancos")
def crear():
    nombre = " ".join(request.form.get("nombre", "").split())
    if not nombre or len(nombre) > 60:
        flash("El nombre del banco es obligatorio (máximo 60 caracteres).", "error")
        return _volver()
    try:
        db.execute("INSERT INTO bancos (nombre) VALUES (%s)", (nombre,))
    except oracledb.IntegrityError as e:
        if _duplicado(e):
            flash("Ya existe un banco con ese nombre.", "error")
        else:
            current_app.logger.exception("Error de integridad creando banco")
            flash("No se pudo crear el banco.", "error")
    except Exception:
        current_app.logger.exception("Error creando banco")
        flash("No se pudo crear el banco.", "error")
    else:
        flash(f"Banco «{nombre}» creado.", "ok")
    return _volver()


@bp.route("/<int:banco_id>/bolsillos", methods=["POST"])
@login_required
@permiso_requerido("gestionar_bancos")
def crear_bolsillo(banco_id):
    nombre = " ".join(request.form.get("nombre", "").split())
    if not nombre or len(nombre) > 60:
        flash("El nombre del bolsillo es obligatorio (máximo 60 caracteres).", "error")
        return _volver()
    try:
        db.execute("INSERT INTO bolsillos (banco_id, nombre) VALUES (%s, %s)", (banco_id, nombre))
    except oracledb.IntegrityError as e:
        if _duplicado(e):
            flash("Ese banco ya tiene un bolsillo con ese nombre.", "error")
        else:
            current_app.logger.exception("Error de integridad creando bolsillo")
            flash("No se pudo crear el bolsillo.", "error")
    except Exception:
        current_app.logger.exception("Error creando bolsillo")
        flash("No se pudo crear el bolsillo.", "error")
    else:
        flash(f"Bolsillo «{nombre}» creado.", "ok")
    return _volver()


@bp.route("/<int:banco_id>/estado", methods=["POST"])
@login_required
@permiso_requerido("gestionar_bancos")
def estado_banco(banco_id):
    activo = 1 if request.form.get("activo") == "1" else 0
    try:
        with db.transaccion() as cur:
            if not cur.execute("SELECT id FROM bancos WHERE id = %s FOR UPDATE", (banco_id,)).fetchone():
                flash("El banco ya no existe.", "error")
                return _volver()
            if not activo:
                s = cur.execute(
                    "SELECT NVL(SUM(CASE WHEN tipo = 'ENTRADA' THEN valor ELSE -valor END), 0) AS s "
                    "FROM movimientos_banco WHERE anulado = 0 AND banco_id = %s", (banco_id,)).fetchone()["s"]
                if int(s) != 0:
                    flash("No puedes desactivar un banco con saldo. Traslada el dinero primero.", "error")
                    return _volver()
            cur.execute("UPDATE bancos SET activo = %s WHERE id = %s", (activo, banco_id))
    except Exception:
        current_app.logger.exception("Error cambiando estado del banco %s", banco_id)
        flash("No se pudo cambiar el estado del banco.", "error")
        return _volver()
    flash("Banco activado." if activo else "Banco desactivado.", "ok")
    return _volver()


@bp.route("/bolsillos/<int:bolsillo_id>/estado", methods=["POST"])
@login_required
@permiso_requerido("gestionar_bancos")
def estado_bolsillo(bolsillo_id):
    activo = 1 if request.form.get("activo") == "1" else 0
    try:
        with db.transaccion() as cur:
            b = cur.execute("SELECT id, banco_id FROM bolsillos WHERE id = %s FOR UPDATE", (bolsillo_id,)).fetchone()
            if not b:
                flash("El bolsillo ya no existe.", "error")
                return _volver()
            if not activo:
                s = cur.execute(
                    "SELECT NVL(SUM(CASE WHEN tipo = 'ENTRADA' THEN valor ELSE -valor END), 0) AS s "
                    "FROM movimientos_banco WHERE anulado = 0 AND bolsillo_id = %s", (bolsillo_id,)).fetchone()["s"]
                if int(s) != 0:
                    flash("No puedes desactivar un bolsillo con saldo. Traslada el dinero primero.", "error")
                    return _volver()
            cur.execute("UPDATE bolsillos SET activo = %s WHERE id = %s", (activo, bolsillo_id))
    except Exception:
        current_app.logger.exception("Error cambiando estado del bolsillo %s", bolsillo_id)
        flash("No se pudo cambiar el estado del bolsillo.", "error")
        return _volver()
    flash("Bolsillo activado." if activo else "Bolsillo desactivado.", "ok")
    return _volver()


# ───────── Editar y borrar bancos y bolsillos ─────────
def _nombre_form(etiqueta):
    nombre = " ".join(request.form.get("nombre", "").split())
    if not nombre or len(nombre) > 60:
        raise BancoError(f"El nombre del {etiqueta} es obligatorio (máximo 60 caracteres).")
    return nombre


@bp.route("/<int:banco_id>/editar", methods=["POST"])
@login_required
@permiso_requerido("gestionar_bancos")
def editar_banco(banco_id):
    try:
        nombre = _nombre_form("banco")
        with db.transaccion() as cur:
            antes = cur.execute("SELECT id, nombre FROM bancos WHERE id = %s FOR UPDATE", (banco_id,)).fetchone()
            if not antes:
                raise BancoError("El banco ya no existe.")
            cur.execute("UPDATE bancos SET nombre = %s WHERE id = %s", (nombre, banco_id))
            _auditar(cur, "BANCO", banco_id, "EDICION", session["uid"],
                     {"nombre": antes["nombre"]}, {"nombre": nombre})
    except BancoError as e:
        flash(str(e), "error")
        return _volver()
    except oracledb.IntegrityError as e:
        flash("Ya existe un banco con ese nombre." if _duplicado(e) else "No se pudo editar el banco.", "error")
        return _volver()
    except Exception:
        current_app.logger.exception("Error editando banco %s", banco_id)
        flash("No se pudo editar el banco.", "error")
        return _volver()
    flash("Banco actualizado.", "ok")
    return _volver()


@bp.route("/bolsillos/<int:bolsillo_id>/editar", methods=["POST"])
@login_required
@permiso_requerido("gestionar_bancos")
def editar_bolsillo(bolsillo_id):
    try:
        nombre = _nombre_form("bolsillo")
        with db.transaccion() as cur:
            antes = cur.execute("SELECT id, nombre FROM bolsillos WHERE id = %s FOR UPDATE",
                                (bolsillo_id,)).fetchone()
            if not antes:
                raise BancoError("El bolsillo ya no existe.")
            cur.execute("UPDATE bolsillos SET nombre = %s WHERE id = %s", (nombre, bolsillo_id))
            _auditar(cur, "BANCO_BOLSILLO", bolsillo_id, "EDICION", session["uid"],
                     {"nombre": antes["nombre"]}, {"nombre": nombre})
    except BancoError as e:
        flash(str(e), "error")
        return _volver()
    except oracledb.IntegrityError as e:
        flash("Ese banco ya tiene un bolsillo con ese nombre." if _duplicado(e)
              else "No se pudo editar el bolsillo.", "error")
        return _volver()
    except Exception:
        current_app.logger.exception("Error editando bolsillo %s", bolsillo_id)
        flash("No se pudo editar el bolsillo.", "error")
        return _volver()
    flash("Bolsillo actualizado.", "ok")
    return _volver()


@bp.route("/<int:banco_id>/borrar", methods=["POST"])
@login_required
@permiso_requerido("gestionar_bancos")
def borrar_banco(banco_id):
    try:
        with db.transaccion() as cur:
            banco = cur.execute("SELECT id, nombre FROM bancos WHERE id = %s FOR UPDATE", (banco_id,)).fetchone()
            if not banco:
                raise BancoError("El banco ya no existe.")
            usados = cur.execute("SELECT COUNT(*) AS n FROM movimientos_banco WHERE banco_id = %s",
                                 (banco_id,)).fetchone()["n"]
            if int(usados):
                raise BancoError("Este banco ya tiene movimientos y no se puede borrar sin perder el historial. "
                                 "Usa «Desactivar» para esconderlo (primero deja su saldo en $0).")
            cur.execute("DELETE FROM bolsillos WHERE banco_id = %s", (banco_id,))
            cur.execute("DELETE FROM bancos WHERE id = %s", (banco_id,))
            _auditar(cur, "BANCO", banco_id, "BORRADO", session["uid"], {"nombre": banco["nombre"]}, None)
    except BancoError as e:
        flash(str(e), "error")
        return _volver()
    except Exception:
        current_app.logger.exception("Error borrando banco %s", banco_id)
        flash("No se pudo borrar el banco. ¿Ya se aplicó la migración 014?", "error")
        return _volver()
    flash(f"Banco «{banco['nombre']}» borrado.", "ok")
    return _volver()


@bp.route("/bolsillos/<int:bolsillo_id>/borrar", methods=["POST"])
@login_required
@permiso_requerido("gestionar_bancos")
def borrar_bolsillo(bolsillo_id):
    try:
        with db.transaccion() as cur:
            b = cur.execute("SELECT id, banco_id, nombre FROM bolsillos WHERE id = %s FOR UPDATE",
                            (bolsillo_id,)).fetchone()
            if not b:
                raise BancoError("El bolsillo ya no existe.")
            usados = cur.execute("SELECT COUNT(*) AS n FROM movimientos_banco WHERE bolsillo_id = %s",
                                 (bolsillo_id,)).fetchone()["n"]
            if int(usados):
                raise BancoError("Este bolsillo ya tiene movimientos y no se puede borrar sin perder el historial. "
                                 "Usa «Desactivar» para esconderlo (primero deja su saldo en $0).")
            cur.execute("DELETE FROM bolsillos WHERE id = %s", (bolsillo_id,))
            _auditar(cur, "BANCO_BOLSILLO", bolsillo_id, "BORRADO", session["uid"],
                     {"nombre": b["nombre"], "banco_id": b["banco_id"]}, None)
    except BancoError as e:
        flash(str(e), "error")
        return _volver()
    except Exception:
        current_app.logger.exception("Error borrando bolsillo %s", bolsillo_id)
        flash("No se pudo borrar el bolsillo. ¿Ya se aplicó la migración 014?", "error")
        return _volver()
    flash(f"Bolsillo «{b['nombre']}» borrado.", "ok")
    return _volver()


# ───────── Ingresos y egresos directos en un banco ─────────
@bp.route("/movimiento", methods=["POST"])
@login_required
@permiso_requerido("gestionar_bancos")
def movimiento():
    tipo = request.form.get("tipo", "")
    categoria = " ".join(request.form.get("categoria", "").upper().split()) or None
    try:
        if tipo not in ("ENTRADA", "SALIDA"):
            raise BancoError("Tipo de movimiento no válido.")
        destino = parsear_destino(request.form.get("destino"))
        if not destino:
            raise BancoError("Elige el banco o bolsillo.")
        valor, concepto = _valor_form(), _concepto_form()
        with db.transaccion() as cur:
            if categoria and not cur.execute(
                    "SELECT categoria FROM categorias_caja WHERE categoria = %s AND activo = 1",
                    (categoria,)).fetchone():
                raise BancoError("Selecciona una categoría activa o deja el campo sin categoría.")
            recibo = movimiento_manual(cur, tipo, destino, valor, concepto, categoria, session["uid"])
    except BancoError as e:
        flash(str(e), "error")
        return _volver()
    except Exception:
        current_app.logger.exception("Error registrando movimiento de banco")
        flash("No se pudo registrar el movimiento. Intenta de nuevo.", "error")
        return _volver()
    flash(f"{'Ingreso' if tipo == 'ENTRADA' else 'Egreso'} registrado en el banco. Referencia {recibo}.", "ok")
    return _volver()


# ───────── Traslados: caja <-> banco y banco <-> banco ─────────
def _punta(texto):
    texto = (texto or "").strip()
    if texto == "caja":
        return "caja"
    destino = parsear_destino(texto)
    if not destino:
        raise BancoError("Elige de dónde sale y a dónde va el dinero.")
    return destino


@bp.route("/traslado", methods=["POST"])
@login_required
@permiso_requerido("gestionar_bancos")
def traslado():
    uid = session["uid"]
    imprimir = None
    try:
        origen, destino = _punta(request.form.get("desde")), _punta(request.form.get("hacia"))
        if origen == destino:
            raise BancoError("El origen y el destino deben ser distintos.")
        valor = _valor_form()
        with db.transaccion() as cur:
            caja = None
            if "caja" in (origen, destino):
                caja = caja_abierta(cur, uid)
                if not caja:
                    raise BancoError("Abre tu caja antes de trasladar dinero desde o hacia la caja.")
            validados = {}
            puntas = {p for p in (origen, destino) if p != "caja"}
            for p in sorted(puntas, key=lambda x: (x[0], x[1] or 0)):   # mismo orden siempre: evita bloqueos cruzados
                validados[p] = validar_destino(cur, p, bloquear=True)

            if origen == "caja":
                if _efectivo_caja(cur, caja) < valor:
                    raise BancoError("No hay tanto efectivo en tu caja.")
                d = validados[destino]
                recibo = numero_recibo(cur)
                cur.execute(
                    "INSERT INTO salidas_caja (numero_recibo, concepto, valor, usuario_id, caja_id, es_traslado) "
                    "VALUES (%s, %s, %s, %s, %s, 1)",
                    (recibo, f"Traslado de caja a {d['texto']}"[:200], valor, uid, caja["id"]))
                registrar(cur, d, "ENTRADA", valor, f"Traslado desde la caja ({recibo})",
                          "TRASLADO_CAJA", recibo, uid)
                imprimir = recibo
            elif destino == "caja":
                d = validados[origen]
                exigir_saldo(cur, d, valor)
                recibo = numero_recibo(cur)
                cur.execute(
                    "INSERT INTO ingresos_caja (numero_recibo, concepto, valor, usuario_id, caja_id, es_traslado) "
                    "VALUES (%s, %s, %s, %s, %s, 1)",
                    (recibo, f"Traslado de {d['texto']} a la caja"[:200], valor, uid, caja["id"]))
                registrar(cur, d, "SALIDA", valor, f"Traslado hacia la caja ({recibo})",
                          "TRASLADO_CAJA", recibo, uid)
                imprimir = recibo
            else:
                o, t = validados[origen], validados[destino]
                exigir_saldo(cur, o, valor)
                recibo = numero_recibo(cur)
                registrar(cur, o, "SALIDA", valor, f"Traslado a {t['texto']}", "TRASLADO_BANCO", recibo, uid)
                registrar(cur, t, "ENTRADA", valor, f"Traslado desde {o['texto']}", "TRASLADO_BANCO", recibo, uid)
    except BancoError as e:
        flash(str(e), "error")
        return _volver()
    except Exception:
        current_app.logger.exception("Error registrando traslado")
        flash("No se pudo registrar el traslado. Intenta de nuevo.", "error")
        return _volver()
    flash(f"Traslado registrado. Referencia {recibo}.", "ok")
    return _volver(recibo_nuevo=imprimir) if imprimir else _volver()


# ───────── Anular un movimiento manual ─────────
@bp.route("/movimientos/<int:mov_id>/anular", methods=["POST"])
@login_required
@permiso_requerido("gestionar_bancos")
def anular(mov_id):
    motivo = " ".join(request.form.get("motivo", "").split())
    if not motivo or len(motivo) > 500:
        flash("El motivo es obligatorio y admite hasta 500 caracteres.", "error")
        return _volver()
    try:
        with db.transaccion() as cur:
            m = cur.execute("""SELECT id, banco_id, bolsillo_id, tipo, valor, origen, anulado, concepto
                               FROM movimientos_banco WHERE id = %s FOR UPDATE""", (mov_id,)).fetchone()
            if not m:
                flash("El movimiento no existe.", "error")
                return _volver()
            if m["anulado"]:
                flash("Ese movimiento ya estaba anulado.", "error")
                return _volver()
            if m["origen"] != "MANUAL":
                flash("Solo se anulan movimientos manuales. Los pagos se anulan desde el alumno; "
                      "para corregir un traslado haz el traslado contrario.", "error")
                return _volver()
            cur.execute("SELECT id FROM bancos WHERE id = %s FOR UPDATE", (m["banco_id"],))
            if m["tipo"] == "ENTRADA":
                exigir_saldo(cur, {"banco_id": int(m["banco_id"]),
                                   "bolsillo_id": int(m["bolsillo_id"]) if m["bolsillo_id"] else None,
                                   "texto": "ese bolsillo"}, int(m["valor"]))
            cur.execute("UPDATE movimientos_banco SET anulado = 1, motivo_anulacion = %s WHERE id = %s",
                        (motivo, mov_id))
            _auditar(cur, "BANCO_MOV", mov_id, "ANULACION", session["uid"], dict(m), {"anulado": 1}, motivo)
    except BancoError as e:
        flash(f"No se puede anular: {e}", "error")
        return _volver()
    except Exception:
        current_app.logger.exception("Error anulando movimiento de banco %s", mov_id)
        flash("No se pudo anular el movimiento.", "error")
        return _volver()
    flash("Movimiento anulado.", "ok")
    return _volver()
