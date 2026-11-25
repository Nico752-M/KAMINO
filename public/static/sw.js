/* Service worker.
   - Guarda en caché SOLO archivos estáticos (CSS, JS, iconos). Cada archivo se pide con ?v=NN,
     así cada versión queda guardada aparte y el dispositivo sigue con la que aceptó.
   - Las páginas y los datos (pagos, alumnos, caja) NUNCA se guardan.
   - Sin internet muestra la pantalla "sin conexión". */
const CACHE = "cea-static"; // offline v2

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.add("/offline")));
  self.skipWaiting();
});

// Conserva la pantalla offline y los estáticos de las 3 versiones más recientes
async function limpiarCache() {
  const cache = await caches.open(CACHE);
  const claves = await cache.keys();
  const versiones = [];
  for (const req of claves) {
    const v = new URL(req.url).searchParams.get("v");
    if (v && !versiones.includes(v)) versiones.push(v);
  }
  const conservar = new Set(versiones.slice(-3));
  await Promise.all(claves.map((req) => {
    const v = new URL(req.url).searchParams.get("v");
    return v && !conservar.has(v) ? cache.delete(req) : null;
  }));
}

self.addEventListener("activate", (e) => {
  e.waitUntil(
    Promise.all([
      limpiarCache(),
      self.registration.navigationPreload
        ? self.registration.navigationPreload.enable()
        : null,
    ]).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/static/")) {
    e.respondWith(
      caches.match(req).then((guardado) => guardado || fetch(req).then((r) => {
        if (r.ok) {
          const copia = r.clone();
          caches.open(CACHE).then((c) => c.put(req, copia)).then(limpiarCache);
        }
        return r;
      }))
    );
    return;
  }

  if (req.mode === "navigate") {
    e.respondWith((async () => {
      try {
        const precargada = await e.preloadResponse;
        return precargada || await fetch(req);
      } catch (err) {
        return caches.match("/offline");
      }
    })());
  }
});