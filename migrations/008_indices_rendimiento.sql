CREATE INDEX ix_pagos_mat_anulado ON pagos (id_matricula, anulado, valor);
CREATE INDEX ix_pagos_fecha ON pagos (fecha_pago);
CREATE INDEX ix_ingresos_fecha ON ingresos_caja (fecha_ingreso);
CREATE INDEX ix_salidas_fecha ON salidas_caja (fecha_salida);
CREATE INDEX ix_mat_fecha ON matriculas (archivado, fecha_registro);
CREATE INDEX ix_mat_runt ON matriculas (archivado, runt_registrado, estado);