import re
import time

import oracledb
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

import db
from auth import login_required, permiso_requerido
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


@bp.route("/alumnos/matricula", methods=["POST"])
@login_required
@permiso_requerido("crear_matricula")
def crear_matricula():
    documento = request.form.get("numero_documento", "").strip()
    nombres = " ".join(request.form.get("nombres", "").split())
    apellidos = " ".join(request.form.get("apellidos", "").split())
    categoria = request.form.get("categoria", "").strip()
    precio_texto = request.form.get("precio_total", "").strip()

    if not re.fullmatch(r"[A-Za-z0-9.-]{1,20}", documento):
        flash("El documento debe tener hasta 20 caracteres válidos.", "error")
        return redirect(url_for("alumnos.lista"))
    if not nombres or len(nombres) > 100 or not apellidos or len(apellidos) > 100:
        flash("Escribe nombres y apellidos de hasta 100 caracteres.", "error")
        return redirect(url_for("alumnos.lista"))
    if not categoria or len(categoria) > 60:
        flash("La categoría es obligatoria y admite hasta 60 caracteres.", "error")
        return redirect(url_for("alumnos.lista"))
    if not precio_texto.isascii() or not precio_texto.isdecimal():
        flash("El precio debe ser un valor entero en pesos.", "error")
        return redirect(url_for("alumnos.lista"))
    precio = int(precio_texto)
    if precio <= 0 or precio > 999_999_999_999:
        flash("El precio debe estar entre $1 y $999.999.999.999.", "error")
        return redirect(url_for("alumnos.lista"))

    anio = hoy().year
    creada = False
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
                        "INSERT INTO alumnos (numero_documento, nombres, apellidos) VALUES (%s, %s, %s)",
                        (documento, nombres, apellidos),
                    )

                orden = cur.execute(
                    "SELECT COALESCE(MAX(numero_orden), 0) + 1 AS siguiente "
                    "FROM matriculas WHERE anio = %s",
                    (anio,),
                ).fetchone()["siguiente"]
                cur.execute("""
                    INSERT INTO matriculas
                        (numero_orden, anio, numero_documento, categoria, estado, precio_total)
                    VALUES (%s, %s, %s, %s, 'Activo', %s)
                """, (orden, anio, documento, categoria, precio))
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
        flash(f"Matrícula {orden}-{str(anio)[-2:]} creada correctamente.", "ok")
    return redirect(url_for("alumnos.lista"))