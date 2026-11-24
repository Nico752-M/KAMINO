-- PERMISOS FINOS DE LA TIENDA · quién puede anular, tocar inventario, servicios, caja, ganancias, cuentas y usuarios.
-- Ejecutar UNA sola vez, conectado como CEA_APP, como script (F5 / "Ejecutar script").
-- Compatible con SQL Developer Web (Database Actions): no usa comandos restringidos como WHENEVER.
-- Todo va en un solo bloque: si una verificación falla, no se inserta nada.
-- No crea tablas: solo reparte permisos nuevos a quienes ya usaban la tienda, para que nadie pierda nada.

DECLARE
    cantidad NUMBER;
BEGIN
    IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> 'CEA_APP' THEN
        RAISE_APPLICATION_ERROR(-20911, 'Conéctate como CEA_APP para ejecutar esta migración.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_tables
    WHERE table_name IN ('USUARIOS', 'PERFILES', 'PERFIL_PERMISOS');
    IF cantidad <> 3 THEN
        RAISE_APPLICATION_ERROR(-20912, 'Aplica primero las migraciones 001-009.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM perfil_permisos
    WHERE codigo IN ('tienda_anular', 'tienda_inventario', 'tienda_servicios', 'tienda_caja',
                     'tienda_ganancias', 'tienda_cuentas', 'tienda_usuarios');
    IF cantidad <> 0 THEN
        RAISE_APPLICATION_ERROR(-20913, 'Los permisos de la tienda ya existen; revisa si la migración ya se aplicó.');
    END IF;

    -- Hasta hoy «ver_tienda» daba acceso a todo. Para que nadie pierda nada,
    -- quien ya tenía ver_tienda recibe los permisos nuevos (menos el de usuarios).
    INSERT INTO perfil_permisos (perfil_id, codigo)
    SELECT pp.perfil_id, c.codigo
    FROM perfil_permisos pp
    CROSS JOIN (
        SELECT 'tienda_anular' AS codigo FROM dual UNION ALL
        SELECT 'tienda_inventario' FROM dual UNION ALL
        SELECT 'tienda_servicios' FROM dual UNION ALL
        SELECT 'tienda_caja' FROM dual UNION ALL
        SELECT 'tienda_ganancias' FROM dual UNION ALL
        SELECT 'tienda_cuentas' FROM dual
    ) c
    WHERE pp.codigo = 'ver_tienda';

    -- Administrar usuarios de la tienda: solo el rol «tienda» (admin 2) y los administradores del CEA.
    INSERT INTO perfil_permisos (perfil_id, codigo)
    SELECT pf.id, 'tienda_usuarios'
    FROM perfiles pf
    JOIN usuarios u ON u.id = pf.usuario_id
    JOIN perfil_permisos pp ON pp.perfil_id = pf.id AND pp.codigo = 'ver_tienda'
    WHERE u.rol IN ('tienda', 'admin');

    COMMIT;
    DBMS_OUTPUT.PUT_LINE('Migración 010 de permisos de la tienda aplicada correctamente.');
END;
/
