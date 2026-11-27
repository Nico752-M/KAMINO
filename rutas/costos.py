"""Costos por matrícula (estampillas, documentos, etc.) y ganancia por alumno."""
import oracledb
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

import db
from auth import login_required, permiso_requerido
from rutas.alumnos import _auditar
from servicios.matriculas import TIPOS_TARIFA, tipo_de_categoria
from utils import parsear_pesos

bp = Blueprint("costos", __name__)

TIPOS = TIPOS_TARIFA
VALOR_MAX = 999_999_999_999


# ───────────── Utilidades ─────────────

def _leer_costo():
    """Lee y valida concepto, valor y observaciones del formulario."""
    concepto = " ".join(request.form.get("concepto", "").split())
    valor = parsear_pesos(request.form.get("valor", "").strip())
    observaciones = " ".join(request.form.get("observaciones", "").split()) or None
    if not concepto or len(concepto) > 100:
        raise ValueError("El concepto es obligatorio y admite hasta 100 caracteres.")
    if valor is None or valor > VALOR_MAX:
        raise ValueError("El valor debe ser en pesos enteros, sin decimales ni signos.")
    if observaciones and len(observaciones) > 500:
        raise ValueError("Las observaciones admiten hasta 500 caracteres.")
    return concepto, valor, observaciones


def _tipo_y_categoria(categoria: str):
    """'Renovación - A2' -> ('RENOVACION', 'A2');  'Recategorización - A2' -> ('RECAT', 'A2');
    'A2' -> ('CURSO', 'A2')."""
    return tipo_de_categoria(categoria)


def _ir_cuenta(matricula_id):
    return redirect(url_for("costos.cuenta", matricula_id=matricula_id))


def _matricula_editable(cur, matricula_id):
    """Bloquea la matrícula. Devuelve (fila, mensaje_de_error)."""
    mat = cur.execute(
        "SELECT id, categoria, archivado FROM matriculas WHERE id = %s FOR UPDATE",
        (matricula_id,),
    ).fetchone()
    if not mat:
        return None, "No se encontró la matrícula."
    if mat["archivado"]:
        return mat, "La matrícula está archivada; no se pueden cambiar sus costos."
    return mat, None


def _costo_editable(cur, costo_id):
    """Bloquea el costo. Devuelve (fila, mensaje_de_error)."""
    costo = cur.execute("""
        SELECT c.id, c.id_matricula, c.concepto, c.valor, c.pagado, c.observaciones,
               c.anulado, m.archivado
        FROM matricula_costos c JOIN matriculas m ON m.id = c.id_matricula
        WHERE c.id = %s FOR UPDATE OF c.id
    """, (costo_id,)).fetchone()
    if not costo:
        return None, "No se encontró el costo."
    if costo["archivado"]:
        return costo, "La matrícula está archivada; no se pueden cambiar sus costos."
    if costo["anulado"]:
        return costo, "Ese costo ya fue anulado."
    return costo, None


# ───────────── Cuenta del alumno ─────────────

@bp.route("/alumnos/matricula/<int:matricula_id>/cuenta")
@login_required
@permiso_requerido("ver_ganancias")
def cuenta(matricula_id):
    alumno = db.fetchone("""
        SELECT m.id, m.numero_orden, m.anio, m.categoria, m.estado, m.archivado, m.precio_total,
               a.numero_documento, a.tipo_documento, a.nombres, a.apellidos
        FROM matriculas m JOIN alumnos a ON a.numero_documento = m.numero_documento
        WHERE m.id = %s
    """, (matricula_id,))
    if not alumno:
        return "Matrícula no encontrada.", 404
    costos = db.fetchall("""
        SELECT c.id, c.concepto, c.valor, c.pagado, c.fecha_pago, c.observaciones,
               c.anulado, u.nombre AS registrado_por,
               COALESCE((SELECT SUM(d.valor) FROM pago_distribucion d
                         JOIN pagos p ON p.id = d.id_pago
                         WHERE d.id_costo = c.id AND p.anulado = 0), 0) AS cubierto
        FROM matricula_costos c LEFT JOIN usuarios u ON u.id = c.usuario_id
        WHERE c.id_matricula = %s
        ORDER BY c.anulado, c.fecha_registro, c.id
    """, (matricula_id,))
    r = db.fetchone("""
        SELECT
          (SELECT COALESCE(SUM(valor), 0) FROM pagos
            WHERE id_matricula = %s AND anulado = 0) AS cobrado,
          (SELECT COALESCE(SUM(d.valor), 0) FROM pago_distribucion d
             JOIN pagos p ON p.id = d.id_pago
            WHERE p.id_matricula = %s AND p.anulado = 0 AND d.id_costo IS NULL) AS ganancia_asignada
        FROM dual
    """, (matricula_id, matricula_id))
    cobrado = int(r["cobrado"])
    ganancia_asignada = int(r["ganancia_asignada"])
    vigentes = [c for c in costos if not c["anulado"]]
    precio = int(alumno["precio_total"] or 0)
    total_costos = sum(int(c["valor"]) for c in vigentes)
    costos_pagados = sum(int(c["valor"]) for c in vigentes if c["pagado"])
    ganancia = precio - total_costos
    resumen = {
        "precio": precio,
        "cobrado": cobrado,
        "total_costos": total_costos,
        "costos_pagados": costos_pagados,
        "costos_pendientes": total_costos - costos_pagados,
        "ganancia": ganancia,
        "margen": round(ganancia * 100 / precio, 1) if precio else 0,
        "disponible": cobrado - costos_pagados,
        "ganancia_asignada": ganancia_asignada,
    }
    return render_template("cuenta_alumno.html", alumno=alumno, costos=costos, resumen=resumen)


