/* Marcar un alumno como "registrado en el RUNT" */
document.querySelectorAll(".js-runt").forEach(function (btn) {
  btn.addEventListener("click", async function () {
    if (!confirm("¿Confirma que " + btn.dataset.nombre + " ya fue registrado en el RUNT?")) return;
    btn.disabled = true;
    const r = await window.postJSON("/tramites/runt/" + btn.dataset.id, {});
    if (r.ok) { window.location.reload(); }
    else { btn.disabled = false; alert(r.error || "No se pudo actualizar."); }
  });
});
