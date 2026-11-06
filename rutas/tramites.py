"""Trámites: recordatorios de registro en el RUNT (y expedientes más adelante)."""
import time

from flask import Blueprint, current_app, jsonify, render_template

import db
from auth import login_required, permiso_requerido
from utils import a_fecha, hoy

bp = Blueprint("tramites", __name__)

_cache = {"t": 0.0, "n": 0}


def _pendientes() -> list[dict]:
    filas = db.fetchall("""
        SELECT m.id, a.nombres, a.apellidos, a.numero_documento, m.categoria,
               m.fecha_registro, m.estado
        FROM matriculas m
        JOIN alumnos a ON a.numero_documento = m.numero_documento
        WHERE (m.runt_registrado IS NULL OR m.runt_registrado = 0)
          AND m.estado <> 'Histórico' AND m.archivado = 0
        ORDER BY m.fecha_registro ASC
    """)
    hoy_ = hoy()
    for f in filas:
        d = a_fecha(f["fecha_registro"])
        f["dias"] = (hoy_ - d).days if d else 0
    return filas


def contar_pendientes_cacheado() -> int:
    """Número para la insignia del menú. Se cachea 60 s para no consultar en cada página."""
    if time.time() - _cache["t"] > 60:
        try:
            resultado = db.fetchone("""
                SELECT COUNT(*) AS n
                FROM matriculas
                WHERE (runt_registrado IS NULL OR runt_registrado = 0)
                  AND estado <> 'Histórico' AND archivado = 0
            """)
        except Exception:
            current_app.logger.exception("No se pudo actualizar el contador de pendientes RUNT")
        else:
            _cache["n"] = int(resultado["n"]) if resultado else 0
        _cache["t"] = time.time()
    return _cache["n"]


@bp.route("/tramites")
@login_required
@permiso_requerido("ver_tramites")
def lista():
    error, filas = None, []
    try:
        filas = _pendientes()
    except Exception:
        error = "No se pudo consultar los pendientes de RUNT."
        current_app.logger.exception("No se pudo consultar los pendientes de RUNT")
    grupos = {
        "urgentes": [f for f in filas if f["dias"] >= 60],
        "proximos": [f for f in filas if 30 <= f["dias"] < 60],
        "recientes": [f for f in filas if f["dias"] < 30],
    }
    return render_template("tramites.html", g=grupos, total=len(filas), error=error)


@bp.route("/tramites/runt/<int:matricula_id>", methods=["POST"])
@login_required
@permiso_requerido("marcar_runt")
def marcar_runt(matricula_id):
    afectadas = db.execute(
        "UPDATE matriculas SET runt_registrado = 1 "
        "WHERE id = %s AND estado <> 'Histórico' AND (runt_registrado IS NULL OR runt_registrado = 0)",
        (matricula_id,),
    )
    if afectadas != 1:
        return jsonify(ok=False, error="La matrícula no existe, es histórica o ya está registrada."), 404
    _cache["t"] = 0  # refrescar la insignia
    return jsonify(ok=True)
