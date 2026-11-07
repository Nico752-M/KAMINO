"""Validaciones compartidas para alumnos y responsables de matrícula."""
import re

TIPOS_DOCUMENTO = frozenset({"CC", "CE", "TI", "RC", "Pasaporte", "PPT", "Otro"})
RELACIONES_RESPONSABLE = frozenset({
    "Padre", "Madre", "Cónyuge", "Hijo/a", "Hermano/a", "Acudiente", "Otro",
})

_LIMITES_ALUMNO = {
    "lugar_nacimiento": 120,
    "sexo": 20,
    "estado_civil": 30,
    "grupo_sanguineo": 5,
    "ocupacion": 120,
    "celular": 30,
    "email": 254,
}
_ESTADOS_CIVILES = frozenset(
    {"Soltero/a", "Casado/a", "Unión libre", "Separado/a", "Viudo/a"}
)
_GRUPOS_SANGUINEOS = frozenset(
    {"O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"}
)
_CORREO = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_DOCUMENTO = re.compile(r"[A-Za-z0-9.-]{1,20}")


def validar_datos_alumno(documento, tipo_documento, nombres, apellidos, opcionales):
    if (not _DOCUMENTO.fullmatch(documento)
            or tipo_documento not in TIPOS_DOCUMENTO
            or not nombres or len(nombres) > 100
            or not apellidos or len(apellidos) > 100):
        raise ValueError("Revisa documento, tipo, nombres y apellidos.")
    if any(valor and len(valor) > _LIMITES_ALUMNO[campo]
           for campo, valor in opcionales.items()):
        raise ValueError("Uno de los datos personales o de contacto supera el largo permitido.")
    if (opcionales.get("sexo") not in (None, "F", "M", "Otro")
            or opcionales.get("estado_civil") not in (None, *_ESTADOS_CIVILES)
            or opcionales.get("grupo_sanguineo") not in (None, *_GRUPOS_SANGUINEOS)
            or (opcionales.get("email") and not _CORREO.fullmatch(opcionales["email"]))):
        raise ValueError("Revisa sexo, estado civil, grupo sanguíneo o correo electrónico.")


def validar_responsable(responsable) -> bool:
    if not any(responsable.values()):
        return False
    if (responsable.get("tipo_documento") not in TIPOS_DOCUMENTO
            or not _DOCUMENTO.fullmatch(responsable.get("numero_documento") or "")
            or not responsable.get("nombres") or len(responsable["nombres"]) > 100
            or not responsable.get("apellidos") or len(responsable["apellidos"]) > 100
            or responsable.get("relacion") not in RELACIONES_RESPONSABLE
            or (responsable.get("celular") and len(responsable["celular"]) > 30)
            or (responsable.get("email") and
                (len(responsable["email"]) > 254
                 or not _CORREO.fullmatch(responsable["email"])))):
        raise ValueError(
            "Completa documento, nombres, apellidos y relación del responsable; "
            "teléfono y correo son opcionales."
        )
    return True
