from flask import Blueprint, render_template, request

import db
from auth import login_required

bp = Blueprint("alumnos", __name__)

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
    except Exception as e:
        error = "No se pudo consultar la lista de alumnos."
        print(f"[alumnos] {e}")

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
                           q=q, error=error, limite=len(filas) >= 200)