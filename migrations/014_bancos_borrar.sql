-- BANCOS · permite borrar bancos y bolsillos que no tengan movimientos.
-- Ejecutar UNA sola vez, conectado como CEA_APP, después de la 013.

GRANT DELETE ON CEA_APP.BANCOS TO CEA_WEB;
GRANT DELETE ON CEA_APP.BOLSILLOS TO CEA_WEB;
