# CEA La 30

Aplicación web Flask con Oracle Autonomous Database, permisos individuales y PWA.

## Desarrollo local

1. Requiere Python 3.11 o superior.
2. Crea y activa un entorno virtual:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
3. Instala dependencias: `pip install -r requirements.txt`.
4. Copia `.env.example` a `.env` y completa las credenciales Oracle y del wallet.
5. Si aún no se ha aplicado, ejecuta una vez la migración como `CEA_APP`:
   `@C:\ruta\al\proyecto\migrations\001_perfiles_personales.sql`
6. Después de `001`, ejecuta una vez `migrations/002_datos_alumno_y_cajas.sql` como `CEA_APP`.
7. Después de `002`, ejecuta una vez `migrations/003_recibos_unificados.sql` como `CEA_APP`.
8. Después de `003`, ejecuta una vez `migrations/004_matriculas_concurrentes.sql` como `CEA_APP` y antes de desplegar la versión nueva de la app.
9. Después de `004`, ejecuta una vez `migrations/005_tarifas_categoria.sql` como `CEA_APP` y antes de desplegar la versión que configura tarifas.
10. Después de `005`, ejecuta una vez `migrations/006_seguridad_y_categorias_caja.sql` como `CEA_APP` y antes de desplegar seguridad persistente y categorías de movimientos.
11. Después de `006`, ejecuta `migrations/007_permisos_cierres_y_tarifas.sql` como `CEA_APP` y antes de desplegar la versión que usa permisos ampliados, tarifas por tipo y conteo de cierre.
12. Si la base todavía no tiene un administrador, crea el primero:
   `python crear_usuario.py admin --nombre "Administrador" --rol admin`
13. Ejecuta `flask --app app run --debug`.

## Oracle

La app se conecta a Oracle Autonomous Database mediante `oracledb` en modo thin.
En local, `WALLET_DIR` apunta por defecto a `./Wallet`. No subas el wallet ni el
archivo `.env` al repositorio.

La migración `migrations/001_perfiles_personales.sql` se ejecuta una sola vez
conectado como propietario `CEA_APP` en SQLcl. Crea un perfil privado por
usuario, asigna permisos iniciales equivalentes a los roles actuales y agrega
`NUMERO_RECIBO` a `SALIDAS_CAJA`. También otorga a `CEA_WEB` los permisos DML
necesarios. La app no ejecuta DDL.

La migración `migrations/002_datos_alumno_y_cajas.sql` se ejecuta después de
`001`, también como `CEA_APP`. Agrega los datos personales y de contacto de
alumnos, precios/descuentos de matrícula, responsables opcionales y cajas
individuales por usuario. Los pagos y movimientos nuevos quedan enlazados a la
caja abierta del usuario; los registros históricos conservan `CAJA_ID` nulo.
La caja calcula efectivo esperado como base inicial + pagos en efectivo +
ingresos manuales - salidas. Los demás métodos se auditan aparte. Cada usuario
con permiso de registrar pagos abre y cierra su propia caja; quienes tengan el
permiso `ver_todas_cajas` consultan todas las cajas y el consolidado diario.

La migración `migrations/003_recibos_unificados.sql` se ejecuta después de
`002`, conectada como `CEA_APP`. Crea la secuencia única `SEQ_RECIBOS`,
agrega anulaciones auditables sin borrar pagos ni movimientos, y registra los
cambios y reimpresiones. Los recibos existentes no se renumeran. Los tres
permisos nuevos se asignan inicialmente solo a perfiles administradores; desde
**Usuarios y permisos** puedes revisar o cambiar los permisos de cada persona.

La migración `migrations/004_matriculas_concurrentes.sql` se ejecuta después de
`003`, conectada como `CEA_APP`. Debe aplicarse antes de desplegar la versión
de la app que la usa. Crea un registro de bloqueo para serializar por transacción
la asignación del consecutivo anual, evitando colisiones cuando dos cajeros
registran matrículas al mismo tiempo.

La migración `migrations/005_tarifas_categoria.sql` se ejecuta después de
`004`, conectada como `CEA_APP`. Crea el catálogo de categorías y precios
administrable desde **Usuarios y permisos**. La selección de una categoría
activa propone su tarifa al registrar una matrícula; el precio puede ajustarse
para esa matrícula sin modificar la tarifa guardada ni otras matrículas.

La migración `migrations/006_seguridad_y_categorias_caja.sql` se ejecuta después
de `005`, conectada como `CEA_APP`. Persiste el límite de intentos fallidos de
inicio de sesión y crea las categorías opcionales de ingresos y salidas,
administrables desde **Usuarios y permisos**. También guarda el cambio devuelto
en cada pago para que las reimpresiones usen el valor original.

