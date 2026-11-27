"""Reportes de alumnos en PDF y Excel: información general, costos y pagos.

Se pueden sacar de un alumno en específico, de un rango de fechas (por fecha de
matrícula o por fecha de pago) o de todos los alumnos registrados hasta hoy.
"""
import re
from datetime import date, timedelta
from io import BytesIO
from xml.sax.saxutils import escape

from flask import Blueprint, Response, current_app, flash, redirect, request, url_for

import db
from auth import login_required, permiso_requerido, permisos_actuales
from rutas.alumnos import _like, _normalizar_busqueda
from servicios.matriculas import ETIQUETA_TIPO, tipo_de_categoria
from utils import a_fecha, ahora, cop, hoy

bp = Blueprint("reportes_alumnos", __name__)

MAX_FILAS = 20_000
_NORMALIZAR = (
    "TRANSLATE(UPPER({}), 'ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝÁÉÍÓÚÜ', "
    "'AAAAAACEEEEIIIINOOOOOUUUUYAEIOUU')"
)


class ReporteInvalido(Exception):
    pass


# ───────────── Parámetros y consultas ─────────────

def _leer_filtros() -> dict:
    alcance = request.args.get("alcance", "todos")
    formato = request.args.get("formato", "pdf")
    if alcance not in ("todos", "fechas", "alumno"):
        raise ReporteInvalido("Elige de quién quieres el reporte.")
    if formato not in ("pdf", "excel"):
        raise ReporteInvalido("Elige el formato: PDF o Excel.")
    filtros = {"alcance": alcance, "formato": formato, "campo": "matricula",
               "desde": None, "hasta": None, "documento": None, "alumno_texto": None}

    if alcance == "fechas":
        filtros["campo"] = "pago" if request.args.get("campo_fecha") == "pago" else "matricula"
        try:
            for clave in ("desde", "hasta"):
                texto = request.args.get(clave, "").strip()
                filtros[clave] = date.fromisoformat(texto) if texto else None
        except ValueError:
            raise ReporteInvalido("Las fechas no tienen un formato válido.")
        if not filtros["desde"] and not filtros["hasta"]:
            raise ReporteInvalido("Escribe al menos una fecha (desde o hasta).")
        if filtros["desde"] and filtros["hasta"] and filtros["desde"] > filtros["hasta"]:
            raise ReporteInvalido("«Desde» no puede ser posterior a «Hasta».")

    elif alcance == "alumno":
        texto = " ".join(request.args.get("documento", "").split())[:60]
        if not texto:
            raise ReporteInvalido("Escribe el documento o el nombre del alumno.")
        filtros["documento"] = _resolver_alumno(texto)
    return filtros


def _resolver_alumno(texto: str) -> str:
    """Devuelve el documento del alumno buscado por documento exacto o por nombre."""
    if re.fullmatch(r"[A-Za-z0-9.-]{1,20}", texto):
        exacto = db.fetchone("SELECT numero_documento FROM alumnos WHERE numero_documento = %s",
                             (texto,))
        if exacto:
            return exacto["numero_documento"]
    like = _like(_normalizar_busqueda(texto))
    nombre = _NORMALIZAR.format("a.nombres || ' ' || a.apellidos")
    encontrados = db.fetchall(
        rf"""SELECT a.numero_documento, a.nombres, a.apellidos FROM alumnos a
             WHERE {nombre} LIKE %s ESCAPE '\'
             ORDER BY a.apellidos, a.nombres FETCH FIRST 6 ROWS ONLY""",
        (like,),
    )
    if not encontrados:
        raise ReporteInvalido("No se encontró ningún alumno con ese documento o nombre.")
    if len(encontrados) > 1:
        opciones = "; ".join(f"{f['nombres']} {f['apellidos']} ({f['numero_documento']})"
                             for f in encontrados[:5])
        raise ReporteInvalido(f"Hay varios alumnos con ese nombre: {opciones}. "
                              "Escribe el número de documento.")
    return encontrados[0]["numero_documento"]


