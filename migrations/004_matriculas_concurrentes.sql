-- Ejecutar una sola vez conectado como propietario CEA_APP, después de 001-003.
-- Serializa la asignación del consecutivo anual para evitar colisiones concurrentes.

SET DEFINE OFF
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK

DECLARE
    cantidad NUMBER;
BEGIN
    IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> 'CEA_APP' THEN
        RAISE_APPLICATION_ERROR(-20401, 'Conéctate como CEA_APP para ejecutar esta migración.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM all_users WHERE username = 'CEA_WEB';
    IF cantidad = 0 THEN
        RAISE_APPLICATION_ERROR(-20402, 'No existe el usuario de aplicación CEA_WEB.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_tables WHERE table_name = 'MATRICULAS';
    IF cantidad = 0 THEN
        RAISE_APPLICATION_ERROR(-20403, 'No existe la tabla MATRICULAS.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_tables WHERE table_name = 'BLOQUEO_MATRICULAS';
    IF cantidad > 0 THEN
        RAISE_APPLICATION_ERROR(-20404, 'BLOQUEO_MATRICULAS ya existe; revisa si la migración ya se aplicó.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM all_constraints
    WHERE owner = 'CEA_APP' AND constraint_name = 'UQ_MAT_ORDEN'
      AND constraint_type = 'U' AND status = 'ENABLED';
    IF cantidad <> 1 THEN
        RAISE_APPLICATION_ERROR(-20405, 'No está habilitada la restricción única anual UQ_MAT_ORDEN.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM all_cons_columns
    WHERE owner = 'CEA_APP' AND constraint_name = 'UQ_MAT_ORDEN'
      AND ((column_name = 'ANIO' AND position = 1)
        OR (column_name = 'NUMERO_ORDEN' AND position = 2));
    IF cantidad <> 2 THEN
        RAISE_APPLICATION_ERROR(-20406, 'UQ_MAT_ORDEN no protege el consecutivo anual esperado.');
    END IF;
END;
/

CREATE TABLE bloqueo_matriculas (
    id NUMBER(1) NOT NULL,
    CONSTRAINT pk_bloqueo_matriculas PRIMARY KEY (id),
    CONSTRAINT ck_bloqueo_matriculas_unico CHECK (id = 1)
);

INSERT INTO bloqueo_matriculas (id) VALUES (1);

GRANT SELECT, UPDATE ON CEA_APP.BLOQUEO_MATRICULAS TO CEA_WEB;

COMMIT;
PROMPT Migración para asignación concurrente de matrículas aplicada correctamente.
