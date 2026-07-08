function formatWhatsappCompact(seconds) {
  const safe = Math.max(0, Number(seconds) || 0);
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function closeWhatsappWindow(element) {
  element.dataset.windowState = "expired";
  element.dataset.remainingSeconds = "0";
  element.classList.remove("active", "warning", "urgent");
  element.classList.add("expired");
  const label = element.querySelector("[data-window-label]");
  if (label) label.textContent = element.dataset.windowKind === "responsible" ? "- vencida" : "fechada";

  document.querySelectorAll(".message-composer").forEach((composer) => {
    composer.classList.add("whatsapp-window-closed");
    if (!composer.querySelector(".composer-window-alert")) {
      const message = document.createElement("div");
      message.className = "composer-window-alert";
      message.textContent = "A janela de atendimento do WhatsApp expirou. Envie um modelo aprovado e aguarde uma nova mensagem do cliente.";
      composer.querySelector(".composer-tabs")?.after(message);
    }
    const textarea = composer.querySelector("textarea");
    if (textarea) {
      textarea.disabled = !composer.classList.contains("is-internal-mode");
    }
  });
  document.querySelectorAll(".message-composer [data-attach-button], .message-composer [data-audio-button]").forEach((control) => {
    control.setAttribute("disabled", "disabled");
  });
}

function tickWhatsappWindow(element) {
  const state = element.dataset.windowState || "";
  if (!["active", "warning", "urgent"].includes(state)) return;
  const next = Math.max(0, Number(element.dataset.remainingSeconds || "0") - 1);
  element.dataset.remainingSeconds = String(next);
  if (next <= 0) {
    closeWhatsappWindow(element);
    return;
  }
  const label = element.querySelector("[data-window-label]");
  if (label) label.textContent = element.dataset.windowKind === "responsible" ? `- ${formatWhatsappCompact(next)}` : formatWhatsappCompact(next);
}

document.addEventListener("DOMContentLoaded", () => {
  const timers = Array.from(document.querySelectorAll("[data-whatsapp-window]"));
  if (timers.length) {
    setInterval(() => {
      timers.forEach(tickWhatsappWindow);
    }, 1000);
  }

  document.querySelectorAll("[data-template-search]").forEach((input) => {
    input.addEventListener("input", () => {
      const query = input.value.trim().toLowerCase();
      document.querySelectorAll("[data-template-item]").forEach((item) => {
        item.hidden = query && !(item.dataset.templateName || "").includes(query);
      });
    });
  });
});
