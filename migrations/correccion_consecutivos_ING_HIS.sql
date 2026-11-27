-- KAMINO: separar consecutivos de pagos nuevos (ING) e historicos (HIS).
-- Ejecutar UNA SOLA VEZ conectado como CEA_APP.
-- Este script corrige exclusivamente los cinco pagos verificados por ID (221 a 225).
-- No elimina pagos ni cambia valores, fechas, matriculas o metodos de pago.

SET DEFINE OFF

DECLARE
    v_count NUMBER;
BEGIN
    IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> 'CEA_APP' THEN
        RAISE_APPLICATION_ERROR(-20931, 'Conectate como CEA_APP para ejecutar esta correccion.');
    END IF;

    -- Comprobar que los cinco registros siguen exactamente como fueron revisados.
    SELECT COUNT(*) INTO v_count
      FROM pagos
     WHERE (id = 221 AND numero_recibo = 'ING-003')
        OR (id = 222 AND numero_recibo = 'ING-001')
        OR (id = 223 AND numero_recibo = 'ING-002')
        OR (id = 224 AND numero_recibo = 'ING-004')
        OR (id = 225 AND numero_recibo = 'ING-005');
    IF v_count <> 5 THEN
        RAISE_APPLICATION_ERROR(-20932, 'Los pagos ya no coinciden con la revision. No se modifico nada.');
    END IF;

    SELECT COUNT(*) INTO v_count FROM user_sequences WHERE sequence_name = 'SEQ_HISTORICOS';
    IF v_count = 0 THEN
        EXECUTE IMMEDIATE 'CREATE SEQUENCE seq_historicos START WITH 4 INCREMENT BY 1 NOCYCLE NOCACHE';
        EXECUTE IMMEDIATE 'GRANT SELECT ON seq_historicos TO CEA_WEB';
    ELSE
        RAISE_APPLICATION_ERROR(-20933, 'SEQ_HISTORICOS ya existe. Revisa antes de ejecutar este script otra vez.');
    END IF;

    -- Primero se pasan los tres historicos a HIS, liberando ING-001/002/003.
    UPDATE pagos SET numero_recibo = 'HIS-001' WHERE id = 222 AND numero_recibo = 'ING-001';
    UPDATE pagos SET numero_recibo = 'HIS-002' WHERE id = 223 AND numero_recibo = 'ING-002';
    UPDATE pagos SET numero_recibo = 'HIS-003' WHERE id = 221 AND numero_recibo = 'ING-003';

    -- Luego se deja ING con los dos pagos reales de caja en el orden solicitado.
    UPDATE pagos SET numero_recibo = 'ING-001' WHERE id = 224 AND numero_recibo = 'ING-004';
    UPDATE pagos SET numero_recibo = 'ING-002' WHERE id = 225 AND numero_recibo = 'ING-005';

    -- Mantener coherentes las referencias de reimpresion, si existen.
    UPDATE reimpresiones_recibos SET numero_recibo = 'HIS-001' WHERE numero_recibo = 'ING-001' AND tipo = 'PAGO';
    UPDATE reimpresiones_recibos SET numero_recibo = 'HIS-002' WHERE numero_recibo = 'ING-002' AND tipo = 'PAGO';
    UPDATE reimpresiones_recibos SET numero_recibo = 'HIS-003' WHERE numero_recibo = 'ING-003' AND tipo = 'PAGO';
    UPDATE reimpresiones_recibos SET numero_recibo = 'ING-001' WHERE numero_recibo = 'ING-004' AND tipo = 'PAGO';
    UPDATE reimpresiones_recibos SET numero_recibo = 'ING-002' WHERE numero_recibo = 'ING-005' AND tipo = 'PAGO';

    -- Actualizar la tabla de equivalencias creada por la migracion 019.
    -- Se busca por numero_nuevo (el ING-00x que dejo la 019) y en el mismo orden que arriba,
    -- para cubrir los cinco pagos sin depender de los numeros viejos (HIST-xxx / CEA-xxxxxx).
    UPDATE recibos_renumerados SET numero_nuevo = 'HIS-001' WHERE numero_nuevo = 'ING-001';
    UPDATE recibos_renumerados SET numero_nuevo = 'HIS-002' WHERE numero_nuevo = 'ING-002';
    UPDATE recibos_renumerados SET numero_nuevo = 'HIS-003' WHERE numero_nuevo = 'ING-003';
    UPDATE recibos_renumerados SET numero_nuevo = 'ING-001' WHERE numero_nuevo = 'ING-004';
    UPDATE recibos_renumerados SET numero_nuevo = 'ING-002' WHERE numero_nuevo = 'ING-005';

    COMMIT;

    -- Siguiente pago nuevo: ING-003. Siguiente abono historico: HIS-004.
    EXECUTE IMMEDIATE 'ALTER SEQUENCE seq_ingresos RESTART START WITH 3';
    EXECUTE IMMEDIATE 'ALTER SEQUENCE seq_historicos RESTART START WITH 4';
END;
/

PROMPT Consecutivos separados. Verifica el resultado:
SELECT id, numero_recibo, concepto, valor, metodo_pago
  FROM pagos
 WHERE id IN (221, 222, 223, 224, 225)
 ORDER BY id;
