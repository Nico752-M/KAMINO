-- Ejecutar una sola vez conectado como propietario CEA_APP, después de 005.
-- Persisten bloqueos de acceso y agregan categorías opcionales a ingresos/salidas.

SET DEFINE OFF
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK

DECLARE
    cantidad NUMBER;
BEGIN
    IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> 'CEA_APP' THEN
        RAISE_APPLICATION_ERROR(-20601, 'Conéctate como CEA_APP para ejecutar esta migración.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM all_users WHERE username = 'CEA_WEB';
    IF cantidad = 0 THEN
        RAISE_APPLICATION_ERROR(-20602, 'No existe el usuario de aplicación CEA_WEB.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_tables
    WHERE table_name IN ('CAJAS', 'TARIFAS_CATEGORIA', 'PAGOS',
                         'INGRESOS_CAJA', 'SALIDAS_CAJA');
    IF cantidad <> 5 THEN
        RAISE_APPLICATION_ERROR(-20603, 'Aplica primero las migraciones 001-005.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_tables
    WHERE table_name IN ('LOGIN_INTENTOS', 'CATEGORIAS_CAJA');
    IF cantidad <> 0 THEN
        RAISE_APPLICATION_ERROR(-20604, 'Se encontraron tablas de esta migración; revisa si ya se aplicó.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_tab_columns
    WHERE table_name IN ('INGRESOS_CAJA', 'SALIDAS_CAJA')
      AND column_name = 'CATEGORIA';
    IF cantidad <> 0 THEN
        RAISE_APPLICATION_ERROR(-20605, 'Ya existe una columna CATEGORIA en movimientos de caja.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_tab_columns
    WHERE table_name = 'PAGOS' AND column_name = 'CAMBIO';
    IF cantidad <> 0 THEN
        RAISE_APPLICATION_ERROR(-20606, 'Ya existe la columna CAMBIO en PAGOS.');
    END IF;
END;
/

CREATE TABLE login_intentos (
    clave VARCHAR2(64) NOT NULL,
    intentos NUMBER(3,0) DEFAULT 0 NOT NULL,
    inicio_ventana TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    bloqueado_hasta TIMESTAMP WITH TIME ZONE,
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_login_intentos PRIMARY KEY (clave),
    CONSTRAINT ck_login_intentos_num CHECK (intentos BETWEEN 1 AND 5)
);

CREATE TABLE categorias_caja (
    categoria VARCHAR2(45) NOT NULL,
    activo NUMBER(1) DEFAULT 1 NOT NULL,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_categorias_caja PRIMARY KEY (categoria),
    CONSTRAINT ck_categoria_caja_activa CHECK (activo IN (0, 1))
);

ALTER TABLE ingresos_caja ADD (categoria VARCHAR2(45));
ALTER TABLE salidas_caja ADD (categoria VARCHAR2(45));
ALTER TABLE pagos ADD (cambio NUMBER(12,0) DEFAULT 0 NOT NULL);
ALTER TABLE pagos ADD CONSTRAINT ck_pago_cambio CHECK (cambio >= 0);
ALTER TABLE ingresos_caja ADD CONSTRAINT fk_ingreso_categoria
    FOREIGN KEY (categoria) REFERENCES categorias_caja (categoria);
ALTER TABLE salidas_caja ADD CONSTRAINT fk_salida_categoria
    FOREIGN KEY (categoria) REFERENCES categorias_caja (categoria);

CREATE INDEX ix_login_intentos_fecha ON login_intentos (actualizado_en);
CREATE INDEX ix_caja_categoria_ingreso ON ingresos_caja (categoria, fecha_ingreso);
CREATE INDEX ix_caja_categoria_salida ON salidas_caja (categoria, fecha_salida);

GRANT SELECT, INSERT, UPDATE, DELETE ON CEA_APP.LOGIN_INTENTOS TO CEA_WEB;
GRANT SELECT, INSERT, UPDATE ON CEA_APP.CATEGORIAS_CAJA TO CEA_WEB;
GRANT SELECT, INSERT, UPDATE ON CEA_APP.INGRESOS_CAJA TO CEA_WEB;
GRANT SELECT, INSERT, UPDATE ON CEA_APP.SALIDAS_CAJA TO CEA_WEB;

COMMIT;
PROMPT Migración de seguridad y categorías de caja aplicada correctamente.
