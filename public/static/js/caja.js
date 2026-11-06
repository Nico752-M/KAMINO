(function () {
  "use strict";
  const modals = [...document.querySelectorAll(".cash-modal-overlay")];

  function abrir(modal) {
    if (!modal) return;
    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
    modal.querySelector("input:not([type=hidden])")?.focus();
  }

  function cerrar(modal) {
    if (!modal) return;
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
  }

  document.getElementById("btnAbrirCierre")?.addEventListener("click", () => {
    abrir(document.getElementById("cierreCajaModal"));
  });
  document.getElementById("btnMovimiento")?.addEventListener("click", () => {
    abrir(document.getElementById("movimientoCajaModal"));
  });

  modals.forEach((modal) => {
    modal.querySelectorAll("[data-close-modal]").forEach((boton) => {
      boton.addEventListener("click", () => cerrar(modal));
    });
    modal.addEventListener("click", (evento) => {
      if (evento.target === modal) cerrar(modal);
    });
  });

  document.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape") modals.forEach(cerrar);
  });

  const denominaciones = [...document.querySelectorAll("[data-denomination]")];
  const efectivoContado = document.getElementById("montoCierre");
  const totalDenominaciones = document.getElementById("totalDenominaciones");
  if (denominaciones.length && efectivoContado && totalDenominaciones) {
    const calcularEfectivo = () => {
      const total = denominaciones.reduce((suma, campo) => {
        const cantidad = Number.parseInt(campo.value, 10) || 0;
        return suma + cantidad * Number(campo.dataset.denomination);
      }, 0);
      efectivoContado.value = window.formatearMiles(total);
      efectivoContado.dispatchEvent(new Event("input", { bubbles: true }));
      totalDenominaciones.textContent = "$ " + window.formatearMiles(total);
    };
    denominaciones.forEach((campo) => campo.addEventListener("input", calcularEfectivo));
  }

  const form = document.getElementById("movimientoCajaForm");
  if (!form) return;
  const valor = document.getElementById("movimientoValor");
  form.addEventListener("submit", (evento) => {
    if (Number.parseInt(window.soloDigitos(valor.value), 10) > 0) return;
    evento.preventDefault();
    valor.setCustomValidity("El valor debe ser mayor a $0.");
    valor.reportValidity();
  });
  valor.addEventListener("input", () => valor.setCustomValidity(""));
  const botonGuardar = document.getElementById("guardarMovimientoCaja");
  const opciones = [...document.querySelectorAll("[data-movement-type]")];
  opciones.forEach((opcion) => {
    opcion.addEventListener("click", () => {
      const tipo = opcion.dataset.movementType;
      opciones.forEach((elemento) => elemento.classList.toggle("active", elemento === opcion));
      form.action = "/caja/movimientos/" + tipo;
      botonGuardar.classList.toggle("red", tipo === "salida");
      botonGuardar.classList.toggle("green", tipo === "ingreso");
      botonGuardar.innerHTML = '<i class="ri-save-line"></i> Guardar ' + (tipo === "salida" ? "salida" : "entrada");
    });
  });
})();
