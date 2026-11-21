/* Tienda: caja + inventario que se descuenta solo + ganancia neta a tu manera.
   Los datos viven en Oracle (esquema de la tienda); aquí solo se muestran y se piden al servidor. */
const TiendaCalculo = (function () {
  "use strict";
  const fmt = (n) => "$ " + Math.round(n).toLocaleString("es-CO");

  // Ganancia neta según lo que el usuario decida descontar (datos = respuesta de /api/ganancias)
  function calcular(datos, a) {
    const dias = datos.dias;
    const sum = (campo) => datos.porDia.reduce((s, d) => s + d[campo], 0);
    const bruto = sum("ventas"), costo = sum("costo"), noEfectivo = sum("noEfectivo"), numVentas = sum("n");
    const gastosCaja = sum("gastos"), mermas = sum("mermas");
    const gananciaBruta = bruto - costo;
    const comision = a.usarComision ? noEfectivo * a.comision / 100 : 0;
    const impuesto = a.usarImpuesto ? bruto * a.impuesto / 100 : 0;
    const gastos = a.usarGastos ? a.gastosMes / 30 * dias : 0;
    const neta = gananciaBruta - comision - impuesto - gastos - gastosCaja - mermas;
    const reserva = a.usarReserva ? Math.max(neta, 0) * a.reserva / 100 : 0;
    const porDia = datos.porDia.map((d) => ({
      fecha: d.fecha, ventas: d.ventas,
      neta: d.ventas - d.costo - (a.usarComision ? d.noEfectivo * a.comision / 100 : 0)
            - (a.usarImpuesto ? d.ventas * a.impuesto / 100 : 0) - (a.usarGastos ? a.gastosMes / 30 : 0)
            - d.gastos - d.mermas,
    }));
    return { dias, numVentas, bruto, costo, gananciaBruta, comision, impuesto, gastos, gastosCaja, mermas, neta, reserva,
             disponible: neta - reserva, margen: bruto ? neta / bruto * 100 : 0, porDia, top: datos.top };
  }
  function estadoStock(p) { return p.stock <= 0 ? "agotado" : p.stock <= p.minimo ? "bajo" : "ok"; }
  return { fmt, calcular, estadoStock };
})();

if (typeof module !== "undefined") module.exports = TiendaCalculo;