def _condicion(filtros: dict) -> tuple[str, list]:
    """WHERE sobre matrículas (alias m) según el alcance elegido."""
    cond, params = [], []
    if filtros["alcance"] == "alumno":
        cond.append("m.numero_documento = %s")
        params.append(filtros["documento"])
    elif filtros["alcance"] == "fechas":
        columna = "m.fecha_registro"
        if filtros["campo"] == "pago":
            sub = ["p.id_matricula = m.id", "p.anulado = 0"]
            if filtros["desde"]:
                sub.append("p.fecha_pago >= %s")
                params.append(filtros["desde"])
            if filtros["hasta"]:
                sub.append("p.fecha_pago < %s")
                params.append(filtros["hasta"] + timedelta(days=1))
            cond.append("EXISTS (SELECT 1 FROM pagos p WHERE " + " AND ".join(sub) + ")")
        else:
            if filtros["desde"]:
                cond.append(f"{columna} >= %s")
                params.append(filtros["desde"])
            if filtros["hasta"]:
                cond.append(f"{columna} < %s")
                params.append(filtros["hasta"] + timedelta(days=1))
    return ("WHERE " + " AND ".join(cond)) if cond else "", params


def _estado(fila: dict) -> str:
    if fila["archivado"]:
        return "Archivado"
    return "Pagado" if fila["estado"] == "Cancelado" else fila["estado"]


