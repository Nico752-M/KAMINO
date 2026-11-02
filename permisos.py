"""Catálogo de permisos y reglas iniciales para conservar los roles existentes."""

PERMISOS = {
    "ver_dashboard": "Ver dashboard",
    "ver_alumnos": "Ver alumnos y matrículas",
    "crear_matricula": "Crear alumnos y matrículas",
    "editar_alumnos": "Editar datos de alumnos y matrículas",
    "eliminar_alumnos": "Anular o archivar matrículas",
    "ver_historial_pagos": "Ver historial de pagos por alumno",
    "registrar_pagos": "Registrar pagos",
    "ver_recibos": "Ver e imprimir recibos",
    "ver_caja": "Ver caja y tesorería",
    "gestionar_caja": "Registrar ingresos y salidas manuales",
    "ver_tramites": "Ver trámites y pendientes RUNT",
    "marcar_runt": "Marcar registros RUNT",
    "gestionar_usuarios": "Gestionar usuarios y permisos",
}

ROLES = ("admin", "cajera", "secretaria", "contadora")

_PANTALLAS = {
    "ver_dashboard",
    "ver_alumnos",
    "ver_caja",
    "ver_tramites",
}

PERMISOS_POR_ROL = {
    "admin": set(PERMISOS),
    "cajera": _PANTALLAS | {"registrar_pagos", "ver_recibos"},
    "secretaria": _PANTALLAS | {"registrar_pagos", "ver_recibos", "marcar_runt"},
    "contadora": _PANTALLAS | {"ver_recibos"},
}
