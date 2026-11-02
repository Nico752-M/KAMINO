from datetime import date, timedelta

from flask import Blueprint, render_template

import db
from auth import login_required, permiso_requerido
from utils import hoy

bp = Blueprint("dashboard", __name__)


def _rango_mes(d: date) -> tuple[date, date]:
    inicio = d.replace(day=1)
    siguiente = (inicio + timedelta(days=32)).replace(day=1)
    return inicio, siguiente


@bp.route("/")
@login_required
@permiso_requerido("ver_dashboard")
def index():
    datos = {"activos": 0, "ingresos_mes": 0, "pendiente_total": 0, "deudores": []}
    error = None
    try:
        inicio, fin = _rango_mes(hoy())
        r = db.fetchone("""
            SELECT
                (SELECT COUNT(*) FROM matriculas
                 WHERE archivado = 0 AND estado NOT IN ('Cancelado', 'Histórico')) AS activos,
                (SELECT COALESCE(SUM(valor), 0) FROM pagos
                 WHERE fecha_pago >= %s AND fecha_pago < %s AND anulado = 0) AS ingresos_mes,
                (SELECT COALESCE(SUM(saldo), 0) FROM (
                    SELECT COALESCE(m.precio_total, 0) - COALESCE(SUM(p.valor), 0) AS saldo
                    FROM matriculas m
                    LEFT JOIN pagos p ON p.id_matricula = m.id AND p.anulado = 0
                    WHERE m.archivado = 0 AND m.estado NOT IN ('Cancelado', 'Histórico')
                    GROUP BY m.id, m.precio_total
                    HAVING COALESCE(m.precio_total, 0) > COALESCE(SUM(p.valor), 0)
                )) AS pendiente_total
            FROM dual
        """, (inicio, fin))
        datos["activos"] = int(r["activos"]) if r else 0
        datos["ingresos_mes"] = float(r["ingresos_mes"]) if r else 0
        datos["pendiente_total"] = float(r["pendiente_total"]) if r else 0

        filas = db.fetchall("""
            SELECT *
            FROM (
                SELECT m.id, a.nombres, a.apellidos, a.numero_documento, m.categoria,
                       COALESCE(m.precio_total, 0) AS precio_total,
                       COALESCE(SUM(p.valor), 0) AS pagado,
                       COALESCE(m.precio_total, 0) - COALESCE(SUM(p.valor), 0) AS saldo
                FROM matriculas m
                JOIN alumnos a ON a.numero_documento = m.numero_documento
                LEFT JOIN pagos p ON p.id_matricula = m.id AND p.anulado = 0
                WHERE m.archivado = 0 AND m.estado NOT IN ('Cancelado', 'Histórico')
                GROUP BY m.id, a.nombres, a.apellidos, a.numero_documento,
                         m.categoria, m.precio_total
                HAVING COALESCE(m.precio_total, 0) > COALESCE(SUM(p.valor), 0)
                ORDER BY saldo DESC
            )
            FETCH FIRST 5 ROWS ONLY
        """)
        datos["deudores"] = filas
    except Exception as e:
        error = "No se pudieron cargar las métricas. Revisa la conexión con la base de datos."
        print(f"[dashboard] {e}")

    return render_template("dashboard.html", d=datos, error=error)