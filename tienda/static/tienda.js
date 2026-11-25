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

  const estado = { cuentas: [], productos: [], servicios: [], ajustes: {}, ventas: [], ganancias: null, ganCache: {}, abierta: false, permisos: [] };
  const puede = (codigo) => estado.permisos.includes(codigo);
  const ui = { mes: null, cuActiva: true, vista: "caja", cat: "Todos", q: "", carrito: {}, carritoSrv: [], kSrv: 0, tab: "productos", srv: null, reqs: [], periodo: "30", enviando: false };

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
  const VISTAS = ["caja", "inventario", "servicios", "ventas", "ganancias", "cuentas", "usuarios"];
  // Cada pantalla pide su permiso; quien no lo tiene vuelve a la caja.
  const PERMISO_VISTA = { inventario: "tienda_inventario", servicios: "tienda_servicios", ganancias: "tienda_ganancias", cuentas: "tienda_cuentas", usuarios: "tienda_usuarios" };
  async function irA(vista) {
    if (!VISTAS.includes(vista) || (PERMISO_VISTA[vista] && !puede(PERMISO_VISTA[vista]))) vista = "caja";
    ui.vista = vista;
    VISTAS.forEach((v) => { $("vista-" + v).hidden = v !== vista; });
    document.querySelectorAll("[data-vista]").forEach((a) => a.classList.toggle("active", a.dataset.vista === vista));
    document.body.classList.remove("sidebar-open");
    if (vista === "caja") { await cargarCierre(); renderCaja(); }
    if (vista === "inventario") { renderInventario(); cargarMermas(); }
    if (vista === "servicios") renderServicios();
    if (vista === "ventas") await cargarVentas();
    if (vista === "cuentas") await cargarMes();
    if (vista === "ganancias") await cargarGanancias();
    if (vista === "usuarios") await cargarUsuarios();
  }
  window.addEventListener("hashchange", () => irA(location.hash.replace("#", "")));

  // ── CAJA ──
  const categorias = () => ["Todos", ...Array.from(new Set(estado.productos.map((p) => p.cat))).sort()];
  const categoriasSrv = () => ["Todos", ...Array.from(new Set(estado.servicios.map((x) => x.cat))).sort()];

  function renderCaja() {
    $("tCajaCerrada").hidden = estado.abierta;
    const esSrv = ui.tab === "servicios";
    document.querySelectorAll("#tTabs [data-tab]").forEach((b) => b.classList.toggle("on", b.dataset.tab === ui.tab));
    $("tBuscar").placeholder = esSrv ? "Buscar servicio…" : "Buscar producto…";
    const cats = esSrv ? categoriasSrv() : categorias();
    $("tChips").innerHTML = cats.length > 2 ? cats.map((c) =>
      `<button type="button" class="t-chip ${c === ui.cat ? "on" : ""}" data-cat="${esc(c)}">${esc(c)}</button>`).join("") : "";
    const q = ui.q.trim().toLowerCase();
    if (esSrv) {
      const lista = estado.servicios.filter((x) => (ui.cat === "Todos" || x.cat === ui.cat) && (!q || x.nombre.toLowerCase().includes(q)));
      if (!estado.servicios.length) {
        $("tGrid").innerHTML = `<div class="t-vacio-grande"><i class="ri-customer-service-2-line"></i><strong>Aún no hay servicios</strong>
          ${puede("tienda_servicios")
            ? `<p>Agrega el primero en Servicios y aparecerá aquí para cobrar.</p>
          <a class="btn-action green" href="#servicios"><i class="ri-add-line"></i> Ir a Servicios</a>`
            : `<p>Pídele a quien administra la tienda que agregue los servicios.</p>`}</div>`;
      } else {
        $("tGrid").innerHTML = lista.length ? lista.map((x) =>
          `<button type="button" class="t-prod" data-sadd="${x.id}" ${!estado.abierta ? "disabled" : ""}>
            <strong>${esc(x.nombre)}</strong><span class="precio">${x.variable ? "Precio variable" : fmt(x.precio)}</span>
            <small>${esc(x.cat)}</small></button>`).join("")
          : `<p class="t-vacio" style="grid-column:1/-1">No hay servicios con ese filtro.</p>`;
      }
      renderCarrito(); badgeBajo();
      return;
    }
    const lista = estado.productos.filter((p) => (ui.cat === "Todos" || p.cat === ui.cat) && (!q || p.nombre.toLowerCase().includes(q)));
    if (!estado.productos.length) {
      $("tGrid").innerHTML = `<div class="t-vacio-grande"><i class="ri-store-2-line"></i><strong>Aún no tienes productos</strong>
        ${puede("tienda_inventario")
          ? `<p>Agrega el primero en Inventario y aparecerá aquí para vender.</p>
        <a class="btn-action green" href="#inventario"><i class="ri-add-line"></i> Ir a Inventario</a>`
          : `<p>Pídele a quien administra la tienda que agregue los productos.</p>`}</div>`;
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
    const hayLineas = ids.length > 0 || ui.carritoSrv.length > 0;
    $("tLineas").innerHTML = ids.length ? ids.map((id) => {
      const p = estado.productos.find((x) => x.id === Number(id));
      if (!p) return "";
      const cant = ui.carrito[id]; total += cant * p.precio;
      return `<div class="t-linea"><strong>${esc(p.nombre)}</strong><span class="sub">${fmt(cant * p.precio)}</span>
        <div class="t-cant"><button type="button" data-menos="${id}" aria-label="Quitar uno">−</button><span>${cant}</span>
        <button type="button" data-mas="${id}" aria-label="Agregar uno">+</button></div><span></span></div>`;
    }).join("") : (hayLineas ? "" : `<p class="t-vacio">Aún no hay nada en la venta.</p>`);
    $("tLineasSrv").innerHTML = ui.carritoSrv.map((l) => {
      total += l.precio;
      return `<div class="t-linea"><strong>${esc(l.nombre)}${l.txt ? `<span class="t-det-srv">${esc(l.txt)}</span>` : ""}</strong><span class="sub">${fmt(l.precio)}</span>
        <div class="t-cant"><button type="button" data-sdel="${l.k}" aria-label="Quitar servicio">×</button></div><span></span></div>`;
    }).join("");
    const dv = digitos($("tDescVal").value);
    const desc = $("tDescTipo").value === "pct" ? Math.round(total * Math.min(dv, 100) / 100) : dv;
    const descMal = desc > 0 && desc >= total;
    $("tDescHint").textContent = descMal ? "El descuento debe ser menor que el total."
      : (desc ? `Subtotal ${fmt(total)} − descuento ${fmt(desc)}` : "");
    const neto = descMal ? total : total - desc;
    $("tTotal").textContent = fmt(neto);
    const efectivo = $("tMetodo").value === "Efectivo";
    const rec = digitos($("tRecibido").value);
    $("tCobrar").disabled = !estado.abierta || !hayLineas || ui.enviando || descMal || (efectivo && rec <= 0);
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

  // ── Servicios en la venta ──
  const reqsDe = (s, tipo) => (s.requisitos || []).filter((r) => r.tipo === tipo);
  function abrirSrv(id) {
    const s = estado.servicios.find((x) => x.id === Number(id));
    if (!s || !estado.abierta) return;
    ui.srv = s;
    $("mSrvTitulo").textContent = s.nombre;
    $("mSrvPrecios").style.display = s.variable ? "" : "none";
    $("mSrvPrecio").value = s.variable && s.precio ? miles(s.precio) : "";
    $("mSrvTerceros").value = s.variable && s.terceros ? miles(s.terceros) : "";
    $("mSrvFijo").textContent = s.variable ? "El precio cambia en cada cobro: escríbelo aquí." : `Precio: ${fmt(s.precio)}`;
    const docs = reqsDe(s, "DOCUMENTO"), datosR = reqsDe(s, "DATO");
    $("mSrvDocs").innerHTML = docs.length ? `<span class="lbl">Documentos que debe traer el cliente</span>`
      + docs.map((d) => `<label class="t-ajuste" style="border:0"><span>${esc(d.texto)}</span><input type="checkbox"></label>`).join("") : "";
    $("mSrvDatos").innerHTML = datosR.map((d) => `<div class="field"><label class="lbl" for="sd${d.id}">${esc(d.texto)}${d.obligatorio ? " *" : ""}</label>
      <input class="input-clean" id="sd${d.id}" data-dato="${d.id}" maxlength="80" autocomplete="off"></div>`).join("");
    $("mSrvError").style.display = "none"; abrirModal("mSrv");
    const primero = $("mSrvDatos").querySelector("input") || (s.variable ? $("mSrvPrecio") : null);
    if (primero) primero.focus();
  }
  function agregarServicio() {
    const s = ui.srv; if (!s) return;
    const precio = s.variable ? digitos($("mSrvPrecio").value) : s.precio;
    const terceros = s.variable ? digitos($("mSrvTerceros").value) : 0;
    if (precio <= 0) return errorEn("mSrvError", s.variable ? "Escribe el precio que vas a cobrar." : "Este servicio no tiene precio. Ponlo en Servicios.");
    if (terceros > precio) return errorEn("mSrvError", "El valor a terceros es mayor que el precio cobrado.");
    const datosR = {}; let falta = null;
    $("mSrvDatos").querySelectorAll("[data-dato]").forEach((inp) => {
      const v = inp.value.trim(); datosR[inp.dataset.dato] = v;
      const r = (s.requisitos || []).find((x) => String(x.id) === inp.dataset.dato);
      if (!v && r && r.obligatorio && !falta) falta = r.texto;
    });
    if (falta) return errorEn("mSrvError", `Falta anotar: ${falta}.`);
    const txt = reqsDe(s, "DATO").map((r) => (datosR[r.id] ? `${r.texto}: ${datosR[r.id]}` : "")).filter(Boolean).join(" · ");
    ui.carritoSrv.push({ k: ++ui.kSrv, id: s.id, nombre: s.nombre, precio, terceros, datos: datosR, txt });
    cerrarModales(); renderCaja();
  }
  function quitarServicioVenta(k) { ui.carritoSrv = ui.carritoSrv.filter((l) => l.k !== Number(k)); renderCaja(); }

  async function cobrar() {
    if (ui.enviando) return;
    const items = Object.entries(ui.carrito).map(([id, cant]) => ({ id: Number(id), cant }));
    const lineasSrv = ui.carritoSrv.map((l) => ({ id: l.id, precio: l.precio, terceros: l.terceros, datos: l.datos }));
    ui.enviando = true; $("tCobrar").disabled = true;
    const r = await api("/tienda/api/ventas", { items, servicios: lineasSrv, metodo: $("tMetodo").value, recibido: digitos($("tRecibido").value), resto: $("tResto").value,
      descuento: { tipo: $("tDescTipo").value, valor: digitos($("tDescVal").value) } });
    ui.enviando = false;
    if (!r.ok) { $("tError").textContent = r.error; $("tError").style.display = "block"; $("tCobrar").disabled = false; await recargarProductos(); return; }
    r.stocks.forEach((s) => { const p = estado.productos.find((x) => x.id === s.id); if (p) p.stock = s.stock; });
    $("vResumen").innerHTML = r.venta.items.map((i) => `<div><span>${i.cant} × ${esc(i.nombre)}${i.detalle ? ` <small>(${esc(i.detalle)})</small>` : ""}</span><strong>${fmt(i.cant * i.precio)}</strong></div>`).join("")
      + (r.venta.descuento ? `<div><span>Descuento</span><strong>− ${fmt(r.venta.descuento)}</strong></div>` : "")
      + `<div><span>Total (${esc(r.venta.metodo)}) · venta #${r.venta.id}</span><strong>${fmt(r.venta.total)}</strong></div>`
      + (r.venta.monto2 ? `<div><span>Resto con ${esc(r.venta.metodo2)}</span><strong>${fmt(r.venta.monto2)}</strong></div>` : "")
      + (r.devuelta ? `<div><span>Devuelta</span><strong>${fmt(r.devuelta)}</strong></div>` : "");
    $("vAvisos").innerHTML = r.bajos.map((b) =>
      `<div class="t-aviso"><i class="ri-alert-line"></i> ${b.stock <= 0 ? "Se agotó" : "Queda poco de"} «${esc(b.nombre)}»${b.stock > 0 ? ` (${b.stock})` : ""}.</div>`).join("");
    ui.carrito = {}; ui.carritoSrv = []; $("tRecibido").value = ""; $("tDescVal").value = "";
    $("vTicket").href = "/tienda/pdf/venta/" + r.venta.id;
    abrirModal("mVenta"); renderCaja();
  }

  async function recargarProductos() {
    const r = await api("/tienda/api/estado");
    if (r.ok) { estado.productos = r.productos; estado.servicios = r.servicios || estado.servicios; estado.ajustes = r.ajustes; estado.cuentas = r.cuentas || estado.cuentas || []; estado.abierta = r.abierta; estado.permisos = r.permisos || estado.permisos; for (const id of Object.keys(ui.carrito)) if (!estado.productos.some((p) => p.id === Number(id))) delete ui.carrito[id]; renderCaja(); }
  }

  // ── INVENTARIO ──
  function badgeBajo() {
    const n = estado.productos.filter((p) => K.estadoStock(p) !== "ok").length;
    const b = $("badgeBajo"); if (!b) return; b.hidden = !n; b.textContent = n;
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

  // ── SERVICIOS (administración) ──
  function renderServicios() {
    const q = ($("sBuscar").value || "").trim().toLowerCase();
    const ls = estado.servicios.filter((x) => !q || x.nombre.toLowerCase().includes(q) || x.cat.toLowerCase().includes(q));
    if (!ls.length) {
      $("tServicios").innerHTML = estado.servicios.length
        ? `<p class="t-vacio">No hay servicios con esa búsqueda.</p>`
        : `<div class="t-vacio-grande"><i class="ri-customer-service-2-line"></i><strong>Aún no hay servicios</strong><p>Agrega el primero con «Nuevo servicio».</p></div>`;
      return;
    }
    const grupos = {};
    ls.forEach((x) => { (grupos[x.cat] = grupos[x.cat] || []).push(x); });
    $("tServicios").innerHTML = Object.keys(grupos).sort().map((cat) =>
      `<h2 class="t-srv-grupo">${esc(cat)}</h2>` + grupos[cat].map((x) => {
        const nDoc = reqsDe(x, "DOCUMENTO").length, nDat = reqsDe(x, "DATO").length;
        const notas = [];
        if (x.terceros) notas.push(`Para terceros: ${fmt(x.terceros)}` + (x.variable ? "" : ` · Te quedan: ${fmt(x.precio - x.terceros)}`));
        if (nDoc || nDat) notas.push(`Se pide: ${nDoc} documento${nDoc === 1 ? "" : "s"} y ${nDat} dato${nDat === 1 ? "" : "s"}`);
        const precio = x.variable
          ? `<span class="t-srv-precio variable">Precio variable</span>${x.precio ? `<small>sugerido ${fmt(x.precio)}</small>` : ""}`
          : `<span class="t-srv-precio">${fmt(x.precio)}</span>`;
        return `<div class="t-srv">
          <div class="t-srv-info"><strong>${esc(x.nombre)}</strong>${notas.length ? `<small>${notas.join(" · ")}</small>` : ""}</div>
          <div class="t-srv-precio-box">${precio}</div>
          <div class="t-srv-btns">
            <button type="button" class="btn-action" data-sedit="${x.id}"><i class="ri-edit-line"></i> Cambiar</button>
            <button type="button" class="btn-action red" data-squitar="${x.id}"><i class="ri-delete-bin-line"></i> Quitar</button>
          </div></div>`;
      }).join("")).join("");
  }
  function pintarReqs() {
    $("sReqs").innerHTML = ui.reqs.length ? ui.reqs.map((r, i) => `<div class="t-req">
      <span class="t-req-tipo">${r.tipo === "DATO" ? "Dato" : "Documento"}</span>
      <input class="input-clean" data-rtxt="${i}" maxlength="80" value="${esc(r.texto)}" placeholder="${r.tipo === "DATO" ? "Ej: Placa" : "Ej: Cédula"}" autocomplete="off">
      ${r.tipo === "DATO" ? `<label class="t-req-ob"><input type="checkbox" data-robl="${i}" ${r.obligatorio ? "checked" : ""}> Obligatorio</label>` : ""}
      <button type="button" data-rup="${i}" aria-label="Subir" ${i === 0 ? "disabled" : ""}>↑</button>
      <button type="button" data-rdown="${i}" aria-label="Bajar" ${i === ui.reqs.length - 1 ? "disabled" : ""}>↓</button>
      <button type="button" data-rdel="${i}" aria-label="Quitar requisito">×</button></div>`).join("")
      : `<p class="hint">Sin requisitos todavía. Agrega lo que se pide para este servicio.</p>`;
  }
  function pintarGananciaServicio() {
    const variable = $("sVariable").checked, precio = digitos($("sPrecio").value), terc = digitos($("sTerceros").value);
    document.querySelectorAll("[data-modo]").forEach((b) => b.classList.toggle("on", (b.dataset.modo === "variable") === variable));
    $("sPrecioEtq").textContent = variable ? "4. Precio sugerido (opcional)" : "4. Precio que se cobra";
    $("sGanancia").textContent = variable ? "Al cobrar se escribe el precio y el valor a terceros de ese día."
      : (precio ? (terc > precio ? "El valor a terceros es mayor que el precio." : `Te queda ${fmt(precio - terc)} por cada servicio.`) : "");
  }

  // ── Pasos del formulario de servicio ──
  let pasoSrv = 0;
  const PASOS_SRV = 3;
  function mostrarPasoSrv(n) {
    pasoSrv = n;
    document.querySelectorAll("#mServicio [data-paso]").forEach((p) => { p.hidden = Number(p.dataset.paso) !== n; });
    document.querySelectorAll("#mServicio .t-pasos-barra i").forEach((b, i) => b.classList.toggle("on", i <= n));
    $("sPasoTxt").textContent = `Paso ${n + 1} de ${PASOS_SRV}`;
    $("sAtras").hidden = n === 0;
    $("sSiguiente").hidden = n === PASOS_SRV - 1;
    $("sGuardar").hidden = n !== PASOS_SRV - 1;
    $("sError").style.display = "none";
  }
  function siguientePasoSrv() {
    if (pasoSrv === 0 && !$("sNombre").value.trim()) return errorEn("sError", "Escribe el nombre del servicio.");
    if (pasoSrv === 1) {
      const variable = $("sVariable").checked, precio = digitos($("sPrecio").value), terc = digitos($("sTerceros").value);
      if (!variable && precio <= 0) return errorEn("sError", "Escribe el precio, o elige «Cambia cada vez».");
      if (!variable && terc > precio) return errorEn("sError", "El valor para otra entidad es mayor que el precio.");
    }
    mostrarPasoSrv(Math.min(pasoSrv + 1, PASOS_SRV - 1));
  }

  function abrirServicio(id) {
    const x = id ? estado.servicios.find((v) => v.id === Number(id)) : null;
    $("mServicioTitulo").textContent = x ? "Cambiar servicio" : "Nuevo servicio";
    $("sId").value = x ? x.id : ""; $("sNombre").value = x ? x.nombre : ""; $("sCat").value = x ? x.cat : "";
    $("sPrecio").value = x && x.precio ? miles(x.precio) : ""; $("sTerceros").value = x && x.terceros ? miles(x.terceros) : "";
    $("sVariable").checked = x ? x.variable : false;
    $("sCatChips").innerHTML = categoriasSrv().filter((c) => c !== "Todos").map((c) =>
      `<button type="button" class="t-chip" data-scat="${esc(c)}">${esc(c)}</button>`).join("");
    ui.reqs = x ? (x.requisitos || []).map((r) => ({ tipo: r.tipo, texto: r.texto, obligatorio: r.obligatorio })) : [];
    pintarReqs(); pintarGananciaServicio(); mostrarPasoSrv(0);
    $("sError").style.display = "none"; abrirModal("mServicio"); $("sNombre").focus();
  }
  async function guardarServicio() {
    const cuerpo = { id: Number($("sId").value) || null, nombre: $("sNombre").value, categoria: $("sCat").value,
      variable: $("sVariable").checked, precio: digitos($("sPrecio").value), terceros: digitos($("sTerceros").value),
      requisitos: ui.reqs.filter((r) => r.texto.trim()) };
    if (!cuerpo.nombre.trim()) return errorEn("sError", "Escribe el nombre del servicio.");
    if (!cuerpo.variable && cuerpo.precio <= 0) return errorEn("sError", "Escribe el precio, o marca «El precio se escribe al cobrar».");
    if (!cuerpo.variable && cuerpo.terceros > cuerpo.precio) return errorEn("sError", "El valor a terceros es mayor que el precio.");
    const r = await conCarga(() => api("/tienda/api/servicios", cuerpo));
    if (!r.ok) return errorEn("sError", r.error);
    estado.servicios = r.servicios; cerrarModales(); renderServicios();
    ui.carritoSrv = ui.carritoSrv.filter((l) => estado.servicios.some((x) => x.id === l.id));
  }
  async function quitarServicio(id) {
    const x = estado.servicios.find((v) => v.id === Number(id));
    if (!confirm(`¿Quitar «${x ? x.nombre : "este servicio"}»? Deja de aparecer en la caja; las ventas anteriores se conservan.`)) return;
    const r = await conCarga(() => api(`/tienda/api/servicios/${id}/quitar`, {}));
    if (!r.ok) return aviso(r.error);
    aviso(""); estado.servicios = r.servicios; renderServicios();
    ui.carritoSrv = ui.carritoSrv.filter((l) => estado.servicios.some((x) => x.id === l.id));
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
    $("cAbierta").hidden = !r.abierta || !puede("tienda_caja");
    $("cEstadoSimple").hidden = !(r.abierta && !puede("tienda_caja"));
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
      const detalle = v.items.map((i) => `${i.cant} × ${esc(i.nombre)}${i.detalle ? ` <small>(${esc(i.detalle)})</small>` : ""}`).join(", ");
      const fecha = v.fecha ? new Date(v.fecha).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" }) : "";
      return `<tr class="${v.anulada ? "t-venta-anulada" : ""}"><td><strong>${v.id}</strong></td><td>${fecha}</td>
        <td class="t-detalle">${detalle}</td><td>${esc(v.metodo)}${v.metodo2 ? " + " + esc(v.metodo2) : ""}</td><td><strong>${fmt(v.total)}</strong>${v.descuento ? `<br><small>desc. ${fmt(v.descuento)}</small>` : ""}</td><td>${esc(v.cajero)}</td>
        <td>${v.anulada ? `<span class="badge-status urgent" title="${esc(v.motivo)}">Anulada</span>` : `<span class="badge-status active">Válida</span>`}</td>
        <td><div class="t-acciones"><a href="/tienda/pdf/venta/${v.id}" download><i class="ri-file-pdf-line"></i> PDF</a>${v.anulada || !puede("tienda_anular") ? "" : `<button type="button" data-anular="${v.id}"><i class="ri-arrow-go-back-line"></i> Anular</button>`}</div></td></tr>`;
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
    pintarTotalCuentas(); $("uGastos").checked = a.usarGastos;
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
       ${g.servicios && g.servicios.n ? `<div class="stat-card"><span>Dinero de terceros</span><strong>${fmt(g.servicios.terceros)}</strong><small>${g.servicios.n} servicio${g.servicios.n > 1 ? "s" : ""} · ya descontado como costo</small></div>` : ""}
       ${a.usarReserva ? `<div class="stat-card green"><span>Libre para ti</span><strong>${fmt(r.disponible)}</strong><small>tras reservar ${fmt(r.reserva)}</small></div>` : ""}`;
    const fila = (txt, val, cls) => `<div class="t-casc ${cls || ""}"><span>${txt}</span><span>${cls && cls.includes("resta") && val ? "− " : ""}${fmt(val)}</span></div>`;
    $("tCascada").innerHTML =
      fila("Ventas", r.bruto) + fila("Costo de la mercancía y pagos a terceros", r.costo, "resta") + fila("Ganancia bruta", r.gananciaBruta, "sub")
      + fila(`Comisión Nequi y tarjeta (${a.comision} %)`, r.comision, "resta" + (a.usarComision ? "" : " apagado"))
      + fila(`Impuesto sobre ventas (${a.impuesto} %)`, r.impuesto, "resta" + (a.usarImpuesto ? "" : " apagado"))
      + fila(`Cuentas del negocio (${r.dias} día${r.dias > 1 ? "s" : ""})`, r.gastos, "resta" + (a.usarGastos ? "" : " apagado")) + detalleCuentas(r.dias, a.usarGastos)
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

  // ── CUENTAS DEL NEGOCIO + pantalla «Mis cuentas» ──
  const CATS_CUENTA = ["Arriendo", "Luz", "Agua", "Gas", "Internet y teléfono", "Sueldos", "Arreglos y mantenimiento", "Impuestos y trámites", "Otros"];
  const totalCuentas = () => (estado.cuentas || []).filter((c) => c.activa).reduce((s, c) => s + c.valor, 0);
  function pintarTotalCuentas() {
    const t = totalCuentas();
    estado.ajustes.gastosMes = t; $("aGastos").value = miles(t);
    $("cuentasTotal").textContent = t ? fmt(t) + " al mes" : "Agregar cuentas";
  }
  function detalleCuentas(dias, usar) {
    if (!usar) return "";
    const por = {};
    (estado.cuentas || []).filter((c) => c.activa).forEach((c) => { por[c.categoria] = (por[c.categoria] || 0) + c.valor; });
    return Object.entries(por).sort((x, y) => y[1] - x[1])
      .map(([cat, v]) => `<div class="t-casc detalle"><span>${esc(cat)}</span><span>${fmt(v / 30 * dias)}</span></div>`).join("");
  }
  const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  const mesDe = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
  const mesTexto = (m) => { const [y, n] = m.split("-"); return MESES[Number(n) - 1] + " de " + y; };
  function mesMover(delta) {
    const [y, n] = (ui.mes || mesDe(new Date())).split("-").map(Number);
    ui.mes = mesDe(new Date(y, n - 1 + delta, 1));
    cargarMes();
  }
  async function cargarMes() {
    ui.mes = ui.mes || mesDe(new Date());
    const r = await conCarga(() => api("/tienda/api/mes?mes=" + ui.mes));
    if (!r.ok) { aviso(r.error); return; }
    aviso(""); estado.mes = r; pintarMes();
  }
  function pintarMes() {
    const r = estado.mes; if (!r) return;
    $("mesNombre").textContent = mesTexto(r.mes);
    $("mesSig").disabled = r.mes >= mesDe(new Date());
    const bien = r.quedo >= 0;
    $("tTres").innerHTML =
      `<div class="t-numero"><span>Vendiste</span><strong>${fmt(r.vendiste)}</strong></div>`
      + `<div class="t-numero"><span>Gastaste</span><strong>${fmt(r.gastaste)}</strong></div>`
      + `<div class="t-numero ${bien ? "bien" : "mal"}"><span>Te queda</span><strong>${bien ? "" : "− "}${fmt(Math.abs(r.quedo))}</strong></div>`;
    const hayCuentas = r.filas.some((f) => f.id);
    $("mcLista").innerHTML = r.filas.map((f) =>
      `<div class="t-fila-c"><span class="t-fila-nombre"><strong>${esc(f.nombre)}</strong><small>${esc(f.sub)}</small></span>`
      + `<span class="t-fila-valor">${fmt(f.valor)}</span>`
      + (f.id ? `<span class="t-fila-btns"><button type="button" class="btn-action" data-cedit="${f.id}">Cambiar</button><button type="button" class="btn-action red" data-cdel="${f.id}">Quitar</button></span>` : "")
      + `</div>`).join("")
      + (hayCuentas ? "" : `<p class="t-hint">Todavía no has anotado cuentas. Toca el botón verde para agregar la primera, por ejemplo la luz.</p>`);
  }
  function abrirCuenta(c) {
    ui.cuActiva = c ? c.activa : true;
    $("mCuentasTitulo").textContent = c ? "Cambiar la cuenta" : "Agregar una cuenta";
    $("cuId").value = c ? c.id : ""; $("cuNombre").value = c ? c.nombre : "";
    $("cuCat").value = c && CATS_CUENTA.includes(c.categoria) ? c.categoria : CATS_CUENTA[0];
    $("cuValor").value = c ? miles(c.valor) : ""; $("cuError").style.display = "none";
    abrirModal("mCuentas"); $("cuNombre").focus();
  }
  const editarCuenta = (id) => abrirCuenta((estado.cuentas || []).find((x) => x.id === Number(id)));
  function cuentasActualizadas(r) {
    estado.cuentas = r.cuentas; cerrarModales(); pintarTotalCuentas(); pintarGanancias();
    if (ui.vista === "cuentas") cargarMes();
  }
  async function guardarCuenta() {
    $("cuError").style.display = "none";
    const r = await conCarga(() => api("/tienda/api/cuentas", { id: $("cuId").value || null, nombre: $("cuNombre").value,
      categoria: $("cuCat").value, valor: digitos($("cuValor").value), activa: ui.cuActiva !== false }));
    if (!r.ok) return errorEn("cuError", r.error);
    cuentasActualizadas(r);
  }
  async function borrarCuenta(id) {
    if (!window.confirm("¿Quitar esta cuenta? Ya no se contará en tus gastos.")) return;
    const r = await conCarga(() => api(`/tienda/api/cuentas/${id}/borrar`, {}));
    if (!r.ok) return aviso(r.error);
    cuentasActualizadas(r);
  }

  // ── USUARIOS DE LA TIENDA ──
  let usu = { lista: [], catalogo: {}, plantillas: {}, nombres: {} };
  const etiquetaPermiso = (txt) => { const t = String(txt).replace(/^Tienda:\s*/, ""); return t.charAt(0).toUpperCase() + t.slice(1); };
  function aplicarUsuarios(r) { usu = { lista: r.usuarios, catalogo: r.catalogo, plantillas: r.plantillas, nombres: r.plantillaNombres || {}, yo: r.yo }; }
  async function cargarUsuarios() {
    const r = await conCarga(() => api("/tienda/api/usuarios"));
    if (!r.ok) { aviso(r.error); return; }
    aviso(""); aplicarUsuarios(r); renderUsuarios();
  }
  function renderUsuarios() {
    $("tUsuarios").querySelector("tbody").innerHTML = usu.lista.length ? usu.lista.map((u) => {
      const acceso = u.ultimoAcceso ? hora(u.ultimoAcceso) : "Nunca";
      const plantilla = usu.nombres[u.rol] || (u.permisos.includes("tienda_usuarios") ? "Administrador" : "Personalizado");
      return `<tr><td><strong>${esc(u.nombre)}</strong>${u.id === usu.yo ? " <small>(tú)</small>" : ""}</td><td>${esc(u.usuario)}</td><td>${esc(plantilla)}</td>
        <td><span class="badge-status ${u.activo ? "active" : "muted"}">${u.activo ? "Activa" : "Inactiva"}</span></td><td>${acceso}</td>
        <td><div class="t-acciones"><button type="button" data-uedit="${u.id}"><i class="ri-edit-line"></i> Editar</button></div></td></tr>`;
    }).join("") : `<tr><td colspan="6"><div class="t-vacio-grande"><i class="ri-user-line"></i><strong>Aún no hay usuarios</strong></div></td></tr>`;
  }
  function pintarPermisosUsuario(lista) {
    const marcados = new Set(lista || []);
    $("usPermisos").innerHTML = Object.keys(usu.catalogo).map((c) =>
      `<label class="t-ajuste" style="border:0"><span><strong>${esc(etiquetaPermiso(usu.catalogo[c]))}</strong></span>
        <input type="checkbox" data-perm="${c}" ${marcados.has(c) || c === "ver_tienda" ? "checked" : ""} ${c === "ver_tienda" ? "disabled" : ""}></label>`).join("");
  }
  function abrirUsuario(id) {
    const u = id ? usu.lista.find((x) => x.id === Number(id)) : null;
    $("usId").value = u ? u.id : "";
    $("mUsuarioTitulo").textContent = u ? "Editar usuario" : "Nuevo usuario";
    $("usNombre").value = u ? u.nombre : "";
    $("usUsuario").value = u ? u.usuario : ""; $("usUsuario").disabled = !!u;
    $("usRol").innerHTML = Object.keys(usu.plantillas).map((r) => `<option value="${r}">${esc(usu.nombres[r] || r)}</option>`).join("");
    $("usRol").value = u ? (u.permisos.includes("tienda_usuarios") ? "tienda_admin" : "tienda_cajero") : "tienda_cajero";
    $("usPass").value = ""; $("usPass2").value = "";
    $("usPassEtq").textContent = u ? "Nueva contraseña (opcional)" : "Contraseña inicial";
    $("usActivo").checked = u ? u.activo : true;
    $("usActivoFila").style.display = u ? "" : "none";
    pintarPermisosUsuario(u ? u.permisos : usu.plantillas[$("usRol").value]);
    $("usError").style.display = "none"; abrirModal("mUsuario"); $("usNombre").focus();
  }
  async function guardarUsuario() {
    const id = $("usId").value;
    const permisos = Array.from(new Set(["ver_tienda", ...Array.from($("usPermisos").querySelectorAll("input[data-perm]:checked")).map((i) => i.dataset.perm)]));
    if (!$("usNombre").value.trim()) return errorEn("usError", "Escribe el nombre.");
    if (!id && !$("usUsuario").value.trim()) return errorEn("usError", "Escribe el usuario de ingreso.");
    if (!id && !$("usPass").value) return errorEn("usError", "Escribe la contraseña inicial.");
    if ($("usPass").value !== $("usPass2").value) return errorEn("usError", "Las contraseñas no coinciden.");
    const cuerpo = { nombre: $("usNombre").value, rol: $("usRol").value, permisos, password: $("usPass").value, confirmacion: $("usPass2").value };
    if (id) cuerpo.activo = $("usActivo").checked; else cuerpo.usuario = $("usUsuario").value;
    const r = await conCarga(() => api(id ? `/tienda/api/usuarios/${id}` : "/tienda/api/usuarios", cuerpo));
    if (!r.ok) return errorEn("usError", r.error);
    aplicarUsuarios(r); cerrarModales(); renderUsuarios();
  }

  // ── Eventos ──
  document.addEventListener("click", (e) => {
    const t = e.target.closest("button, [data-cat]"); if (!t) return;
    if (t.dataset.add) agregar(t.dataset.add);
    else if (t.dataset.mas) agregar(t.dataset.mas);
    else if (t.dataset.menos) quitar(t.dataset.menos);
    else if (t.dataset.cat) { ui.cat = t.dataset.cat; renderCaja(); }
    else if (t.dataset.tab) { ui.tab = t.dataset.tab; ui.cat = "Todos"; ui.q = ""; $("tBuscar").value = ""; renderCaja(); }
    else if (t.dataset.sadd) abrirSrv(t.dataset.sadd);
    else if (t.dataset.sdel) quitarServicioVenta(t.dataset.sdel);
    else if (t.dataset.sedit) abrirServicio(t.dataset.sedit);
    else if (t.dataset.squitar) quitarServicio(t.dataset.squitar);
    else if (t.dataset.modo) { $("sVariable").checked = t.dataset.modo === "variable"; pintarGananciaServicio(); }
    else if (t.dataset.scat) { $("sCat").value = t.dataset.scat; }
    else if (t.dataset.radd) { ui.reqs.push({ tipo: t.dataset.radd, texto: "", obligatorio: false }); pintarReqs(); const c = $("sReqs").querySelectorAll("[data-rtxt]"); if (c.length) c[c.length - 1].focus(); }
    else if (t.dataset.rdel !== undefined) { ui.reqs.splice(Number(t.dataset.rdel), 1); pintarReqs(); }
    else if (t.dataset.rup !== undefined) { const i = Number(t.dataset.rup); if (i > 0) { [ui.reqs[i - 1], ui.reqs[i]] = [ui.reqs[i], ui.reqs[i - 1]]; pintarReqs(); } }
    else if (t.dataset.rdown !== undefined) { const i = Number(t.dataset.rdown); if (i < ui.reqs.length - 1) { [ui.reqs[i + 1], ui.reqs[i]] = [ui.reqs[i], ui.reqs[i + 1]]; pintarReqs(); } }
    else if (t.dataset.reab) abrirReabastecer(t.dataset.reab);
    else if (t.dataset.edit) abrirProducto(t.dataset.edit);
    else if (t.dataset.hist) abrirHistorial(t.dataset.hist);
    else if (t.dataset.baja) abrirBaja(t.dataset.baja);
    else if (t.dataset.amerma) anularMerma(t.dataset.amerma);
    else if (t.dataset.mov) abrirMov(t.dataset.mov);
    else if (t.dataset.qmov) quitarMov(t.dataset.qmov);
    else if (t.dataset.rango) fijarRango(t.dataset.rango);
    else if (t.dataset.anular) abrirAnular(t.dataset.anular);
    else if (t.dataset.cedit) editarCuenta(t.dataset.cedit);
    else if (t.dataset.cdel) borrarCuenta(t.dataset.cdel);
    else if (t.dataset.uedit) abrirUsuario(t.dataset.uedit);
    else if (t.dataset.p) { ui.periodo = t.dataset.p; cargarGanancias(); }
    else if (t.hasAttribute("data-cerrar")) cerrarModales();
  });

  $("tBuscar").addEventListener("input", (e) => { ui.q = e.target.value; renderCaja(); });
  $("tVaciar").addEventListener("click", () => { ui.carrito = {}; renderCaja(); });
  $("tMetodo").addEventListener("change", renderCarrito);
  $("tRecibido").addEventListener("input", renderCarrito);
  $("tDescVal").addEventListener("input", renderCarrito);
  $("tDescTipo").addEventListener("change", renderCarrito);
  $("tCobrar").addEventListener("click", cobrar);
  $("tNuevo").addEventListener("click", () => abrirProducto(null));
  $("pGuardar").addEventListener("click", guardarProducto);
  $("sNuevo").addEventListener("click", () => abrirServicio(null));
  $("sBuscar").addEventListener("input", renderServicios);
  $("sSiguiente").addEventListener("click", siguientePasoSrv);
  $("sAtras").addEventListener("click", () => mostrarPasoSrv(Math.max(pasoSrv - 1, 0)));
  $("sGuardar").addEventListener("click", guardarServicio);
  $("mSrvAgregar").addEventListener("click", agregarServicio);
  $("sReqs").addEventListener("input", (e) => { if (e.target.dataset.rtxt !== undefined) ui.reqs[Number(e.target.dataset.rtxt)].texto = e.target.value; });
  $("sReqs").addEventListener("change", (e) => { if (e.target.dataset.robl !== undefined) ui.reqs[Number(e.target.dataset.robl)].obligatorio = e.target.checked; });
  ["sPrecio", "sTerceros", "mSrvPrecio", "mSrvTerceros"].forEach((id) => money($(id)));
  ["sPrecio", "sTerceros"].forEach((id) => $(id).addEventListener("input", pintarGananciaServicio));
  $("sVariable").addEventListener("change", pintarGananciaServicio);
  $("rGuardar").addEventListener("click", guardarReabastecer);
  $("aGuardar").addEventListener("click", guardarAnular);
  $("cuCat").innerHTML = CATS_CUENTA.map((c) => `<option>${esc(c)}</option>`).join("");
  $("bCuentas").addEventListener("click", () => { location.hash = "#cuentas"; });
  $("mcAgregar").addEventListener("click", () => abrirCuenta());
  $("mesAnt").addEventListener("click", () => mesMover(-1));
  $("mesSig").addEventListener("click", () => mesMover(1));
  $("cuGuardar").addEventListener("click", guardarCuenta);
  $("usNuevo").addEventListener("click", () => abrirUsuario(null));
  $("usGuardar").addEventListener("click", guardarUsuario);
  $("usRol").addEventListener("change", () => pintarPermisosUsuario(usu.plantillas[$("usRol").value]));
  money($("cuValor"));
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
    estado.productos = r.productos; estado.servicios = r.servicios || []; estado.ajustes = r.ajustes; estado.cuentas = r.cuentas || estado.cuentas || []; estado.abierta = r.abierta; estado.permisos = r.permisos || estado.permisos;
    fijarRango("hoy");
    irA(location.hash.replace("#", "") || "caja");
  })();
})();

/* Método de pago con botones grandes (la lista de siempre queda oculta y sigue mandando) */
(function () {
  const sel = document.getElementById("tMetodo");
  if (!sel || sel.dataset.botones) return;
  sel.dataset.botones = "1";
  const caja = document.createElement("div");
  caja.className = "t-metodos";
  const pintar = () => caja.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.m === sel.value));
  Array.from(sel.options).forEach((o) => {
    const b = document.createElement("button");
    b.type = "button"; b.dataset.m = o.value; b.textContent = o.text;
    b.addEventListener("click", () => { sel.value = o.value; sel.dispatchEvent(new Event("change")); pintar(); });
    caja.appendChild(b);
  });
  sel.style.display = "none";
  sel.insertAdjacentElement("afterend", caja);
  sel.addEventListener("change", pintar);
  pintar();
})();
