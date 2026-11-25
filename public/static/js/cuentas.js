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
  const mesTexto = (m) => { const [y, n] = m.split("-"); const nombre = MESES[Number(n) - 1]; return nombre[0].toUpperCase() + nombre.slice(1) + " de " + y; };

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
    `<div class="mc-fila${conBotones && f.id ? " con-btns" : ""}"><span class="mc-fila-nombre"><strong>${esc(f.nombre)}</strong><small>${conBotones ? `<span class="mc-tag ${f.id ? "fija" : "caja"}">${f.tag || (f.id ? "Cuenta fija" : "Caja")}</span>` : ""}${esc(f.sub)}</small></span>`
    + `<span class="mc-fila-valor">${fmt(f.valor)}</span>`
    + (conBotones && f.id ? `<span class="mc-fila-btns"><button type="button" class="btn-action" data-editar="${f.id}">Cambiar</button><button type="button" class="btn-action red" data-borrar="${f.id}">Quitar</button></span>` : "")
    + `</div>`;

  function pintar() {
    const r = estado.datos; if (!r) return;
    $("mesNombre").textContent = mesTexto(r.mes);
    $("mesSig").disabled = r.mes >= mesDe(new Date());
    const bien = r.quedo >= 0;
    $("mcTres").innerHTML =
      `<div class="mc-numero entro"><span>Entró</span><strong>${fmt(r.entro)}</strong></div>`
      + `<div class="mc-numero salio"><span>Salió</span><strong>${fmt(r.salio)}</strong></div>`
      + `<div class="mc-numero ${bien ? "bien" : "mal"}"><span>Te queda</span><strong>${bien ? "" : "− "}${fmt(Math.abs(r.quedo))}</strong></div>`;
    const total = (texto, valor) => `<div class="mc-total"><span>${texto}</span><strong>${fmt(valor)}</strong></div>`;
    $("mcEntradas").innerHTML = r.entradas.length
      ? r.entradas.map((f) => fila(f, false)).join("") + total("Total que entró", r.entro)
      : `<p class="mc-hint">En este mes no entró plata por pagos ni por la caja.</p>`;
    const hayFijas = r.gastos.some((f) => f.id);
    $("mcGastos").innerHTML = r.gastos.map((f) => fila(f, true)).join("")
      + (r.gastos.length ? total("Total que salió", r.salio) : "")
      + (hayFijas ? "" : `<p class="mc-hint">Todavía no has anotado cuentas fijas. Toca el botón verde para agregar la primera, por ejemplo el arriendo.</p>`);
    pintarVeh(r);
  }

  // ── Gastos de vehículos ──
  let vhTipo = null;
  const hoyIso = () => { const d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); };
  const fila2 = (a, b) => `<div class="mc-veh-fila"><span>${a}</span><span>${b}</span></div>`;

  function pintarVeh(r) {
    const lista = r.vehiculos || [];
    $("mcVeh").innerHTML = lista.length
      ? lista.map((v) => `<div class="mc-veh-tarjeta"><div class="mc-veh-cab"><strong>${esc(v.vehiculo)}</strong><span>${fmt(v.total)}</span></div>`
          + v.tipos.map((t) => fila2(esc(t.tipo), fmt(t.valor))).join("") + `</div>`).join("")
      : `<p class="mc-hint">En este mes no hay gastos de vehículos. Toca el botón verde para anotar el primero.</p>`;
    const sem = r.semanas || [];
    $("mcSemanas").innerHTML = sem.length
      ? `<h3 class="mc-veh-sub">Por semana</h3>` + sem.map((s) => fila2(esc(s.nombre), fmt(s.valor))).join("") : "";
    const movs = r.movimientos_veh || [];
    $("mcVehLista").innerHTML = movs.length ? movs.map((m) =>
      `<div class="mc-veh-mov"><span><strong>${esc(m.vehiculo)} · ${esc(m.tipo)}</strong><small>${m.fecha.slice(8, 10)}/${m.fecha.slice(5, 7)}${m.nota ? " · " + esc(m.nota) : ""}</small></span>`
      + `<span class="mc-fila-valor">${fmt(m.valor)}</span><button type="button" class="btn-action red" data-vdel="${m.id}">Quitar</button></div>`).join("")
      : `<p class="mc-hint">Sin gastos este mes.</p>`;
  }

  function marcarTipo(t) {
    vhTipo = t;
    document.querySelectorAll("#vhTipos [data-tipo]").forEach((b) => b.classList.toggle("on", b.dataset.tipo === t));
  }
  function abrirVeh() {
    $("vhVehiculo").value = ""; marcarTipo(null); $("vhValor").value = ""; $("vhNota").value = "";
    $("vhFecha").value = hoyIso(); $("vhFecha").max = hoyIso(); $("vhError").style.display = "none";
    $("vhChips").innerHTML = ((estado.datos && estado.datos.nombres_vehiculos) || []).map((n) =>
      `<button type="button" class="mc-chip" data-vchip="${esc(n)}">${esc(n)}</button>`).join("");
    $("mVeh").classList.add("on"); $("vhVehiculo").focus();
  }
  async function guardarVeh() {
    $("vhError").style.display = "none";
    const r = await conCarga(() => api("/cuentas/api/vehiculos", {
      vehiculo: $("vhVehiculo").value, tipo: vhTipo, valor: digitos($("vhValor").value),
      fecha: $("vhFecha").value, nota: $("vhNota").value }));
    if (!r.ok) { $("vhError").textContent = r.error; $("vhError").style.display = "block"; return; }
    $("mVeh").classList.remove("on"); cargar();
  }
  async function borrarVeh(id) {
    if (!window.confirm("¿Quitar este gasto de vehículo?")) return;
    const r = await conCarga(() => api(`/cuentas/api/vehiculos/${id}/borrar`, {}));
    if (!r.ok) return aviso(r.error);
    cargar();
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

  $("vhAgregar").addEventListener("click", abrirVeh);
  $("vhGuardar").addEventListener("click", guardarVeh);
  $("vhValor").addEventListener("input", (e) => { const v = digitos(e.target.value); e.target.value = v ? miles(v) : ""; });
  $("mVeh").addEventListener("click", (e) => { if (e.target === $("mVeh") || e.target.closest("[data-cerrar]")) $("mVeh").classList.remove("on"); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("mVeh").classList.remove("on"); });
  document.addEventListener("click", (e) => {
    const t = e.target.closest("button"); if (!t) return;
    if (t.dataset.vchip) $("vhVehiculo").value = t.dataset.vchip;
    else if (t.dataset.tipo) marcarTipo(t.dataset.tipo);
    else if (t.dataset.vdel) borrarVeh(t.dataset.vdel);
  });

  cargar();
})();