def _cargar(filtros: dict) -> dict:
    """Consulta matrículas, pagos y (si hay permiso) costos con el mismo filtro."""
    donde, params = _condicion(filtros)
    con_costos = "ver_ganancias" in permisos_actuales()
    por_pago = filtros["alcance"] == "fechas" and filtros["campo"] == "pago"

    # Pagos dentro del rango (solo cuando se filtra por fecha de pago)
    filtro_pago, params_pago = "", []
    if por_pago:
        if filtros["desde"]:
            filtro_pago += " AND p.fecha_pago >= %s"
            params_pago.append(filtros["desde"])
        if filtros["hasta"]:
            filtro_pago += " AND p.fecha_pago < %s"
            params_pago.append(filtros["hasta"] + timedelta(days=1))

    matriculas = db.fetchall(f"""
        SELECT m.id, m.numero_orden, m.anio, m.categoria, m.estado, m.archivado,
               m.fecha_registro, m.runt_registrado,
               COALESCE(m.precio_base, 0) AS precio_base,
               COALESCE(m.descuento_valor, 0) AS descuento_valor,
               COALESCE(m.precio_total, 0) AS precio_total,
               a.tipo_documento, a.numero_documento, a.nombres, a.apellidos,
               a.celular, a.email, a.fecha_nacimiento,
               COALESCE((SELECT SUM(p.valor) FROM pagos p
                          WHERE p.id_matricula = m.id AND p.anulado = 0), 0) AS pagado,
               COALESCE((SELECT SUM(p.valor) FROM pagos p
                          WHERE p.id_matricula = m.id AND p.anulado = 0{filtro_pago}), 0) AS pagado_periodo,
               COALESCE((SELECT SUM(c.valor) FROM matricula_costos c
                          WHERE c.id_matricula = m.id AND c.anulado = 0), 0) AS costos,
               COALESCE((SELECT SUM(c.valor) FROM matricula_costos c
                          WHERE c.id_matricula = m.id AND c.anulado = 0
                            AND NVL(c.pagado, 0) <> 0), 0) AS costos_pagados
        FROM matriculas m
        JOIN alumnos a ON a.numero_documento = m.numero_documento
        {donde}
        ORDER BY a.apellidos, a.nombres, m.fecha_registro, m.id
        FETCH FIRST {MAX_FILAS + 1} ROWS ONLY
    """, tuple(params_pago + params))
    if len(matriculas) > MAX_FILAS:
        raise ReporteInvalido("El reporte es demasiado grande. Acota el rango de fechas.")

    subconsulta = f"SELECT m.id FROM matriculas m JOIN alumnos a ON a.numero_documento = m.numero_documento {donde}"
    # Se traen TODOS los pagos de esas matrículas (aunque se filtre por fecha de pago) para
    # numerar los abonos y calcular lo acumulado y el saldo correctamente.
    pagos = db.fetchall(f"""
        SELECT p.id_matricula, p.fecha_pago, p.numero_recibo, p.concepto, p.metodo_pago,
               p.valor, p.anulado, p.confirmado, p.motivo_anulacion
        FROM pagos p
        WHERE p.id_matricula IN ({subconsulta})
        ORDER BY p.fecha_pago, p.numero_recibo
    """, tuple(params))

    costos = []
    if con_costos:
        costos = db.fetchall(f"""
            SELECT c.id_matricula, c.concepto, c.valor, c.pagado, c.fecha_pago, c.observaciones
            FROM matricula_costos c
            WHERE c.anulado = 0 AND c.id_matricula IN ({subconsulta})
            ORDER BY c.id_matricula, c.fecha_registro, c.id
        """, tuple(params))

    # ── Datos derivados por matrícula ──
    por_id = {}
    for m in matriculas:
        tipo, base = tipo_de_categoria(m["categoria"])
        m["codigo"] = f"{m['numero_orden']}-{str(m['anio'])[-2:]}"
        m["tipo_texto"] = ETIQUETA_TIPO[tipo]
        m["categoria_base"] = base
        m["estado_texto"] = _estado(m)
        m["alumno"] = f"{m['nombres']} {m['apellidos']}".strip()
        m["saldo"] = max(int(m["precio_total"]) - int(m["pagado"]), 0)
        m["ganancia"] = int(m["precio_total"]) - int(m["costos"])
        m["n_pagos"], m["primer_pago"], m["ultimo_pago"] = 0, None, None
        por_id[m["id"]] = m

    # ── Pagos: número de abono, acumulado y saldo después de cada uno ──
    acumulado, numero = {}, {}
    for p in pagos:
        m = por_id.get(p["id_matricula"])
        p["codigo"] = m["codigo"] if m else ""
        p["documento"] = m["numero_documento"] if m else ""
        p["alumno"] = m["alumno"] if m else ""
        p["categoria"] = m["categoria"] if m else ""
        p["estado_texto"] = ("Anulado" if p["anulado"]
                             else "Confirmado" if p["confirmado"] else "Pendiente")
        p["abono_n"] = p["acumulado"] = p["saldo_despues"] = None
        if m and not p["anulado"]:
            numero[m["id"]] = numero.get(m["id"], 0) + 1
            acumulado[m["id"]] = acumulado.get(m["id"], 0) + int(p["valor"])
            p["abono_n"] = numero[m["id"]]
            p["acumulado"] = acumulado[m["id"]]
            p["saldo_despues"] = max(int(m["precio_total"]) - acumulado[m["id"]], 0)
            m["n_pagos"] += 1
            fecha = a_fecha(p["fecha_pago"])
            m["primer_pago"] = m["primer_pago"] or fecha
            m["ultimo_pago"] = fecha
    for c in costos:
        m = por_id.get(c["id_matricula"])
        c["codigo"] = m["codigo"] if m else ""
        c["alumno"] = m["alumno"] if m else ""
        c["categoria"] = m["categoria"] if m else ""

    # Si se filtra por fecha de pago, el detalle muestra solo los pagos de ese rango
    if por_pago:
        def en_rango(p):
            f = a_fecha(p["fecha_pago"])
            return (f is not None and (not filtros["desde"] or f >= filtros["desde"])
                    and (not filtros["hasta"] or f <= filtros["hasta"]))
        pagos = [p for p in pagos if en_rango(p)]
    vigentes = [p for p in pagos if not p["anulado"]]

    # ── Resumen por alumno ──
    alumnos = {}
    for m in matriculas:
        g = alumnos.setdefault(m["numero_documento"], {
            "tipo_documento": m["tipo_documento"], "documento": m["numero_documento"],
            "nombres": m["nombres"], "apellidos": m["apellidos"], "alumno": m["alumno"],
            "celular": m["celular"], "email": m["email"], "matriculas": 0, "categorias": [],
            "total": 0, "pagado": 0, "saldo": 0, "costos": 0, "ganancia": 0,
            "n_pagos": 0, "ultimo_pago": None,
        })
        g["matriculas"] += 1
        g["categorias"].append(f"{m['categoria_base']} ({m['tipo_texto']})")
        g["total"] += int(m["precio_total"])
        g["pagado"] += int(m["pagado"])
        g["saldo"] += m["saldo"]
        g["costos"] += int(m["costos"])
        g["ganancia"] += m["ganancia"]
        g["n_pagos"] += m["n_pagos"]
        if m["ultimo_pago"] and (not g["ultimo_pago"] or m["ultimo_pago"] > g["ultimo_pago"]):
            g["ultimo_pago"] = m["ultimo_pago"]
    for g in alumnos.values():
        g["categorias_texto"] = ", ".join(g["categorias"])
        g["estado_texto"] = "Con saldo pendiente" if g["saldo"] > 0 else "Al día"
    alumnos = list(alumnos.values())

    # ── Matrículas con saldo pendiente (mayor deuda primero) ──
    hoy_ = hoy()
    deudores = []
    for m in matriculas:
        if m["saldo"] > 0 and not m["archivado"]:
            fecha = a_fecha(m["fecha_registro"])
            m["dias"] = (hoy_ - fecha).days if fecha else None
            deudores.append(m)
    deudores.sort(key=lambda m: m["saldo"], reverse=True)

    # ── Desgloses ──
    def agrupar(filas, clave, valores):
        grupos = {}
        for f in filas:
            g = grupos.setdefault(clave(f), [0] + [0] * len(valores))
            g[0] += 1
            for i, v in enumerate(valores, 1):
                g[i] += int(v(f))
        return sorted(([k, *v] for k, v in grupos.items()), key=lambda x: str(x[0]))

    por_categoria = [[k[0], k[1], *v] for k, *v in agrupar(
        matriculas, lambda m: (m["tipo_texto"], m["categoria_base"]),
        (lambda m: m["precio_total"], lambda m: m["pagado"], lambda m: m["saldo"]))]
    por_estado = agrupar(
        matriculas, lambda m: m["estado_texto"],
        (lambda m: m["precio_total"], lambda m: m["pagado"], lambda m: m["saldo"]))
    por_medio = agrupar(vigentes, lambda p: p["metodo_pago"], (lambda p: p["valor"],))

    resumen = {
        "matriculas": len(matriculas),
        "alumnos": len(alumnos),
        "total": sum(int(m["precio_total"]) for m in matriculas),
        "descuentos": sum(int(m["descuento_valor"]) for m in matriculas),
        "pagado": sum(int(m["pagado"]) for m in matriculas),
        "saldo": sum(m["saldo"] for m in matriculas),
        "n_pagos": len(vigentes),
        "con_saldo": len({m["numero_documento"] for m in deudores}),
        "al_dia": len(alumnos) - len({m["numero_documento"] for m in deudores}),
        "pagado_periodo": sum(int(p["valor"]) for p in vigentes) if por_pago else None,
        "costos": sum(int(m["costos"]) for m in matriculas) if con_costos else None,
        "costos_pagados": sum(int(m["costos_pagados"]) for m in matriculas) if con_costos else None,
    }
    if con_costos:
        resumen["ganancia"] = resumen["total"] - resumen["costos"]
    return {"matriculas": matriculas, "pagos": pagos, "costos": costos, "alumnos": alumnos,
            "deudores": deudores, "por_categoria": por_categoria, "por_estado": por_estado,
            "por_medio": por_medio, "resumen": resumen, "con_costos": con_costos,
            "por_pago": por_pago}


