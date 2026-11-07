"""Reglas compartidas para el estado de pago de una matrícula."""


def estado_matricula(estado_actual: str, precio_total: int | float,
                     total_pagado: int | float) -> str:
    if estado_actual in ("Histórico", "Completado"):
        return estado_actual
    if precio_total > 0 and total_pagado >= precio_total:
        return "Cancelado"
    return "Pendiente Pago" if total_pagado > 0 else "Activo"
