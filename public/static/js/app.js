/* Comportamiento general: tema, menú móvil, pestañas y helper de peticiones */
(function () {
  "use strict";

  // ── Tema claro / noche (se recuerda en el navegador) ──
  const html = document.documentElement;
  const btnTema = document.getElementById("theme-btn");
  function pintarBotonTema() {
    if (!btnTema) return;
    const noche = html.getAttribute("data-theme") === "night";
    btnTema.querySelector("i").className = noche ? "ri-sun-line" : "ri-moon-line";
    btnTema.querySelector("span").textContent = noche ? "Modo Claro (Crema)" : "Modo Noche (Azul)";
  }
  if (btnTema) {
    btnTema.addEventListener("click", function () {
      const nuevo = html.getAttribute("data-theme") === "light" ? "night" : "light";
      html.setAttribute("data-theme", nuevo);
      try { localStorage.setItem("tema", nuevo); } catch (e) {}
      pintarBotonTema();
    });
    pintarBotonTema();
  }

  const btnMenu = document.getElementById("menu-btn");
  const contenido = document.querySelector(".preview-content");
  if (btnMenu && contenido) {
    btnMenu.addEventListener("click", (evento) => {
      evento.stopPropagation();
      document.body.classList.toggle("sidebar-open");
    });
    contenido.addEventListener("click", () => document.body.classList.remove("sidebar-open"));
    document.querySelectorAll(".preview-menu a").forEach((enlace) => {
      enlace.addEventListener("click", () => document.body.classList.remove("sidebar-open"));
    });
  }

  document.addEventListener("submit", (evento) => {
    const f = evento.target;
    if (f.dataset.confirm && !window.confirm(f.dataset.confirm)) {
      evento.preventDefault();
      return;
    }
    if (!f.matches("form[data-reason-confirm]")) return;
    const motivo = window.prompt(f.dataset.reasonPrompt || "Escribe el motivo obligatorio.");
    if (!motivo || !motivo.trim() || !window.confirm(f.dataset.confirmMessage || "¿Confirmas esta acción?")) {
      evento.preventDefault();
      return;
    }
    f.querySelector('[name="motivo"]').value = motivo.trim();
  }, true);

  // ── Pesos: separador de miles solo visual, los formularios envían dígitos ──
  const soloDigitos = (valor) => String(valor || "").replace(/\D/g, "");
  window.soloDigitos = soloDigitos;
  window.formatearMiles = (valor) => {
    const digitos = soloDigitos(valor);
    return digitos.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  };
  window.formatearCampoMoneda = (campo) => {
    const posicion = campo.selectionStart;
    const digitosAntes = soloDigitos(campo.value.slice(0, posicion)).length;
    campo.value = window.formatearMiles(campo.value);
    if (posicion === null) return;
    let cursor = 0;
    let encontrados = 0;
    while (cursor < campo.value.length && encontrados < digitosAntes) {
      if (/\d/.test(campo.value[cursor])) encontrados += 1;
      cursor += 1;
    }
    campo.setSelectionRange(cursor, cursor);
  };
  document.querySelectorAll("[data-money-input]").forEach((campo) => window.formatearCampoMoneda(campo));
  document.addEventListener("input", (e) => {
    if (e.target.matches("[data-money-input]")) window.formatearCampoMoneda(e.target);
  });
  const precioBaseEdicion = document.getElementById("editBase");
  const descuentoEdicion = document.getElementById("editDescuento");
  const totalEdicion = document.getElementById("editTotal");
  if (precioBaseEdicion && descuentoEdicion && totalEdicion) {
    const calcularEdicion = () => {
      const base = Number(soloDigitos(precioBaseEdicion.value)) || 0;
      const descuento = Number(soloDigitos(descuentoEdicion.value)) || 0;
      totalEdicion.textContent = "$ " + window.formatearMiles(Math.max(base - descuento, 0));
    };
    precioBaseEdicion.addEventListener("input", calcularEdicion);
    descuentoEdicion.addEventListener("input", calcularEdicion);
  }
  document.addEventListener("submit", (evento) => {
    evento.target.querySelectorAll("[data-money-input]").forEach((campo) => {
      campo.value = soloDigitos(campo.value);
    });
  }, true);

  // ── Pestañas internas (data-tab="id-del-panel") ──
  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".internal-tabs button[data-tab]");
    if (!btn) return;
    const scope = btn.closest(".tabs-scope");
    scope.querySelectorAll(".internal-tabs button").forEach(b => b.classList.remove("active"));
    scope.querySelectorAll(".subtab-content").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
  });

  // ── Formularios de páginas con {% set ajax = true %}: se envían sin recargar ──
  document.addEventListener("submit", async (evento) => {
    const f = evento.target;
    if (evento.defaultPrevented || !f.closest("#zona[data-ajax]") || f.target === "_blank") return;
    evento.preventDefault();
    const zona = document.getElementById("zona");
    const antes = {
      abiertos: [...zona.querySelectorAll("details[id][open]")].map((d) => d.id),
      tabs: [...zona.querySelectorAll(".subtab-content.active")].map((p) => p.id),
      y: contenido.scrollTop,
    };
    const datos = new FormData(f, evento.submitter);
    const botones = [...f.querySelectorAll("button")];
    botones.forEach((b) => (b.disabled = true));
    try {
      const resp = await fetch(f.action, { method: "POST", body: datos, credentials: "same-origin" });
      if (new URL(resp.url).pathname !== location.pathname) { location.href = resp.url; return; }
      const nueva = new DOMParser().parseFromString(await resp.text(), "text/html").getElementById("zona");
      if (!nueva) { location.href = resp.url; return; }
      zona.replaceWith(nueva);
      antes.abiertos.forEach((id) => { const d = document.getElementById(id); if (d) d.open = true; });
      antes.tabs.forEach((id) => document.querySelector('.internal-tabs button[data-tab="' + id + '"]')?.click());
      nueva.querySelectorAll("[data-money-input]").forEach((c) => window.formatearCampoMoneda(c));
      contenido.scrollTop = antes.y;
    } catch (e) {
      botones.forEach((b) => (b.disabled = false));
      alert("Sin conexión. Revisa tu internet e intenta de nuevo.");
    }
  });

  // ── Recordar detalles abiertos, pestaña y posición al recargar tras guardar ──
  const claveUI = "ui:" + location.pathname;
  try {
    const g = JSON.parse(sessionStorage.getItem(claveUI) || "null");
    sessionStorage.removeItem(claveUI);
    if (g && Date.now() - g.t < 10000) {
      document.querySelectorAll("details[id]").forEach((d) => { d.open = g.abiertos.includes(d.id); });
      g.tabs.forEach((id) => document.querySelector('.internal-tabs button[data-tab="' + id + '"]')?.click());
      if (contenido) contenido.scrollTop = g.y;
    }
  } catch (e) {}
  document.addEventListener("submit", (evento) => {
    if (evento.defaultPrevented) return;
    try {
      sessionStorage.setItem(claveUI, JSON.stringify({
        t: Date.now(),
        abiertos: [...document.querySelectorAll("details[id][open]")].map((d) => d.id),
        tabs: [...document.querySelectorAll(".subtab-content.active")].map((p) => p.id),
        y: contenido ? contenido.scrollTop : 0,
      }));
    } catch (e) {}
  });

  // ── Helper global: POST JSON con token CSRF ──
  window.postJSON = async function (url, datos) {
    const token = document.querySelector('meta[name="csrf-token"]').content;
    let resp;
    try {
      resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
        body: JSON.stringify(datos || {}),
        credentials: "same-origin",
      });
    } catch (e) {
      return { ok: false, error: "Sin conexión. Revisa tu internet e intenta de nuevo." };
    }
    let cuerpo = {};
    try { cuerpo = await resp.json(); } catch (e) {}
    if (resp.status === 401) { window.location.href = "/login"; }
    return { ok: resp.ok && cuerpo.ok !== false, ...cuerpo, error: cuerpo.error };
  };

  // ── Actualizaciones: versión aceptada en este dispositivo vs. versión del servidor ──
  const versionServidor = document.body.dataset.version;
  const hayNueva = document.body.dataset.nueva === "1";
  const esIngreso = document.body.dataset.login === "1";
  const guardarVersion = (v) => {
    document.cookie = "cea_v=" + v + "; path=/; max-age=31536000; SameSite=Lax";
  };
  // Primera vez en este dispositivo: se queda con la versión actual
  if (!/(?:^|; )cea_v=/.test(document.cookie)) guardarVersion(versionServidor);

  function aplicarActualizacion() {
    const modalAbierto = document.querySelector(".modal-overlay.open");
    if (modalAbierto && !confirm("Tienes una ventana abierta. Si actualizas ahora se perderá lo que estés escribiendo. ¿Actualizar de todas formas?")) {
      return;
    }
    guardarVersion(versionServidor);
    window.location.reload();
  }

  if (hayNueva) {
    // Apartado fijo en el menú
    const item = document.getElementById("update-nav");
    if (item) {
      item.hidden = false;
      item.onclick = (e) => { e.preventDefault(); aplicarActualizacion(); };
    }
    document.getElementById("menu-btn")?.classList.add("has-update");

    // Aviso grande: solo justo después de iniciar sesión
    const banner = document.getElementById("update-banner");
    if (esIngreso && banner) {
      banner.hidden = false;
      document.getElementById("update-btn").onclick = aplicarActualizacion;
      document.getElementById("update-later").onclick = () => { banner.hidden = true; };
    }
  }

  // ── Service worker (PWA) ──
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => navigator.serviceWorker.register("/static/sw.js", { scope: "/" }).catch(() => {}));
  }
})();