def _descripcion(filtros: dict, datos: dict) -> str:
    if filtros["alcance"] == "todos":
        return "Todos los alumnos registrados hasta hoy"
    if filtros["alcance"] == "alumno":
        if datos["matriculas"]:
            m = datos["matriculas"][0]
            return f"Alumno: {m['alumno']} · {m['tipo_documento']} {m['numero_documento']}"
        return f"Alumno con documento {filtros['documento']}"
    campo = "fecha de pago" if filtros["campo"] == "pago" else "fecha de matrícula"
    d, h = filtros["desde"], filtros["hasta"]
    rango = (f"del {d:%d/%m/%Y} al {h:%d/%m/%Y}" if d and h
             else f"desde el {d:%d/%m/%Y}" if d else f"hasta el {h:%d/%m/%Y}")
    return f"Alumnos por {campo}, {rango}"


def _nombre_archivo(filtros: dict) -> str:
    if filtros["alcance"] == "alumno":
        base = "alumno-" + re.sub(r"[^A-Za-z0-9-]", "", filtros["documento"] or "")
    elif filtros["alcance"] == "fechas":
        d, h = filtros["desde"], filtros["hasta"]
        base = "alumnos-" + (f"{d:%Y%m%d}" if d else "inicio") + "_" + (f"{h:%Y%m%d}" if h else "hoy")
    else:
        base = f"alumnos-todos-{hoy():%Y%m%d}"
    return "reporte-" + base


# ───────────── Excel ─────────────

_DINERO = '"$"#,##0'
_ENCABEZADOS_DINERO = {
    "Precio base", "Descuento", "Total a pagar", "Pagado", "Saldo", "Pagado en el rango",
    "Costos", "Costos pagados", "Ganancia estimada", "Valor", "Acumulado pagado",
    "Saldo después del pago", "Ganancia",
}