@bp.route("/alumnos/matricula/<int:matricula_id>/costos", methods=["POST"])
@login_required
@permiso_requerido("gestionar_costos")
def agregar(matricula_id):
    try:
        concepto, valor, observaciones = _leer_costo()
    except ValueError as e:
        flash(str(e), "error")
        return _ir_cuenta(matricula_id)
    pagado = request.form.get("pagado") == "1"
    try:
        with db.transaccion() as cur:
            _, error = _matricula_editable(cur, matricula_id)
            if error:
                flash(error, "error")
                return _ir_cuenta(matricula_id)
            if pagado:
                cur.execute("""
                    INSERT INTO matricula_costos
                        (id_matricula, concepto, valor, pagado, fecha_pago, observaciones, usuario_id)
                    VALUES (%s, %s, %s, 1, CURRENT_TIMESTAMP, %s, %s)
                """, (matricula_id, concepto, valor, observaciones, session["uid"]))
            else:
                cur.execute("""
                    INSERT INTO matricula_costos
                        (id_matricula, concepto, valor, pagado, fecha_pago, observaciones, usuario_id)
                    VALUES (%s, %s, %s, 0, NULL, %s, %s)
                """, (matricula_id, concepto, valor, observaciones, session["uid"]))
            _auditar(cur, "MATRICULA", matricula_id, "COSTO_AGREGADO", session["uid"], None,
                     {"concepto": concepto, "valor": valor, "pagado": int(pagado)})
    except Exception:
        current_app.logger.exception("Error agregando costo a la matrícula %s", matricula_id)
        flash("No se pudo guardar el costo. Intenta de nuevo.", "error")
        return _ir_cuenta(matricula_id)
    flash(f"Costo «{concepto}» agregado.", "ok")
    return _ir_cuenta(matricula_id)


@bp.route("/alumnos/costos/<int:costo_id>/editar", methods=["POST"])
@login_required
@permiso_requerido("gestionar_costos")
def editar(costo_id):
    try:
        concepto, valor, observaciones = _leer_costo()
    except ValueError as e:
        flash(str(e), "error")
        costo = db.fetchone("SELECT id_matricula FROM matricula_costos WHERE id = %s", (costo_id,))
        return _ir_cuenta(costo["id_matricula"]) if costo else redirect(url_for("alumnos.lista"))
    try:
        with db.transaccion() as cur:
            costo, error = _costo_editable(cur, costo_id)
            if not costo:
                flash(error, "error")
                return redirect(url_for("alumnos.lista"))
            if error:
                flash(error, "error")
                return _ir_cuenta(costo["id_matricula"])
            cur.execute("""
                UPDATE matricula_costos SET concepto = %s, valor = %s, observaciones = %s
                WHERE id = %s
            """, (concepto, valor, observaciones, costo_id))
            _auditar(cur, "COSTO", costo_id, "EDITAR", session["uid"],
                     {"concepto": costo["concepto"], "valor": costo["valor"],
                      "observaciones": costo["observaciones"]},
                     {"concepto": concepto, "valor": valor, "observaciones": observaciones})
            matricula_id = costo["id_matricula"]
    except Exception:
        current_app.logger.exception("Error editando costo %s", costo_id)
        flash("No se pudo editar el costo. Intenta de nuevo.", "error")
        return redirect(url_for("alumnos.lista"))
    flash("Costo actualizado.", "ok")
    return _ir_cuenta(matricula_id)


