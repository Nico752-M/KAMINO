(function () {
  "use strict";
  const modal = document.getElementById("matriculaModal");
  const abrir = document.getElementById("btnNuevaMatricula");
  if (!modal || !abrir) return;

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
