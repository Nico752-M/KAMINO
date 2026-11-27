-- RECATEGORIZACIÓN · agrega el tercer tipo de matrícula (junto a curso completo y renovación).
-- Ejecutar UNA sola vez, conectado como CEA_APP, después de la 019.
-- El código del tipo es 'RECAT' (la columna TIPO mide 12 caracteres).
-- Compatible con el SQL Worksheet web (sin comandos de SQL*Plus).

ALTER TABLE tarifas_categoria DROP CONSTRAINT ck_tarifa_tipo;
ALTER TABLE tarifas_categoria ADD CONSTRAINT ck_tarifa_tipo
    CHECK (tipo IN ('CURSO', 'RENOVACION', 'RECAT'));

ALTER TABLE costos_plantilla DROP CONSTRAINT ck_cplantilla_tipo;
ALTER TABLE costos_plantilla ADD CONSTRAINT ck_cplantilla_tipo
    CHECK (tipo IN ('CURSO', 'RENOVACION', 'RECAT'));
