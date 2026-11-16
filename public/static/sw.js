/* Service worker.
   - Guarda en caché SOLO archivos estáticos (CSS, JS, iconos). Cada archivo se pide con ?v=NN,
     así cada versión queda guardada aparte y el dispositivo sigue con la que aceptó.
   - Las páginas y los datos (pagos, alumnos, caja) NUNCA se guardan.
   - Sin internet muestra la pantalla "sin conexión". */
const VERSION = "cea-v22";
const CACHE = "cea-static";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.add("/offline")));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/static/")) {
    e.respondWith(
      caches.match(req).then((guardado) => guardado || fetch(req).then((r) => {
        if (r.ok) { const copia = r.clone(); caches.open(CACHE).then((c) => c.put(req, copia)); }
        return r;
      }))
    );
    return;
  }

  if (req.mode === "navigate") {
    e.respondWith(fetch(req).catch(() => caches.match("/offline")));
  }
});