def _excel(filtros: dict, datos: dict) -> Response:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    r, con_costos, por_pago = datos["resumen"], datos["con_costos"], datos["por_pago"]
    libro = Workbook()
    relleno = PatternFill("solid", fgColor="253449")

    def estilo_encabezado(fila):
        for celda in fila:
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = relleno
            celda.alignment = Alignment(vertical="center", wrap_text=True)

    # ── Resumen general ──
    hoja = libro.active
    hoja.title = "Resumen"
    hoja.append(["Reporte de alumnos — CEA La 30"])
    hoja["A1"].font = Font(bold=True, size=14)
    hoja.append(["Alcance", _descripcion(filtros, datos)])
    hoja.append(["Generado", ahora().strftime("%d/%m/%Y %H:%M")])
    hoja.append([])
    filas_resumen = [
        ("Alumnos", r["alumnos"], False), ("Matrículas", r["matriculas"], False),
        ("Alumnos con saldo pendiente", r["con_saldo"], False),
        ("Alumnos al día", r["al_dia"], False),
        ("Pagos registrados (válidos)", r["n_pagos"], False),
        ("Valor total de las matrículas", r["total"], True),
        ("Descuentos otorgados", r["descuentos"], True),
        ("Total pagado", r["pagado"], True), ("Saldo pendiente", r["saldo"], True),
    ]
    if por_pago:
        filas_resumen.append(("Pagado dentro del rango de fechas", r["pagado_periodo"], True))
    if con_costos:
        filas_resumen += [("Costos", r["costos"], True), ("Costos pagados", r["costos_pagados"], True),
                          ("Ganancia estimada", r["ganancia"], True)]
    for nombre, valor, es_dinero in filas_resumen:
        hoja.append([nombre, valor])
        hoja.cell(row=hoja.max_row, column=2).alignment = Alignment(horizontal="right")
        if es_dinero:
            hoja.cell(row=hoja.max_row, column=2).number_format = _DINERO

    def tabla_resumen(titulo, encabezados, filas, dinero):
        hoja.append([])
        hoja.append([titulo])
        hoja.cell(row=hoja.max_row, column=1).font = Font(bold=True, size=12)
        hoja.append(encabezados)
        estilo_encabezado(hoja[hoja.max_row])
        for fila in filas:
            hoja.append(list(fila))
            for i in dinero:
                hoja.cell(row=hoja.max_row, column=i + 1).number_format = _DINERO
        if not filas:
            hoja.append(["Sin registros"])

    tabla_resumen("Por proceso y categoría",
                  ["Proceso", "Categoría", "Matrículas", "Total a pagar", "Pagado", "Saldo"],
                  datos["por_categoria"], (3, 4, 5))
    tabla_resumen("Por estado de la matrícula",
                  ["Estado", "Matrículas", "Total a pagar", "Pagado", "Saldo"],
                  datos["por_estado"], (2, 3, 4))
    tabla_resumen("Por medio de pago",
                  ["Medio de pago", "Pagos", "Valor"], datos["por_medio"], (2,))
    hoja.column_dimensions["A"].width = 38
    for letra in "BCDEF":
        hoja.column_dimensions[letra].width = 20
    hoja.column_dimensions["B"].width = 46

    def hoja_datos(nombre, encabezados, filas):
        h = libro.create_sheet(nombre)
        h.append(encabezados)
        for fila in filas:
            h.append(list(fila))
        return h

    # ── Resumen por alumno ──
    enc_a = ["Tipo documento", "Documento", "Nombres", "Apellidos", "Celular", "Correo",
             "Matrículas", "Categorías", "Total a pagar", "Pagado", "Saldo", "Nº de pagos",
             "Último pago", "Estado"]
    if con_costos:
        enc_a += ["Costos", "Ganancia"]
    filas_a = []
    for g in datos["alumnos"]:
        fila = [g["tipo_documento"], g["documento"], g["nombres"], g["apellidos"],
                g["celular"] or "", g["email"] or "", g["matriculas"], g["categorias_texto"],
                g["total"], g["pagado"], g["saldo"], g["n_pagos"], g["ultimo_pago"],
                g["estado_texto"]]
        if con_costos:
            fila += [g["costos"], g["ganancia"]]
        filas_a.append(fila)
    hoja_datos("Resumen por alumno", enc_a, filas_a)

    # ── Saldos pendientes ──
    hoja_datos(
        "Saldos pendientes",
        ["Código", "Documento", "Alumno", "Celular", "Proceso", "Categoría", "Fecha matrícula",
         "Días desde la matrícula", "Total a pagar", "Pagado", "Saldo", "Último pago"],
        [[m["codigo"], m["numero_documento"], m["alumno"], m["celular"] or "", m["tipo_texto"],
          m["categoria_base"], m["fecha_registro"], m["dias"], int(m["precio_total"]),
          int(m["pagado"]), m["saldo"], m["ultimo_pago"]] for m in datos["deudores"]],
    )

    # ── Alumnos y matrículas (detalle completo) ──
    enc_m = ["Código", "Fecha matrícula", "Tipo documento", "Documento", "Nombres", "Apellidos",
             "Celular", "Correo", "Fecha de nacimiento", "Proceso", "Categoría", "Estado", "RUNT",
             "Precio base", "Descuento", "Total a pagar", "Pagado", "Saldo", "Nº de pagos",
             "Primer pago", "Último pago"]
    if por_pago:
        enc_m.append("Pagado en el rango")
    if con_costos:
        enc_m += ["Costos", "Costos pagados", "Ganancia estimada"]
    filas_m = []
    for m in datos["matriculas"]:
        fila = [m["codigo"], m["fecha_registro"], m["tipo_documento"], m["numero_documento"],
                m["nombres"], m["apellidos"], m["celular"] or "", m["email"] or "",
                m["fecha_nacimiento"], m["tipo_texto"], m["categoria_base"], m["estado_texto"],
                "Sí" if m["runt_registrado"] else "No",
                int(m["precio_base"]), int(m["descuento_valor"]), int(m["precio_total"]),
                int(m["pagado"]), m["saldo"], m["n_pagos"], m["primer_pago"], m["ultimo_pago"]]
        if por_pago:
            fila.append(int(m["pagado_periodo"]))
        if con_costos:
            fila += [int(m["costos"]), int(m["costos_pagados"]), m["ganancia"]]
        filas_m.append(fila)
    hoja_datos("Alumnos y matrículas", enc_m, filas_m)

    # ── Pagos y abonos (cuotas) ──
    hoja_datos(
        "Pagos y abonos",
        ["Fecha", "Recibo", "Código matrícula", "Documento", "Alumno", "Categoría", "Concepto",
         "Medio de pago", "Abono Nº", "Valor", "Acumulado pagado", "Saldo después del pago",
         "Estado", "Motivo de anulación"],
        [[p["fecha_pago"], p["numero_recibo"], p["codigo"], p["documento"], p["alumno"],
          p["categoria"], p["concepto"], p["metodo_pago"], p["abono_n"], int(p["valor"]),
          p["acumulado"], p["saldo_despues"], p["estado_texto"], p["motivo_anulacion"] or ""]
         for p in datos["pagos"]],
    )

    if con_costos:
        hoja_datos(
            "Costos",
            ["Código matrícula", "Alumno", "Categoría", "Concepto", "Valor", "Pagado",
             "Fecha de pago", "Observaciones"],
            [[c["codigo"], c["alumno"], c["categoria"], c["concepto"], int(c["valor"]),
              "Sí" if c["pagado"] else "No", c["fecha_pago"], c["observaciones"] or ""]
             for c in datos["costos"]],
        )

    for h in libro.worksheets:
        if h.title == "Resumen":
            continue
        h.freeze_panes = "A2"
        h.auto_filter.ref = h.dimensions
        estilo_encabezado(h[1])
        dinero = {c.column for c in h[1] if c.value in _ENCABEZADOS_DINERO}
        for fila in h.iter_rows(min_row=2):
            for celda in fila:
                if isinstance(celda.value, str):
                    celda.data_type = "s"          # evita que un texto se ejecute como fórmula
                elif celda.column in dinero:
                    celda.number_format = _DINERO
                elif hasattr(celda.value, "strftime"):
                    celda.number_format = ("dd/mm/yyyy hh:mm"
                                           if hasattr(celda.value, "hour") else "dd/mm/yyyy")
        for columna in h.columns:
            ancho = max(len(str(c.value if c.value is not None else "")) for c in columna) + 2
            h.column_dimensions[columna[0].column_letter].width = min(max(ancho, 12), 42)

    salida = BytesIO()
    libro.save(salida)
    return Response(
        salida.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{_nombre_archivo(filtros)}.xlsx"'},
    )


