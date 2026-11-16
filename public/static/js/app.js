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

  document.querySelectorAll("form[data-reason-confirm]").forEach((formulario) => {
    formulario.addEventListener("submit", (evento) => {
      const motivo = window.prompt(formulario.dataset.reasonPrompt || "Escribe el motivo obligatorio.");
      if (!motivo || !motivo.trim()) {
        evento.preventDefault();
        return;
      }
      if (!window.confirm(formulario.dataset.confirmMessage || "¿Confirmas esta acción?")) {
        evento.preventDefault();
        return;
      }
      formulario.querySelector('[name="motivo"]').value = motivo.trim();
    });
  });

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
  document.querySelectorAll("[data-money-input]").forEach((campo) => {
    window.formatearCampoMoneda(campo);
    campo.addEventListener("input", () => window.formatearCampoMoneda(campo));
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

  // ── Service worker (PWA) con aviso de actualización ──
  if ("serviceWorker" in navigator) {
    const teniaControlador = !!navigator.serviceWorker.controller;

    function mostrarActualizacion(reg) {
      const banner = document.getElementById("update-banner");
      const boton = document.getElementById("update-btn");
      if (!banner || !boton) return;
      banner.hidden = false;
      boton.onclick = () => {
        boton.disabled = true;
        boton.textContent = "Actualizando...";
        if (reg.waiting) reg.waiting.postMessage({ type: "SKIP_WAITING" });
      };
      document.getElementById("update-later").onclick = () => { banner.hidden = true; };
    }

    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/static/sw.js", { scope: "/" }).then((reg) => {
        if (reg.waiting && navigator.serviceWorker.controller) mostrarActualizacion(reg);
        reg.addEventListener("updatefound", () => {
          const nuevo = reg.installing;
          if (!nuevo) return;
          nuevo.addEventListener("statechange", () => {
            if (nuevo.state === "installed" && navigator.serviceWorker.controller) mostrarActualizacion(reg);
          });
        });
        // Buscar versión nueva al volver a la app y cada 30 min
        document.addEventListener("visibilitychange", () => { if (!document.hidden) reg.update(); });
        setInterval(() => reg.update(), 30 * 60 * 1000);
      }).catch(() => {});
    });

    // Cuando el usuario acepta, la versión nueva toma el control: recargar una sola vez
    let recargando = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (recargando || !teniaControlador) return;
      recargando = true;
      window.location.reload();
    });
  }
})();
