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

  // ── Menú lateral en celular ──
  const btnMenu = document.getElementById("menu-btn");
  if (btnMenu) {
    btnMenu.addEventListener("click", () => document.body.classList.toggle("sidebar-open"));
    document.querySelector(".preview-content").addEventListener("click", () =>
      document.body.classList.remove("sidebar-open"));
  }

  // ── Pestañas internas (data-tab="id-del-panel") ──
  document.querySelectorAll(".internal-tabs button[data-tab]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const scope = btn.closest(".tabs-scope");
      scope.querySelectorAll(".internal-tabs button").forEach(b => b.classList.remove("active"));
      scope.querySelectorAll(".subtab-content").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(btn.dataset.tab).classList.add("active");
    });
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

  // ── Registrar el service worker (PWA) ──
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
  }
})();