@bp.route("/alumnos/costos/<int:costo_id>/pagado", methods=["POST"])
@login_required
@permiso_requerido("gestionar_costos")
def marcar_pagado(costo_id):
    pagado = 1 if request.form.get("pagado") == "1" else 0
    try:
        with db.transaccion() as cur:
            costo, error = _costo_editable(cur, costo_id)
            if not costo:
                flash(error, "error")
                return redirect(url_for("alumnos.lista"))
            if error:
                flash(error, "error")
                return _ir_cuenta(costo["id_matricula"])
            cur.execute("""
                UPDATE matricula_costos
                SET pagado = %s, fecha_pago = CASE WHEN %s = 1 THEN CURRENT_TIMESTAMP END
                WHERE id = %s
            """, (pagado, pagado, costo_id))
            _auditar(cur, "COSTO", costo_id, "PAGADO" if pagado else "PENDIENTE", session["uid"],
                     {"pagado": costo["pagado"]}, {"pagado": pagado})
            matricula_id = costo["id_matricula"]
    except Exception:
        current_app.logger.exception("Error cambiando estado del costo %s", costo_id)
        flash("No se pudo cambiar el estado del costo.", "error")
        return redirect(url_for("alumnos.lista"))
    flash("Costo marcado como pagado." if pagado else "Costo marcado como pendiente.", "ok")
    return _ir_cuenta(matricula_id)


@bp.route("/alumnos/costos/<int:costo_id>/anular", methods=["POST"])
@login_required
@permiso_requerido("gestionar_costos")
def anular(costo_id):
    motivo = " ".join(request.form.get("motivo", "").split())
    if not motivo or len(motivo) > 500:
        flash("El motivo es obligatorio y admite hasta 500 caracteres.", "error")
        costo = db.fetchone("SELECT id_matricula FROM matricula_costos WHERE id = %s", (costo_id,))
        return _ir_cuenta(costo["id_matricula"]) if costo else redirect(url_for("alumnos.lista"))
    try:
        with db.transaccion() as cur:
            costo, error = _costo_editable(cur, costo_id)
            if not costo:
                flash(error, "error")
                return redirect(url_for("alumnos.lista"))
            if error:
                flash(error, "error")
                return _ir_cuenta(costo["id_matricula"])
            cur.execute("UPDATE matricula_costos SET anulado = 1 WHERE id = %s", (costo_id,))
            _auditar(cur, "COSTO", costo_id, "ANULAR", session["uid"],
                     {"concepto": costo["concepto"], "valor": costo["valor"]},
                     {"anulado": 1}, motivo)
            matricula_id = costo["id_matricula"]
    except Exception:
        current_app.logger.exception("Error anulando costo %s", costo_id)
        flash("No se pudo anular el costo. Intenta de nuevo.", "error")
        return redirect(url_for("alumnos.lista"))
    flash("Costo anulado. Queda registrado en el historial.", "ok")
    return _ir_cuenta(matricula_id)


@bp.route("/alumnos/matricula/<int:matricula_id>/costos/plantilla", methods=["POST"])
@login_required
@permiso_requerido("gestionar_costos")
def cargar_plantilla(matricula_id):
    """Copia a una matrícula ya creada los costos de la plantilla de su categoría."""
    try:
        with db.transaccion() as cur:
            mat, error = _matricula_editable(cur, matricula_id)
            if error:
                flash(error, "error")
                return _ir_cuenta(matricula_id) if mat else redirect(url_for("alumnos.lista"))
            existentes = cur.execute(
                "SELECT COUNT(*) AS n FROM matricula_costos WHERE id_matricula = %s AND anulado = 0",
                (matricula_id,),
            ).fetchone()["n"]
            if existentes:
                flash("Esta matrícula ya tiene costos. Edítalos o anúlalos antes de cargar la plantilla.", "error")
                return _ir_cuenta(matricula_id)
            tipo, categoria = _tipo_y_categoria(mat["categoria"])
            cur.execute("""
                INSERT INTO matricula_costos (id_matricula, concepto, valor, usuario_id)
                SELECT %s, concepto, valor, %s FROM costos_plantilla
                WHERE tipo = %s AND categoria = %s AND activo = 1
            """, (matricula_id, session["uid"], tipo, categoria))
            insertados = cur.rowcount
            if insertados:
                _auditar(cur, "MATRICULA", matricula_id, "COSTOS_PLANTILLA", session["uid"], None,
                         {"costos_cargados": insertados})
    except Exception:
        current_app.logger.exception("Error cargando plantilla en matrícula %s", matricula_id)
        flash("No se pudo cargar la plantilla. Intenta de nuevo.", "error")
        return _ir_cuenta(matricula_id)
    if insertados:
        flash(f"Se cargaron {insertados} costos desde la plantilla.", "ok")
    else:
        flash("No hay una plantilla de costos configurada para esta categoría.", "error")
    return _ir_cuenta(matricula_id)


