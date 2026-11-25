/* Página única del taller: formularios sin recargar, horario y accesos. */
(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function api(url, opciones) {
    const r = await fetch(url, opciones);
    let data = {};
    try { data = await r.json(); } catch (e) { /* sin cuerpo JSON */ }
    return { ok: r.ok, status: r.status, data };
  }

  /* ---------- ¿Abierto ahora? (hora de Lima) ---------- */
  function horarioActual() {
    const ahora = new Date(new Date().toLocaleString("en-US", { timeZone: "America/Lima" }));
    const dia = ahora.getDay();
    const h = ahora.getHours() + ahora.getMinutes() / 60;
    const abierto = (dia >= 1 && dia <= 5 && h >= 8 && h < 18) || (dia === 6 && h >= 8 && h < 13);
    const badge = $("[data-abierto]");
    if (badge) {
      badge.textContent = abierto ? "Abierto ahora" : "Cerrado ahora";
      badge.classList.add(abierto ? "is-open" : "is-closed");
    }
    $$("[data-horario] tr").forEach((tr) => {
      if (tr.dataset.dias.split(",").map(Number).includes(dia)) tr.classList.add("hoy");
    });
  }

  /* ---------- Agendar cita ---------- */
  const formCita = $('[data-form="cita"]');
  const ok = $("[data-cita-ok]");
  if (formCita) {
    const error = $("[data-form-error]", formCita);
    formCita.addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = new FormData(formCita);
      error.hidden = true;
      if (!f.get("fecha") || !f.get("hora")) {
        error.textContent = "Elige la fecha y la hora de tu cita.";
        error.hidden = false;
        return;
      }
      const boton = $("button", formCita);
      boton.disabled = true;
      const res = await api("/api/citas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nombre_cliente: f.get("nombre"), modelo_auto: f.get("modelo"), servicio: f.get("servicio"),
          fecha_hora: `${f.get("fecha")} ${f.get("hora")}`, telefono: f.get("telefono") || null,
          correo: f.get("correo") || null, placa: f.get("placa") || null,
        }),
      });
      boton.disabled = false;
      if (!res.ok) {
        error.textContent = res.data.error || "No se pudo registrar la cita. Inténtalo otra vez.";
        error.hidden = false;
        return;
      }
      $("[data-cita-codigo]").textContent = "#" + res.data.codigo;
      $("[data-cita-mensaje]").textContent = res.data.mensaje;
      $("[data-ver-estado]").dataset.codigo = res.data.codigo;
      formCita.hidden = true;
      ok.hidden = false;
      formCita.reset();
    });
    $("[data-otra-cita]").addEventListener("click", () => { ok.hidden = true; formCita.hidden = false; });
    $("[data-ver-estado]").addEventListener("click", (e) => {
      const codigo = e.currentTarget.dataset.codigo || $("[data-cita-codigo]").textContent.replace("#", "").trim();
      if (codigo) consultarEstado(codigo);
    });
  }

  // Botones "Agendar" / "Quiero la oferta": preseleccionan el servicio
  $$("[data-servicio]").forEach((a) => a.addEventListener("click", () => {
    const sel = formCita && $('select[name="servicio"]', formCita);
    if (sel) sel.value = a.dataset.servicio;
    if (ok) { ok.hidden = true; formCita.hidden = false; }
    setTimeout(() => $('input[name="nombre"]', formCita)?.focus({ preventScroll: true }), 500);
  }));

  /* ---------- Estado del vehículo ---------- */
  const resEstado = $("[data-estado-resultado]");
  const formEstado = $('[data-form="estado"]');
  const PASOS = [["Recepción", 1], ["Revisión", 30], ["Reparación", 60], ["Prueba final", 85], ["Listo", 100]];

  function tarjetaEstado(c) {
    const pasos = PASOS.map(([n, u]) => `<li class="${c.avance >= u ? "done" : ""}">${n}</li>`).join("");
    const av = Number(c.avance);
    return `<div class="status">
      <p class="status__title"><b>${esc(c.modelo)}</b> · placa ${esc(c.placa || "—")} · código ${esc(c.codigo)}</p>
      <p>${esc(c.servicio)}, cita del ${esc(c.fecha_hora)}.</p>
      <div class="bar"><div style="width:${av}%"></div></div>
      <p>Avance: <b>${av}%</b> · Etapa: <b>${esc(c.estado)}</b></p>
      <ol class="timeline">${pasos}</ol></div>`;
  }

  async function consultarEstado(valor) {
    valor = (valor || "").trim();
    if (!valor || !resEstado) return;
    $('input[name="q"]', formEstado).value = valor.toUpperCase();
    $("#estado").scrollIntoView({ behavior: "smooth" });
    resEstado.innerHTML = '<p class="note">Buscando…</p>';
    const res = await api("/api/estado/" + encodeURIComponent(valor));
    resEstado.innerHTML = res.data.encontrado
      ? tarjetaEstado(res.data.cita)
      : `<div class="alert alert--error">${esc(res.data.mensaje || "No encontramos ese vehículo.")}</div>`;
  }

  if (formEstado) formEstado.addEventListener("submit", (e) => { e.preventDefault(); consultarEstado($('input[name="q"]', formEstado).value); });
  const rapido = $('[data-form="estado-rapido"]');
  if (rapido) rapido.addEventListener("submit", (e) => { e.preventDefault(); consultarEstado($("input", rapido).value); });
  $$("[data-probar]").forEach((b) => b.addEventListener("click", () => consultarEstado(b.dataset.probar)));

  /* ---------- Repuestos ---------- */
  const formRep = $('[data-form="repuesto"]');
  const resRep = $("[data-repuesto-resultado]");
  if (formRep) {
    formRep.addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = new FormData(formRep);
      const q = new URLSearchParams({ pieza: f.get("pieza"), modelo: f.get("modelo") });
      const res = await api("/api/repuestos/cotizar?" + q);
      const clase = !res.ok ? "alert--error" : res.data.disponible ? "alert--ok" : "alert--warn";
      resRep.innerHTML = `<div class="alert ${clase}">${esc(res.data.mensaje || res.data.error)}</div>`;
    });
    $$("[data-cotizar]").forEach((b) => b.addEventListener("click", () => {
      $('input[name="pieza"]', formRep).value = b.dataset.cotizar;
      const modelo = $('input[name="modelo"]', formRep);
      formRep.scrollIntoView({ behavior: "smooth", block: "center" });
      if (modelo.value.trim()) formRep.requestSubmit();
      else setTimeout(() => modelo.focus(), 400);
    }));
  }

  /* ---------- Asistente ---------- */
  $$("[data-open-chat]").forEach((b) => b.addEventListener("click", () => {
    const w = $("#chatWidget");
    if (w && w.hidden) $("#chatFab").click();
  }));

  /* ---------- Menú móvil: cerrar al elegir ---------- */
  $$(".nav a").forEach((a) => a.addEventListener("click", () => { const m = $("#menu"); if (m) m.checked = false; }));

  /* ---------- Sección inicial (rutas /citas, /estado, /repuestos) ---------- */
  const inicial = $("[data-seccion-inicial]")?.dataset.seccionInicial;
  if (inicial && !location.hash) document.getElementById(inicial)?.scrollIntoView();

  horarioActual();
})();
