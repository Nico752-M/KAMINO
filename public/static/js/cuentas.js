/* Mis cuentas (CEA): selector de mes, tres totales y cuentas fijas. Los datos los pide al servidor. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const fmt = (n) => "$ " + Math.round(n).toLocaleString("es-CO");
  const digitos = (s) => parseInt(String(s || "").replace(/\D/g, ""), 10) || 0;
  const miles = (n) => (n ? Math.round(n).toLocaleString("es-CO") : "");
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  const mesDe = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
  const mesTexto = (m) => { const [y, n] = m.split("-"); return MESES[Number(n) - 1] + " de " + y; };

  const estado = { mes: null, datos: null };

  async function api(url, cuerpo) {
    const opciones = cuerpo === undefined
      ? { credentials: "same-origin" }
      : { method: "POST", credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]').content },
          body: JSON.stringify(cuerpo) };
    try {
      const r = await fetch(url, opciones);
      if (r.status === 401 || r.redirected) { window.location.href = "/login"; return { ok: false, error: "Tu sesión expiró." }; }
      const d = await r.json().catch(() => ({}));
      if (d.ok === undefined) d.ok = r.ok;
      if (!d.ok && !d.error) d.error = "No se pudo completar la operación.";
      return d;
    } catch (e) { return { ok: false, error: "Sin conexión con el servidor. Intenta de nuevo." }; }
  }
  const conCarga = async (fn) => { window.mostrarCarga && window.mostrarCarga(); try { return await fn(); } finally { window.ocultarCarga && window.ocultarCarga(); } };
  function aviso(msg) { const a = $("mcAviso"); a.textContent = msg || ""; a.style.display = msg ? "block" : "none"; }

  function mover(delta) {
    const [y, n] = (estado.mes || mesDe(new Date())).split("-").map(Number);
    estado.mes = mesDe(new Date(y, n - 1 + delta, 1));
    cargar();
  }

  async function cargar() {
    estado.mes = estado.mes || mesDe(new Date());
    const r = await conCarga(() => api("/cuentas/api/mes?mes=" + estado.mes));
    if (!r.ok) { aviso(r.error); return; }
    aviso(""); estado.datos = r; pintar();
  }

  const fila = (f, conBotones) =>
    `<div class="mc-fila"><span class="mc-fila-nombre"><strong>${esc(f.nombre)}</strong><small>${esc(f.sub)}</small></span>`
    + `<span class="mc-fila-valor">${fmt(f.valor)}</span>`
    + (conBotones && f.id ? `<span class="mc-fila-btns"><button type="button" class="btn-action" data-editar="${f.id}">Cambiar</button><button type="button" class="btn-action red" data-borrar="${f.id}">Quitar</button></span>` : "")
    + `</div>`;

  function pintar() {
    const r = estado.datos; if (!r) return;
    $("mesNombre").textContent = mesTexto(r.mes);
    $("mesSig").disabled = r.mes >= mesDe(new Date());
    const bien = r.quedo >= 0;
    $("mcTres").innerHTML =
      `<div class="mc-numero"><span>Entró</span><strong>${fmt(r.entro)}</strong></div>`
      + `<div class="mc-numero"><span>Salió</span><strong>${fmt(r.salio)}</strong></div>`
      + `<div class="mc-numero ${bien ? "bien" : "mal"}"><span>Te queda</span><strong>${bien ? "" : "− "}${fmt(Math.abs(r.quedo))}</strong></div>`;
    $("mcEntradas").innerHTML = r.entradas.length
      ? r.entradas.map((f) => fila(f, false)).join("")
      : `<p class="mc-hint">En este mes no entró plata por pagos ni por la caja.</p>`;
    const hayFijas = r.gastos.some((f) => f.id);
    $("mcGastos").innerHTML = r.gastos.map((f) => fila(f, true)).join("")
      + (hayFijas ? "" : `<p class="mc-hint">Todavía no has anotado cuentas fijas. Toca el botón verde para agregar la primera, por ejemplo el arriendo.</p>`);
  }

  // ── Ventana para agregar o cambiar una cuenta ──
  const abrir = () => $("mCuentas").classList.add("on");
  const cerrar = () => $("mCuentas").classList.remove("on");

  function abrirCuenta(c) {
    $("mCuentasTitulo").textContent = c ? "Cambiar la cuenta" : "Agregar una cuenta";
    $("cuId").value = c ? c.id : "";
    $("cuNombre").value = c ? c.nombre : "";
    const sel = $("cuCat");
    sel.value = c && Array.from(sel.options).some((o) => o.value === c.categoria) ? c.categoria : sel.options[0].value;
    $("cuValor").value = c ? miles(c.valor) : "";
    $("cuError").style.display = "none";
    abrir(); $("cuNombre").focus();
  }

  async function guardar() {
    $("cuError").style.display = "none";
    const r = await conCarga(() => api("/cuentas/api/cuentas", {
      id: $("cuId").value || null, nombre: $("cuNombre").value, categoria: $("cuCat").value, valor: digitos($("cuValor").value),
    }));
    if (!r.ok) { $("cuError").textContent = r.error; $("cuError").style.display = "block"; return; }
    cerrar(); cargar();
  }

  async function borrar(id) {
    if (!window.confirm("¿Quitar esta cuenta? Ya no se contará en los gastos.")) return;
    const r = await conCarga(() => api(`/cuentas/api/cuentas/${id}/borrar`, {}));
    if (!r.ok) return aviso(r.error);
    cargar();
  }

  // ── Eventos ──
  $("mesAnt").addEventListener("click", () => mover(-1));
  $("mesSig").addEventListener("click", () => mover(1));
  $("mcAgregar").addEventListener("click", () => abrirCuenta());
  $("cuGuardar").addEventListener("click", guardar);
  $("cuValor").addEventListener("input", (e) => { const v = digitos(e.target.value); e.target.value = v ? miles(v) : ""; });
  $("mCuentas").addEventListener("click", (e) => { if (e.target === $("mCuentas") || e.target.closest("[data-cerrar]")) cerrar(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrar(); });
  document.addEventListener("click", (e) => {
    const t = e.target.closest("button"); if (!t) return;
    if (t.dataset.editar) abrirCuenta((estado.datos.gastos || []).find((x) => x.id === Number(t.dataset.editar)));
    else if (t.dataset.borrar) borrar(t.dataset.borrar);
  });

  cargar();
})();