# ───────────── Plantillas por categoría ─────────────

@bp.route("/costos/plantillas")
@login_required
@permiso_requerido("gestionar_costos")

def plantillas():
    filas = db.fetchall("""
        SELECT t.tipo, t.categoria, t.precio_base, c.id, c.concepto, c.valor
        FROM tarifas_categoria t
        LEFT JOIN costos_plantilla c
               ON c.tipo = t.tipo AND c.categoria = t.categoria AND c.activo = 1
        ORDER BY t.tipo, t.categoria, c.concepto
    """)
    grupos = {}
    for f in filas:
        g = grupos.setdefault((f["tipo"], f["categoria"]), {
            "tipo": f["tipo"], "categoria": f["categoria"],
            "precio": int(f["precio_base"]), "costos": [], "total": 0})
        if f["id"]:
            g["costos"].append(f)
            g["total"] += int(f["valor"])
    lista = list(grupos.values())
    for g in lista:
        g["ganancia"] = g["precio"] - g["total"]
    return render_template("costos_plantillas.html", grupos=lista)

@bp.route("/costos/plantillas", methods=["POST"])
@login_required
@permiso_requerido("gestionar_costos")
def crear_plantilla():
    tipo = request.form.get("tipo", "")
    categoria = " ".join(request.form.get("categoria", "").upper().split())
    try:
        concepto, valor, _ = _leer_costo()
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("costos.plantillas"))
    if tipo not in TIPOS or not categoria:
        flash("Tipo o categoría no válidos.", "error")
        return redirect(url_for("costos.plantillas"))
    existe = db.fetchone(
        "SELECT 1 AS ok FROM tarifas_categoria WHERE tipo = %s AND categoria = %s", (tipo, categoria))
    if not existe:
        flash("Esa categoría no tiene una tarifa configurada.", "error")
        return redirect(url_for("costos.plantillas"))
    try:
        db.execute(
            "INSERT INTO costos_plantilla (tipo, categoria, concepto, valor, activo) VALUES (%s, %s, %s, %s, 1)",
            (tipo, categoria, concepto, valor))
    except oracledb.IntegrityError as e:
        if getattr(e.args[0] if e.args else None, "code", None) == 1:
            flash("Esa categoría ya tiene un costo con ese concepto.", "error")
        else:
            current_app.logger.exception("Error de integridad creando plantilla de costo")
            flash("No se pudo guardar el costo de la plantilla.", "error")
    except Exception:
        current_app.logger.exception("Error creando plantilla de costo")
        flash("No se pudo guardar el costo de la plantilla.", "error")
    else:
        flash(f"Costo «{concepto}» agregado a la plantilla de {categoria}.", "ok")
    return redirect(url_for("costos.plantillas"))


@bp.route("/costos/plantillas/<int:plantilla_id>/editar", methods=["POST"])
@login_required
@permiso_requerido("gestionar_costos")
def editar_plantilla(plantilla_id):
    try:
        concepto, valor, _ = _leer_costo()
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("costos.plantillas"))
    try:
        afectadas = db.execute(
            "UPDATE costos_plantilla SET concepto = %s, valor = %s WHERE id = %s",
            (concepto, valor, plantilla_id))
    except oracledb.IntegrityError:
        flash("Esa categoría ya tiene un costo con ese concepto.", "error")
        return redirect(url_for("costos.plantillas"))
    except Exception:
        current_app.logger.exception("Error editando plantilla de costo %s", plantilla_id)
        flash("No se pudo editar el costo de la plantilla.", "error")
        return redirect(url_for("costos.plantillas"))
    flash("Costo de la plantilla actualizado. Las matrículas ya creadas no cambian." if afectadas
          else "No se encontró ese costo.", "ok" if afectadas else "error")
    return redirect(url_for("costos.plantillas"))


@bp.route("/costos/plantillas/<int:plantilla_id>/eliminar", methods=["POST"])
@login_required
@permiso_requerido("gestionar_costos")
def eliminar_plantilla(plantilla_id):
    try:
        afectadas = db.execute("DELETE FROM costos_plantilla WHERE id = %s", (plantilla_id,))
    except Exception:
        current_app.logger.exception("Error eliminando plantilla de costo %s", plantilla_id)
        flash("No se pudo eliminar el costo de la plantilla.", "error")
        return redirect(url_for("costos.plantillas"))
    flash("Costo quitado de la plantilla. Las matrículas ya creadas no cambian." if afectadas
          else "No se encontró ese costo.", "ok" if afectadas else "error")
    return redirect(url_for("costos.plantillas"))
