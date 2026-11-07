/* Service worker.
   - Guarda en caché SOLO archivos estáticos (CSS, JS, iconos) para que la app abra rápido.
   - Las páginas y los datos (pagos, alumnos, caja) NUNCA se guardan: siempre vienen del servidor.
   - Sin internet muestra una pantalla "sin conexión".
   Cuando cambies CSS/JS, sube VERSION para que los celulares se actualicen. */
const VERSION = "cea-v15";
const CACHE_FILES = ["/offline", "/static/css/app.css", "/static/js/app.js", "/static/icons/icon-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(CACHE_FILES)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/static/")) {
    e.respondWith(
      caches.match(req).then((guardado) => {
        const red = fetch(req).then((r) => {
          if (r.ok) { const copia = r.clone(); caches.open(VERSION).then((c) => c.put(req, copia)); }
          return r;
        }).catch(() => guardado);
        return guardado || red;
      })
    );
    return;
  }

  if (req.mode === "navigate") {
    e.respondWith(fetch(req).catch(() => caches.match("/offline")));
  }
});
