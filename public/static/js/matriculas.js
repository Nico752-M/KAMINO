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
    precioTotal.value = base ? window.formatearMiles(Math.max(base - descuento, 0)) : "";
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
  precioTotal.addEventListener("input", () => {
    const base = soloDigitos(precioBase.value);
    const total = soloDigitos(precioTotal.value);
    descuentoPesos.value = base && total <= base ? window.formatearMiles(base - total) : "";
    descuentoPorcentaje.value = "";
  });

  const cerrar = () => modal.classList.remove("open");
  abrir.addEventListener("click", () => {
    form.reset();
    autocompletados = {};
    lookupMessage.textContent = "";
    descuentoPesos.value = "";
    descuentoPorcentaje.value = "";
    form.querySelectorAll("[data-money-input]").forEach(window.formatearCampoMoneda);
    filtrarTarifas();
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
