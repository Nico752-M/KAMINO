# Tienda

Caja, inventario que se descuenta solo con cada venta y ganancia neta a tu manera.
Vive en esta carpeta y usa su propio usuario de Oracle, aparte del CEA.

## Archivos
- `__init__.py` — registra el módulo (`/tienda`).
- `rutas.py` — la página y la API (`/tienda/api/...`). Todo exige sesión y el permiso `ver_tienda`.
- `servicios.py` — la lógica: productos, ventas (descuenta inventario), anulaciones, ganancias.
- `datos.py` — conexión a Oracle con el usuario de la tienda.
- `migraciones/001_tienda.sql` — crea las tablas (se ejecuta una vez como el usuario de la tienda).
- `templates/tienda/tienda.html`, `static/tienda.css`, `static/tienda.js` — la pantalla.

## Variables de entorno (además de las del CEA: DB_DSN, WALLET_PASSWORD, wallet)
- `TIENDA_DB_USER` — el usuario de Oracle creado para la tienda.
- `TIENDA_DB_PASSWORD` — su contraseña.
- `TIENDA_DB_SCHEMA` — opcional; solo si las tablas viven en un esquema distinto al del usuario.

## Tablas (todas empiezan por `t_`)
`t_productos`, `t_ventas`, `t_venta_items`, `t_movimientos` (historial de entradas y salidas), `t_ajustes`.

## Usuario de la tienda
    python crear_usuario.py "admin 2" --nombre "Admin 2" --rol tienda
La contraseña se escribe al ejecutarlo (no se guarda en ningún archivo). El rol `tienda` solo ve la tienda.
