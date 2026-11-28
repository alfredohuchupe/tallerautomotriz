/* Asistente virtual: widget flotante y página completa. */
(function () {
  const fab = document.getElementById("chatFab");
  const widget = document.getElementById("chatWidget");
  const root = widget || document.getElementById("chatPage");
  if (!root) return;

  const log = root.querySelector("[data-chat-log]");
  const form = root.querySelector("[data-chat-form]");
  const input = form.querySelector("input");
  const micBtn = root.querySelector("[data-chat-mic]");

  if (fab && widget) {
    fab.addEventListener("click", () => {
      widget.hidden = !widget.hidden;
      if (!widget.hidden) input.focus();
    });
    root.querySelector("[data-chat-close]").addEventListener("click", () => (widget.hidden = true));
    if (fab.hasAttribute("data-open")) widget.hidden = false; // ruta /asistente
  }

  function add(text, cls) {
    const div = document.createElement("div");
    div.className = "msg " + cls;
    // Texto seguro: se escapa y solo se convierte **negrita** a <b>
    const seguro = String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    div.innerHTML = seguro.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  async function send(text) {
    text = (text || "").trim();
    if (!text) return;
    add(text, "msg--user");
    input.value = "";
    const typing = add("Pensando…", "msg--bot msg--typing");
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensaje: text }),
      });
      const data = await r.json();
      typing.remove();
      if (!r.ok) return add("⚠️ " + (data.error || "Error"), "msg--bot");
      (data.funciones || []).forEach((f) =>
        add("🔧 Function Calling → " + f.funcion + " " + JSON.stringify(f.argumentos), "msg--fn")
      );
      add(data.respuesta, "msg--bot");
    } catch (e) {
      typing.remove();
      add("❌ No se pudo conectar con el asistente.", "msg--bot");
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    send(input.value);
  });
  root.querySelectorAll("[data-chip]").forEach((b) =>
    b.addEventListener("click", () => send(b.dataset.chip))
  );
  root.querySelector("[data-chat-reset]").addEventListener("click", async () => {
    const r = await fetch("/api/chat/reiniciar", { method: "POST" });
    const data = await r.json();
    log.innerHTML = "";
    add(data.respuesta, "msg--bot");
  });

  // Entrada por voz (Web Speech API del navegador)
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    micBtn.hidden = true;
  } else {
    const rec = new SR();
    rec.lang = "es-PE";
    rec.interimResults = false;
    rec.onresult = (ev) => {
      const texto = ev.results[0][0].transcript;
      add("🎙️ Texto transcrito: " + texto, "msg--fn");
      send(texto);
    };
    rec.onend = () => micBtn.classList.remove("on");
    micBtn.addEventListener("click", () => {
      micBtn.classList.add("on");
      rec.start();
    });
  }
})();
