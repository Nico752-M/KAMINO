-- Ejecutar una sola vez conectado como propietario CEA_APP, después de 006.
-- Ajusta grants, permisos, tarifas de renovación y conteo de efectivo de cierres.

SET DEFINE OFF
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK

DECLARE
    cantidad NUMBER;
BEGIN
    IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> 'CEA_APP' THEN
        RAISE_APPLICATION_ERROR(-20701, 'Conéctate como CEA_APP para ejecutar esta migración.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM all_users WHERE username = 'CEA_WEB';
    IF cantidad = 0 THEN
        RAISE_APPLICATION_ERROR(-20702, 'No existe el usuario de aplicación CEA_WEB.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_tables
    WHERE table_name IN ('ALUMNOS', 'RESPONSABLES_MATRICULA', 'PERFILES',
                         'PERFIL_PERMISOS', 'TARIFAS_CATEGORIA', 'CAJAS');
    IF cantidad <> 6 THEN
        RAISE_APPLICATION_ERROR(-20703, 'Aplica primero las migraciones 001-006.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_tab_columns
    WHERE table_name = 'TARIFAS_CATEGORIA' AND column_name = 'TIPO';
    IF cantidad <> 0 THEN
        RAISE_APPLICATION_ERROR(-20704, 'La columna TIPO ya existe en TARIFAS_CATEGORIA.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_tab_columns
    WHERE table_name = 'CAJAS' AND column_name = 'CONTEO_DENOMINACIONES';
    IF cantidad <> 0 THEN
        RAISE_APPLICATION_ERROR(-20705, 'La columna CONTEO_DENOMINACIONES ya existe en CAJAS.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_tab_columns
    WHERE table_name IN ('PAGOS', 'INGRESOS_CAJA', 'SALIDAS_CAJA')
      AND column_name IN ('IMPRESO_ORIGINAL_POR', 'FECHA_IMPRESION_ORIGINAL');
    IF cantidad <> 0 THEN
        RAISE_APPLICATION_ERROR(-20707, 'Ya existen columnas de impresión original; revisa si la migración ya se aplicó.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM perfil_permisos
    WHERE codigo IN ('anular_pagos', 'ver_todas_cajas');
    IF cantidad <> 0 THEN
        RAISE_APPLICATION_ERROR(-20706, 'Los permisos de caja ya existen; revisa si la migración ya se aplicó.');
    END IF;
END;
/

ALTER TABLE tarifas_categoria ADD (tipo VARCHAR2(12) DEFAULT 'CURSO' NOT NULL);
ALTER TABLE tarifas_categoria DROP CONSTRAINT pk_tarifas_categoria;
ALTER TABLE tarifas_categoria ADD CONSTRAINT pk_tarifas_categoria
    PRIMARY KEY (tipo, categoria);
ALTER TABLE tarifas_categoria ADD CONSTRAINT ck_tarifa_tipo
    CHECK (tipo IN ('CURSO', 'RENOVACION'));
INSERT INTO tarifas_categoria (categoria, tipo, precio_base, activo, fecha_actualizacion)
SELECT categoria, 'RENOVACION', precio_base, activo, fecha_actualizacion
FROM tarifas_categoria
WHERE tipo = 'CURSO';

ALTER TABLE cajas ADD (conteo_denominaciones CLOB);

ALTER TABLE pagos ADD (impreso_original_por NUMBER, fecha_impresion_original TIMESTAMP);
ALTER TABLE ingresos_caja ADD (impreso_original_por NUMBER, fecha_impresion_original TIMESTAMP);
ALTER TABLE salidas_caja ADD (impreso_original_por NUMBER, fecha_impresion_original TIMESTAMP);
ALTER TABLE pagos ADD CONSTRAINT fk_pagos_impreso_usr
    FOREIGN KEY (impreso_original_por) REFERENCES usuarios (id);
ALTER TABLE ingresos_caja ADD CONSTRAINT fk_ingresos_impreso_usr
    FOREIGN KEY (impreso_original_por) REFERENCES usuarios (id);
ALTER TABLE salidas_caja ADD CONSTRAINT fk_salidas_impreso_usr
    FOREIGN KEY (impreso_original_por) REFERENCES usuarios (id);

UPDATE pagos p
SET fecha_impresion_original = (
    SELECT MIN(r.fecha) FROM reimpresiones_recibos r
    WHERE r.tipo = 'PAGO' AND r.numero_recibo = p.numero_recibo
)
WHERE EXISTS (SELECT 1 FROM reimpresiones_recibos r
              WHERE r.tipo = 'PAGO' AND r.numero_recibo = p.numero_recibo);
UPDATE ingresos_caja i
SET fecha_impresion_original = (
    SELECT MIN(r.fecha) FROM reimpresiones_recibos r
    WHERE r.tipo = 'INGRESO' AND r.numero_recibo = i.numero_recibo
)
WHERE EXISTS (SELECT 1 FROM reimpresiones_recibos r
              WHERE r.tipo = 'INGRESO' AND r.numero_recibo = i.numero_recibo);
UPDATE salidas_caja s
SET fecha_impresion_original = (
    SELECT MIN(r.fecha) FROM reimpresiones_recibos r
    WHERE r.tipo = 'EGRESO' AND r.numero_recibo = s.numero_recibo
)
WHERE EXISTS (SELECT 1 FROM reimpresiones_recibos r
              WHERE r.tipo = 'EGRESO' AND r.numero_recibo = s.numero_recibo);

INSERT INTO perfil_permisos (perfil_id, codigo)
SELECT pf.id, permisos.codigo
FROM perfiles pf
JOIN usuarios u ON u.id = pf.usuario_id
CROSS JOIN (
    SELECT 'anular_pagos' AS codigo FROM dual UNION ALL
    SELECT 'ver_todas_cajas' FROM dual
) permisos
WHERE u.rol = 'admin';

GRANT SELECT, INSERT, UPDATE, DELETE ON CEA_APP.ALUMNOS TO CEA_WEB;
GRANT SELECT, INSERT, UPDATE, DELETE ON CEA_APP.RESPONSABLES_MATRICULA TO CEA_WEB;
GRANT SELECT, INSERT, UPDATE ON CEA_APP.CAJAS TO CEA_WEB;
GRANT SELECT, INSERT, UPDATE ON CEA_APP.TARIFAS_CATEGORIA TO CEA_WEB;

COMMIT;
PROMPT Migración 007 de permisos, cajas y tarifas aplicada correctamente.
