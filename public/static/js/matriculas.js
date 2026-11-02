(function () {
  "use strict";
  const modal = document.getElementById("matriculaModal");
  const abrir = document.getElementById("btnNuevaMatricula");
  if (!modal || !abrir) return;

  const precioBase = document.getElementById("precioBase");
  const descuentoPesos = document.getElementById("descuentoPesos");
  const descuentoPorcentaje = document.getElementById("descuentoPorcentaje");
  const precioTotal = document.getElementById("matriculaPrecio");
  const soloDigitos = (valor) => Number.parseInt(String(valor || "").replace(/\D/g, ""), 10) || 0;

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
    modal.classList.add("open");
    document.getElementById("matriculaDocumento").focus();
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
