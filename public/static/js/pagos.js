/* Modal "Registrar Pago / Abono" */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const modal = $("paymentModal");
  if (!modal) return;

  const fmt = (n) => "$ " + Math.round(n).toLocaleString("es-CO");
  const soloDigitos = (s) => parseInt(window.soloDigitos(s), 10) || 0;

  let ctx = { matricula: 0, saldo: 0, guardando: false };

  function abrir(btn) {
    ctx = { matricula: btn.dataset.matricula, saldo: Number(btn.dataset.saldo) || 0, guardando: false };
    $("modalStudentName").textContent = btn.dataset.nombre;
    $("modalStudentBalance").textContent = fmt(ctx.saldo);
    $("pagoConcepto").value = btn.dataset.concepto || "Pago curso de conducción";
    $("selectPaymentMethod").value = "Efectivo";
    $("inputAmount").value = window.formatearMiles(Math.round(ctx.saldo));
    $("inputReceived").value = "";
    $("pagoNotas").value = "";
    $("pagoAcompanante").value = "";
    $("cashCalculatorBox").classList.remove("open");
    $("pagoError").style.display = "none";
    $("pagoForm").style.display = "flex";
    $("pagoExito").style.display = "none";
    $("btnGuardarPago").disabled = false;
    cambioMetodo();
    recalcular();
    modal.classList.add("open");
    $("inputAmount").focus();
    $("inputAmount").select();
  }

  function cerrar(recargar) {
    modal.classList.remove("open");
    if (recargar) window.location.reload();
  }

  function cambioMetodo() {
    const efectivo = $("selectPaymentMethod").value === "Efectivo";
    $("toggleChangeBtn").style.display = efectivo ? "inline-flex" : "none";
    if (!efectivo) $("cashCalculatorBox").classList.remove("open");
  }

  function recalcular() {
    const abono = soloDigitos($("inputAmount").value);
    const recibido = soloDigitos($("inputReceived").value);
    $("inputAmountFmt").textContent = abono ? fmt(abono) : "";
    $("lblChange").textContent = fmt(recibido > abono ? recibido - abono : 0);
  }

  function error(msg) {
    const e = $("pagoError");
    e.textContent = msg;
    e.style.display = "block";
  }

  async function guardar() {
    if (ctx.guardando) return;
    const valor = soloDigitos($("inputAmount").value);
    if (valor <= 0) return error("Escribe el valor a abonar.");
    if (ctx.saldo > 0 && valor > ctx.saldo)
      return error("El abono no puede superar el saldo pendiente (" + fmt(ctx.saldo) + ").");

    ctx.guardando = true;
    $("btnGuardarPago").disabled = true;
    $("pagoError").style.display = "none";

    const r = await window.postJSON("/pagos/registrar", {
      matricula_id: ctx.matricula,
      valor: valor,
      metodo: $("selectPaymentMethod").value,
      concepto: $("pagoConcepto").value,
      observaciones: $("pagoNotas").value,
      acompanante: $("pagoAcompanante").value,
      recibido: soloDigitos($("inputReceived").value),
    });

    ctx.guardando = false;
    if (!r.ok) {
      $("btnGuardarPago").disabled = false;
      return error(r.error || "No se pudo guardar el pago.");
    }

    $("exitoRecibo").textContent = r.numero_recibo;
    $("exitoSaldo").textContent = fmt(r.saldo);
    $("exitoCambioFila").style.display = r.cambio > 0 ? "block" : "none";
    $("exitoCambio").textContent = fmt(r.cambio);
    $("btnImprimir").href = r.recibo_url;
    $("pagoForm").style.display = "none";
    $("pagoExito").style.display = "flex";
  }

  // Eventos
  document.querySelectorAll(".js-cobrar").forEach((b) => b.addEventListener("click", () => abrir(b)));
  $("btnCerrarModal").addEventListener("click", () => cerrar(false));
  $("btnCancelarPago").addEventListener("click", () => cerrar(false));
  $("btnTerminar").addEventListener("click", () => cerrar(true));
  $("btnGuardarPago").addEventListener("click", guardar);
  $("selectPaymentMethod").addEventListener("change", cambioMetodo);
  $("inputAmount").addEventListener("input", recalcular);
  $("inputReceived").addEventListener("input", recalcular);
  $("toggleChangeBtn").addEventListener("click", () => {
    $("cashCalculatorBox").classList.toggle("open");
    $("inputReceived").focus();
  });
  $("btnCerrarCalc").addEventListener("click", () => {
    $("cashCalculatorBox").classList.remove("open");
    $("inputReceived").value = "";
    recalcular();
  });
})();
