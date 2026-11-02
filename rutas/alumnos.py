import re
import time
import uuid
from datetime import date

import oracledb
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

import db
from auth import login_required, permiso_requerido, permisos_actuales
from utils import hoy

bp = Blueprint("alumnos", __name__)


class DatosMatriculaInvalidos(Exception):
    pass


ESTADO_CLASE = {
    "Activo": "active",
    "Pendiente Pago": "pending",
    "Cancelado": "paid",      # en el sistema actual "Cancelado" = pagó todo
    "Completado": "paid",
    "Histórico": "muted",
}
TIPOS_DOCUMENTO = {"CC", "CE", "TI", "RC", "Pasaporte", "PPT", "Otro"}


def _like(texto: str) -> str:
    texto = texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{texto}%"


@bp.route("/alumnos")
@login_required
@permiso_requerido("ver_alumnos")
def lista():
    q = request.args.get("q", "").strip()[:60]
    error = None
    filas = []

    filtro, params = "", ()
    if q:
        like = _like(q)
        filtro = r"""WHERE (a.numero_documento LIKE %s ESCAPE '\' OR a.nombres LIKE %s ESCAPE '\'
                   OR a.apellidos LIKE %s ESCAPE '\' OR m.categoria LIKE %s ESCAPE '\'
                   OR (m.numero_orden || '-' || SUBSTR(TO_CHAR(m.anio), -2)) LIKE %s ESCAPE '\')"""
        params = (like,) * 5

    try:
        filas = db.fetchall(f"""
            SELECT m.id AS matricula_id, m.numero_orden, m.anio, m.categoria, m.estado,
                   COALESCE(m.precio_total, 0) AS precio_total, m.fecha_registro,
                   a.numero_documento, a.nombres, a.apellidos,
                   COALESCE((SELECT SUM(p.valor) FROM pagos p WHERE p.id_matricula = m.id), 0) AS pagado
            FROM matriculas m
            JOIN alumnos a ON a.numero_documento = m.numero_documento
            {filtro}
            ORDER BY m.fecha_registro DESC
            FETCH FIRST 200 ROWS ONLY
        """, params)
    except Exception:
        error = "No se pudo consultar la lista de alumnos."
        current_app.logger.exception("No se pudo consultar la lista de alumnos")

    cursos, renovaciones = [], []
    for f in filas:
        saldo = max(float(f["precio_total"]) - float(f["pagado"]), 0)
        item = {
            **f,
            "codigo": f"{f['numero_orden']}-{str(f['anio'])[-2:]}",
            "saldo": saldo,
            "clase_estado": ESTADO_CLASE.get(f["estado"], "muted"),
            "concepto": (f"Renovación de licencia — {f['categoria']}"
                         if str(f["categoria"]).startswith("Renovación")
                         else "Pago curso de conducción"),
        }
        (renovaciones if str(f["categoria"]).startswith("Renovación") else cursos).append(item)

    return render_template("alumnos.html", cursos=cursos, renovaciones=renovaciones,
                           q=q, error=error, limite=len(filas) >= 200,
                           anio_actual=hoy().year)


def _duplicado_unico(error: Exception) -> bool:
    causa = error.args[0] if error.args else None
    return getattr(causa, "code", None) == 1


def _numero_recibo() -> str:
    return f"CEA-{hoy():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


