/* Modal "Registrar Pago / Abono" */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const modal = $("paymentModal");
  if (!modal) return;

  const fmt = (n) => "$ " + Math.round(n).toLocaleString("es-CO");
  const soloDigitos = (s) => parseInt(window.soloDigitos(s), 10) || 0;

  let ctx = { matricula: 0, saldo: 0, guardando: false, costos: [], editado: false };

  function abrir(btn) {
    ctx = { btn, matricula: btn.dataset.matricula, saldo: Number(btn.dataset.saldo) || 0, guardando: false, costos: [], editado: false };
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
    if ($("distribDetalle")) {
      $("distribDetalle").style.display = "none";
      $("btnEditarReparto").textContent = "Cambiar";
    }
    cambioMetodo();
    recalcular();
    cargarDistribucion();
    modal.classList.add("open");
    $("inputAmount").focus();
    $("inputAmount").select();
  }

  function cerrar() {
    modal.classList.remove("open");
  }

  // Actualiza la fila del alumno sin recargar la página
  function actualizarFila(saldo) {
    const celdas = ctx.btn.closest("tr").children;
    const valor = celdas[3].querySelector("strong");
    valor.textContent = fmt(saldo);
    valor.style.color = saldo > 0 ? "var(--accent-red)" : "var(--accent-green)";
    const estado = celdas[4].querySelector(".badge-status");
    if (saldo > 0) {
      ctx.btn.dataset.saldo = saldo;
      if (estado.textContent.trim() === "Activo") {
        estado.textContent = "Pendiente Pago";
        estado.className = "badge-status pending";
      }
    } else {
      ctx.btn.remove();
      estado.textContent = "Pagado";
      estado.className = "badge-status paid";
    }
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
    if (!ctx.editado) sugerirReparto(); else actualizarPendiente();
  }

  // ── Reparto del pago entre costos y ganancia ──
  const campoReparto = (clave) => document.querySelector('[data-reparto="' + clave + '"]');

  async function cargarDistribucion() {
    const caja = $("distribSection");
    if (!caja) return;
    caja.style.display = "none";
    const matricula = ctx.matricula;
    let datos;
    try {
      const resp = await fetch("/pagos/distribucion/" + encodeURIComponent(matricula), { credentials: "same-origin" });
      datos = await resp.json();
      if (!resp.ok || datos.ok === false) return;
    } catch (e) { return; }
    if (matricula !== ctx.matricula) return;   // se cerró o se abrió otro alumno
    const todos = datos.costos || [];
    if (!todos.length) return;   // sin costos no hay nada que repartir
    ctx.costos = todos.filter((c) => c.restante > 0);   // solo los que aún faltan
    const filas = ctx.costos.map((c) =>
      '<div class="distrib-row"><div><strong>' + escapar(c.concepto) + '</strong>' +
      '<small>Costo ' + fmt(c.valor) + ' · cubierto ' + fmt(c.asignado) + ' · falta ' + fmt(c.restante) + '</small></div>' +
      '<input class="input-clean" type="text" inputmode="numeric" autocomplete="off" data-money-input ' +
      'data-reparto="' + c.id + '" data-restante="' + c.restante + '" placeholder="0"></div>'
    );
    filas.push('<div class="distrib-row"><div><strong>Ganancia</strong><small>Automática: lo que sobra después de los costos</small></div>' +
      '<input class="input-clean" type="text" autocomplete="off" readonly tabindex="-1" ' +
      'data-reparto="ganancia" placeholder="0" style="opacity:.85"></div>');
    $("distribFilas").innerHTML = filas.join("");
    $("distribFilas").querySelectorAll("input:not([readonly])").forEach((inp) => inp.addEventListener("input", () => {
      window.formatearCampoMoneda(inp);
      ctx.editado = true;
      actualizarPendiente();
    }));
    caja.style.display = "block";
    sugerirReparto();
  }

  function escapar(t) {
    const d = document.createElement("div");
    d.textContent = t == null ? "" : String(t);
    return d.innerHTML;
  }

  // Primero cubre los costos que faltan; lo que sobra queda como ganancia.
  function sugerirReparto() {
    if (!$("distribSection") || !ctx.costos.length && !campoReparto("ganancia")) return;
    let resto = soloDigitos($("inputAmount").value);
    ctx.costos.forEach((c) => {
      const campo = campoReparto(c.id);
      if (!campo) return;
      const parte = Math.min(c.restante, resto);
      campo.value = parte ? window.formatearMiles(parte) : "";
      resto -= parte;
    });
    actualizarPendiente();
  }

  function leerReparto() {
    const partes = [];
    document.querySelectorAll("#distribFilas [data-reparto]").forEach((inp) => {
      const valor = soloDigitos(inp.value);
      if (valor > 0) partes.push({ costo_id: inp.dataset.reparto === "ganancia" ? null : Number(inp.dataset.reparto), valor });
    });
    return partes;
  }

  // Suma de lo asignado a costos (todo menos la ganancia, que es automática).
  function sumaCostos() {
    let total = 0;
    document.querySelectorAll("#distribFilas [data-reparto]:not([data-reparto='ganancia'])").forEach((inp) => {
      total += soloDigitos(inp.value);
    });
    return total;
  }

  // La ganancia es lo que sobra del pago después de los costos. Devuelve lo que
  // falta por cuadrar: 0 si todo bien, negativo si los costos superan el pago.
  function actualizarPendiente() {
    const caja = $("distribSection");
    if (!caja) return 0;
    const abono = soloDigitos($("inputAmount").value);
    const costos = sumaCostos();
    const ganancia = Math.max(abono - costos, 0);
    const g = campoReparto("ganancia");
    if (g) g.value = ganancia ? window.formatearMiles(ganancia) : "";
    const pendiente = abono - costos - ganancia;   // 0, o negativo si los costos se pasan
    const resumen = $("distribResumen");
    if (resumen) resumen.textContent = "Costos " + fmt(costos) + " · Ganancia " + fmt(ganancia);
    $("distribPendiente").textContent = fmt(pendiente);
    $("distribPendiente").parentElement.className = "distrib-total " + (pendiente === 0 ? "ok" : "falta");
    return pendiente;
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

    const hayReparto = $("distribSection") && $("distribSection").style.display !== "none";
    if (hayReparto && actualizarPendiente() !== 0)
      return error("Los costos asignados superan el valor del pago (" + fmt(valor) + "). Ajusta los valores.");
    const reparto = hayReparto ? leerReparto() : [];
    for (const p of reparto) {
      const campo = p.costo_id === null ? null : campoReparto(p.costo_id);
      if (campo && p.valor > Number(campo.dataset.restante))
        return error("Un costo recibe más de lo que le falta. Ajusta el reparto.");
    }

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
      distribucion: reparto,
    });

    ctx.guardando = false;
    if (!r.ok) {
      $("btnGuardarPago").disabled = false;
      return error(r.error || "No se pudo guardar el pago.");
    }

    actualizarFila(r.saldo);
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
  $("btnTerminar").addEventListener("click", cerrar);
  $("btnGuardarPago").addEventListener("click", guardar);
  if ($("btnEditarReparto")) $("btnEditarReparto").addEventListener("click", () => {
    const detalle = $("distribDetalle");
    const mostrar = detalle.style.display === "none";
    detalle.style.display = mostrar ? "block" : "none";
    $("btnEditarReparto").textContent = mostrar ? "Volver a automático" : "Cambiar";
    if (!mostrar) { ctx.editado = false; sugerirReparto(); }
  });
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
