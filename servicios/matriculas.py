"""Reglas compartidas para el estado de pago de una matrícula."""


def estado_matricula(estado_actual: str, precio_total: int | float,
                     total_pagado: int | float) -> str:
    if estado_actual in ("Histórico", "Completado"):
        return estado_actual
    if precio_total > 0 and total_pagado >= precio_total:
        return "Cancelado"
    return "Pendiente Pago" if total_pagado > 0 else "Activo"


# ───────────── Tipo de matrícula ─────────────
# El tipo se guarda como prefijo de la categoría en la matrícula ("Renovación - A2") y como
# código en las tarifas y plantillas de costos. El curso completo no lleva prefijo.
# OJO: el código de recategorización es corto ("RECAT") porque la columna TIPO de las
# tablas de tarifas mide solo 12 caracteres.
TIPO_CURSO = "CURSO"
TIPO_RENOVACION = "RENOVACION"
TIPO_RECATEGORIZACION = "RECAT"
TIPOS_TARIFA = (TIPO_CURSO, TIPO_RENOVACION, TIPO_RECATEGORIZACION)

PREFIJOS_TIPO = {
    TIPO_RENOVACION: "Renovación - ",
    TIPO_RECATEGORIZACION: "Recategorización - ",
}
# Valor que envían los formularios -> código de tipo.
TIPO_DESDE_FORMULARIO = {
    "curso": TIPO_CURSO,
    "renovacion": TIPO_RENOVACION,
    "recategorizacion": TIPO_RECATEGORIZACION,
}
ETIQUETA_TIPO = {
    TIPO_CURSO: "Curso completo",
    TIPO_RENOVACION: "Renovación",
    TIPO_RECATEGORIZACION: "Recategorización",
}
_CONCEPTO_PAGO = {
    TIPO_CURSO: "Pago curso de conducción",
    TIPO_RENOVACION: "Renovación de licencia — {}",
    TIPO_RECATEGORIZACION: "Recategorización de licencia — {}",
}


def tipo_desde_formulario(valor: str) -> str | None:
    """'renovacion' -> 'RENOVACION'. Devuelve None si el valor no es un tipo válido."""
    return TIPO_DESDE_FORMULARIO.get(valor)


def armar_categoria(tipo: str, categoria_base: str) -> str:
    """('RECAT', 'A2') -> 'Recategorización - A2';  ('CURSO', 'A2') -> 'A2'."""
    return PREFIJOS_TIPO.get(tipo, "") + categoria_base


def tipo_de_categoria(categoria: str | None) -> tuple[str, str]:
    """'Recategorización - A2' -> ('RECAT', 'A2');  'A2' -> ('CURSO', 'A2')."""
    categoria = (categoria or "").strip()
    for tipo, prefijo in PREFIJOS_TIPO.items():
        if categoria.startswith(prefijo):
            return tipo, categoria[len(prefijo):]
    return TIPO_CURSO, categoria


def concepto_pago(tipo: str, categoria_base: str) -> str:
    """Concepto que llevan los pagos de la matrícula según su tipo."""
    return _CONCEPTO_PAGO.get(tipo, _CONCEPTO_PAGO[TIPO_CURSO]).format(categoria_base)
