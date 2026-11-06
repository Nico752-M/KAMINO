-- Ejecutar una sola vez conectado como propietario CEA_APP, después de 001-004.

SET DEFINE OFF
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK

DECLARE
    cantidad NUMBER;
BEGIN
    IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> 'CEA_APP' THEN
        RAISE_APPLICATION_ERROR(-20501, 'Conéctate como CEA_APP para ejecutar esta migración.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM all_users WHERE username = 'CEA_WEB';
    IF cantidad = 0 THEN
        RAISE_APPLICATION_ERROR(-20502, 'No existe el usuario de aplicación CEA_WEB.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_tables
    WHERE table_name IN ('MATRICULAS', 'BLOQUEO_MATRICULAS');
    IF cantidad <> 2 THEN
        RAISE_APPLICATION_ERROR(-20503, 'Aplica primero las migraciones 001-004.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_tables WHERE table_name = 'TARIFAS_CATEGORIA';
    IF cantidad > 0 THEN
        RAISE_APPLICATION_ERROR(-20504, 'TARIFAS_CATEGORIA ya existe; revisa si la migración ya se aplicó.');
    END IF;
END;
/

CREATE TABLE tarifas_categoria (
    categoria VARCHAR2(45) NOT NULL,
    precio_base NUMBER(12,0) NOT NULL,
    activo NUMBER(1) DEFAULT 1 NOT NULL,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_tarifas_categoria PRIMARY KEY (categoria),
    CONSTRAINT ck_tarifa_precio CHECK (precio_base > 0),
    CONSTRAINT ck_tarifa_activa CHECK (activo IN (0, 1))
);

GRANT SELECT, INSERT, UPDATE ON CEA_APP.TARIFAS_CATEGORIA TO CEA_WEB;

COMMIT;
PROMPT Migración de tarifas por categoría aplicada correctamente.
