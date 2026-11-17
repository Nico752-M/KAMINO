from datetime import date, timedelta

from flask import Blueprint, current_app, render_template

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
    datos = {
        "activos": 0, "ingresos_mes": 0, "pendiente_total": 0,
        "matriculas_mes": 0, "matriculas_mes_anterior": 0,
        "por_categoria": [], "recientes": [], "deudores": [],
    }
    error = None
    try:
        inicio, fin = _rango_mes(hoy())
        inicio_mes_anterior = (inicio - timedelta(days=1)).replace(day=1)
        r = db.fetchone("""
            SELECT
                (SELECT COUNT(*) FROM matriculas
                 WHERE archivado = 0 AND estado <> 'Histórico') AS activos,
                (SELECT COUNT(*) FROM matriculas
                 WHERE archivado = 0 AND fecha_registro >= %s AND fecha_registro < %s) AS matriculas_mes,
                (SELECT COUNT(*) FROM matriculas
                 WHERE archivado = 0 AND fecha_registro >= %s AND fecha_registro < %s) AS matriculas_mes_anterior,
                (SELECT COALESCE(SUM(valor), 0) FROM pagos
                 WHERE fecha_pago >= %s AND fecha_pago < %s AND anulado = 0
                   AND concepto <> 'Abono histórico previo') AS ingresos_mes,
                (SELECT COALESCE(SUM(saldo), 0) FROM (
                    SELECT COALESCE(m.precio_total, 0) - COALESCE(SUM(p.valor), 0) AS saldo
                    FROM matriculas m
                    LEFT JOIN pagos p ON p.id_matricula = m.id AND p.anulado = 0
                    WHERE m.archivado = 0 AND m.estado <> 'Histórico'
                    GROUP BY m.id, m.precio_total
                    HAVING COALESCE(m.precio_total, 0) > COALESCE(SUM(p.valor), 0)
                )) AS pendiente_total
            FROM dual
        """, (inicio, fin, inicio_mes_anterior, inicio, inicio, fin))
        datos["activos"] = int(r["activos"]) if r else 0
        datos["matriculas_mes"] = int(r["matriculas_mes"]) if r else 0
        datos["matriculas_mes_anterior"] = int(r["matriculas_mes_anterior"]) if r else 0
        datos["ingresos_mes"] = float(r["ingresos_mes"]) if r else 0
        datos["pendiente_total"] = float(r["pendiente_total"]) if r else 0

        sql_categoria = """
            SELECT categoria, COUNT(*) AS cantidad
            FROM matriculas
            WHERE archivado = 0 AND fecha_registro >= %s AND fecha_registro < %s
            GROUP BY categoria
            ORDER BY cantidad DESC, categoria
            FETCH FIRST 8 ROWS ONLY
        """
        sql_recientes = """
            SELECT m.id, m.fecha_registro, m.categoria,
                   CASE WHEN m.estado = 'Cancelado' THEN 'Pagado' ELSE m.estado END AS estado,
                   a.nombres, a.apellidos, m.precio_total,
                   COALESCE((SELECT SUM(p.valor) FROM pagos p
                             WHERE p.id_matricula = m.id AND p.anulado = 0), 0) AS pagado
            FROM (
                SELECT id, fecha_registro, categoria, estado, numero_documento, precio_total
                FROM matriculas
                WHERE archivado = 0
                ORDER BY fecha_registro DESC, id DESC
                FETCH FIRST 8 ROWS ONLY
            ) m
            JOIN alumnos a ON a.numero_documento = m.numero_documento
            ORDER BY m.fecha_registro DESC, m.id DESC
        """
        sql_deudores = """
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
        """
        datos["por_categoria"] = db.fetchall(sql_categoria, (inicio, fin))
        datos["recientes"] = db.fetchall(sql_recientes)
        datos["deudores"] = db.fetchall(sql_deudores)

        for matricula in datos["recientes"]:
            total = float(matricula["precio_total"] or 0)
            pagado = float(matricula["pagado"] or 0)
            matricula["progreso"] = min(100, round(pagado * 100 / total)) if total else 0
            matricula["saldo"] = max(total - pagado, 0)
    except Exception as e:
        error = "No se pudieron cargar las métricas. Revisa la conexión con la base de datos."
        current_app.logger.exception("No se pudieron cargar las métricas del dashboard: %s", e)

    return render_template("dashboard.html", d=datos, error=error)