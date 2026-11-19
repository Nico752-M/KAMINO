"""Catálogo de permisos y reglas iniciales para conservar los roles existentes."""

PERMISOS = {
    "ver_dashboard": "Ver dashboard",
    "ver_alumnos": "Ver alumnos y matrículas",
    "crear_matricula": "Crear alumnos y matrículas",
    "editar_alumnos": "Editar datos de alumnos y matrículas",
    "eliminar_alumnos": "Anular o archivar matrículas",
    "ver_historial_pagos": "Ver historial de pagos por alumno",
    "registrar_pagos": "Registrar pagos",
    "anular_pagos": "Anular pagos",
    "ver_recibos": "Ver e imprimir recibos",
    "ver_caja": "Ver caja y tesorería",
    "ver_todas_cajas": "Ver todas las cajas",
    "gestionar_caja": "Registrar ingresos y salidas manuales",
    "ver_tramites": "Ver trámites y pendientes RUNT",
    "marcar_runt": "Marcar registros RUNT",
    "gestionar_costos": "Gestionar costos de las matrículas",
    "ver_ganancias": "Ver ganancia de las matrículas",
    "gestionar_usuarios": "Gestionar usuarios y permisos",
}

ROLES = ("admin", "cajera", "secretaria", "contadora")

GRUPOS_PERMISOS = {
    "Alumnos": (
        "ver_alumnos", "crear_matricula", "editar_alumnos",
        "eliminar_alumnos", "ver_historial_pagos",
        "gestionar_costos", "ver_ganancias",
    ),
    "Caja": (
        "ver_caja", "registrar_pagos", "anular_pagos",
        "ver_recibos", "gestionar_caja", "ver_todas_cajas",
    ),
    "Trámites": ("ver_tramites", "marcar_runt"),
    "Administración": ("ver_dashboard", "gestionar_usuarios"),
}

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
