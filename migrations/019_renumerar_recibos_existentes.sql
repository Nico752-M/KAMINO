-- Ejecutar una sola vez conectado como propietario CEA_APP, DESPUÉS de la 018.
-- Renumera los recibos que ya existen (CEA-000221, HIST-205...) al formato nuevo,
-- en orden cronológico (por fecha del movimiento):
--   ING-001...  pagos de alumnos (incluye abonos históricos), ingresos de caja e ingresos de banco
--   EGR-001...  egresos de caja y de banco
--   TRA-001...  traslados entre bancos
-- Actualiza en el mismo paso: pagos, ingresos_caja, salidas_caja, reimpresiones_recibos y
-- las referencias de movimientos_banco (y el número que aparece escrito en sus conceptos CEA-...).
-- Guarda cada cambio en la tabla RECIBOS_RENUMERADOS (numero_anterior -> numero_nuevo),
-- por si hay que volver a ubicar un recibo viejo.
-- Al terminar deja las secuencias listas para continuar con el siguiente número.
-- Los recibos que ya tengan formato ING-/EGR-/TRA- no se tocan.

SET DEFINE OFF

CREATE TABLE recibos_renumerados (
    numero_anterior VARCHAR2(50) NOT NULL,
    numero_nuevo    VARCHAR2(50) NOT NULL,
    fecha           TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_recibos_renumerados PRIMARY KEY (numero_anterior)
);

DECLARE
    ing NUMBER;
    egr NUMBER;
    tra NUMBER;

    FUNCTION formato(p_prefijo VARCHAR2, p_n NUMBER) RETURN VARCHAR2 IS
    BEGIN
        RETURN p_prefijo || '-' || CASE WHEN p_n < 1000 THEN LPAD(p_n, 3, '0') ELSE TO_CHAR(p_n) END;
    END;

    FUNCTION maximo(p_prefijo VARCHAR2) RETURN NUMBER IS
        v NUMBER;
    BEGIN
        SELECT NVL(MAX(TO_NUMBER(SUBSTR(n, LENGTH(p_prefijo) + 2))), 0) INTO v
        FROM (SELECT numero_recibo AS n FROM pagos
              UNION ALL SELECT numero_recibo FROM ingresos_caja
              UNION ALL SELECT numero_recibo FROM salidas_caja
              UNION ALL SELECT referencia FROM movimientos_banco)
        WHERE REGEXP_LIKE(n, '^' || p_prefijo || '-[0-9]+$');
        RETURN v;
    END;

    PROCEDURE renombrar(p_viejo VARCHAR2, p_nuevo VARCHAR2) IS
    BEGIN
        UPDATE pagos                 SET numero_recibo = p_nuevo WHERE numero_recibo = p_viejo;
        UPDATE ingresos_caja         SET numero_recibo = p_nuevo WHERE numero_recibo = p_viejo;
        UPDATE salidas_caja          SET numero_recibo = p_nuevo WHERE numero_recibo = p_viejo;
        UPDATE reimpresiones_recibos SET numero_recibo = p_nuevo WHERE numero_recibo = p_viejo;
        UPDATE movimientos_banco     SET referencia    = p_nuevo WHERE referencia    = p_viejo;
        -- Solo los CEA-000123 (ancho fijo) pueden aparecer escritos dentro de un concepto.
        IF p_viejo LIKE 'CEA-%' THEN
            UPDATE movimientos_banco
               SET concepto = SUBSTR(REPLACE(concepto, p_viejo, p_nuevo), 1, 200)
             WHERE INSTR(concepto, p_viejo) > 0;
        END IF;
        INSERT INTO recibos_renumerados (numero_anterior, numero_nuevo) VALUES (p_viejo, p_nuevo);
    END;
BEGIN
    IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> 'CEA_APP' THEN
        RAISE_APPLICATION_ERROR(-20901, 'Conéctate como CEA_APP para ejecutar esta migración.');
    END IF;

    ing := maximo('ING');
    egr := maximo('EGR');
    tra := maximo('TRA');

    -- Ingresos: pagos de alumnos, ingresos de caja e ingresos directos a un banco.
    FOR r IN (
        SELECT numero FROM (
            SELECT numero, MIN(fecha) AS f FROM (
                SELECT numero_recibo AS numero, fecha_pago AS fecha FROM pagos
                 WHERE numero_recibo IS NOT NULL AND numero_recibo NOT LIKE 'ING-%'
                UNION ALL
                SELECT numero_recibo, fecha_ingreso FROM ingresos_caja
                 WHERE numero_recibo IS NOT NULL AND numero_recibo NOT LIKE 'ING-%'
                UNION ALL
                SELECT referencia, fecha FROM movimientos_banco
                 WHERE origen = 'MANUAL' AND tipo = 'ENTRADA'
                   AND referencia IS NOT NULL AND referencia NOT LIKE 'ING-%'
            ) GROUP BY numero
        ) ORDER BY f, numero
    ) LOOP
        ing := ing + 1;
        renombrar(r.numero, formato('ING', ing));
    END LOOP;

    -- Egresos: salidas de caja y egresos directos de un banco.
    FOR r IN (
        SELECT numero FROM (
            SELECT numero, MIN(fecha) AS f FROM (
                SELECT numero_recibo AS numero, fecha_salida AS fecha FROM salidas_caja
                 WHERE numero_recibo IS NOT NULL AND numero_recibo NOT LIKE 'EGR-%'
                UNION ALL
                SELECT referencia, fecha FROM movimientos_banco
                 WHERE origen = 'MANUAL' AND tipo = 'SALIDA'
                   AND referencia IS NOT NULL AND referencia NOT LIKE 'EGR-%'
            ) GROUP BY numero
        ) ORDER BY f, numero
    ) LOOP
        egr := egr + 1;
        renombrar(r.numero, formato('EGR', egr));
    END LOOP;

    -- Traslados entre bancos.
    FOR r IN (
        SELECT referencia AS numero FROM movimientos_banco
         WHERE origen = 'TRASLADO_BANCO' AND referencia IS NOT NULL AND referencia NOT LIKE 'TRA-%'
         GROUP BY referencia ORDER BY MIN(fecha), referencia
    ) LOOP
        tra := tra + 1;
        renombrar(r.numero, formato('TRA', tra));
    END LOOP;

    COMMIT;

    -- Las secuencias siguen desde el último número usado.
    EXECUTE IMMEDIATE 'ALTER SEQUENCE seq_ingresos  RESTART START WITH ' || (ing + 1);
    EXECUTE IMMEDIATE 'ALTER SEQUENCE seq_egresos   RESTART START WITH ' || (egr + 1);
    EXECUTE IMMEDIATE 'ALTER SEQUENCE seq_traslados RESTART START WITH ' || (tra + 1);
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END;
/

-- Resultado: cada recibo viejo y el número que recibió.
SELECT numero_anterior, numero_nuevo FROM recibos_renumerados ORDER BY numero_nuevo;

PROMPT Recibos existentes renumerados correctamente.
