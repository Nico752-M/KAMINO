(function () {
  "use strict";
  const modal = document.getElementById("matriculaModal");
  const abrir = document.getElementById("btnNuevaMatricula");
  if (!modal || !abrir) return;

  const precioBase = document.getElementById("precioBase");
  const descuentoPesos = document.getElementById("descuentoPesos");
  const descuentoPorcentaje = document.getElementById("descuentoPorcentaje");
  const precioTotal = document.getElementById("matriculaPrecio");
  const form = modal.querySelector("form");
  const pasos = [...modal.querySelectorAll("[data-step-pane]")];
  const indicadores = [...modal.querySelectorAll("[data-step-indicator]")];
  const btnAnterior = document.getElementById("btnPasoAnterior");
  const btnSiguiente = document.getElementById("btnPasoSiguiente");
  const btnGuardar = document.getElementById("btnGuardarMatricula");
  let pasoActual = 0;
  form.noValidate = true;
  const soloDigitos = (valor) => Number.parseInt(String(valor || "").replace(/\D/g, ""), 10) || 0;

  function mostrarPaso(indice) {
    pasoActual = indice;
    pasos.forEach((paso, i) => {
      paso.hidden = i !== indice;
      paso.classList.toggle("active", i === indice);
    });
    indicadores.forEach((indicador, i) => {
      indicador.classList.toggle("active", i === indice);
      indicador.classList.toggle("done", i < indice);
    });
    btnAnterior.hidden = indice === 0;
    btnSiguiente.hidden = indice === pasos.length - 1;
    btnGuardar.hidden = indice !== pasos.length - 1;
    pasos[indice].querySelector("input, select, textarea")?.focus({ preventScroll: true });
    pasos[indice].scrollIntoView({ block: "nearest" });
  }

  function validarPaso() {
    const campos = [...pasos[pasoActual].querySelectorAll("input, select, textarea")]
      .filter((campo) => campo.willValidate);
    for (const campo of campos) {
      if (!campo.checkValidity()) {
        campo.reportValidity();
        return false;
      }
    }
    return true;
  }

  function calcularTotal() {
    const base = soloDigitos(precioBase.value);
    const pesos = soloDigitos(descuentoPesos.value);
    const porcentaje = Number(descuentoPorcentaje.value) || 0;
    const descuento = pesos || Math.round(base * porcentaje / 100);
    precioTotal.value = base ? Math.max(base - descuento, 0) : "";
  }

  precioBase.addEventListener("input", calcularTotal);
  descuentoPesos.addEventListener("input", () => {
    if (descuentoPesos.value) descuentoPorcentaje.value = "";
    calcularTotal();
  });
  descuentoPorcentaje.addEventListener("input", () => {
    if (descuentoPorcentaje.value) descuentoPesos.value = "";
    calcularTotal();
  });
  precioTotal.addEventListener("input", () => {
    const base = soloDigitos(precioBase.value);
    const total = soloDigitos(precioTotal.value);
    descuentoPesos.value = base && total <= base ? base - total : "";
    descuentoPorcentaje.value = "";
  });

  const cerrar = () => modal.classList.remove("open");
  abrir.addEventListener("click", () => {
    form.reset();
    descuentoPesos.value = "";
    descuentoPorcentaje.value = "";
    mostrarPaso(0);
    modal.classList.add("open");
    document.getElementById("matriculaDocumento").focus();
  });
  btnSiguiente.addEventListener("click", () => {
    if (validarPaso()) mostrarPaso(Math.min(pasoActual + 1, pasos.length - 1));
  });
  btnAnterior.addEventListener("click", () => mostrarPaso(Math.max(pasoActual - 1, 0)));
  form.addEventListener("submit", (evento) => {
    if (!validarPaso()) evento.preventDefault();
  });
  document.getElementById("btnCerrarMatricula").addEventListener("click", cerrar);
  document.getElementById("btnCancelarMatricula").addEventListener("click", cerrar);
  modal.addEventListener("click", (evento) => {
    if (evento.target === modal) cerrar();
  });
  document.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape") cerrar();
  });
})();
