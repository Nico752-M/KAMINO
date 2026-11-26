-- Ejecutar una sola vez conectado como propietario CEA_APP, después de 001-017.
-- Crea los consecutivos de recibos por tipo:
--   ING-001  todo lo que entra: pagos de alumnos (incluye abonos históricos), ingresos de caja y de banco.
--   EGR-001  todo lo que sale: egresos de caja y de banco.
--   TRA-001  traslados entre bancos.
-- Los recibos que ya existen (CEA-000123, HIST-205...) NO se renumeran y siguen funcionando igual.
-- SEQ_RECIBOS se conserva sin uso para no romper nada; la app deja de usarla.

SET DEFINE OFF
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK

DECLARE
    cantidad NUMBER;
BEGIN
    IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> 'CEA_APP' THEN
        RAISE_APPLICATION_ERROR(-20801, 'Conéctate como CEA_APP para ejecutar esta migración.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM all_users WHERE username = 'CEA_WEB';
    IF cantidad = 0 THEN
        RAISE_APPLICATION_ERROR(-20802, 'No existe el usuario de aplicación CEA_WEB.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_sequences
    WHERE sequence_name IN ('SEQ_INGRESOS', 'SEQ_EGRESOS', 'SEQ_TRASLADOS');
    IF cantidad <> 0 THEN
        RAISE_APPLICATION_ERROR(-20803, 'Ya existe alguna secuencia de ingresos/egresos/traslados; revisa si la migración ya se aplicó.');
    END IF;
END;
/

CREATE SEQUENCE seq_ingresos  START WITH 1 INCREMENT BY 1 NOCYCLE NOCACHE;
CREATE SEQUENCE seq_egresos   START WITH 1 INCREMENT BY 1 NOCYCLE NOCACHE;
CREATE SEQUENCE seq_traslados START WITH 1 INCREMENT BY 1 NOCYCLE NOCACHE;

-- NOCACHE: así el consecutivo no salta números si la base se reinicia.

GRANT SELECT ON CEA_APP.SEQ_INGRESOS  TO CEA_WEB;
GRANT SELECT ON CEA_APP.SEQ_EGRESOS   TO CEA_WEB;
GRANT SELECT ON CEA_APP.SEQ_TRASLADOS TO CEA_WEB;

COMMIT;
PROMPT Consecutivos ING / EGR / TRA creados correctamente.
