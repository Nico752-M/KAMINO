-- Confirmación de pagos por el administrador (solo CEA; la tienda no se toca).
-- Ejecutar una sola vez conectado como propietario CEA_APP, después de la 011.
-- El pago entra a caja como siempre; queda «pendiente» hasta que alguien con el
-- permiso confirmar_pagos lo confirme.

SET DEFINE OFF
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK

DECLARE
    cantidad NUMBER;
BEGIN
    IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> 'CEA_APP' THEN
        RAISE_APPLICATION_ERROR(-20301, 'Conéctate como CEA_APP para ejecutar esta migración.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM user_tab_columns
    WHERE table_name = 'PAGOS'
      AND column_name IN ('CONFIRMADO', 'CONFIRMADO_POR', 'FECHA_CONFIRMACION');
    IF cantidad <> 0 THEN
        RAISE_APPLICATION_ERROR(-20302, 'Ya existen columnas de confirmación; revisa si la migración ya se aplicó.');
    END IF;

    SELECT COUNT(*) INTO cantidad FROM perfil_permisos WHERE codigo = 'confirmar_pagos';
    IF cantidad <> 0 THEN
        RAISE_APPLICATION_ERROR(-20303, 'El permiso confirmar_pagos ya existe; revisa si la migración ya se aplicó.');
    END IF;
END;
/

-- Con DEFAULT 1 todos los pagos que ya existen quedan confirmados (el historial no queda pendiente).
ALTER TABLE pagos ADD (
    confirmado NUMBER(1) DEFAULT 1 NOT NULL,
    confirmado_por NUMBER,
    fecha_confirmacion TIMESTAMP
);
ALTER TABLE pagos ADD CONSTRAINT ck_pagos_confirmado CHECK (confirmado IN (0, 1));
ALTER TABLE pagos ADD CONSTRAINT fk_pagos_confirmado_usr
    FOREIGN KEY (confirmado_por) REFERENCES usuarios (id);

-- Desde ahora, un pago nuevo nace pendiente salvo que la aplicación indique otra cosa.
ALTER TABLE pagos MODIFY (confirmado DEFAULT 0);

CREATE INDEX ix_pagos_pendientes ON pagos (confirmado, anulado);

-- El administrador recibe el permiso; luego puede darlo a otros desde Administración.
INSERT INTO perfil_permisos (perfil_id, codigo)
SELECT pf.id, 'confirmar_pagos'
FROM perfiles pf
JOIN usuarios u ON u.id = pf.usuario_id
WHERE u.rol = 'admin';

COMMIT;
PROMPT Migración de confirmación de pagos aplicada correctamente.