La migración `migrations/007_permisos_cierres_y_tarifas.sql` se ejecuta después
de `006`, conectada como `CEA_APP`. Otorga `DELETE` a `CEA_WEB` para las tablas
de alumnos/responsables, agrega los permisos `anular_pagos` y
`ver_todas_cajas`, habilita tarifas separadas para cursos y renovaciones, y
guarda el conteo de denominaciones en cierres. Asigna los dos permisos nuevos
a los perfiles de usuarios cuyo rol existente es `admin`; los demás permisos
se editan individualmente en **Administración → Usuarios**.

Cada perfil pertenece a una única persona: varios usuarios pueden tener la
misma categoría (`admin`, `cajera`, `secretaria` o `contadora`), pero no
comparten perfil ni permisos. El administrador puede cambiar individualmente
los permisos de cada cuenta desde **Administración → Usuarios**. El campo `ROL` se
mantiene por compatibilidad y como categoría; la autorización usa el perfil.

El consecutivo de matrícula empieza de nuevo cada año. La app bloquea la fila
de `BLOQUEO_MATRICULAS` mientras asigna e inserta el siguiente número; la
restricción única `UQ_MAT_ORDEN (ANIO, NUMERO_ORDEN)` permanece como protección
final contra duplicados.

## Vercel

Vercel sirve la app Flask desde `index.py` y los archivos estáticos desde
`public/`. No hace falta comprar ni configurar un dominio: se puede usar el
dominio gratuito `*.vercel.app`. La función está fijada a `gru1` (São Paulo),
la región de Vercel más cercana disponible al Autonomous Database en Bogotá;
confirma que tu proyecto pueda desplegar en esa región.

En **Project → Settings → Environment Variables**, configura para Production
(y Preview si corresponde):

- `APP_ENV=production`
- `SECRET_KEY`: valor aleatorio largo y privado.
- `DB_USER=CEA_WEB`
- `DB_PASSWORD`: contraseña del usuario Oracle `CEA_WEB`.
- `DB_DSN=kamino_low`
- `DB_SCHEMA=CEA_APP`
- `WALLET_PASSWORD`: contraseña del wallet de Oracle.
- `WALLET_PEM_B64`: contenido base64 del archivo `ewallet.pem`.
- `WALLET_TNS_B64`: contenido base64 de `tnsnames.ora`.
- `TRUST_PROXY=1`
- Opcionales para los comprobantes: `CEA_CIUDAD` y `CEA_NIT`.

En PowerShell, desde la raíz del proyecto, puedes generar los dos valores del
wallet localmente (no los publiques ni los pegues en el repositorio):

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("Wallet\ewallet.pem"))
[Convert]::ToBase64String([IO.File]::ReadAllBytes("Wallet\tnsnames.ora"))
```

Vercel usa el espacio temporal `/tmp` para materializar esos dos archivos en
cada instancia. No almacenes el wallet, contraseñas ni datos persistentes en el
filesystem de una función. La base Oracle debe aceptar conexiones desde Vercel;
verifica la configuración de acceso de red de Autonomous Database. No abras la
base a internet sin comprobar antes sus restricciones y el uso de wallet.

Después de configurar las variables, vuelve a desplegar. Los errores de
conexión se consultan en **Vercel → Deployments → Functions/Logs**. El archivo
`vercel.json` establece el límite de ejecución de la función Flask; los límites
exactos disponibles dependen del plan de Vercel. El plan Hobby permite una sola
región para funciones; `gru1` se configura como esa única región.

## Funcionalidad

- Inicio/cierre de sesión, CSRF y cuentas con contraseña cifrada.
- Dashboard, búsqueda de alumnos y matrículas, edición/archivo con auditoría,
  historial de pagos y recibos PDF reimprimibles.
- Registro de alumnos y renovaciones con datos personales, responsable
  opcional, precio/descuento y abono inicial opcional.
- Creación de matrículas con consecutivo anual.
- Tarifas administrables por categoría y autocompletado de alumno por documento
  al registrar cursos y renovaciones, con precios diferenciados para cada tipo.
- Apertura/cierre individual de caja, consulta/reimpresión de movimientos y
  registro autorizado de ingresos/salidas manuales con recibos PDF.
- Exportación a PDF y Excel de cierres cerrados desde Caja → Cierres, con
  resumen, conteo de efectivo y detalle de pagos, ingresos y salidas.
- Categorías opcionales para clasificar ingresos y salidas manuales de caja.
- Dashboard con matrículas del mes, comparación con el mes anterior,
  distribución por categoría y avance de pago de las matrículas recientes.
- Menú lateral con Dashboard, Alumnos, Caja, Trámites y Administración; Caja
  tiene tres pestañas y Administración dos. El registro de alumnos se guía en cuatro pasos;
  acciones de caja y movimientos se muestran por contexto para reducir ruido.
- Seguimiento RUNT.
- Administración de cuentas y perfiles de permisos individuales.

La exportación de cierres a PDF/Excel, expedientes y otras funciones no tienen
todavía una interfaz implementada.

## Pruebas y ejecución local

- Ejecutar la aplicación: `flask --app app run --debug`
- Comprobar salud: `http://127.0.0.1:5000/healthz`
- Desplegar en Vercel conectando el repositorio o con Vercel CLI.
