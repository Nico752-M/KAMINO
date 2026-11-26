-- USUARIOS · permite eliminar cuentas que no tengan movimientos ni historial.
-- Ejecutar UNA sola vez, conectado como CEA_APP, después de la 015.

GRANT DELETE ON CEA_APP.USUARIOS TO CEA_WEB;
GRANT DELETE ON CEA_APP.PERFILES TO CEA_WEB;