# ───────────── PDF ─────────────

def _pdf(filtros: dict, datos: dict) -> Response:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    r, con_costos, por_pago = datos["resumen"], datos["con_costos"], datos["por_pago"]
    salida = BytesIO()
    pdf = SimpleDocTemplate(salida, pagesize=landscape(letter), leftMargin=10 * mm,
                            rightMargin=10 * mm, topMargin=12 * mm, bottomMargin=14 * mm,
                            title="Reporte de alumnos — CEA La 30")
    estilos = getSampleStyleSheet()
    estilos.add(ParagraphStyle(name="TituloRep", parent=estilos["Title"], alignment=TA_CENTER,
                               fontSize=16, leading=20))
    estilos.add(ParagraphStyle(name="Celda", parent=estilos["BodyText"], fontSize=7, leading=8.5))
    celda = lambda v: Paragraph(escape(str(v if v not in (None, "") else "—")), estilos["Celda"])
    fmt_fecha = lambda f: f"{f:%d/%m/%Y}" if f else "—"

    def tabla(encabezados, filas, alinear_derecha=()):
        contenido = [encabezados] + [[celda(v) for v in fila] for fila in filas]
        if not filas:
            contenido.append([celda("Sin registros")] + [""] * (len(encabezados) - 1))
        t = Table(contenido, repeatRows=1, hAlign="LEFT")
        estilo = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#253449")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#ccd2da")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f5f7")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        for i in alinear_derecha:
            estilo.append(("ALIGN", (i, 1), (i, -1), "RIGHT"))
        t.setStyle(TableStyle(estilo))
        return t

    def seccion(titulo):
        story.extend([Spacer(1, 10), Paragraph(titulo, estilos["Heading2"])])

    story = [
        Paragraph("REPORTE DE ALUMNOS — CEA LA 30", estilos["TituloRep"]),
        Paragraph(escape(_descripcion(filtros, datos)) + f" · Generado el {ahora():%d/%m/%Y %H:%M}",
                  estilos["BodyText"]),
        Spacer(1, 6),
    ]

    # Resumen general
    resumen = [["Alumnos", "Matrículas", "Con saldo", "Al día", "Total a pagar", "Pagado", "Saldo pendiente"],
               [r["alumnos"], r["matriculas"], r["con_saldo"], r["al_dia"],
                cop(r["total"]), cop(r["pagado"]), cop(r["saldo"])]]
    if por_pago:
        resumen[0].append("Pagado en el rango")
        resumen[1].append(cop(r["pagado_periodo"]))
    if con_costos:
        resumen[0] += ["Costos", "Ganancia estimada"]
        resumen[1] += [cop(r["costos"]), cop(r["ganancia"])]
    story.append(tabla(resumen[0], [resumen[1]]))

    # Resumen por alumno
    seccion("Resumen por alumno")
    enc = ["Alumno", "Documento", "Celular", "Matrículas", "Categorías", "Total", "Pagado",
           "Saldo", "Nº pagos", "Último pago", "Estado"]
    if con_costos:
        enc += ["Costos", "Ganancia"]
    filas = []
    for g in datos["alumnos"]:
        fila = [g["alumno"], f"{g['tipo_documento']} {g['documento']}", g["celular"], g["matriculas"],
                g["categorias_texto"], cop(g["total"]), cop(g["pagado"]), cop(g["saldo"]),
                g["n_pagos"], fmt_fecha(g["ultimo_pago"]), g["estado_texto"]]
        if con_costos:
            fila += [cop(g["costos"]), cop(g["ganancia"])]
        filas.append(fila)
    story.append(tabla(enc, filas, alinear_derecha=(5, 6, 7) + ((11, 12) if con_costos else ())))

    # Saldos pendientes
    seccion("Matrículas con saldo pendiente (mayor deuda primero)")
    story.append(tabla(
        ["Código", "Alumno", "Documento", "Celular", "Categoría", "Fecha", "Días", "Total", "Pagado", "Saldo", "Último pago"],
        [[m["codigo"], m["alumno"], m["numero_documento"], m["celular"],
          f"{m['categoria_base']} ({m['tipo_texto']})", fmt_fecha(m["fecha_registro"]), m["dias"],
          cop(m["precio_total"]), cop(m["pagado"]), cop(m["saldo"]), fmt_fecha(m["ultimo_pago"])]
         for m in datos["deudores"]],
        alinear_derecha=(7, 8, 9),
    ))

    # Desgloses
    seccion("Por proceso y categoría")
    story.append(tabla(["Proceso", "Categoría", "Matrículas", "Total", "Pagado", "Saldo"],
                       [[a, b, c, cop(d), cop(e), cop(f)] for a, b, c, d, e, f in datos["por_categoria"]],
                       alinear_derecha=(3, 4, 5)))
    seccion("Por estado de la matrícula")
    story.append(tabla(["Estado", "Matrículas", "Total", "Pagado", "Saldo"],
                       [[a, b, cop(c), cop(d), cop(e)] for a, b, c, d, e in datos["por_estado"]],
                       alinear_derecha=(2, 3, 4)))
    seccion("Por medio de pago")
    story.append(tabla(["Medio de pago", "Pagos", "Valor"],
                       [[a, b, cop(c)] for a, b, c in datos["por_medio"]], alinear_derecha=(2,)))

    # Detalle de matrículas
    seccion("Detalle de alumnos y matrículas")
    enc = ["Código", "Fecha", "Documento", "Alumno", "Celular", "Correo", "Proceso", "Categoría",
           "Estado", "Total", "Pagado", "Saldo", "Nº pagos"]
    if con_costos:
        enc += ["Costos", "Ganancia"]
    filas = []
    for m in datos["matriculas"]:
        fila = [m["codigo"], fmt_fecha(m["fecha_registro"]),
                f"{m['tipo_documento']} {m['numero_documento']}", m["alumno"], m["celular"],
                m["email"], m["tipo_texto"], m["categoria_base"], m["estado_texto"],
                cop(m["precio_total"]), cop(m["pagado"]), cop(m["saldo"]), m["n_pagos"]]
        if con_costos:
            fila += [cop(m["costos"]), cop(m["ganancia"])]
        filas.append(fila)
    story.append(tabla(enc, filas, alinear_derecha=(9, 10, 11) + ((13, 14) if con_costos else ())))

    # Pagos y abonos
    seccion("Detalle de pagos y abonos")
    story.append(tabla(
        ["Fecha", "Recibo", "Matrícula", "Alumno", "Categoría", "Concepto", "Medio", "Abono Nº",
         "Valor", "Acumulado", "Saldo después", "Estado"],
        [[f"{p['fecha_pago']:%d/%m/%Y %H:%M}" if p["fecha_pago"] else "—", p["numero_recibo"],
          p["codigo"], p["alumno"], p["categoria"], p["concepto"], p["metodo_pago"], p["abono_n"],
          cop(p["valor"]), cop(p["acumulado"]) if p["acumulado"] is not None else "—",
          cop(p["saldo_despues"]) if p["saldo_despues"] is not None else "—", p["estado_texto"]]
         for p in datos["pagos"]],
        alinear_derecha=(8, 9, 10),
    ))

    if con_costos:
        seccion("Costos de las matrículas")
        story.append(tabla(
            ["Matrícula", "Alumno", "Categoría", "Concepto", "Valor", "Pagado", "Observaciones"],
            [[c["codigo"], c["alumno"], c["categoria"], c["concepto"], cop(c["valor"]),
              "Sí" if c["pagado"] else "No", c["observaciones"]] for c in datos["costos"]],
            alinear_derecha=(4,),
        ))

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(landscape(letter)[0] - 10 * mm, 8 * mm, f"Página {doc.page}")
        canvas.restoreState()

    pdf.build(story, onFirstPage=pie, onLaterPages=pie)
    return Response(salida.getvalue(), mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{_nombre_archivo(filtros)}.pdf"'})


# ───────────── Ruta ─────────────

@bp.route("/alumnos/reporte")
@login_required
@permiso_requerido("ver_historial_pagos")
def descargar():
    try:
        filtros = _leer_filtros()
        datos = _cargar(filtros)
        if not datos["matriculas"]:
            raise ReporteInvalido("No hay alumnos que coincidan con lo que elegiste.")
        return _excel(filtros, datos) if filtros["formato"] == "excel" else _pdf(filtros, datos)
    except ReporteInvalido as e:
        flash(str(e), "error")
    except Exception:
        current_app.logger.exception("No se pudo generar el reporte de alumnos")
        flash("No se pudo generar el reporte. Intenta de nuevo.", "error")
    return redirect(url_for("alumnos.lista"))