/* ═════════════ Interfaz ═════════════ */
if (typeof document !== "undefined") (function () {
  "use strict";
  const K = TiendaCalculo;
  const $ = (id) => document.getElementById(id);
  const fmt = K.fmt;
  const digitos = (s) => parseInt(String(s || "").replace(/\D/g, ""), 10) || 0;
  const miles = (n) => (n ? Math.round(n).toLocaleString("es-CO") : "");
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (inp) => inp.addEventListener("input", () => { const v = digitos(inp.value); inp.value = v ? miles(v) : ""; });

  const estado = { productos: [], ajustes: {}, ventas: [], ganancias: null, ganCache: {}, abierta: false };
  const ui = { vista: "caja", cat: "Todos", q: "", carrito: {}, periodo: "30", enviando: false };

  // ── Comunicación con el servidor ──
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
  function aviso(msg) { const a = $("tAviso"); a.textContent = msg || ""; a.style.display = msg ? "block" : "none"; }

  // ── Navegación entre vistas ──
  const VISTAS = ["caja", "inventario", "ventas", "ganancias"];
  async function irA(vista) {
    if (!VISTAS.includes(vista)) vista = "caja";
    ui.vista = vista;
    VISTAS.forEach((v) => { $("vista-" + v).hidden = v !== vista; });
    document.querySelectorAll("[data-vista]").forEach((a) => a.classList.toggle("active", a.dataset.vista === vista));
    document.body.classList.remove("sidebar-open");
    if (vista === "caja") { await cargarCierre(); renderCaja(); }
    if (vista === "inventario") { renderInventario(); cargarMermas(); }
    if (vista === "ventas") await cargarVentas();
    if (vista === "ganancias") await cargarGanancias();
  }
  window.addEventListener("hashchange", () => irA(location.hash.replace("#", "")));

  // ── CAJA ──
  const categorias = () => ["Todos", ...Array.from(new Set(estado.productos.map((p) => p.cat))).sort()];

  function renderCaja() {
    $("tCajaCerrada").hidden = estado.abierta;
    $("tChips").innerHTML = categorias().length > 2 ? categorias().map((c) =>
      `<button type="button" class="t-chip ${c === ui.cat ? "on" : ""}" data-cat="${esc(c)}">${esc(c)}</button>`).join("") : "";
    const q = ui.q.trim().toLowerCase();
    const lista = estado.productos.filter((p) => (ui.cat === "Todos" || p.cat === ui.cat) && (!q || p.nombre.toLowerCase().includes(q)));
    if (!estado.productos.length) {
      $("tGrid").innerHTML = `<div class="t-vacio-grande"><i class="ri-store-2-line"></i><strong>Aún no tienes productos</strong>
        <p>Agrega el primero en Inventario y aparecerá aquí para vender.</p>
        <a class="btn-action green" href="#inventario"><i class="ri-add-line"></i> Ir a Inventario</a></div>`;
    } else {
      $("tGrid").innerHTML = lista.length ? lista.map((p) => {
        const est = K.estadoStock(p), enCarrito = ui.carrito[p.id] || 0, quedan = p.stock - enCarrito;
        const etiqueta = est === "agotado" ? "Agotado" : (est === "bajo" ? `¡Quedan ${quedan}!` : `Quedan ${quedan}`);
        return `<button type="button" class="t-prod" data-add="${p.id}" ${quedan <= 0 || !estado.abierta ? "disabled" : ""}>
          <strong>${esc(p.nombre)}</strong><span class="precio">${fmt(p.precio)}</span>
          <small class="${est !== "ok" ? "bajo" : ""}">${etiqueta}</small></button>`;
      }).join("") : `<p class="t-vacio" style="grid-column:1/-1">No hay productos con ese filtro.</p>`;
    }
    renderCarrito(); badgeBajo();
  }

  function renderCarrito() {
    const ids = Object.keys(ui.carrito).filter((id) => ui.carrito[id] > 0);
    let total = 0;
    $("tLineas").innerHTML = ids.length ? ids.map((id) => {
      const p = estado.productos.find((x) => x.id === Number(id));
      if (!p) return "";
      const cant = ui.carrito[id]; total += cant * p.precio;
      return `<div class="t-linea"><strong>${esc(p.nombre)}</strong><span class="sub">${fmt(cant * p.precio)}</span>
        <div class="t-cant"><button type="button" data-menos="${id}" aria-label="Quitar uno">−</button><span>${cant}</span>
        <button type="button" data-mas="${id}" aria-label="Agregar uno">+</button></div><span></span></div>`;
    }).join("") : `<p class="t-vacio">Aún no hay productos en la venta.</p>`;
    const dv = digitos($("tDescVal").value);
    const desc = $("tDescTipo").value === "pct" ? Math.round(total * Math.min(dv, 100) / 100) : dv;
    const descMal = desc > 0 && desc >= total;
    $("tDescHint").textContent = descMal ? "El descuento debe ser menor que el total."
      : (desc ? `Subtotal ${fmt(total)} − descuento ${fmt(desc)}` : "");
    const neto = descMal ? total : total - desc;
    $("tTotal").textContent = fmt(neto);
    const efectivo = $("tMetodo").value === "Efectivo";
    const rec = digitos($("tRecibido").value);
    $("tCobrar").disabled = !estado.abierta || !ids.length || ui.enviando || descMal || (efectivo && rec <= 0);
    $("tCampoRecibido").style.display = efectivo ? "" : "none";
    $("tCampoResto").style.display = efectivo && rec > 0 && rec < neto ? "" : "none";
    $("tDevuelta").textContent = efectivo && rec ? (rec >= neto ? `Devuelta: ${fmt(rec - neto)}` : `Resto por cobrar: ${fmt(neto - rec)}`) : "";
    $("tError").style.display = "none";
  }

  function agregar(id) {
    const p = estado.productos.find((x) => x.id === Number(id));
    if (!estado.abierta || !p || (ui.carrito[id] || 0) + 1 > p.stock) return;
    ui.carrito[id] = (ui.carrito[id] || 0) + 1; renderCaja();
  }
  function quitar(id) {
    if (!ui.carrito[id]) return;
    ui.carrito[id]--; if (ui.carrito[id] <= 0) delete ui.carrito[id]; renderCaja();
  }

  async function cobrar() {
    if (ui.enviando) return;
    const items = Object.entries(ui.carrito).map(([id, cant]) => ({ id: Number(id), cant }));
    ui.enviando = true; $("tCobrar").disabled = true;
    const r = await api("/tienda/api/ventas", { items, metodo: $("tMetodo").value, recibido: digitos($("tRecibido").value), resto: $("tResto").value,
      descuento: { tipo: $("tDescTipo").value, valor: digitos($("tDescVal").value) } });
    ui.enviando = false;
    if (!r.ok) { $("tError").textContent = r.error; $("tError").style.display = "block"; $("tCobrar").disabled = false; await recargarProductos(); return; }
    r.stocks.forEach((s) => { const p = estado.productos.find((x) => x.id === s.id); if (p) p.stock = s.stock; });
    $("vResumen").innerHTML = r.venta.items.map((i) => `<div><span>${i.cant} × ${esc(i.nombre)}</span><strong>${fmt(i.cant * i.precio)}</strong></div>`).join("")
      + (r.venta.descuento ? `<div><span>Descuento</span><strong>− ${fmt(r.venta.descuento)}</strong></div>` : "")
      + `<div><span>Total (${esc(r.venta.metodo)}) · venta #${r.venta.id}</span><strong>${fmt(r.venta.total)}</strong></div>`
      + (r.venta.monto2 ? `<div><span>Resto con ${esc(r.venta.metodo2)}</span><strong>${fmt(r.venta.monto2)}</strong></div>` : "")
      + (r.devuelta ? `<div><span>Devuelta</span><strong>${fmt(r.devuelta)}</strong></div>` : "");
    $("vAvisos").innerHTML = r.bajos.map((b) =>
      `<div class="t-aviso"><i class="ri-alert-line"></i> ${b.stock <= 0 ? "Se agotó" : "Queda poco de"} «${esc(b.nombre)}»${b.stock > 0 ? ` (${b.stock})` : ""}.</div>`).join("");
    ui.carrito = {}; $("tRecibido").value = ""; $("tDescVal").value = "";
    $("vTicket").href = "/tienda/pdf/venta/" + r.venta.id;
    abrirModal("mVenta"); renderCaja();
  }

  async function recargarProductos() {
    const r = await api("/tienda/api/estado");
    if (r.ok) { estado.productos = r.productos; estado.ajustes = r.ajustes; estado.abierta = r.abierta; for (const id of Object.keys(ui.carrito)) if (!estado.productos.some((p) => p.id === Number(id))) delete ui.carrito[id]; renderCaja(); }
  }

  // ── INVENTARIO ──
  function badgeBajo() {
    const n = estado.productos.filter((p) => K.estadoStock(p) !== "ok").length;
    const b = $("badgeBajo"); b.hidden = !n; b.textContent = n;
  }

  function renderInventario() {
    const ps = estado.productos;
    const valor = ps.reduce((a, p) => a + p.stock * p.costo, 0);
    const bajos = ps.filter((p) => K.estadoStock(p) === "bajo").length, agot = ps.filter((p) => K.estadoStock(p) === "agotado").length;
    $("tStatsInv").innerHTML =
      `<div class="stat-card gold"><span>Productos</span><strong>${ps.length}</strong></div>
       <div class="stat-card green"><span>Valor del inventario</span><strong>${fmt(valor)}</strong><small>a precio de costo</small></div>
       <div class="stat-card gold"><span>Stock bajo</span><strong>${bajos}</strong></div>
       <div class="stat-card red"><span>Agotados</span><strong>${agot}</strong></div>`;
    $("tTabla").querySelector("tbody").innerHTML = ps.length ? ps.map((p) => {
      const est = K.estadoStock(p), margen = p.precio ? (p.precio - p.costo) / p.precio * 100 : 0;
      const badge = est === "agotado" ? `<span class="badge-status urgent">Agotado</span>` : est === "bajo" ? `<span class="badge-status pending">Stock bajo</span>` : `<span class="badge-status active">Disponible</span>`;
      return `<tr><td><strong>${esc(p.nombre)}</strong></td><td>${esc(p.cat)}</td><td>${fmt(p.costo)}</td><td>${fmt(p.precio)}</td>
        <td>${margen.toFixed(0)} %</td><td><strong>${p.stock}</strong></td><td>${badge}</td>
        <td><div class="t-acciones"><button type="button" class="t-mas" data-reab="${p.id}"><i class="ri-add-line"></i> Reabastecer</button>
        <button type="button" data-edit="${p.id}"><i class="ri-edit-line"></i> Editar</button>
        <button type="button" data-hist="${p.id}"><i class="ri-history-line"></i> Historial</button>
        <button type="button" data-baja="${p.id}"><i class="ri-delete-bin-line"></i> Baja</button></div></td></tr>`;
    }).join("") : `<tr><td colspan="8"><div class="t-vacio-grande"><i class="ri-archive-line"></i><strong>Tu inventario está vacío</strong><p>Agrega tu primer producto con «Nuevo producto».</p></div></td></tr>`;
    badgeBajo();
  }

  // ── Modales ──
  const abrirModal = (id) => $(id).classList.add("on");
  const cerrarModales = () => document.querySelectorAll(".t-modal.on").forEach((m) => m.classList.remove("on"));
  const errorEn = (id, m) => { $(id).textContent = m; $(id).style.display = "block"; };

  function abrirProducto(id) {
    const p = id ? estado.productos.find((x) => x.id === Number(id)) : null;
    $("mProductoTitulo").textContent = p ? "Editar producto" : "Nuevo producto";
    $("pId").value = p ? p.id : "";
    $("pNombre").value = p ? p.nombre : ""; $("pCat").value = p ? p.cat : "";
    $("pCosto").value = p ? miles(p.costo) : ""; $("pPrecio").value = p ? miles(p.precio) : "";
    $("pStock").value = p ? String(p.stock) : ""; $("pMin").value = p ? String(p.minimo) : "5";
    $("tCats").innerHTML = categorias().filter((c) => c !== "Todos").map((c) => `<option value="${esc(c)}">`).join("");
    $("pError").style.display = "none"; abrirModal("mProducto"); $("pNombre").focus();
  }

  async function guardarProducto() {
    const cuerpo = { id: Number($("pId").value) || null, nombre: $("pNombre").value, categoria: $("pCat").value,
      costo: digitos($("pCosto").value), precio: digitos($("pPrecio").value), stock: digitos($("pStock").value), minimo: digitos($("pMin").value) };
    if (!cuerpo.nombre.trim()) return errorEn("pError", "Escribe el nombre del producto.");
    if (cuerpo.precio <= 0) return errorEn("pError", "Escribe el precio de venta.");
    if (cuerpo.costo > cuerpo.precio) return errorEn("pError", "El costo es mayor que el precio: venderías con pérdida.");
    const r = await conCarga(() => api("/tienda/api/productos", cuerpo));
    if (!r.ok) return errorEn("pError", r.error);
    estado.productos = r.productos; cerrarModales(); renderInventario(); if (ui.vista === "caja") renderCaja();
  }

  function abrirReabastecer(id) {
    const p = estado.productos.find((x) => x.id === Number(id));
    $("rId").value = p.id; $("rNombre").textContent = `${p.nombre} · hoy hay ${p.stock}`;
    $("rCant").value = ""; $("rError").style.display = "none"; abrirModal("mReabastecer"); $("rCant").focus();
  }
  async function guardarReabastecer() {
    const cant = digitos($("rCant").value);
    if (cant <= 0) return errorEn("rError", "Escribe cuántas unidades llegaron.");
    const r = await conCarga(() => api(`/tienda/api/productos/${$("rId").value}/entrada`, { cantidad: cant }));
    if (!r.ok) return errorEn("rError", r.error);
    estado.productos = r.productos; cerrarModales(); renderInventario();
  }

  // ── VENTAS (historial y anulación) ──
  async function cargarVentas() {
    const r = await conCarga(() => api("/tienda/api/ventas"));
    if (!r.ok) { aviso(r.error); return; } aviso("");
    estado.ventas = r.ventas; renderVentas(); cargarCierre();
  }

  // ── Cierre de caja y movimientos del producto ──
  const hora = (iso) => new Date(iso).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" });
  const ETIQ = { BASE: "Base", INGRESO: "Entrada", EGRESO: "Salida" };
  function pintarCierre(r) {
    estado.abierta = r.abierta;
    $("cAbrir").hidden = r.abierta;
    $("cAbierta").hidden = !r.abierta;
    const card = (t, v, c) => `<div class="stat-card ${c || ""}"><span>${t}</span><strong>${fmt(v)}</strong></div>`;
    $("cResumen").innerHTML = card("Base", r.base) + card("Ventas en efectivo", r.efectivo, "green")
      + card("Entradas", r.ingresos) + card("Salidas", r.egresos, "red") + card("Efectivo esperado", r.esperado, "gold");
    $("cMovs").innerHTML = r.movs.map((m) => `<div class="t-mov-fila"><span>${hora(m.fecha)} · <strong>${ETIQ[m.tipo]}</strong> ${fmt(m.monto)} · ${esc(m.motivo)}${m.gasto ? " <small>(gasto)</small>" : ""} · ${esc(m.usuario)}</span>
      <button type="button" class="t-link" data-qmov="${m.id}">Quitar</button></div>`).join("");
    $("cLista").innerHTML = r.cierres.map((c) =>
      `<div>${hora(c.fecha)} · esperado ${fmt(c.esperado)} · contado ${fmt(c.contado)} · <strong style="color:${c.diferencia === 0 ? "var(--accent-green)" : "var(--accent-red)"}">dif. ${fmt(c.diferencia)}</strong> · ${esc(c.usuario)}</div>`).join("");
  }
  function abrirMov(tipo) {
    $("mvTipo").value = tipo;
    $("mMovTitulo").textContent = tipo === "BASE" ? "Base de caja" : tipo === "INGRESO" ? "Entrada de dinero" : "Salida de dinero";
    $("mvMonto").value = ""; $("mvMotivo").value = tipo === "BASE" ? "Base inicial" : "";
    $("mvGastoFila").style.display = tipo === "EGRESO" ? "" : "none"; $("mvGasto").checked = true;
    $("mvError").style.display = "none"; abrirModal("mMov"); $("mvMonto").focus();
  }
  async function guardarMov() {
    const monto = digitos($("mvMonto").value);
    if (monto <= 0) return errorEn("mvError", "Escribe el valor.");
    const r = await conCarga(() => api("/tienda/api/caja/mov", { tipo: $("mvTipo").value, monto, motivo: $("mvMotivo").value, gasto: $("mvGasto").checked }));
    if (!r.ok) return errorEn("mvError", r.error);
    estado.ganCache = {}; cerrarModales(); pintarCierre(r);
  }
  async function quitarMov(id) {
    if (!confirm("¿Quitar este movimiento de la caja?")) return;
    const r = await conCarga(() => api(`/tienda/api/caja/mov/${id}/quitar`, {}));
    if (!r.ok) return aviso(r.error);
    estado.ganCache = {}; aviso(""); pintarCierre(r);
  }

  // ── Mermas ──
  function abrirBaja(id) {
    const p = estado.productos.find((x) => x.id === Number(id));
    $("bId").value = p.id; $("bNombre").textContent = `${p.nombre} · hoy hay ${p.stock}`;
    $("bCant").value = ""; $("bNota").value = ""; $("bError").style.display = "none"; abrirModal("mBaja"); $("bCant").focus();
  }
  async function guardarBaja() {
    const cant = digitos($("bCant").value);
    if (cant <= 0) return errorEn("bError", "Escribe cuántas unidades se pierden.");
    const r = await conCarga(() => api(`/tienda/api/productos/${$("bId").value}/baja`, { cantidad: cant, motivo: $("bMotivo").value, nota: $("bNota").value }));
    if (!r.ok) return errorEn("bError", r.error);
    estado.productos = r.productos; estado.ganCache = {}; cerrarModales(); renderInventario(); pintarMermas(r.mermas);
  }
  function pintarMermas(lista) {
    $("tMermas").innerHTML = lista.length ? lista.map((m) => `<div class="${m.anulada ? "t-venta-anulada" : ""}">${hora(m.fecha)} · ${m.cant} × ${esc(m.nombre)} · ${esc(m.motivo)}${m.nota ? " (" + esc(m.nota) + ")" : ""}
      · <strong style="color:var(--accent-red)">− ${fmt(m.cant * m.costo)}</strong>
      ${m.anulada ? "(anulada)" : `<button type="button" class="t-link" data-amerma="${m.id}">Anular</button>`}</div>`).join("")
      : `<p class="t-vacio">Sin bajas registradas.</p>`;
  }
  async function cargarMermas() { const r = await api("/tienda/api/mermas"); if (r.ok) pintarMermas(r.mermas); }
  async function anularMerma(id) {
    if (!confirm("¿Anular esta baja? Las unidades vuelven al stock.")) return;
    const r = await conCarga(() => api(`/tienda/api/mermas/${id}/anular`, {}));
    if (!r.ok) return aviso(r.error);
    estado.productos = r.productos; estado.ganCache = {}; aviso(""); renderInventario(); pintarMermas(r.mermas);
  }

  // ── Reporte por fechas ──
  const isoLocal = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  function enlacesReporte() {
    const q = "?desde=" + $("rDesde").value + "&hasta=" + $("rHasta").value;
    $("rXls").href = "/tienda/excel/reporte" + q; $("rPdf").href = "/tienda/pdf/reporte" + q;
  }
  function fijarRango(k) {
    const fin = new Date(), ini = new Date();
    if (k === "7") ini.setDate(ini.getDate() - 6);
    if (k === "mes") ini.setDate(1);
    $("rDesde").value = isoLocal(ini); $("rHasta").value = isoLocal(fin); enlacesReporte();
  }
  async function cargarCierre() { const r = await api("/tienda/api/cierre"); if (r.ok) pintarCierre(r); }
  async function guardarCierre() {
    if (!$("cContado").value) { $("cError").textContent = "Escribe el efectivo contado."; $("cError").style.display = "block"; return; }
    const r = await conCarga(() => api("/tienda/api/cierre", { contado: digitos($("cContado").value) }));
    $("cError").style.display = r.ok ? "none" : "block";
    if (!r.ok) { $("cError").textContent = r.error; return; }
    $("cContado").value = ""; pintarCierre(r);
  }
  async function abrirHistorial(id) {
    const p = estado.productos.find((x) => x.id === Number(id));
    const r = await conCarga(() => api(`/tienda/api/productos/${id}/movimientos`));
    if (!r.ok) return aviso(r.error);
    $("hNombre").textContent = p.nombre;
    $("hLista").innerHTML = r.movimientos.length ? r.movimientos.map((m) =>
      `<tr><td>${new Date(m.fecha).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" })}</td>
       <td>${esc(m.tipo)}${m.venta ? " #" + m.venta : ""}</td>
       <td><strong style="color:${m.cant < 0 ? "var(--accent-red)" : "var(--accent-green)"}">${m.cant > 0 ? "+" : ""}${m.cant}</strong></td>
       <td>${m.stock}</td></tr>`).join("") : `<tr><td colspan="4" class="t-vacio">Sin movimientos.</td></tr>`;
    abrirModal("mHistorial");
  }
  function renderVentas() {
    $("tVentas").querySelector("tbody").innerHTML = estado.ventas.length ? estado.ventas.map((v) => {
      const detalle = v.items.map((i) => `${i.cant} × ${esc(i.nombre)}`).join(", ");
      const fecha = v.fecha ? new Date(v.fecha).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" }) : "";
      return `<tr class="${v.anulada ? "t-venta-anulada" : ""}"><td><strong>${v.id}</strong></td><td>${fecha}</td>
        <td class="t-detalle">${detalle}</td><td>${esc(v.metodo)}${v.metodo2 ? " + " + esc(v.metodo2) : ""}</td><td><strong>${fmt(v.total)}</strong>${v.descuento ? `<br><small>desc. ${fmt(v.descuento)}</small>` : ""}</td><td>${esc(v.cajero)}</td>
        <td>${v.anulada ? `<span class="badge-status urgent" title="${esc(v.motivo)}">Anulada</span>` : `<span class="badge-status active">Válida</span>`}</td>
        <td><div class="t-acciones"><a href="/tienda/pdf/venta/${v.id}" download><i class="ri-file-pdf-line"></i> PDF</a>${v.anulada ? "" : `<button type="button" data-anular="${v.id}"><i class="ri-arrow-go-back-line"></i> Anular</button>`}</div></td></tr>`;
    }).join("") : `<tr><td colspan="8"><div class="t-vacio-grande"><i class="ri-receipt-line"></i><strong>Aún no hay ventas</strong></div></td></tr>`;
  }
  function abrirAnular(id) {
    const v = estado.ventas.find((x) => x.id === Number(id));
    $("aId").value = v.id; $("aInfo").textContent = `Venta #${v.id} por ${fmt(v.total)}. Los productos vuelven al inventario.`;
    $("aMotivo").value = ""; $("aError").style.display = "none"; abrirModal("mAnular"); $("aMotivo").focus();
  }
  async function guardarAnular() {
    const motivo = $("aMotivo").value.trim();
    if (!motivo) return errorEn("aError", "Escribe el motivo de la anulación.");
    const r = await conCarga(() => api(`/tienda/api/ventas/${$("aId").value}/anular`, { motivo }));
    if (!r.ok) return errorEn("aError", r.error);
    estado.productos = r.productos; estado.ventas = r.ventas; cerrarModales(); renderVentas(); badgeBajo();
  }

  // ── GANANCIAS ──
  async function cargarGanancias() {
    const a = estado.ajustes, periodo = ui.periodo;
    $("aGastos").value = miles(a.gastosMes); $("uGastos").checked = a.usarGastos;
    $("aComision").value = a.comision; $("uComision").checked = a.usarComision;
    $("aImpuesto").value = a.impuesto; $("uImpuesto").checked = a.usarImpuesto;
    $("aReserva").value = a.reserva; $("uReserva").checked = a.usarReserva;
    const guardado = estado.ganCache[periodo];
    if (guardado) { estado.ganancias = guardado; pintarGanancias(); }   // lo último, al instante
    const url = "/tienda/api/ganancias?periodo=" + periodo;
    const r = await (guardado ? api(url) : conCarga(() => api(url)));
    if (!r.ok) { aviso(r.error); return; } aviso("");
    estado.ganCache[periodo] = r;
    if (ui.periodo !== periodo) return;   // cambió de período mientras cargaba
    estado.ganancias = r; pintarGanancias();
  }

  function pintarGanancias() {
    if (!estado.ganancias) return;
    const r = K.calcular(estado.ganancias, estado.ajustes), a = estado.ajustes;
    const g = estado.ganancias, ant = g.anterior;
    const cmp = (x, y) => y ? (x >= y ? "▲ " : "▼ ") + Math.abs((x - y) / y * 100).toFixed(0) + " % vs período anterior" : "sin período anterior";
    document.querySelectorAll("#tPeriodos button").forEach((b) => b.classList.toggle("active", b.dataset.p === ui.periodo));
    $("pdfGan").href = "/tienda/pdf/ganancias?periodo=" + ui.periodo;
    $("xlsGan").href = "/tienda/excel/ganancias?periodo=" + ui.periodo;
    $("tStatsGan").innerHTML =
      `<div class="stat-card gold"><span>Ventas</span><strong>${fmt(r.bruto)}</strong><small>${r.numVentas} ventas · ${cmp(r.bruto, ant.ventas)}</small></div>
       <div class="stat-card ${r.neta >= 0 ? "green" : "red"}"><span>Ganancia neta</span><strong>${fmt(r.neta)}</strong><small>margen ${r.margen.toFixed(1)} %</small></div>
       <div class="stat-card gold"><span>Ganancia bruta</span><strong>${fmt(r.gananciaBruta)}</strong><small>${cmp(r.gananciaBruta, ant.bruta)}</small></div>
       <div class="stat-card"><span>Ticket promedio</span><strong>${fmt(r.numVentas ? r.bruto / r.numVentas : 0)}</strong><small>por venta</small></div>
       ${a.usarReserva ? `<div class="stat-card green"><span>Libre para ti</span><strong>${fmt(r.disponible)}</strong><small>tras reservar ${fmt(r.reserva)}</small></div>` : ""}`;
    const fila = (txt, val, cls) => `<div class="t-casc ${cls || ""}"><span>${txt}</span><span>${cls && cls.includes("resta") && val ? "− " : ""}${fmt(val)}</span></div>`;
    $("tCascada").innerHTML =
      fila("Ventas", r.bruto) + fila("Costo de la mercancía", r.costo, "resta") + fila("Ganancia bruta", r.gananciaBruta, "sub")
      + fila(`Comisión Nequi y tarjeta (${a.comision} %)`, r.comision, "resta" + (a.usarComision ? "" : " apagado"))
      + fila(`Impuesto sobre ventas (${a.impuesto} %)`, r.impuesto, "resta" + (a.usarImpuesto ? "" : " apagado"))
      + fila(`Gastos fijos (${r.dias} día${r.dias > 1 ? "s" : ""})`, r.gastos, "resta" + (a.usarGastos ? "" : " apagado"))
      + fila("Gastos de caja", r.gastosCaja, "resta")
      + fila("Mermas (producto perdido)", r.mermas, "resta")
      + fila("Ganancia neta", r.neta, "final")
      + (a.usarReserva ? fila(`Reinversión (${a.reserva} %)`, r.reserva, "resta") + fila("Libre para ti", r.disponible, "sub") : "");
    const dias = r.porDia, max = Math.max(1, ...dias.map((d) => Math.abs(d.neta)), ...dias.map((d) => d.ventas));
    const W = Math.max(dias.length * 22, 320), H = 180, base = 150, paso = W / dias.length;
    const nombreDia = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("es-CO");
    $("tGrafica").innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="min-width:${Math.min(W, 640)}px" role="img" aria-label="Ventas y ganancia neta por día">
      <line x1="0" y1="${base}" x2="${W}" y2="${base}" stroke="var(--border-color)"/>` + dias.map((d, i) => {
      const hv = d.ventas / max * 130, hn = Math.abs(d.neta) / max * 130, x = i * paso;
      return `<rect x="${x + paso * 0.12}" y="${base - hv}" width="${paso * 0.36}" height="${hv}" rx="2" fill="var(--accent-gold)" opacity=".55"><title>${nombreDia(d.fecha)}: ventas ${fmt(d.ventas)}</title></rect>
        <rect x="${x + paso * 0.5}" y="${d.neta >= 0 ? base - hn : base}" width="${paso * 0.36}" height="${hn}" rx="2" fill="${d.neta >= 0 ? "var(--accent-green)" : "var(--accent-red)"}"><title>${nombreDia(d.fecha)}: neta ${fmt(d.neta)}</title></rect>`;
    }).join("") + `</svg><p class="hint"><span style="color:var(--accent-gold)">■</span> Ventas &nbsp; <span style="color:var(--accent-green)">■</span> Ganancia neta del día</p>`;
    const maxG = Math.max(1, ...r.top.map((t) => t.ganancia));
    $("tTop").innerHTML = r.top.length ? r.top.map((t) => `<div class="t-barra-fila"><span>${esc(t.nombre)}</span>
      <div class="t-barra"><i style="width:${Math.max(t.ganancia, 0) / maxG * 100}%"></i></div><strong>${fmt(t.ganancia)}</strong></div>`).join("")
      : `<p class="t-vacio">Aún no hay ventas en este periodo.</p>`;
    const barras = (filas) => {
      const m = Math.max(1, ...filas.map((f) => f.v));
      return filas.length ? filas.map((f) => `<div class="t-barra-fila"><span>${esc(f.n)}</span>
        <div class="t-barra"><i style="width:${f.v / m * 100}%"></i></div><strong>${fmt(f.v)}</strong></div>`).join("")
        : `<p class="t-vacio">Sin ventas en este periodo.</p>`;
    };
    $("tMetodos").innerHTML = barras(g.metodos.map((x) => ({ n: x.metodo, v: x.valor })));
    $("tHoras").innerHTML = barras(g.horas.map((x) => ({ n: x.h + ":00", v: x.ventas })));
    const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"], sem = DIAS.map(() => 0);
    r.porDia.forEach((d) => { sem[(new Date(d.fecha + "T12:00:00").getDay() + 6) % 7] += d.ventas; });
    $("tSemana").innerHTML = barras(DIAS.map((n, i) => ({ n, v: sem[i] })));
    $("tQuietos").innerHTML = g.quietos.length
      ? g.quietos.map((q) => `<div class="t-barra-fila" style="grid-template-columns:1fr auto"><span>${esc(q.nombre)} <small class="hint">(${q.stock} und)</small></span><strong>${fmt(q.parado)}</strong></div>`).join("")
        + `<p class="hint">Dinero parado en inventario, a precio de costo.</p>`
      : `<p class="t-vacio">Todo se está moviendo 🎉</p>`;
  }

  // Las preferencias se recalculan al instante y se guardan en el servidor un momento después
  let tGuardar = null;
  function leerAjustes() {
    const a = estado.ajustes;
    a.gastosMes = digitos($("aGastos").value); a.usarGastos = $("uGastos").checked;
    a.comision = Math.min(20, Math.max(0, parseFloat($("aComision").value) || 0)); a.usarComision = $("uComision").checked;
    a.impuesto = Math.min(30, Math.max(0, parseFloat($("aImpuesto").value) || 0)); a.usarImpuesto = $("uImpuesto").checked;
    a.reserva = Math.min(100, Math.max(0, parseFloat($("aReserva").value) || 0)); a.usarReserva = $("uReserva").checked;
    pintarGanancias();
    clearTimeout(tGuardar);
    tGuardar = setTimeout(async () => { const r = await api("/tienda/api/ajustes", a); if (!r.ok) aviso(r.error); else aviso(""); }, 700);
  }

  // ── Eventos ──
  document.addEventListener("click", (e) => {
    const t = e.target.closest("button, [data-cat]"); if (!t) return;
    if (t.dataset.add) agregar(t.dataset.add);
    else if (t.dataset.mas) agregar(t.dataset.mas);
    else if (t.dataset.menos) quitar(t.dataset.menos);
    else if (t.dataset.cat) { ui.cat = t.dataset.cat; renderCaja(); }
    else if (t.dataset.reab) abrirReabastecer(t.dataset.reab);
    else if (t.dataset.edit) abrirProducto(t.dataset.edit);
    else if (t.dataset.hist) abrirHistorial(t.dataset.hist);
    else if (t.dataset.baja) abrirBaja(t.dataset.baja);
    else if (t.dataset.amerma) anularMerma(t.dataset.amerma);
    else if (t.dataset.mov) abrirMov(t.dataset.mov);
    else if (t.dataset.qmov) quitarMov(t.dataset.qmov);
    else if (t.dataset.rango) fijarRango(t.dataset.rango);
    else if (t.dataset.anular) abrirAnular(t.dataset.anular);
    else if (t.dataset.p) { ui.periodo = t.dataset.p; cargarGanancias(); }
    else if (t.hasAttribute("data-cerrar")) cerrarModales();
  });
  document.querySelectorAll(".t-modal").forEach((m) => m.addEventListener("click", (e) => { if (e.target === m) cerrarModales(); }));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrarModales(); });
  $("tBuscar").addEventListener("input", (e) => { ui.q = e.target.value; renderCaja(); });
  $("tVaciar").addEventListener("click", () => { ui.carrito = {}; renderCaja(); });
  $("tMetodo").addEventListener("change", renderCarrito);
  $("tRecibido").addEventListener("input", renderCarrito);
  $("tDescVal").addEventListener("input", renderCarrito);
  $("tDescTipo").addEventListener("change", renderCarrito);
  $("tCobrar").addEventListener("click", cobrar);
  $("tNuevo").addEventListener("click", () => abrirProducto(null));
  $("pGuardar").addEventListener("click", guardarProducto);
  $("rGuardar").addEventListener("click", guardarReabastecer);
  $("aGuardar").addEventListener("click", guardarAnular);
  $("cGuardar").addEventListener("click", guardarCierre);
  $("mvGuardar").addEventListener("click", guardarMov);
  $("bGuardar").addEventListener("click", guardarBaja);
  ["rDesde", "rHasta"].forEach((id) => $(id).addEventListener("change", enlacesReporte));
  ["tRecibido", "pCosto", "pPrecio", "pStock", "pMin", "rCant", "aGastos", "cContado", "tDescVal", "mvMonto", "bCant"].forEach((id) => money($(id)));
  ["aGastos", "aComision", "aImpuesto", "aReserva"].forEach((id) => $(id).addEventListener("input", leerAjustes));
  ["uGastos", "uComision", "uImpuesto", "uReserva"].forEach((id) => $(id).addEventListener("change", leerAjustes));

  // ── Arranque ──
  (async function iniciar() {
    const r = await conCarga(() => api("/tienda/api/estado"));
    if (!r.ok) { aviso(r.error); $("tGrid").innerHTML = ""; return; }
    estado.productos = r.productos; estado.ajustes = r.ajustes; estado.abierta = r.abierta;
    fijarRango("hoy");
    irA(location.hash.replace("#", "") || "caja");
  })();
})();
