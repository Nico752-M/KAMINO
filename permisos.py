"""Catálogo de permisos y reglas iniciales para conservar los roles existentes."""

PERMISOS = {
    "ver_dashboard": "Ver dashboard",
    "ver_alumnos": "Ver alumnos y matrículas",
    "crear_matricula": "Crear alumnos y matrículas",
    "editar_alumnos": "Editar datos de alumnos y matrículas",
    "eliminar_alumnos": "Borrar alumnos y matrículas",
    "ver_historial_pagos": "Ver historial de pagos por alumno",
    "registrar_pagos": "Registrar pagos",
    "anular_pagos": "Anular pagos",
    "confirmar_pagos": "Confirmar pagos (validar los pagos recibidos en caja)",
    "ver_recibos": "Ver e imprimir recibos",
    "ver_caja": "Ver caja y tesorería",
    "ver_todas_cajas": "Ver todas las cajas",
    "gestionar_caja": "Registrar ingresos y salidas manuales",
    "ver_tramites": "Ver trámites y pendientes RUNT",
    "marcar_runt": "Marcar registros RUNT",
    "gestionar_costos": "Gestionar costos de las matrículas",
    "ver_ganancias": "Ver ganancia de las matrículas",
    "gestionar_usuarios": "Gestionar usuarios y permisos",
    "ver_tienda": "Tienda: entrar y cobrar (productos y servicios)",
    "tienda_anular": "Tienda: anular ventas",
    "tienda_inventario": "Tienda: inventario (productos, entradas de stock y bajas)",
    "tienda_servicios": "Tienda: editar servicios, precios y requisitos",
    "tienda_caja": "Tienda: entradas, salidas, cierre de caja y reportes",
    "tienda_ganancias": "Tienda: ver ganancias",
    "tienda_cuentas": "Tienda: Mis cuentas (luz, agua, arriendo, nómina…)",
    "tienda_usuarios": "Tienda: crear y administrar usuarios de la tienda",
    "ver_cuentas": "Ver y administrar Mis cuentas (ingresos y gastos del CEA)",
}

ROLES = ("admin", "cajera", "secretaria", "contadora", "tienda", "tienda_admin", "tienda_cajero")

# Permisos que pertenecen solo a la tienda «Todo en Tránsito».
PERMISOS_TIENDA = (
    "ver_tienda", "tienda_anular", "tienda_inventario", "tienda_servicios",
    "tienda_caja", "tienda_ganancias", "tienda_cuentas", "tienda_usuarios",
)
# Plantillas con las que el administrador de la tienda puede crear usuarios.
ROLES_TIENDA = ("tienda_admin", "tienda_cajero")
# Roles que se consideran «de la tienda» (incluye «tienda», el rol de antes).
ROLES_DE_TIENDA = ("tienda", "tienda_admin", "tienda_cajero")

GRUPOS_PERMISOS = {
    "Alumnos": (
        "ver_alumnos", "crear_matricula", "editar_alumnos",
        "eliminar_alumnos", "ver_historial_pagos",
        "gestionar_costos", "ver_ganancias",
    ),
    "Caja": (
        "ver_caja", "registrar_pagos", "anular_pagos", "confirmar_pagos",
        "ver_recibos", "gestionar_caja", "ver_todas_cajas",
    ),
    "Trámites": ("ver_tramites", "marcar_runt"),
    "Administración": ("ver_dashboard", "gestionar_usuarios", "ver_cuentas"),
    "Tienda": PERMISOS_TIENDA,
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
    "tienda": {"ver_tienda"},
    "tienda_admin": set(PERMISOS_TIENDA),
    "tienda_cajero": {"ver_tienda"},
}