@bp.route("/alumnos/matricula", methods=["POST"])
@login_required
@permiso_requerido("crear_matricula")
def crear_matricula():
    documento = request.form.get("numero_documento", "").strip()
    tipo_documento = request.form.get("tipo_documento", "").strip()
    nombres = " ".join(request.form.get("nombres", "").split())
    apellidos = " ".join(request.form.get("apellidos", "").split())
    categoria_base = request.form.get("categoria", "").strip()
    tipo_matricula = request.form.get("tipo_matricula", "curso")
    categoria = f"Renovación - {categoria_base}" if tipo_matricula == "renovacion" else categoria_base
    fecha_texto = request.form.get("fecha_nacimiento", "").strip()
    fecha_nacimiento = None
    if fecha_texto:
        try:
            fecha_nacimiento = date.fromisoformat(fecha_texto)
        except ValueError:
            flash("La fecha de nacimiento no es válida.", "error")
            return redirect(url_for("alumnos.lista"))
        if fecha_nacimiento > hoy():
            flash("La fecha de nacimiento no puede ser futura.", "error")
            return redirect(url_for("alumnos.lista"))

    lugar_nacimiento = request.form.get("lugar_nacimiento", "").strip() or None
    sexo = request.form.get("sexo", "").strip() or None
    estado_civil = request.form.get("estado_civil", "").strip() or None
    grupo_sanguineo = request.form.get("grupo_sanguineo", "").strip() or None
    ocupacion = request.form.get("ocupacion", "").strip() or None
    celular = request.form.get("celular", "").strip() or None
    email = request.form.get("email", "").strip() or None
    precio_base_texto = request.form.get("precio_base", "").strip()
    precio_texto = request.form.get("precio_total", "").strip()
    abono_texto = request.form.get("abono_inicial", "").strip() or "0"
    metodo_pago = request.form.get("metodo_pago", "").strip()
    observaciones_abono = " ".join(request.form.get("observaciones", "").split()) or None
    acompanante = " ".join(request.form.get("acompanante", "").split()) or None

    if not re.fullmatch(r"[A-Za-z0-9.-]{1,20}", documento):
        flash("El documento debe tener hasta 20 caracteres válidos.", "error")
        return redirect(url_for("alumnos.lista"))
    if tipo_documento not in TIPOS_DOCUMENTO:
        flash("Selecciona un tipo de documento válido.", "error")
        return redirect(url_for("alumnos.lista"))
    if not nombres or len(nombres) > 100 or not apellidos or len(apellidos) > 100:
        flash("Escribe nombres y apellidos de hasta 100 caracteres.", "error")
        return redirect(url_for("alumnos.lista"))
    if tipo_matricula not in ("curso", "renovacion") or not categoria_base or len(categoria) > 60:
        flash("Selecciona el tipo de matrícula y una categoría de hasta 60 caracteres.", "error")
        return redirect(url_for("alumnos.lista"))
    if any(value and len(value) > limit for value, limit in (
        (lugar_nacimiento, 120), (sexo, 20), (estado_civil, 30),
        (grupo_sanguineo, 5), (ocupacion, 120), (celular, 30), (email, 254),
        (observaciones_abono, 1000), (acompanante, 100),
    )):
        flash("Uno de los datos personales o de contacto supera el largo permitido.", "error")
        return redirect(url_for("alumnos.lista"))
    if (sexo not in (None, "F", "M", "Otro")
            or estado_civil not in (None, "Soltero/a", "Casado/a", "Unión libre", "Separado/a", "Viudo/a")
            or grupo_sanguineo not in (None, "O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-")
            or (email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))):
        flash("Revisa el sexo, estado civil, grupo sanguíneo o correo electrónico.", "error")
        return redirect(url_for("alumnos.lista"))
    if not precio_base_texto.isascii() or not precio_base_texto.isdecimal() \
            or not precio_texto.isascii() or not precio_texto.isdecimal():
        flash("El precio base y el total deben ser valores enteros en pesos.", "error")
        return redirect(url_for("alumnos.lista"))
    precio_base, precio = int(precio_base_texto), int(precio_texto)
    if precio_base <= 0 or precio_base > 999_999_999_999 or precio <= 0 or precio > precio_base:
        flash("El total debe ser mayor a $0 y no puede superar el precio base.", "error")
        return redirect(url_for("alumnos.lista"))
    if not abono_texto.isascii() or not abono_texto.isdecimal():
        flash("El abono inicial debe ser un valor entero en pesos.", "error")
        return redirect(url_for("alumnos.lista"))
    abono = int(abono_texto)
    if abono > 100_000_000 or abono > precio:
        flash("El abono inicial no puede superar $100.000.000 ni el total del curso.", "error")
        return redirect(url_for("alumnos.lista"))
    if abono and (metodo_pago not in ("Efectivo", "Transferencia", "Nequi", "Daviplata", "Sistecredit", "Otro")
                  or "registrar_pagos" not in permisos_actuales()):
        flash("No tienes permiso para registrar el abono o el método de pago no es válido.", "error")
        return redirect(url_for("alumnos.lista"))

    responsable = {
        "tipo_documento": request.form.get("responsable_tipo_documento", "").strip(),
        "numero_documento": request.form.get("responsable_documento", "").strip(),
        "nombres": " ".join(request.form.get("responsable_nombres", "").split()),
        "apellidos": " ".join(request.form.get("responsable_apellidos", "").split()),
        "celular": request.form.get("responsable_celular", "").strip() or None,
        "email": request.form.get("responsable_email", "").strip() or None,
        "relacion": request.form.get("responsable_relacion", "").strip(),
    }
    if any(responsable.values()):
        if (responsable["tipo_documento"] not in TIPOS_DOCUMENTO
                or not re.fullmatch(r"[A-Za-z0-9.-]{1,20}", responsable["numero_documento"])
                or not responsable["nombres"] or len(responsable["nombres"]) > 100
                or not responsable["apellidos"] or len(responsable["apellidos"]) > 100
                or responsable["relacion"] not in
                ("Padre", "Madre", "Cónyuge", "Hijo/a", "Hermano/a", "Acudiente", "Otro")
                or (responsable["celular"] and len(responsable["celular"]) > 30)
                or (responsable["email"] and
                    (len(responsable["email"]) > 254
                     or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", responsable["email"])))):
            flash("Completa documento, nombres, apellidos y relación del responsable; teléfono y correo son opcionales.", "error")
            return redirect(url_for("alumnos.lista"))

    anio = hoy().year
    creada = False
    recibo_inicial = None
    for intento in range(5):
        try:
            with db.transaccion() as cur:
                existente = cur.execute(
                    "SELECT nombres, apellidos FROM alumnos WHERE numero_documento = %s FOR UPDATE",
                    (documento,),
                ).fetchone()
                if existente:
                    nombre_guardado = " ".join(existente["nombres"].split())
                    apellido_guardado = " ".join(existente["apellidos"].split())
                    if (nombre_guardado.casefold() != nombres.casefold()
                            or apellido_guardado.casefold() != apellidos.casefold()):
                        raise DatosMatriculaInvalidos(
                            "Ese documento ya existe con otros nombres. Verifica los datos antes de crear la matrícula."
                        )
                else:
                    cur.execute(
                        """INSERT INTO alumnos
                           (numero_documento, tipo_documento, nombres, apellidos, fecha_nacimiento,
                            lugar_nacimiento, sexo, estado_civil, grupo_sanguineo, ocupacion, celular, email)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (documento, tipo_documento, nombres, apellidos, fecha_nacimiento,
                         lugar_nacimiento, sexo, estado_civil, grupo_sanguineo, ocupacion, celular, email),
                    )
                if existente:
                    cur.execute(
                        """UPDATE alumnos
                           SET tipo_documento = %s,
                               fecha_nacimiento = COALESCE(%s, fecha_nacimiento),
                               lugar_nacimiento = COALESCE(%s, lugar_nacimiento),
                               sexo = COALESCE(%s, sexo),
                               estado_civil = COALESCE(%s, estado_civil),
                               grupo_sanguineo = COALESCE(%s, grupo_sanguineo),
                               ocupacion = COALESCE(%s, ocupacion),
                               celular = COALESCE(%s, celular),
                               email = COALESCE(%s, email)
                           WHERE numero_documento = %s""",
                        (tipo_documento, fecha_nacimiento, lugar_nacimiento, sexo, estado_civil,
                         grupo_sanguineo, ocupacion, celular, email, documento),
                    )

                orden = cur.execute(
                    "SELECT COALESCE(MAX(numero_orden), 0) + 1 AS siguiente "
                    "FROM matriculas WHERE anio = %s",
                    (anio,),
                ).fetchone()["siguiente"]
                cur.execute("""
                    INSERT INTO matriculas
                        (numero_orden, anio, numero_documento, categoria, estado, precio_total,
                         precio_base, descuento_valor, descuento_porcentaje)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (orden, anio, documento, categoria,
                      "Cancelado" if abono >= precio else "Pendiente Pago" if abono else "Activo",
                      precio, precio_base, precio_base - precio,
                      round((precio_base - precio) * 100 / precio_base, 2)))
                matricula_id = cur.execute("SELECT id FROM matriculas WHERE anio = %s AND numero_orden = %s",
                                           (anio, orden)).fetchone()["id"]
                if responsable:
                    cur.execute("""
                        INSERT INTO responsables_matricula
                            (id_matricula, tipo_documento, numero_documento, nombres, apellidos,
                             celular, email, relacion)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (matricula_id, responsable["tipo_documento"], responsable["numero_documento"],
                          responsable["nombres"], responsable["apellidos"], responsable["celular"],
                          responsable["email"], responsable["relacion"]))
                if abono:
                    caja = cur.execute(
                        "SELECT id FROM cajas WHERE usuario_id = %s AND estado = 'ABIERTA' FOR UPDATE",
                        (session["uid"],),
                    ).fetchone()
                    if not caja:
                        raise DatosMatriculaInvalidos("Abre tu caja antes de registrar un abono inicial.")
                    recibo_inicial = _numero_recibo()
                    cur.execute("""
                        INSERT INTO pagos (id_matricula, concepto, valor, metodo_pago, numero_recibo,
                                           usuario_id, caja_id, observaciones, acompanante)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (matricula_id,
                          f"Renovación de licencia — {categoria_base}" if tipo_matricula == "renovacion"
                          else "Pago curso de conducción",
                          abono, metodo_pago, recibo_inicial, session["uid"], caja["id"],
                          observaciones_abono, acompanante))
            creada = True
            break
        except DatosMatriculaInvalidos as e:
            flash(str(e), "error")
            return redirect(url_for("alumnos.lista"))
        except oracledb.IntegrityError as e:
            if not _duplicado_unico(e):
                raise
            if intento == 4:
                current_app.logger.exception("No se pudo asignar consecutivo de matrícula tras reintentos")
                flash("No se pudo asignar un consecutivo. Intenta de nuevo.", "error")
                return redirect(url_for("alumnos.lista"))
            time.sleep(0.05 * (intento + 1))
        except Exception:
            current_app.logger.exception("Error creando matrícula")
            flash("No se pudo guardar la matrícula. Revisa la conexión y vuelve a intentar.", "error")
            return redirect(url_for("alumnos.lista"))

    if creada:
        flash(f"{'Renovación' if tipo_matricula == 'renovacion' else 'Matrícula'} "
              f"{orden}-{str(anio)[-2:]} creada correctamente."
              + (f" Recibo del abono: {recibo_inicial}." if recibo_inicial else ""), "ok")
    return redirect(url_for("alumnos.lista"))