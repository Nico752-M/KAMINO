import json
import re
import time
import unicodedata
from datetime import date, timedelta

import oracledb
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for

import db
from auth import login_required, permiso_requerido, permisos_actuales
from servicios.matriculas import estado_matricula
from servicios.recibos import numero_recibo
from utils import entero, hoy

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


def _normalizar_busqueda(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto.upper())
    return "".join(caracter for caracter in descompuesto
                   if unicodedata.category(caracter) != "Mn")


def _siguiente_orden_matricula(cur, anio: int) -> int:
    bloqueo = cur.execute(
        "SELECT id FROM bloqueo_matriculas WHERE id = 1 FOR UPDATE"
    ).fetchone()
    if not bloqueo:
        raise RuntimeError("Falta aplicar la migración 004 de concurrencia de matrículas.")
    return cur.execute(
        "SELECT COALESCE(MAX(numero_orden), 0) + 1 AS siguiente "
        "FROM matriculas WHERE anio = %s",
        (anio,),
    ).fetchone()["siguiente"]


def _pesos(texto: str) -> int | None:
    if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)", texto):
        return None
    return entero(texto, -1)


def _auditar(cur, entidad, entidad_id, accion, usuario_id, antes, despues, motivo=None):
    cur.execute(
        """INSERT INTO auditoria_cambios
           (entidad, entidad_id, accion, usuario_id, antes, despues, motivo)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (entidad, entidad_id, accion, usuario_id,
         json.dumps(antes, ensure_ascii=False, default=str) if antes is not None else None,
         json.dumps(despues, ensure_ascii=False, default=str) if despues is not None else None,
         motivo),
    )


@bp.route("/alumnos")
@login_required
@permiso_requerido("ver_alumnos")
def lista():
    q = request.args.get("q", "").strip()[:60]
    desde_texto = request.args.get("desde", "").strip()
    hasta_texto = request.args.get("hasta", "").strip()
    hay_filtros = bool(q or desde_texto or hasta_texto)
    try:
        pagina = max(1, min(int(request.args.get("pagina", "1")), 1_000_000))
    except ValueError:
        pagina = 1
    if not hay_filtros:
        pagina = 1
    fecha_desde = None
    fecha_hasta = None
    recibo_nuevo = request.args.get("recibo_nuevo", "").strip()[:50]
    error = None
    filas = []
    tarifas, error_tarifas = [], None

    try:
        tarifas = db.fetchall(
            "SELECT categoria, precio_base FROM tarifas_categoria "
            "WHERE activo = 1 ORDER BY categoria"
        )
    except Exception:
        error_tarifas = "No se pudieron cargar las tarifas por categoría."
        current_app.logger.exception("No se pudieron cargar las tarifas")

    condiciones, params = [], []
    if q:
        like = _like(_normalizar_busqueda(q))
        normalizar = (
            "TRANSLATE(UPPER({}), 'ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝÁÉÍÓÚÜ', "
            "'AAAAAACEEEEIIIINOOOOOUUUUYAEIOUU')"
        )
        condiciones.append(rf"""({normalizar.format('a.numero_documento')} LIKE %s ESCAPE '\'
                   OR {normalizar.format('a.nombres')} LIKE %s ESCAPE '\'
                   OR {normalizar.format('a.apellidos')} LIKE %s ESCAPE '\'
                   OR {normalizar.format('m.categoria')} LIKE %s ESCAPE '\'
                   OR {normalizar.format("(m.numero_orden || '-' || SUBSTR(TO_CHAR(m.anio), -2))")} LIKE %s ESCAPE '\')""")
        params.extend((like,) * 5)

    try:
        if desde_texto:
            fecha_desde = date.fromisoformat(desde_texto)
            condiciones.append("m.fecha_registro >= %s")
            params.append(fecha_desde)
        if hasta_texto:
            fecha_hasta = date.fromisoformat(hasta_texto)
            condiciones.append("m.fecha_registro < %s")
            params.append(fecha_hasta + timedelta(days=1))
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            raise ValueError
    except ValueError:
        error = "Revisa las fechas: el formato no es válido y «Desde» no puede ser posterior a «Hasta»."

    if not error:
        try:
            filtro = "WHERE " + " AND ".join(condiciones) if condiciones else ""
            params.extend(((pagina - 1) * 10, 11))
            filas = db.fetchall(f"""
                SELECT m.id AS matricula_id, m.numero_orden, m.anio, m.categoria,
                       CASE WHEN m.archivado = 1 THEN 'Archivado' ELSE m.estado END AS estado,
                       COALESCE(m.precio_total, 0) AS precio_total, m.fecha_registro,
                       a.numero_documento, a.nombres, a.apellidos,
                       COALESCE((SELECT SUM(p.valor) FROM pagos p
                                 WHERE p.id_matricula = m.id AND p.anulado = 0), 0) AS pagado
                FROM matriculas m
                JOIN alumnos a ON a.numero_documento = m.numero_documento
                {filtro}
                ORDER BY m.fecha_registro DESC, m.id DESC
                OFFSET %s ROWS FETCH NEXT %s ROWS ONLY
            """, tuple(params))
        except Exception:
            error = "No se pudo consultar la lista de alumnos."
            current_app.logger.exception("No se pudo consultar la lista de alumnos")

    hay_siguiente = len(filas) > 10
    if hay_siguiente:
        filas = filas[:10]

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
                           tarifas=tarifas, error_tarifas=error_tarifas,
                           q=q, desde=desde_texto, hasta=hasta_texto, pagina=pagina,
                           hay_filtros=hay_filtros,
                           hay_anterior=hay_filtros and pagina > 1,
                           hay_siguiente=hay_filtros and hay_siguiente,
                           primer_resultado=(pagina - 1) * 10 + 1 if filas else 0,
                           ultimo_resultado=(pagina - 1) * 10 + len(filas),
                           error=error, anio_actual=hoy().year, recibo_nuevo=recibo_nuevo)


@bp.route("/alumnos/documento/<documento>")
@login_required
@permiso_requerido("crear_matricula")
def buscar_documento(documento: str):
    if not re.fullmatch(r"[A-Za-z0-9.-]{1,20}", documento):
        return jsonify(ok=False, error="Documento no válido."), 400
    try:
        alumno = db.fetchone("""
            SELECT tipo_documento, numero_documento, nombres, apellidos,
                   fecha_nacimiento, lugar_nacimiento, sexo, estado_civil,
                   grupo_sanguineo, ocupacion, celular, email
            FROM alumnos
            WHERE numero_documento = %s
        """, (documento,))
    except Exception:
        current_app.logger.exception("Error buscando alumno por documento")
        return jsonify(ok=False, error="No se pudo consultar el documento."), 500
    if not alumno:
        return jsonify(ok=True, encontrado=False)
    if alumno.get("fecha_nacimiento"):
        alumno["fecha_nacimiento"] = alumno["fecha_nacimiento"].strftime("%Y-%m-%d")
    return jsonify(ok=True, encontrado=True, alumno=alumno)


def _duplicado_unico(error: Exception) -> bool:
    causa = error.args[0] if error.args else None
    return getattr(causa, "code", None) == 1


@bp.route("/alumnos/matricula", methods=["POST"])
@login_required
@permiso_requerido("crear_matricula")
def crear_matricula():
    documento = request.form.get("numero_documento", "").strip()
    tipo_documento = request.form.get("tipo_documento", "").strip()
    nombres = " ".join(request.form.get("nombres", "").split())
    apellidos = " ".join(request.form.get("apellidos", "").split())
    categoria_base = " ".join(request.form.get("categoria", "").upper().split())
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
    precio_base = _pesos(precio_base_texto)
    precio = _pesos(precio_texto)
    if precio_base is None or precio is None:
        flash("El precio base y el total deben ser valores enteros en pesos.", "error")
        return redirect(url_for("alumnos.lista"))
    if precio_base <= 0 or precio_base > 999_999_999_999 or precio <= 0 or precio > precio_base:
        flash("El total debe ser mayor a $0 y no puede superar el precio base.", "error")
        return redirect(url_for("alumnos.lista"))
    abono = _pesos(abono_texto)
    if abono is None:
        flash("El abono inicial debe ser un valor entero en pesos.", "error")
        return redirect(url_for("alumnos.lista"))
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
    responsable_informado = any(responsable.values())
    if responsable_informado:
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
                tarifa = cur.execute(
                    """SELECT categoria FROM tarifas_categoria
                       WHERE categoria = %s AND activo = 1""",
                    (categoria_base,),
                ).fetchone()
                if not tarifa:
                    raise DatosMatriculaInvalidos(
                        "Selecciona una categoría activa con tarifa configurada."
                    )
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

                orden = _siguiente_orden_matricula(cur, anio)
                cur.execute("""
                    INSERT INTO matriculas
                        (numero_orden, anio, numero_documento, categoria, estado, precio_total,
                         precio_base, descuento_valor, descuento_porcentaje)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (orden, anio, documento, categoria,
                      estado_matricula("Activo", precio, abono),
                      precio, precio_base, precio_base - precio,
                      round((precio_base - precio) * 100 / precio_base, 2)))
                matricula_id = cur.execute("SELECT id FROM matriculas WHERE anio = %s AND numero_orden = %s",
                                           (anio, orden)).fetchone()["id"]
                if responsable_informado:
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
                    recibo_inicial = numero_recibo(cur)
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
    return redirect(url_for("alumnos.lista", recibo_nuevo=recibo_inicial) if recibo_inicial
                    else url_for("alumnos.lista"))


@bp.route("/alumnos/matricula/<int:matricula_id>/editar", methods=["GET", "POST"])
@login_required
@permiso_requerido("editar_alumnos")
def editar_matricula(matricula_id):
    try:
        if request.method == "GET":
            fila = db.fetchone("""
                SELECT m.id, m.numero_documento AS documento_original, m.categoria, m.estado,
                       m.precio_base, m.precio_total, m.descuento_valor, m.descuento_porcentaje,
                       a.tipo_documento, a.nombres, a.apellidos, a.fecha_nacimiento,
                       a.lugar_nacimiento, a.sexo, a.estado_civil, a.grupo_sanguineo,
                       a.ocupacion, a.celular, a.email,
                       r.tipo_documento AS responsable_tipo_documento,
                       r.numero_documento AS responsable_documento,
                       r.nombres AS responsable_nombres, r.apellidos AS responsable_apellidos,
                       r.celular AS responsable_celular, r.email AS responsable_email,
                       r.relacion AS responsable_relacion
                FROM matriculas m
                JOIN alumnos a ON a.numero_documento = m.numero_documento
                LEFT JOIN responsables_matricula r ON r.id_matricula = m.id
                WHERE m.id = %s AND m.archivado = 0
            """, (matricula_id,))
            if not fila:
                return "Matrícula no encontrada.", 404
            pagado = db.fetchone(
                "SELECT COALESCE(SUM(valor), 0) AS total FROM pagos "
                "WHERE id_matricula = %s AND anulado = 0",
                (matricula_id,),
            )["total"]
            return render_template("editar_alumno.html", alumno=fila, pagado=pagado)

        documento_original = request.form.get("documento_original", "").strip()
        documento = request.form.get("numero_documento", "").strip()
        tipo_documento = request.form.get("tipo_documento", "").strip()
        nombres = " ".join(request.form.get("nombres", "").split())
        apellidos = " ".join(request.form.get("apellidos", "").split())
        categoria = " ".join(request.form.get("categoria", "").split())
        fecha_texto = request.form.get("fecha_nacimiento", "").strip()
        fecha_nacimiento = None
        if fecha_texto:
            try:
                fecha_nacimiento = date.fromisoformat(fecha_texto)
            except ValueError:
                raise DatosMatriculaInvalidos("La fecha de nacimiento no es válida.")
            if fecha_nacimiento > hoy():
                raise DatosMatriculaInvalidos("La fecha de nacimiento no puede ser futura.")

        opcionales = {
            "lugar_nacimiento": request.form.get("lugar_nacimiento", "").strip() or None,
            "sexo": request.form.get("sexo", "").strip() or None,
            "estado_civil": request.form.get("estado_civil", "").strip() or None,
            "grupo_sanguineo": request.form.get("grupo_sanguineo", "").strip() or None,
            "ocupacion": request.form.get("ocupacion", "").strip() or None,
            "celular": request.form.get("celular", "").strip() or None,
            "email": request.form.get("email", "").strip() or None,
        }
        limites = {"lugar_nacimiento": 120, "sexo": 20, "estado_civil": 30,
                   "grupo_sanguineo": 5, "ocupacion": 120, "celular": 30, "email": 254}
        if (not re.fullmatch(r"[A-Za-z0-9.-]{1,20}", documento)
                or tipo_documento not in TIPOS_DOCUMENTO
                or not nombres or len(nombres) > 100 or not apellidos or len(apellidos) > 100
                or not categoria or len(categoria) > 60):
            raise DatosMatriculaInvalidos("Revisa documento, tipo, nombres, apellidos y categoría.")
        if any(value and len(value) > limites[campo] for campo, value in opcionales.items()):
            raise DatosMatriculaInvalidos("Uno de los datos personales o de contacto supera el largo permitido.")
        if (opcionales["sexo"] not in (None, "F", "M", "Otro")
                or opcionales["estado_civil"] not in
                (None, "Soltero/a", "Casado/a", "Unión libre", "Separado/a", "Viudo/a")
                or opcionales["grupo_sanguineo"] not in
                (None, "O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-")
                or (opcionales["email"] and
                    not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", opcionales["email"]))):
            raise DatosMatriculaInvalidos("Revisa sexo, estado civil, grupo sanguíneo o correo electrónico.")

        base = _pesos(request.form.get("precio_base", "").strip())
        descuento_valor = _pesos(request.form.get("descuento_valor", "").strip() or "0")
        porcentaje_texto = request.form.get("descuento_porcentaje", "").strip() or "0"
        if (base is None or descuento_valor is None
                or not re.fullmatch(r"(?:[0-9]+(?:\.[0-9]{1,2})?)", porcentaje_texto)):
            raise DatosMatriculaInvalidos("El precio y los descuentos deben ser valores válidos en pesos.")
        porcentaje = float(porcentaje_texto)
        if (base <= 0 or base > 999_999_999_999 or descuento_valor < 0
                or porcentaje < 0 or porcentaje > 100
                or (descuento_valor and porcentaje)):
            raise DatosMatriculaInvalidos("El descuento debe ser positivo y no puede superar el precio base.")
        if porcentaje:
            descuento_valor = round(base * porcentaje / 100)
        elif descuento_valor:
            porcentaje = round(descuento_valor * 100 / base, 2)
        total = base - descuento_valor
        if total <= 0:
            raise DatosMatriculaInvalidos("El total a pagar debe ser mayor a $0.")

        responsable = {
            "tipo_documento": request.form.get("responsable_tipo_documento", "").strip(),
            "numero_documento": request.form.get("responsable_documento", "").strip(),
            "nombres": " ".join(request.form.get("responsable_nombres", "").split()),
            "apellidos": " ".join(request.form.get("responsable_apellidos", "").split()),
            "celular": request.form.get("responsable_celular", "").strip() or None,
            "email": request.form.get("responsable_email", "").strip() or None,
            "relacion": request.form.get("responsable_relacion", "").strip(),
        }
        if any(responsable.values()) and (
                responsable["tipo_documento"] not in TIPOS_DOCUMENTO
                or not re.fullmatch(r"[A-Za-z0-9.-]{1,20}", responsable["numero_documento"])
                or not responsable["nombres"] or len(responsable["nombres"]) > 100
                or not responsable["apellidos"] or len(responsable["apellidos"]) > 100
                or responsable["relacion"] not in
                ("Padre", "Madre", "Cónyuge", "Hijo/a", "Hermano/a", "Acudiente", "Otro")
                or (responsable["celular"] and len(responsable["celular"]) > 30)
                or (responsable["email"] and
                    (len(responsable["email"]) > 254
                     or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", responsable["email"])))):
            raise DatosMatriculaInvalidos(
                "Completa documento, nombres, apellidos y relación del responsable; teléfono y correo son opcionales."
            )

        with db.transaccion() as cur:
            actual = cur.execute("""
                SELECT m.id, m.numero_documento, m.categoria, m.estado, m.archivado, m.precio_base,
                       m.precio_total, m.descuento_valor, m.descuento_porcentaje,
                       a.tipo_documento, a.nombres, a.apellidos, a.fecha_nacimiento,
                       a.lugar_nacimiento, a.sexo, a.estado_civil, a.grupo_sanguineo,
                       a.ocupacion, a.celular, a.email
                FROM matriculas m JOIN alumnos a ON a.numero_documento = m.numero_documento
                WHERE m.id = %s AND m.archivado = 0 FOR UPDATE
            """, (matricula_id,)).fetchone()
            if not actual:
                raise DatosMatriculaInvalidos("La matrícula no existe o ya fue archivada.")
            if documento_original != actual["numero_documento"]:
                raise DatosMatriculaInvalidos("Los datos cambiaron. Recarga la página e intenta de nuevo.")
            pagado = cur.execute(
                "SELECT COALESCE(SUM(valor), 0) AS total FROM pagos "
                "WHERE id_matricula = %s AND anulado = 0",
                (matricula_id,),
            ).fetchone()["total"]
            if total < int(pagado):
                raise DatosMatriculaInvalidos(
                    "El nuevo precio no puede ser menor a lo ya pagado."
                )
            responsable_actual = cur.execute(
                """SELECT tipo_documento, numero_documento, nombres, apellidos, celular, email, relacion
                   FROM responsables_matricula WHERE id_matricula = %s FOR UPDATE""",
                (matricula_id,),
            ).fetchone()
            antes = {"alumno": dict(actual), "responsable": dict(responsable_actual)
                     if responsable_actual else None, "matricula_id": matricula_id}

            if documento != documento_original:
                duplicado = cur.execute(
                    "SELECT numero_documento FROM alumnos WHERE numero_documento = %s",
                    (documento,),
                ).fetchone()
                if duplicado:
                    raise DatosMatriculaInvalidos("Ya existe un alumno con ese número de documento.")
                cur.execute("""
                    INSERT INTO alumnos
                        (numero_documento, tipo_documento, nombres, apellidos, fecha_nacimiento,
                         lugar_nacimiento, sexo, estado_civil, grupo_sanguineo, ocupacion, celular, email)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (documento, tipo_documento, nombres, apellidos, fecha_nacimiento,
                      opcionales["lugar_nacimiento"], opcionales["sexo"], opcionales["estado_civil"],
                      opcionales["grupo_sanguineo"], opcionales["ocupacion"],
                      opcionales["celular"], opcionales["email"]))
                cur.execute("UPDATE matriculas SET numero_documento = %s WHERE numero_documento = %s",
                            (documento, documento_original))
                cur.execute("DELETE FROM alumnos WHERE numero_documento = %s", (documento_original,))
            else:
                cur.execute("""
                    UPDATE alumnos SET tipo_documento = %s, nombres = %s, apellidos = %s,
                        fecha_nacimiento = %s, lugar_nacimiento = %s, sexo = %s,
                        estado_civil = %s, grupo_sanguineo = %s, ocupacion = %s,
                        celular = %s, email = %s
                    WHERE numero_documento = %s
                """, (tipo_documento, nombres, apellidos, fecha_nacimiento,
                      opcionales["lugar_nacimiento"], opcionales["sexo"], opcionales["estado_civil"],
                      opcionales["grupo_sanguineo"], opcionales["ocupacion"],
                      opcionales["celular"], opcionales["email"], documento_original))

            estado = estado_matricula(actual["estado"], total, int(pagado))
            cur.execute("""
                UPDATE matriculas
                SET categoria = %s, precio_base = %s, precio_total = %s,
                    descuento_valor = %s, descuento_porcentaje = %s, estado = %s
                WHERE id = %s
            """, (categoria, base, total, descuento_valor, porcentaje, estado, matricula_id))

            if any(responsable.values()):
                if responsable_actual:
                    cur.execute("""
                        UPDATE responsables_matricula
                        SET tipo_documento = %s, numero_documento = %s, nombres = %s,
                            apellidos = %s, celular = %s, email = %s, relacion = %s
                        WHERE id_matricula = %s
                    """, (responsable["tipo_documento"], responsable["numero_documento"],
                          responsable["nombres"], responsable["apellidos"], responsable["celular"],
                          responsable["email"], responsable["relacion"], matricula_id))
                else:
                    cur.execute("""
                        INSERT INTO responsables_matricula
                            (id_matricula, tipo_documento, numero_documento, nombres, apellidos,
                             celular, email, relacion)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (matricula_id, responsable["tipo_documento"], responsable["numero_documento"],
                          responsable["nombres"], responsable["apellidos"], responsable["celular"],
                          responsable["email"], responsable["relacion"]))
            elif responsable_actual:
                cur.execute("DELETE FROM responsables_matricula WHERE id_matricula = %s", (matricula_id,))

            despues = {"documento": documento, "tipo_documento": tipo_documento,
                       "nombres": nombres, "apellidos": apellidos, **opcionales,
                       "categoria": categoria, "precio_base": base, "precio_total": total,
                       "descuento_valor": descuento_valor, "descuento_porcentaje": porcentaje,
                       "estado": estado,
                       "responsable": responsable if any(responsable.values()) else None}
            _auditar(cur, "MATRICULA", matricula_id, "EDICION", session["uid"], antes, despues)
    except DatosMatriculaInvalidos as e:
        flash(str(e), "error")
        return redirect(url_for("alumnos.editar_matricula", matricula_id=matricula_id))
    except Exception:
        current_app.logger.exception("Error editando matrícula %s", matricula_id)
        flash("No se pudieron guardar los cambios. Intenta de nuevo.", "error")
        return redirect(url_for("alumnos.lista"))

    flash("Los datos del alumno y la matrícula se actualizaron correctamente.", "ok")
    return redirect(url_for("alumnos.lista"))


@bp.route("/alumnos/matricula/<int:matricula_id>/archivar", methods=["POST"])
@login_required
@permiso_requerido("eliminar_alumnos")
def archivar_matricula(matricula_id):
    motivo = " ".join(request.form.get("motivo", "").split())
    if not motivo or len(motivo) > 500:
        flash("El motivo es obligatorio y admite hasta 500 caracteres.", "error")
        return redirect(url_for("alumnos.lista"))
    try:
        with db.transaccion() as cur:
            actual = cur.execute(
                """SELECT id, numero_documento, categoria, estado, precio_total, archivado,
                          motivo_archivo, archivado_por, fecha_archivo
                   FROM matriculas WHERE id = %s FOR UPDATE""",
                (matricula_id,),
            ).fetchone()
            if not actual:
                flash("La matrícula ya no existe.", "error")
                return redirect(url_for("alumnos.lista"))
            if actual["archivado"]:
                flash("La matrícula ya está archivada.", "error")
                return redirect(url_for("alumnos.lista"))
            cur.execute("""
                UPDATE matriculas SET archivado = 1, motivo_archivo = %s,
                    archivado_por = %s, fecha_archivo = CURRENT_TIMESTAMP
                WHERE id = %s AND archivado = 0
            """, (motivo, session["uid"], matricula_id))
            _auditar(cur, "MATRICULA", matricula_id, "ARCHIVO", session["uid"],
                     dict(actual), {**actual, "archivado": 1, "motivo_archivo": motivo,
                                    "archivado_por": session["uid"]}, motivo)
    except Exception:
        current_app.logger.exception("Error archivando matrícula %s", matricula_id)
        flash("No se pudo archivar la matrícula. Intenta de nuevo.", "error")
        return redirect(url_for("alumnos.lista"))
    flash("Matrícula archivada. Sus pagos y recibos se conservaron.", "ok")
    return redirect(url_for("alumnos.lista"))


@bp.route("/alumnos/matricula/<int:matricula_id>/historial")
@login_required
@permiso_requerido("ver_historial_pagos")
def historial(matricula_id):
    alumno = db.fetchone("""
        SELECT m.id, m.numero_orden, m.anio, m.categoria, m.estado, m.precio_total,
               a.numero_documento, a.tipo_documento, a.nombres, a.apellidos
        FROM matriculas m JOIN alumnos a ON a.numero_documento = m.numero_documento
        WHERE m.id = %s
    """, (matricula_id,))
    if not alumno:
        return "Matrícula no encontrada.", 404
    pagos = db.fetchall("""
        SELECT p.numero_recibo, p.fecha_pago, p.concepto, p.metodo_pago, p.valor,
               p.anulado, p.motivo_anulacion, u.nombre AS cajero
        FROM pagos p LEFT JOIN usuarios u ON u.id = p.usuario_id
        WHERE p.id_matricula = %s
        ORDER BY p.fecha_pago DESC
    """, (matricula_id,))
    pagado = sum(float(p["valor"]) for p in pagos if not p["anulado"])
    return render_template("historial_pagos.html", alumno=alumno, pagos=pagos,
                           pagado=pagado, saldo=max(float(alumno["precio_total"]) - pagado, 0))


@bp.route("/pagos/<numero>/anular", methods=["POST"])
@login_required
@permiso_requerido("registrar_pagos")
def anular_pago(numero):
    motivo = " ".join(request.form.get("motivo", "").split())
    if not re.fullmatch(r"[A-Za-z0-9-]{6,50}", numero):
        return "Recibo no válido.", 404
    if not motivo or len(motivo) > 500:
        flash("El motivo de anulación es obligatorio y admite hasta 500 caracteres.", "error")
        return redirect(url_for("alumnos.lista"))
    try:
        with db.transaccion() as cur:
            pago = cur.execute("""
                SELECT id, id_matricula, numero_recibo, concepto, valor, metodo_pago,
                       anulado, motivo_anulacion
                FROM pagos WHERE numero_recibo = %s FOR UPDATE
            """, (numero,)).fetchone()
            if not pago:
                flash("No se encontró el pago.", "error")
                return redirect(url_for("alumnos.lista"))
            if pago["anulado"]:
                flash("Este pago ya fue anulado.", "error")
                return redirect(url_for("alumnos.historial", matricula_id=pago["id_matricula"]))
            cur.execute("""
                UPDATE pagos SET anulado = 1, motivo_anulacion = %s,
                    anulado_por = %s, fecha_anulacion = CURRENT_TIMESTAMP
                WHERE id = %s AND anulado = 0
            """, (motivo, session["uid"], pago["id"]))
            _auditar(cur, "PAGO", pago["id"], "ANULACION", session["uid"],
                     dict(pago), {**pago, "anulado": 1, "motivo_anulacion": motivo}, motivo)
            matricula = cur.execute(
                "SELECT estado, precio_total, archivado FROM matriculas WHERE id = %s FOR UPDATE",
                (pago["id_matricula"],),
            ).fetchone()
            pagado = cur.execute(
                "SELECT COALESCE(SUM(valor), 0) AS total FROM pagos "
                "WHERE id_matricula = %s AND anulado = 0",
                (pago["id_matricula"],),
            ).fetchone()["total"]
            if matricula and not matricula["archivado"] and matricula["estado"] != "Histórico":
                estado = estado_matricula(matricula["estado"],
                                          int(matricula["precio_total"]), int(pagado))
                if estado != matricula["estado"]:
                    cur.execute("UPDATE matriculas SET estado = %s WHERE id = %s",
                                (estado, pago["id_matricula"]))
                    _auditar(cur, "MATRICULA", pago["id_matricula"], "AJUSTE_ESTADO_PAGO",
                             session["uid"], {"estado": matricula["estado"]},
                             {"estado": estado}, motivo)
    except Exception:
        current_app.logger.exception("Error anulando recibo %s", numero)
        flash("No se pudo anular el pago. Intenta de nuevo.", "error")
        return redirect(url_for("alumnos.lista"))
    flash(f"El pago {numero} fue anulado. El recibo y el registro se conservaron.", "ok")
    return redirect(url_for("alumnos.historial", matricula_id=pago["id_matricula"]))