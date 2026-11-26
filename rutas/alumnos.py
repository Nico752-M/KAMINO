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
from servicios.validaciones import validar_datos_alumno, validar_responsable
from utils import cacheado, hoy, parsear_pesos

bp = Blueprint("alumnos", __name__)


class DatosMatriculaInvalidos(Exception):
    pass


ESTADO_CLASE = {
    "Activo": "active",
    "Pendiente Pago": "pending",
    "Cancelado": "paid",
    "Pagado": "paid",
    "Completado": "paid",
    "Histórico": "muted",
}
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
        tarifas = cacheado("tarifas_activas", 60, lambda: db.fetchall(
            "SELECT categoria, tipo, precio_base FROM tarifas_categoria "
            "WHERE activo = 1 ORDER BY tipo, categoria"
        ))
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
                       CASE WHEN m.archivado = 1 THEN 'Archivado'
                            WHEN m.estado = 'Cancelado' THEN 'Pagado' ELSE m.estado END AS estado,
                       COALESCE(m.precio_total, 0) AS precio_total, m.fecha_registro,
                       a.numero_documento, a.nombres, a.apellidos,
                       COALESCE((SELECT SUM(p.valor) FROM pagos p
                                 WHERE p.id_matricula = m.id AND p.anulado = 0), 0) AS pagado,
                       (SELECT LISTAGG(m2.categoria, ', ') WITHIN GROUP (ORDER BY m2.categoria)
                          FROM matriculas m2
                         WHERE m2.numero_documento = m.numero_documento
                           AND m2.id <> m.id AND m2.archivado = 0) AS otras_categorias
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


