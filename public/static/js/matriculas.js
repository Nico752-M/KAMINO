(function () {
  "use strict";
  const modal = document.getElementById("matriculaModal");
  const abrir = document.getElementById("btnNuevaMatricula");
  if (!modal || !abrir) return;

  const precioBase = document.getElementById("precioBase");
  const categoria = document.getElementById("matriculaCategoria");
  const tipoMatricula = document.getElementById("tipoMatricula");
  const documento = document.getElementById("matriculaDocumento");
  const lookupMessage = document.getElementById("matriculaLookupMessage");
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
  const soloDigitos = (valor) => Number.parseInt(window.soloDigitos(valor), 10) || 0;

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
    if (pasoActual === 0 && categoria.value) {
      const vistas = [categoria.value];
      for (const cat of document.querySelectorAll("#cursosExtraCat [data-x-cat]")) {
        if (!cat.value) {
          cat.focus();
          alert("Selecciona la categoría de cada curso adicional o quítalo.");
          return false;
        }
        if (vistas.includes(cat.value)) {
          cat.focus();
          alert("No puedes repetir la misma categoría (" + cat.value + ").");
          return false;
        }
        vistas.push(cat.value);
      }
    }
    if (pasoActual === pasos.length - 1) {
      for (const fila of document.querySelectorAll("#cursosExtra > div")) {
        if (!fila.querySelector("[name='extra_precio_base']").value) {
          fila.querySelector("[data-x-base]").focus();
          alert("Escribe el precio base de cada curso adicional.");
          return false;
        }
      }
    }
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

  const abonoInicial = document.getElementById("abonoInicial");
  const saldoVisible = document.getElementById("saldoVisible");
  const hintTotalCurso = document.getElementById("hintTotalCurso");

  function mostrarSaldo() {
    actualizarResumen();
    const total = soloDigitos(precioTotal.value);
    const abono = soloDigitos(abonoInicial.value);
    if (!total) {
      saldoVisible.value = "";
      hintTotalCurso.textContent = "El total se calcula con el precio y el descuento.";
      return;
    }
    const saldo = Math.max(total - abono, 0);
    saldoVisible.value = "$ " + window.formatearMiles(saldo);
    hintTotalCurso.textContent = "Total del curso: $ " + window.formatearMiles(total) +
      " − abono: $ " + window.formatearMiles(Math.min(abono, total));
  }

  function calcularTotal() {
    const base = soloDigitos(precioBase.value);
    const pesos = soloDigitos(descuentoPesos.value);
    const porcentaje = Number(descuentoPorcentaje.value) || 0;
    const descuento = pesos || Math.round(base * porcentaje / 100);
    precioTotal.value = base ? String(Math.max(base - descuento, 0)) : "";
    mostrarSaldo();
  }

  const opcionesTarifas = [...categoria.options].map((opcion) => ({
    value: opcion.value,
    text: opcion.textContent,
    price: opcion.dataset.price || "",
    type: opcion.dataset.tariffType || "",
  })).filter((opcion) => opcion.value);

  function filtrarTarifas() {
    const tipo = tipoMatricula.value === "renovacion" ? "RENOVACION" : "CURSO";
    const seleccion = categoria.value;
    categoria.innerHTML = "";

    const opcionVacia = document.createElement("option");
    opcionVacia.value = "";
    opcionVacia.textContent = "Selecciona";
    categoria.appendChild(opcionVacia);

    const filtradas = opcionesTarifas.filter((opcion) => opcion.type === tipo);
    filtradas.forEach((opcion) => {
      const elemento = document.createElement("option");
      elemento.value = opcion.value;
      elemento.textContent = opcion.text;
      elemento.dataset.price = opcion.price;
      elemento.dataset.tariffType = opcion.type;
      categoria.appendChild(elemento);
    });

    categoria.value = filtradas.some((opcion) => opcion.value === seleccion) ? seleccion : "";
    precioBase.value = "";
    calcularTotal();
  }
  categoria.addEventListener("change", () => {
    const precio = categoria.selectedOptions[0]?.dataset.price;
    precioBase.value = precio ? window.formatearMiles(precio) : "";
    calcularTotal();
  });
  tipoMatricula.addEventListener("change", filtrarTarifas);
  filtrarTarifas();

  const camposAlumno = {
    tipo_documento: document.getElementById("matriculaTipoDocumento"),
    nombres: document.getElementById("matriculaNombres"),
    apellidos: document.getElementById("matriculaApellidos"),
    fecha_nacimiento: document.getElementById("fechaNacimiento"),
    lugar_nacimiento: document.getElementById("lugarNacimiento"),
    sexo: document.getElementById("sexoAlumno"),
    estado_civil: document.getElementById("estadoCivil"),
    grupo_sanguineo: document.getElementById("grupoSanguineo"),
    ocupacion: document.getElementById("ocupacionAlumno"),
    celular: document.getElementById("celularAlumno"),
    email: document.getElementById("emailAlumno"),
  };
  let autocompletados = {};
  let consultaDocumento = 0;
  documento.addEventListener("blur", async () => {
    const numero = documento.value.trim();
    if (!numero) return;
    Object.entries(autocompletados).forEach(([nombre, valor]) => {
      if (camposAlumno[nombre].value === valor) camposAlumno[nombre].value = "";
    });
    autocompletados = {};
    const consulta = ++consultaDocumento;
    lookupMessage.textContent = "Buscando alumno...";
    try {
      const base = documento.dataset.documentLookupUrl.replace("DOCUMENTO", encodeURIComponent(numero));
      const respuesta = await fetch(base, { credentials: "same-origin" });
      const resultado = await respuesta.json();
      if (consulta !== consultaDocumento || documento.value.trim() !== numero) return;
      if (!respuesta.ok || !resultado.ok) {
        lookupMessage.textContent = resultado.error || "No se pudo consultar el documento.";
        return;
      }
      if (!resultado.encontrado) {
        lookupMessage.textContent = "Alumno nuevo. Completa sus datos en el siguiente paso.";
        return;
      }
      Object.entries(camposAlumno).forEach(([nombre, campo]) => {
        const valor = resultado.alumno[nombre] || "";
        if (valor && !campo.value) {
          campo.value = valor;
          autocompletados[nombre] = valor;
        }
      });
      lookupMessage.textContent = "Datos encontrados y precargados.";
    } catch (error) {
      if (consulta === consultaDocumento) {
        lookupMessage.textContent = "No se pudo consultar el documento. Revisa la conexión e intenta de nuevo.";
      }
    }
  });

  precioBase.addEventListener("input", calcularTotal);
  descuentoPesos.addEventListener("input", () => {
    if (descuentoPesos.value) descuentoPorcentaje.value = "";
    calcularTotal();
  });
  descuentoPorcentaje.addEventListener("input", () => {
    if (descuentoPorcentaje.value) descuentoPesos.value = "";
    calcularTotal();
  });
  // El total ya no se edita a mano: se calcula con el precio base y el descuento.
  abonoInicial.addEventListener("input", mostrarSaldo);

  // Alumno que ya venía cursando: pide la fecha original y trata el abono como "ya pagado"
  const enCurso = document.getElementById("alumnoEnCurso");
  const bloqueEnCurso = document.getElementById("bloqueEnCurso");
  const fechaOriginal = document.getElementById("fechaMatriculaOriginal");
  function actualizarEnCurso() {
    const activo = enCurso.checked;
    bloqueEnCurso.style.display = activo ? "" : "none";   // (el atributo hidden pierde contra display:grid)
    fechaOriginal.required = activo;
    const hoyLocal = new Date();
    fechaOriginal.max = hoyLocal.getFullYear() + "-" +
      String(hoyLocal.getMonth() + 1).padStart(2, "0") + "-" + String(hoyLocal.getDate()).padStart(2, "0");
    document.getElementById("campoMetodoPago").style.display = activo ? "none" : "";
    document.getElementById("lblAbonoInicial").textContent =
      activo ? "Lo que ya ha pagado hasta hoy (COP)" : "Abono inicial (COP)";
    document.getElementById("hintAbonoInicial").textContent =
      activo ? "Escribe 0 si aún no ha pagado nada." : "Escribe 0 si no paga ahora.";
  }
  enCurso.addEventListener("change", actualizarEnCurso);

  // ── Cursos adicionales (ej. A1 y B2 para el mismo alumno) ──────────────────────────
  // La categoría de cada curso extra se elige en el paso 1 (#cursosExtraCat);
  // su precio, descuento y abono se llenan en el paso 4 (#cursosExtra). Van en el mismo orden.
  const cursosExtraCat = document.getElementById("cursosExtraCat");
  const cursosExtra = document.getElementById("cursosExtra");
  const btnAgregarCurso = document.getElementById("btnAgregarCurso");
  const MAX_CURSOS_EXTRA = 4;

  function opcionesCategoria() {
    const tipo = tipoMatricula.value === "renovacion" ? "RENOVACION" : "CURSO";
    return opcionesTarifas.filter((o) => o.type === tipo);
  }

  function actualizarResumen() {
    const caja = document.getElementById("resumenTotal");
    if (!caja) return;
    const filas = [...document.querySelectorAll("#cursosExtra > div")];
    caja.style.display = filas.length ? "" : "none";
    const titulo = document.getElementById("tituloCurso1");
    titulo.style.display = filas.length ? "" : "none";
    titulo.textContent = "Curso 1 · " + (categoria.value || "sin categoría");
    let total = soloDigitos(precioTotal.value);
    let abonos = Math.min(soloDigitos(abonoInicial.value), total);
    filas.forEach((fila) => {
      const t = soloDigitos(fila.querySelector("[name='extra_precio_total']").value);
      const a = soloDigitos(fila.querySelector("[name='extra_abono']").value);
      total += t;
      abonos += Math.min(a, t);
    });
    document.getElementById("resTotal").textContent = "$ " + window.formatearMiles(total);
    document.getElementById("resAbonos").textContent = "$ " + window.formatearMiles(abonos);
    document.getElementById("resSaldo").textContent = "$ " + window.formatearMiles(Math.max(total - abonos, 0));
  }

  function recalcularFila(fila) {
    const base = soloDigitos(fila.querySelector("[data-x-base]").value);
    const pesos = soloDigitos(fila.querySelector("[data-x-desc]").value);
    const total = Math.max(base - pesos, 0);
    fila.querySelector("[name='extra_precio_base']").value = base ? String(base) : "";
    fila.querySelector("[name='extra_precio_total']").value = base ? String(total) : "";
    const abono = soloDigitos(fila.querySelector("[name='extra_abono']").value);
    fila.querySelector("[data-x-saldo]").textContent =
      base ? "Total del curso: $ " + window.formatearMiles(total) + " · Saldo: $ " + window.formatearMiles(Math.max(total - abono, 0)) : "";
    actualizarResumen();
  }

  function numerarFilas() {
    [...cursosExtraCat.children].forEach((filaCat, i) => {
      filaCat.querySelector("[data-x-titulo]").textContent = "Curso " + (i + 2);
      const filaPrecio = cursosExtra.children[i];
      if (filaPrecio) {
        const cat = filaCat.querySelector("[data-x-cat]").value;
        filaPrecio.querySelector("[data-x-titulo]").textContent = "Curso " + (i + 2) + (cat ? " · " + cat : "");
      }
    });
    btnAgregarCurso.hidden = cursosExtraCat.children.length >= MAX_CURSOS_EXTRA;
    actualizarResumen();
  }

  function limpiarExtras() {
    cursosExtraCat.innerHTML = "";
    cursosExtra.innerHTML = "";
    numerarFilas();
  }

  function aplicarEnCursoAFilas() {
    const activo = enCurso.checked;
    cursosExtra.querySelectorAll("[data-x-encurso]").forEach((el) => {
      el.style.display = activo ? "" : "none";
    });
  }

  function agregarCurso() {
    if (cursosExtraCat.children.length >= MAX_CURSOS_EXTRA) return;

    // Paso 1: solo la categoría
    const filaCat = document.createElement("div");
    filaCat.style.cssText = "display:flex;gap:.5rem;align-items:flex-end;margin-top:.5rem";
    filaCat.innerHTML =
      '<div class="field" style="flex:1;margin:0"><label class="lbl"><span data-x-titulo></span> <span class="required-mark">*</span></label>' +
        '<select class="input-clean" name="extra_categoria" data-x-cat></select></div>' +
      '<button type="button" class="btn-action" data-x-quitar aria-label="Quitar curso"><i class="ri-delete-bin-line"></i> Quitar</button>';
    const select = filaCat.querySelector("[data-x-cat]");
    select.innerHTML = '<option value="">Selecciona</option>';
    opcionesCategoria().forEach((o) => {
      const op = document.createElement("option");
      op.value = o.value; op.textContent = o.text; op.dataset.price = o.price;
      select.appendChild(op);
    });

    // Paso 4: precio, descuento y abono de ese curso
    const fila = document.createElement("div");
    fila.className = "form-section";
    fila.style.cssText = "border:1px solid var(--border,#d9dee7);border-radius:10px;padding:.75rem;margin-bottom:.75rem";
    fila.innerHTML =
      '<strong data-x-titulo style="display:block;margin-bottom:.5rem"></strong>' +
      '<div class="form-grid two">' +
        '<div class="field"><label class="lbl">Precio base (COP)</label>' +
          '<input class="input-clean" inputmode="numeric" data-money-input data-x-base>' +
          '<input type="hidden" name="extra_precio_base">' +
          '<input type="hidden" name="extra_precio_total"></div>' +
        '<div class="field"><label class="lbl">Descuento ($)</label>' +
          '<input class="input-clean" inputmode="numeric" data-money-input data-x-desc placeholder="Ej: 50.000"></div>' +
        '<div class="field"><label class="lbl">Abono / ya pagado (COP)</label>' +
          '<input class="input-clean" inputmode="numeric" data-money-input name="extra_abono" value="0">' +
          '<p class="hint" data-x-saldo></p></div>' +
        '<div class="field" data-x-encurso><label class="lbl">Fecha en que se matriculó</label>' +
          '<input class="input-clean" type="date" name="extra_fecha"></div>' +
        '<div class="field" data-x-encurso><label class="lbl">¿Ya está en el RUNT?</label>' +
          '<select class="input-clean" name="extra_runt"><option value="0">No</option><option value="1">Sí</option></select></div>' +
      '</div>';

    select.addEventListener("change", () => {
      const precio = select.selectedOptions[0]?.dataset.price;
      fila.querySelector("[data-x-base]").value = precio ? window.formatearMiles(precio) : "";
      recalcularFila(fila);
      numerarFilas();
    });
    fila.addEventListener("input", () => recalcularFila(fila));
    filaCat.querySelector("[data-x-quitar]").addEventListener("click", () => {
      filaCat.remove();
      fila.remove();
      numerarFilas();
    });
    fila.querySelector("[name='extra_fecha']").value = fechaOriginal.value || "";
    fila.querySelector("[name='extra_fecha']").max = fechaOriginal.max || "";
    cursosExtraCat.appendChild(filaCat);
    cursosExtra.appendChild(fila);
    numerarFilas();
    aplicarEnCursoAFilas();
    select.focus();
  }

  btnAgregarCurso.addEventListener("click", agregarCurso);
  enCurso.addEventListener("change", aplicarEnCursoAFilas);
  // Al cambiar entre Curso completo / Renovación las categorías disponibles cambian: se limpian las filas
  tipoMatricula.addEventListener("change", limpiarExtras);

  const cerrar = () => modal.classList.remove("open");
  abrir.addEventListener("click", () => {
    form.reset();
    limpiarExtras();
    actualizarEnCurso();
    autocompletados = {};
    lookupMessage.textContent = "";
    descuentoPesos.value = "";
    descuentoPorcentaje.value = "";
    form.querySelectorAll("[data-money-input]").forEach(window.formatearCampoMoneda);
    filtrarTarifas();
    mostrarSaldo();
    mostrarPaso(0);
    modal.classList.add("open");
    document.getElementById("matriculaDocumento").focus();
  });
  // «Agregar otra categoría»: abre la matrícula con el documento del alumno ya puesto
  document.addEventListener("click", (evento) => {
    const enlace = evento.target.closest(".js-otra-categoria");
    if (!enlace) return;
    evento.preventDefault();
    enlace.closest("details")?.removeAttribute("open");
    abrir.click();
    documento.value = enlace.dataset.documento;
    documento.dispatchEvent(new Event("blur"));
    categoria.focus();
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
})();
