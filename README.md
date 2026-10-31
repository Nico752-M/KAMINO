# CEA Practicar — versión web (Flask + MySQL + PWA)

## Cómo correrlo en tu PC
1. Python 3.11 o superior.
2. `python -m venv venv` y activarlo (`venv\Scripts\activate` en Windows).
3. `pip install -r requirements.txt`
4. Copia `.env.example` a `.env` y llena los datos de tu MySQL (la misma base `cea_p`).
5. Crea tu usuario con contraseña segura:
   `python crear_usuario.py admin --nombre "Administrador" --rol admin`
6. `flask --app app run --debug` y abre http://127.0.0.1:5000

## Revisa tu base de datos (el código asume esto)
Los .sql que me pasaste no coinciden con el código del escritorio. Verifica en tu MySQL real:
- `pagos` tiene: `id_matricula, concepto, valor, metodo_pago, numero_recibo, usuario_id, observaciones, acompanante, fecha_pago`
- `pagos.metodo_pago` incluye `Sistecredit` (si es ENUM sin ese valor, hay que ampliarlo con ALTER TABLE)
- `matriculas` tiene: `numero_orden, anio, categoria, estado, precio_total, fecha_registro, runt_registrado`
- Existen `ingresos_caja` (`fecha_ingreso`) y `salidas_caja` (`fecha_salida`, `numero_recibo`) y `usuarios` con `activo`, `rol`, `ultimo_acceso`
Si algo falta, la pantalla correspondiente muestra un aviso (no se cae todo) y el detalle sale en la consola.

## Estructura
- `app.py` arranque, seguridad (CSRF, cabeceras) y rutas PWA
- `config.py` / `.env` configuración y claves (nada sensible en el código)
- `db.py` pool de conexiones MySQL y transacciones
- `auth.py` login, sesiones, roles
- `rutas/` una pantalla por archivo (dashboard, alumnos, pagos, caja, tramites)
- `servicios/recibos.py` ticket PDF de 80 mm
- `templates/` HTML (base.html = menú + barra superior)
- `public/static/` CSS, JS, iconos, `manifest.json`, `sw.js`

## Publicar
- Procfile listo: `gunicorn wsgi:app`
- Variables en el servidor: `APP_ENV=production`, `SECRET_KEY`, `DB_*`, `TRUST_PROXY=1`
- Debe servirse por HTTPS (sin HTTPS no se puede instalar como PWA).
- Cuando cambies CSS/JS sube `ASSET_V` en `config.py` y `VERSION` en `public/static/sw.js`.

### Publicar en Vercel
- Para la etapa visual, Vercel sirve `public/index.html` como entrada y las páginas
  `public/dashboard.html`, `public/alumnos.html`, `public/tesoreria.html` y `public/tramites.html`
  como prototipo estático. El formulario simula el ingreso y no valida credenciales ni guarda datos.
- Las plantillas Jinja originales siguen en `templates/` para cuando se conecte el backend Flask.
  `index.py` exporta esa aplicación; sus rutas y el prototipo estático son superficies separadas.
- La vista estática no requiere variables de base de datos. Para activar el backend después,
  configura `APP_ENV=production`, `SECRET_KEY`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`,
  `DB_PASSWORD` y `TRUST_PROXY=1`. La base MySQL debe permitir conexiones desde Vercel;
  no uses `127.0.0.1` como `DB_HOST`.

## Pendiente (siguientes fases)
Nueva matrícula/editar/ver/eliminar, alumno histórico, precios, renovaciones (alumno externo),
registrar salidas/ingresos de caja, cierre de caja (conteo, PDF, Excel), expedientes, ficha y evaluaciones.