@bp.route("/alumnos/version")
@login_required
@permiso_requerido("ver_alumnos")
def version():
    v = cacheado("alumnos_version", 10, lambda: db.fetchone(
        "SELECT (SELECT NVL(MAX(id), 0) FROM matriculas) AS m, "
        "(SELECT NVL(MAX(id), 0) FROM pagos) AS p FROM dual"))
    return jsonify(v=f"{v['m']}-{v['p']}")


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
    tipo_tarifa = "RENOVACION" if tipo_matricula == "renovacion" else "CURSO"
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

    # Alumno que ya venía cursando antes de usar la app: conserva su fecha original y
    # lo que ya pagó queda como "abono histórico previo" (sin caja ni recibo de hoy).
    en_curso = request.form.get("alumno_en_curso") == "1"
    fecha_matricula = None
    runt_ya = en_curso and request.form.get("runt_registrado") == "1"
    if en_curso:
        try:
            fecha_matricula = date.fromisoformat(request.form.get("fecha_matricula", "").strip())
        except ValueError:
            flash("Escribe la fecha en que se matriculó el alumno.", "error")
            return redirect(url_for("alumnos.lista"))
        if fecha_matricula > hoy() or (hoy() - fecha_matricula).days > 1100:
            flash("La fecha de matrícula no puede ser futura ni de hace más de 3 años.", "error")
            return redirect(url_for("alumnos.lista"))
        metodo_pago = "Otro"

    try:
        validar_datos_alumno(
            documento, tipo_documento, nombres, apellidos,
            {"lugar_nacimiento": lugar_nacimiento, "sexo": sexo,
             "estado_civil": estado_civil, "grupo_sanguineo": grupo_sanguineo,
             "ocupacion": ocupacion, "celular": celular, "email": email},
        )
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("alumnos.lista"))
    if tipo_matricula not in ("curso", "renovacion") or not categoria_base or len(categoria) > 60:
        flash("Selecciona el tipo de matrícula y una categoría de hasta 60 caracteres.", "error")
        return redirect(url_for("alumnos.lista"))
    if any(value and len(value) > limit for value, limit in (
        (observaciones_abono, 1000), (acompanante, 100),
    )):
        flash("Uno de los datos personales o de contacto supera el largo permitido.", "error")
        return redirect(url_for("alumnos.lista"))
    precio_base = parsear_pesos(precio_base_texto)
    precio = parsear_pesos(precio_texto)
    if precio_base is None or precio is None:
        flash("El precio base y el total deben ser valores enteros en pesos.", "error")
        return redirect(url_for("alumnos.lista"))
    if precio_base <= 0 or precio_base > 999_999_999_999 or precio <= 0 or precio > precio_base:
        flash("El total debe ser mayor a $0 y no puede superar el precio base.", "error")
        return redirect(url_for("alumnos.lista"))
    abono = parsear_pesos(abono_texto)
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
    try:
        responsable_informado = validar_responsable(responsable)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("alumnos.lista"))
    if any((valor or "") for valor in responsable.values()) and not responsable_informado:
        flash("Completa documento, nombres, apellidos y relación del responsable; teléfono y correo son opcionales.", "error")
        return redirect(url_for("alumnos.lista"))

    # Cursos adicionales en la misma matrícula (ej. A1 y B2): cada uno crea su propia
    # matrícula con su consecutivo, precio, descuento y abono.
    cursos = [{
        "categoria_base": categoria_base, "categoria": categoria,
        "precio_base": precio_base, "precio": precio, "abono": abono,
        "fecha": fecha_matricula, "runt": runt_ya,
    }]
    extra_cats = request.form.getlist("extra_categoria")
    extra_bases = request.form.getlist("extra_precio_base")
    extra_totales = request.form.getlist("extra_precio_total")
    extra_abonos = request.form.getlist("extra_abono")
    extra_fechas = request.form.getlist("extra_fecha")
    extra_runts = request.form.getlist("extra_runt")
    if len(extra_cats) > 4:
        flash("Puedes registrar hasta 5 cursos a la vez.", "error")
        return redirect(url_for("alumnos.lista"))
    for i, cat_texto in enumerate(extra_cats):
        n = i + 2
        cat_base = " ".join(cat_texto.upper().split())
        if not cat_base:
            flash(f"Selecciona la categoría del curso {n} o quítalo.", "error")
            return redirect(url_for("alumnos.lista"))
        cat_final = f"Renovación - {cat_base}" if tipo_matricula == "renovacion" else cat_base
        if len(cat_final) > 60:
            flash(f"La categoría del curso {n} es demasiado larga.", "error")
            return redirect(url_for("alumnos.lista"))
        base_x = parsear_pesos(extra_bases[i] if i < len(extra_bases) else "")
        total_x = parsear_pesos(extra_totales[i] if i < len(extra_totales) else "")
        if base_x is None or total_x is None:
            flash(f"El precio base y el total del curso {n} deben ser valores enteros en pesos.", "error")
            return redirect(url_for("alumnos.lista"))
        if base_x <= 0 or base_x > 999_999_999_999 or total_x <= 0 or total_x > base_x:
            flash(f"El total del curso {n} debe ser mayor a $0 y no puede superar su precio base.", "error")
            return redirect(url_for("alumnos.lista"))
        abono_x = parsear_pesos((extra_abonos[i] if i < len(extra_abonos) else "") or "0")
        if abono_x is None:
            flash(f"El abono del curso {n} debe ser un valor entero en pesos.", "error")
            return redirect(url_for("alumnos.lista"))
        if abono_x > 100_000_000 or abono_x > total_x:
            flash(f"El abono del curso {n} no puede superar $100.000.000 ni el total de ese curso.", "error")
            return redirect(url_for("alumnos.lista"))
        if abono_x and (metodo_pago not in ("Efectivo", "Transferencia", "Nequi", "Daviplata",
                                            "Sistecredit", "Otro")
                        or "registrar_pagos" not in permisos_actuales()):
            flash("No tienes permiso para registrar el abono o el método de pago no es válido.", "error")
            return redirect(url_for("alumnos.lista"))
        fecha_x, runt_x = None, False
        if en_curso:
            texto_fecha = (extra_fechas[i] if i < len(extra_fechas) else "").strip()
            if texto_fecha:
                try:
                    fecha_x = date.fromisoformat(texto_fecha)
                except ValueError:
                    flash(f"La fecha de matrícula del curso {n} no es válida.", "error")
                    return redirect(url_for("alumnos.lista"))
                if fecha_x > hoy() or (hoy() - fecha_x).days > 1100:
                    flash(f"La fecha del curso {n} no puede ser futura ni de hace más de 3 años.", "error")
                    return redirect(url_for("alumnos.lista"))
            else:
                fecha_x = fecha_matricula
            runt_x = (extra_runts[i] if i < len(extra_runts) else "0") == "1"
        cursos.append({
            "categoria_base": cat_base, "categoria": cat_final,
            "precio_base": base_x, "precio": total_x, "abono": abono_x,
            "fecha": fecha_x, "runt": runt_x,
        })
    if len({c["categoria"] for c in cursos}) != len(cursos):
        flash("No repitas la misma categoría dentro de la misma matrícula.", "error")
        return redirect(url_for("alumnos.lista"))

    anio = hoy().year
    creada = False
    recibos = []
    codigos = []
    for intento in range(5):
        try:
            with db.transaccion() as cur:
                recibos, codigos = [], []
                for curso in cursos:
                    tarifa = cur.execute(
                        """SELECT categoria FROM tarifas_categoria
                           WHERE categoria = %s AND tipo = %s AND activo = 1""",
                        (curso["categoria_base"], tipo_tarifa),
                    ).fetchone()
                    if not tarifa:
                        raise DatosMatriculaInvalidos(
                            f"La categoría {curso['categoria_base']} no tiene una tarifa activa configurada."
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

                for curso in cursos:
                    c_base, c_cat = curso["categoria_base"], curso["categoria"]
                    c_pbase, c_precio, c_abono = curso["precio_base"], curso["precio"], curso["abono"]
                    orden = _siguiente_orden_matricula(cur, anio)
                    datos_mat = (orden, anio, documento, c_cat,
                                 estado_matricula("Activo", c_precio, c_abono),
                                 c_precio, c_pbase, c_pbase - c_precio,
                                 round((c_pbase - c_precio) * 100 / c_pbase, 2))
                    if en_curso:
                        cur.execute("""
                            INSERT INTO matriculas
                                (numero_orden, anio, numero_documento, categoria, estado, precio_total,
                                 precio_base, descuento_valor, descuento_porcentaje,
                                 fecha_registro, runt_registrado)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, datos_mat + (curso["fecha"], 1 if curso["runt"] else 0))
                    else:
                        cur.execute("""
                            INSERT INTO matriculas
                                (numero_orden, anio, numero_documento, categoria, estado, precio_total,
                                 precio_base, descuento_valor, descuento_porcentaje)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, datos_mat)
                    matricula_id = cur.execute("SELECT id FROM matriculas WHERE anio = %s AND numero_orden = %s",
                                               (anio, orden)).fetchone()["id"]
                    codigos.append(f"{orden}-{str(anio)[-2:]}")
                    cur.execute("""
                        INSERT INTO matricula_costos (id_matricula, concepto, valor, usuario_id)
                        SELECT %s, concepto, valor, %s FROM costos_plantilla
                        WHERE tipo = %s AND categoria = %s AND activo = 1
                    """, (matricula_id, session["uid"], tipo_tarifa, c_base))
                    if responsable_informado:
                        cur.execute("""
                            INSERT INTO responsables_matricula
                                (id_matricula, tipo_documento, numero_documento, nombres, apellidos,
                                 celular, email, relacion)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (matricula_id, responsable["tipo_documento"], responsable["numero_documento"],
                              responsable["nombres"], responsable["apellidos"], responsable["celular"],
                              responsable["email"], responsable["relacion"]))
                    if c_abono and en_curso:
                        cur.execute("""
                            INSERT INTO pagos (id_matricula, concepto, valor, metodo_pago, numero_recibo,
                                               usuario_id, caja_id, observaciones, acompanante, fecha_pago)
                            VALUES (%s, 'Abono histórico previo', %s, 'Otro', %s, %s, NULL, %s, %s, %s)
                        """, (matricula_id, c_abono, f"HIST-{matricula_id}", session["uid"],
                              observaciones_abono, acompanante, curso["fecha"]))
                    elif c_abono:
                        caja = cur.execute(
                            "SELECT id FROM cajas WHERE usuario_id = %s AND estado = 'ABIERTA' FOR UPDATE",
                            (session["uid"],),
                        ).fetchone()
                        if not caja:
                            raise DatosMatriculaInvalidos("Abre tu caja antes de registrar un abono inicial.")
                        recibo = numero_recibo(cur)
                        recibos.append(recibo)
                        cur.execute("""
                            INSERT INTO pagos (id_matricula, concepto, valor, metodo_pago, numero_recibo,
                                               usuario_id, caja_id, observaciones, acompanante)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (matricula_id,
                              f"Renovación de licencia — {c_base}" if tipo_matricula == "renovacion"
                              else "Pago curso de conducción",
                              c_abono, metodo_pago, recibo, session["uid"], caja["id"],
                              observaciones_abono, acompanante))
            creada = True
            break
        except DatosMatriculaInvalidos as e:
            flash(str(e), "error")
            return redirect(url_for("alumnos.lista"))
        except oracledb.IntegrityError as e:
            if not _duplicado_unico(e) or "UQ_MAT_ORDEN" not in str(e).upper():
                # No es el consecutivo: es otra restricción de la base de datos (p. ej. una que
                # impida varias matrículas por alumno). Se muestra su nombre para poder quitarla.
                restriccion = re.search(r"\(([\w.$]+)\)", str(e))
                current_app.logger.exception("Restricción de la base al crear matrícula")
                flash("La base de datos no dejó guardar esta matrícula"
                      + (f" (restricción {restriccion.group(1)})" if restriccion else "")
                      + ". Si el alumno ya tiene otra categoría, avisa a soporte con este mensaje.", "error")
                return redirect(url_for("alumnos.lista"))
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
        if len(codigos) > 1:
            detalle = ", ".join(f"{cod} ({c['categoria']})" for cod, c in zip(codigos, cursos))
            flash(f"Se registraron {len(codigos)} cursos para el alumno: {detalle}."
                  + (f" Recibos de abono: {', '.join(recibos)}." if recibos else ""), "ok")
        else:
            flash(f"{'Alumno en curso registrado' if en_curso else 'Renovación' if tipo_matricula == 'renovacion' else 'Matrícula'} "
                  f"{codigos[0]} creada correctamente."
                  + (f" Recibo del abono: {recibos[0]}." if recibos else ""), "ok")
    return redirect(url_for("alumnos.lista", recibo_nuevo=recibos[0]) if recibos
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
            categoria_actual = (fila["categoria"] or "").strip()
            tipo_matricula = "RENOVACION" if str(categoria_actual).startswith("Renovación") else "CURSO"
            categoria_base = categoria_actual.replace("Renovación - ", "", 1) if tipo_matricula == "RENOVACION" else categoria_actual
            tarifas = db.fetchall(
                "SELECT categoria FROM tarifas_categoria WHERE activo = 1 AND tipo = %s ORDER BY categoria",
                (tipo_matricula,),
            )
            pagado = db.fetchone(
                "SELECT COALESCE(SUM(valor), 0) AS total FROM pagos "
                "WHERE id_matricula = %s AND anulado = 0",
                (matricula_id,),
            )["total"]
            return render_template(
                "editar_alumno.html",
                alumno=fila,
                pagado=pagado,
                tarifas=tarifas,
                tipo_matricula=tipo_matricula,
                categoria_base=categoria_base,
            )

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
        if not categoria or len(categoria) > 60:
            raise DatosMatriculaInvalidos("La categoría es obligatoria y admite hasta 60 caracteres.")
        try:
            validar_datos_alumno(
                documento, tipo_documento, nombres, apellidos, opcionales,
            )
        except ValueError as e:
            raise DatosMatriculaInvalidos(str(e)) from e

        base = parsear_pesos(request.form.get("precio_base", "").strip())
        descuento_valor = parsear_pesos(request.form.get("descuento_valor", "").strip() or "0")
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
        try:
            validar_responsable(responsable)
        except ValueError as e:
            raise DatosMatriculaInvalidos(str(e)) from e

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
            tipo_matricula = "RENOVACION" if str(actual["categoria"]).startswith("Renovación") else "CURSO"
            categoria_base = " ".join(request.form.get("categoria", "").upper().split())
            categoria_final = f"Renovación - {categoria_base}" if tipo_matricula == "RENOVACION" else categoria_base
            if not categoria_base or len(categoria_final) > 60:
                raise DatosMatriculaInvalidos("La categoría es obligatoria y admite hasta 60 caracteres.")
            tarifa_activa = cur.execute(
                "SELECT categoria FROM tarifas_categoria WHERE categoria = %s AND tipo = %s AND activo = 1",
                (categoria_base, tipo_matricula),
            ).fetchone()
            if not tarifa_activa and categoria_final != actual["categoria"]:
                raise DatosMatriculaInvalidos("Selecciona una categoría activa del mismo tipo.")
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
            """, (categoria_final, base, total, descuento_valor, porcentaje, estado, matricula_id))

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
                       "categoria": categoria_final, "precio_base": base, "precio_total": total,
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


@bp.route("/alumnos/matricula/<int:matricula_id>/borrar", methods=["POST"])
@login_required
@permiso_requerido("eliminar_alumnos")
def borrar_matricula(matricula_id):
    """Borra de verdad la matrícula con sus pagos, costos y reparto. Si el alumno no
    tiene otras matrículas, también borra al alumno. Deja una copia en la auditoría."""
    motivo = " ".join(request.form.get("motivo", "").split())
    if not motivo or len(motivo) > 500:
        flash("El motivo es obligatorio y admite hasta 500 caracteres.", "error")
        return redirect(url_for("alumnos.lista"))
    try:
        with db.transaccion() as cur:
            mat = cur.execute(
                """SELECT id, numero_orden, anio, numero_documento, categoria, estado,
                          precio_total, archivado
                   FROM matriculas WHERE id = %s FOR UPDATE""",
                (matricula_id,),
            ).fetchone()
            if not mat:
                flash("La matrícula ya no existe.", "error")
                return redirect(url_for("alumnos.lista"))

            pagos = cur.execute(
                """SELECT p.id, p.numero_recibo, p.concepto, p.valor, p.metodo_pago, p.anulado,
                          p.caja_id, c.estado AS estado_caja
                   FROM pagos p LEFT JOIN cajas c ON c.id = p.caja_id
                   WHERE p.id_matricula = %s""",
                (matricula_id,),
            ).fetchall()
            if any(p["estado_caja"] == "CERRADA" for p in pagos):
                flash("No se puede borrar: tiene pagos en una caja que ya fue cerrada.", "error")
                return redirect(url_for("alumnos.lista"))

            costos = cur.execute(
                "SELECT id, concepto, valor, pagado, anulado FROM matricula_costos WHERE id_matricula = %s",
                (matricula_id,),
            ).fetchall()
            alumno = cur.execute(
                "SELECT numero_documento, tipo_documento, nombres, apellidos "
                "FROM alumnos WHERE numero_documento = %s",
                (mat["numero_documento"],),
            ).fetchone()

            # Copia de lo que se borra, para que quede rastro de quién y por qué.
            _auditar(cur, "MATRICULA", matricula_id, "BORRADO", session["uid"],
                     {"matricula": dict(mat), "alumno": dict(alumno) if alumno else None,
                      "pagos": [{k: p[k] for k in ("numero_recibo", "concepto", "valor",
                                                   "metodo_pago", "anulado")} for p in pagos],
                      "costos": [dict(c) for c in costos]},
                     None, motivo)

            # Orden: primero lo que depende de otras filas.
            cur.execute("""DELETE FROM pago_distribucion
                           WHERE id_pago IN (SELECT id FROM pagos WHERE id_matricula = %s)""",
                        (matricula_id,))
            cur.execute("""DELETE FROM pago_distribucion
                           WHERE id_costo IN (SELECT id FROM matricula_costos WHERE id_matricula = %s)""",
                        (matricula_id,))
            cur.execute("DELETE FROM pagos WHERE id_matricula = %s", (matricula_id,))
            cur.execute("DELETE FROM matricula_costos WHERE id_matricula = %s", (matricula_id,))
            cur.execute("DELETE FROM responsables_matricula WHERE id_matricula = %s", (matricula_id,))
            cur.execute("DELETE FROM matriculas WHERE id = %s", (matricula_id,))

            otras = cur.execute(
                "SELECT COUNT(*) AS n FROM matriculas WHERE numero_documento = %s",
                (mat["numero_documento"],),
            ).fetchone()["n"]
            if not otras:
                cur.execute("DELETE FROM alumnos WHERE numero_documento = %s",
                            (mat["numero_documento"],))
    except Exception:
        current_app.logger.exception("Error borrando matrícula %s", matricula_id)
        flash("No se pudo borrar. Intenta de nuevo.", "error")
        return redirect(url_for("alumnos.lista"))
    flash("Alumno borrado definitivamente junto con sus pagos y costos.", "ok")
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
               p.anulado, p.motivo_anulacion, u.nombre AS cajero,
               p.confirmado, uc.nombre AS confirmado_por_nombre, p.fecha_confirmacion
        FROM pagos p LEFT JOIN usuarios u ON u.id = p.usuario_id
        LEFT JOIN usuarios uc ON uc.id = p.confirmado_por
        WHERE p.id_matricula = %s
        ORDER BY p.fecha_pago DESC
    """, (matricula_id,))
    pagado = sum(float(p["valor"]) for p in pagos if not p["anulado"])
    return render_template("historial_pagos.html", alumno=alumno, pagos=pagos,
                           pagado=pagado, saldo=max(float(alumno["precio_total"]) - pagado, 0))


@bp.route("/pagos/<numero>/anular", methods=["POST"])
@login_required
@permiso_requerido("anular_pagos")
def anular_pago(numero):
    motivo = " ".join(request.form.get("motivo", "").split())
    desde_bandeja = request.form.get("origen") == "pendientes"
    bandeja = url_for("caja.resumen", pendientes=1)
    if not re.fullmatch(r"[A-Za-z0-9-]{6,50}", numero):
        return "Recibo no válido.", 404
    if not motivo or len(motivo) > 500:
        flash("El motivo de anulación es obligatorio y admite hasta 500 caracteres.", "error")
        return redirect(bandeja if desde_bandeja else url_for("alumnos.lista"))
    try:
        with db.transaccion() as cur:
            pago = cur.execute("""
                SELECT id, id_matricula, numero_recibo, concepto, valor, metodo_pago,
                       anulado, motivo_anulacion, caja_id
                FROM pagos WHERE numero_recibo = %s FOR UPDATE
            """, (numero,)).fetchone()
            if not pago:
                flash("No se encontró el pago.", "error")
                return redirect(bandeja if desde_bandeja else url_for("alumnos.lista"))
            if pago["anulado"]:
                flash("Este pago ya fue anulado.", "error")
                return redirect(bandeja if desde_bandeja else url_for("alumnos.historial", matricula_id=pago["id_matricula"]))
            if pago["caja_id"]:
                caja_pago = cur.execute(
                    "SELECT estado FROM cajas WHERE id = %s FOR UPDATE",
                    (pago["caja_id"],),
                ).fetchone()
                if caja_pago and caja_pago["estado"] == "CERRADA":
                    flash("No se puede anular un pago de una caja cerrada.", "error")
                    return redirect(bandeja if desde_bandeja else url_for("alumnos.historial", matricula_id=pago["id_matricula"]))
            cur.execute("""
                UPDATE pagos SET anulado = 1, motivo_anulacion = %s,
                    anulado_por = %s, fecha_anulacion = CURRENT_TIMESTAMP
                WHERE id = %s AND anulado = 0
            """, (motivo, session["uid"], pago["id"]))
            cur.execute("""
                UPDATE movimientos_banco SET anulado = 1, motivo_anulacion = %s
                WHERE origen = 'PAGO' AND referencia = %s AND anulado = 0
            """, (f"Pago anulado: {motivo}"[:500], numero))
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
        return redirect(bandeja if desde_bandeja else url_for("alumnos.lista"))
    flash(f"El pago {numero} fue anulado. El recibo y el registro se conservaron.", "ok")
    return redirect(bandeja if desde_bandeja else url_for("alumnos.historial", matricula_id=pago["id_matricula"]))


@bp.route("/pagos/<numero>/confirmar", methods=["POST"])
@login_required
@permiso_requerido("confirmar_pagos")
def confirmar_pago(numero):
    if not re.fullmatch(r"[A-Za-z0-9-]{6,50}", numero):
        return "Recibo no válido.", 404
    desde_bandeja = request.form.get("origen") == "pendientes"
    bandeja = url_for("caja.resumen", pendientes=1)
    destino = bandeja if desde_bandeja else url_for("alumnos.lista")
    try:
        with db.transaccion() as cur:
            pago = cur.execute("""
                SELECT id, id_matricula, numero_recibo, concepto, valor, metodo_pago,
                       anulado, confirmado
                FROM pagos WHERE numero_recibo = %s FOR UPDATE
            """, (numero,)).fetchone()
            if not pago:
                flash("No se encontró el pago.", "error")
                return redirect(destino)
            if not desde_bandeja:
                destino = url_for("alumnos.historial", matricula_id=pago["id_matricula"])
            if pago["anulado"]:
                flash("Un pago anulado no se puede confirmar.", "error")
                return redirect(destino)
            if pago["confirmado"]:
                flash("Este pago ya estaba confirmado.", "error")
                return redirect(destino)
            cur.execute("""
                UPDATE pagos SET confirmado = 1, confirmado_por = %s,
                    fecha_confirmacion = CURRENT_TIMESTAMP
                WHERE id = %s AND confirmado = 0 AND anulado = 0
            """, (session["uid"], pago["id"]))
            _auditar(cur, "PAGO", pago["id"], "CONFIRMACION", session["uid"],
                     dict(pago), {**pago, "confirmado": 1})
    except Exception:
        current_app.logger.exception("Error confirmando recibo %s", numero)
        flash("No se pudo confirmar el pago. Intenta de nuevo.", "error")
        return redirect(destino)
    flash(f"El pago {numero} quedó confirmado.", "ok")
    return redirect(destino)
