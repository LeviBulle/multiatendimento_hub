function applyQuickReply(content) {
  const textarea = document.querySelector("#message_text");
  if (!textarea) return;
  textarea.value = content;
  textarea.dataset.quickReplyJustApplied = String(Date.now());
  resizeComposerTextarea(textarea);
  textarea.focus();
}

function applyQuickReplyButton(button) {
  if (!button) return false;
  applyQuickReply(decodeURIComponent(button.dataset.quickText || ""));
  const menu = document.querySelector("[data-quick-reply-menu]");
  if (menu) menu.classList.remove("is-open");
  return true;
}

function selectQuickReplyOption(menu, nextIndex) {
  const options = Array.from(menu.querySelectorAll("[data-quick-text]"));
  if (!options.length) return;
  const normalizedIndex = (nextIndex + options.length) % options.length;
  options.forEach((option, index) => {
    option.classList.toggle("is-selected", index === normalizedIndex);
    option.setAttribute("aria-selected", index === normalizedIndex ? "true" : "false");
  });
}

function selectedQuickReplyOption(menu) {
  return menu.querySelector("[data-quick-text].is-selected") || menu.querySelector("[data-quick-text]");
}

function selectMenuOption(menu, selector, selectedClass, nextIndex) {
  const options = Array.from(menu.querySelectorAll(selector));
  if (!options.length) return;
  const normalizedIndex = (nextIndex + options.length) % options.length;
  options.forEach((option, index) => {
    option.classList.toggle(selectedClass, index === normalizedIndex);
    option.setAttribute("aria-selected", index === normalizedIndex ? "true" : "false");
  });
}

function currentMentionToken(textarea) {
  const cursor = textarea.selectionStart || textarea.value.length;
  const beforeCursor = textarea.value.slice(0, cursor);
  const match = beforeCursor.match(/(^|\s)@([\p{L}\p{N}._-]*)$/u);
  if (!match) return null;
  return {
    start: beforeCursor.length - match[0].trimStart().length,
    end: cursor,
    query: match[2].toLocaleLowerCase("pt-BR"),
  };
}

function insertMention(textarea, mention) {
  const token = currentMentionToken(textarea);
  if (!token) return false;
  textarea.value = `${textarea.value.slice(0, token.start)}${mention} ${textarea.value.slice(token.end)}`;
  textarea.selectionStart = token.start + mention.length + 1;
  textarea.selectionEnd = token.start + mention.length + 1;
  resizeComposerTextarea(textarea);
  textarea.focus();
  const menu = document.querySelector("[data-mention-menu]");
  if (menu) menu.classList.remove("is-open");
  return true;
}

function selectedMentionOption(menu) {
  return menu.querySelector("[data-mention-text].is-selected") || menu.querySelector("[data-mention-text]");
}

function insertAtCursor(textarea, value) {
  const start = textarea.selectionStart || 0;
  const end = textarea.selectionEnd || 0;
  textarea.value = `${textarea.value.slice(0, start)}${value}${textarea.value.slice(end)}`;
  textarea.selectionStart = start + value.length;
  textarea.selectionEnd = start + value.length;
  textarea.focus();
}

function resizeComposerTextarea(textarea) {
  textarea.style.height = "24px";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 96)}px`;
}

function onlyDigits(value) {
  return (value || "").replace(/\D/g, "");
}

function titleCase(value) {
  return (value || "").toLocaleLowerCase("pt-BR").replace(/\b\p{L}/gu, (letter) => letter.toLocaleUpperCase("pt-BR"));
}

function maskBirthDate(value) {
  const digits = onlyDigits(value).slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

function maskCpf(value) {
  const digits = onlyDigits(value).slice(0, 11);
  if (digits.length <= 3) return digits;
  if (digits.length <= 6) return `${digits.slice(0, 3)}.${digits.slice(3)}`;
  if (digits.length <= 9) return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6)}`;
  return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9)}`;
}

function maskPhoneNumber(value) {
  const digits = onlyDigits(value).slice(0, 9);
  if (digits.length <= 4) return digits;
  if (digits.length <= 8) return `${digits.slice(0, 4)}-${digits.slice(4)}`;
  return `${digits.slice(0, 5)}-${digits.slice(5)}`;
}

function composePhoneFromPanel(panel) {
  const country = onlyDigits(panel.querySelector("[name='phone_country_code']")?.value || "");
  const ddd = onlyDigits(panel.querySelector("[name='phone_area_code']")?.value || "");
  const number = panel.querySelector("[name='phone_number']")?.value || "";
  return [country ? `+${country}` : "", ddd, number].filter(Boolean).join(" ");
}

function extractNumberAfterDdd(fullPhone) {
  const digits = onlyDigits(fullPhone);
  if (digits.length >= 13) return maskPhoneNumber(digits.slice(4));
  if (digits.length >= 12) return maskPhoneNumber(digits.slice(4));
  if (digits.length >= 10) return maskPhoneNumber(digits.slice(2));
  return maskPhoneNumber(digits);
}

async function copyToClipboard(value, feedbackButton) {
  const text = value || "";
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      const helper = document.createElement("textarea");
      helper.value = text;
      helper.setAttribute("readonly", "");
      helper.style.position = "fixed";
      helper.style.left = "-9999px";
      document.body.appendChild(helper);
      helper.select();
      document.execCommand("copy");
      helper.remove();
    }
  } catch (error) {
    const helper = document.createElement("textarea");
    helper.value = text;
    helper.setAttribute("readonly", "");
    helper.style.position = "fixed";
    helper.style.left = "-9999px";
    document.body.appendChild(helper);
    helper.select();
    document.execCommand("copy");
    helper.remove();
  }
  if (!feedbackButton) return;
  const original = feedbackButton.textContent;
  feedbackButton.textContent = "ok";
  setTimeout(() => { feedbackButton.textContent = original; }, 900);
}

function fillShortcut(shortcutMap) {
  const textarea = document.querySelector("#message_text");
  if (!textarea) return;
  const value = textarea.value.trim();
  if (shortcutMap[value]) {
    textarea.value = shortcutMap[value];
  }
}

function openModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  const firstInput = modal.querySelector("input, select, textarea, button");
  if (firstInput) firstInput.focus();
}

function closeModal(modal) {
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
}

function scrollConversationToLatest() {
  const messagePane = document.querySelector(".conversation-messages");
  if (!messagePane) return;
  messagePane.scrollTop = messagePane.scrollHeight;
}

function focusMessageComposer() {
  const textarea = document.querySelector("#message_text");
  if (!textarea) return;
  textarea.focus({ preventScroll: true });
}

function setEllubCollapsed(collapsed) {
  const sideNav = document.querySelector(".side-nav");
  const toggle = document.querySelector("[data-toggle-ellub]");
  if (!sideNav || !toggle) return;
  sideNav.classList.toggle("ellub-collapsed", collapsed);
  toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
  localStorage.setItem("ellubMenuCollapsed", collapsed ? "1" : "0");
}

function setSidebarCompact(compact) {
  const appLayout = document.querySelector(".app-layout");
  const toggle = document.querySelector("[data-toggle-sidebar]");
  if (!appLayout || !toggle) return;
  appLayout.classList.toggle("sidebar-compact", compact);
  toggle.setAttribute("aria-label", compact ? "Mostrar menu lateral" : "Ocultar menu lateral");
  toggle.setAttribute("title", compact ? "Mostrar menu lateral" : "Ocultar menu lateral");
  localStorage.setItem("ellubSidebarCompact", compact ? "1" : "0");
}

document.addEventListener("DOMContentLoaded", () => {
  const csrf = document.querySelector("meta[name='csrf-token']")?.content || "";
  document.querySelectorAll("form[method='post']").forEach((form) => {
    if (!form.querySelector("input[name='csrf_token']")) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "csrf_token";
      input.value = csrf;
      form.prepend(input);
    }
  });
  setEllubCollapsed(localStorage.getItem("ellubMenuCollapsed") === "1");
  setSidebarCompact(localStorage.getItem("ellubSidebarCompact") === "1");
  document.querySelectorAll("#message_text").forEach(resizeComposerTextarea);
  document.querySelectorAll("[data-mask-birth-date]").forEach((input) => { input.value = maskBirthDate(input.value); });
  document.querySelectorAll("[data-mask-cpf]").forEach((input) => { input.value = maskCpf(input.value); });
  document.querySelectorAll("[data-mask-country]").forEach((input) => {
    const digits = onlyDigits(input.value).slice(0, 3);
    input.value = digits ? `+${digits}` : "";
  });
  document.querySelectorAll("[data-mask-ddd]").forEach((input) => { input.value = onlyDigits(input.value).slice(0, 2); });
  document.querySelectorAll("[data-mask-phone-number]").forEach((input) => { input.value = maskPhoneNumber(input.value); });
  const card = document.querySelector(".nexys-card");
  if (card) card.classList.toggle("client-panel-hidden", localStorage.getItem("ellubClientPanelHidden") === "1");
  document.documentElement.dataset.theme = localStorage.getItem("ellubTheme") || "light";
  scrollConversationToLatest();
  focusMessageComposer();
});

window.addEventListener("load", () => {
  scrollConversationToLatest();
  focusMessageComposer();
});

document.addEventListener("click", (event) => {
  const sidebarToggle = event.target.closest("[data-toggle-sidebar]");
  if (sidebarToggle) {
    return;
  }

  const ellubToggle = event.target.closest("[data-toggle-ellub]");
  if (ellubToggle) {
    return;
  }

  const opener = event.target.closest("[data-open-modal]");
  if (opener) {
    openModal(opener.dataset.openModal);
    return;
  }

  const clientPanelToggle = event.target.closest("[data-toggle-client-panel]");
  if (clientPanelToggle) {
    const card = document.querySelector(".nexys-card");
    if (card) {
      const hidden = !card.classList.contains("client-panel-hidden");
      card.classList.toggle("client-panel-hidden", hidden);
      localStorage.setItem("ellubClientPanelHidden", hidden ? "1" : "0");
    }
    return;
  }

  const copyButton = event.target.closest("[data-copy-field]");
  if (copyButton) {
    const field = copyButton.parentElement.querySelector("input, textarea");
    if (field) {
      copyToClipboard(field.value || "", copyButton);
    }
    return;
  }

  const copyText = event.target.closest("[data-copy-text]");
  if (copyText) {
    copyToClipboard(copyText.dataset.copyText || copyText.textContent.trim());
    return;
  }

  const copyHeaderPhone = event.target.closest("[data-copy-phone-header]");
  if (copyHeaderPhone) {
    copyToClipboard(copyHeaderPhone.dataset.phoneNumber || extractNumberAfterDdd(copyHeaderPhone.dataset.phoneFull || copyHeaderPhone.textContent));
    return;
  }

  const copyPhoneFull = event.target.closest("[data-copy-phone-full]");
  if (copyPhoneFull) {
    const panel = copyPhoneFull.closest(".phone-field");
    if (panel) copyToClipboard(composePhoneFromPanel(panel), copyPhoneFull);
    return;
  }

  const copyPhoneNumber = event.target.closest("[data-copy-phone-number]");
  if (copyPhoneNumber) {
    const panel = copyPhoneNumber.closest(".phone-field");
    const number = panel ? panel.querySelector("[name='phone_number']")?.value : "";
    copyToClipboard(number || "", copyPhoneNumber);
    return;
  }

  const menuToggle = event.target.closest("[data-toggle-menu]");
  if (menuToggle) {
    event.stopPropagation();
    const menu = document.getElementById(menuToggle.dataset.toggleMenu);
    if (menu) menu.classList.toggle("is-open");
    return;
  }

  if (event.target.matches("[data-close-modal]")) {
    closeModal(event.target.closest(".modal-backdrop"));
    return;
  }

  if (event.target.classList.contains("modal-backdrop")) {
    closeModal(event.target);
  }

  const themeToggle = event.target.closest("[data-theme-toggle]");
  if (themeToggle) {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("ellubTheme", next);
    return;
  }

  document.querySelectorAll(".action-menu.is-open, .notification-menu.is-open, .account-menu.is-open").forEach((menu) => {
    if (!menu.contains(event.target)) menu.classList.remove("is-open");
  });
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  document.querySelectorAll(".modal-backdrop.is-open").forEach(closeModal);
  document.querySelectorAll(".action-menu.is-open, .notification-menu.is-open, .account-menu.is-open").forEach((menu) => menu.classList.remove("is-open"));
});

document.addEventListener("change", (event) => {
  const mode = event.target.closest("input[name='composer_mode']");
  if (mode) {
    const composer = mode.closest(".message-composer");
    const internalInput = composer ? composer.querySelector("input[name='is_internal']") : null;
    const textarea = composer ? composer.querySelector("#message_text") : null;
    const isInternal = mode.value === "internal";
    const isWindowClosed = composer ? composer.classList.contains("whatsapp-window-closed") : false;
    if (composer) composer.classList.toggle("is-internal-mode", isInternal);
    if (internalInput) internalInput.value = isInternal ? "true" : "";
    if (textarea) {
      textarea.placeholder = isInternal
        ? "Escreva uma anotacao interna para este atendimento."
        : "Digite sua mensagem ou use / para mensagens padrao.";
      textarea.disabled = isWindowClosed && !isInternal;
      if (!textarea.disabled) textarea.focus();
    }
  }

  const attachment = event.target.closest("#attachment_input");
  if (attachment) {
    const chip = document.querySelector("[data-attachment-chip]");
    if (chip && attachment.files.length) {
      chip.textContent = attachment.files[0].name;
      chip.hidden = false;
    }
  }
});

document.addEventListener("input", (event) => {
  const birthDate = event.target.closest("[data-mask-birth-date]");
  if (birthDate) birthDate.value = maskBirthDate(birthDate.value);

  const cpf = event.target.closest("[data-mask-cpf]");
  if (cpf) cpf.value = maskCpf(cpf.value);

  const country = event.target.closest("[data-mask-country]");
  if (country) {
    const digits = onlyDigits(country.value).slice(0, 3);
    country.value = digits ? `+${digits}` : "";
  }

  const ddd = event.target.closest("[data-mask-ddd]");
  if (ddd) ddd.value = onlyDigits(ddd.value).slice(0, 2);

  const phoneNumber = event.target.closest("[data-mask-phone-number]");
  if (phoneNumber) phoneNumber.value = maskPhoneNumber(phoneNumber.value);

  const upperName = event.target.closest("[data-name-upper]");
  if (upperName) upperName.value = upperName.value.toLocaleUpperCase("pt-BR");

  const textarea = event.target.closest("#message_text");
  if (!textarea) return;
  resizeComposerTextarea(textarea);
  const menu = document.querySelector("[data-quick-reply-menu]");
  const mentionMenu = document.querySelector("[data-mention-menu]");
  if (!menu) return;
  const shortcuts = JSON.parse(textarea.dataset.shortcuts || "{}");
  const value = textarea.value.trim();
  if (!value.startsWith("/")) {
    menu.classList.remove("is-open");
  } else {
    const matches = Object.entries(shortcuts).filter(([shortcut]) => shortcut.startsWith(value));
    menu.innerHTML = matches.map(([shortcut, rendered]) => (
      `<button type="button" role="option" data-quick-text="${encodeURIComponent(rendered)}">${shortcut}</button>`
    )).join("");
    menu.classList.toggle("is-open", matches.length > 0);
    if (matches.length > 0) selectQuickReplyOption(menu, 0);
  }

  if (!mentionMenu) return;
  const composer = textarea.closest(".message-composer");
  const token = composer?.classList.contains("is-internal-mode") ? currentMentionToken(textarea) : null;
  if (!token) {
    mentionMenu.classList.remove("is-open");
    return;
  }
  const mentionOptions = JSON.parse(textarea.dataset.mentions || "[]");
  const mentionMatches = mentionOptions.filter((item) => item.name.toLocaleLowerCase("pt-BR").startsWith(token.query));
  mentionMenu.innerHTML = mentionMatches.map((item) => (
    `<button type="button" role="option" data-mention-text="${encodeURIComponent(item.insert)}">${item.name}</button>`
  )).join("");
  mentionMenu.classList.toggle("is-open", mentionMatches.length > 0);
  if (mentionMatches.length > 0) selectMenuOption(mentionMenu, "[data-mention-text]", "is-selected", 0);
});

document.addEventListener("blur", (event) => {
  const titleName = event.target.closest("[data-name-title]");
  if (titleName) titleName.value = titleCase(titleName.value.trim());
}, true);

document.addEventListener("keydown", (event) => {
  const textarea = event.target.closest("#message_text");
  if (!textarea || event.shiftKey) return;
  const menu = document.querySelector("[data-quick-reply-menu].is-open");
  const mentionMenu = document.querySelector("[data-mention-menu].is-open");
  if (mentionMenu && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
    event.preventDefault();
    const options = Array.from(mentionMenu.querySelectorAll("[data-mention-text]"));
    const currentIndex = Math.max(0, options.findIndex((option) => option.classList.contains("is-selected")));
    selectMenuOption(mentionMenu, "[data-mention-text]", "is-selected", currentIndex + (event.key === "ArrowDown" ? 1 : -1));
    return;
  }
  if (menu && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
    event.preventDefault();
    const options = Array.from(menu.querySelectorAll("[data-quick-text]"));
    const currentIndex = Math.max(0, options.findIndex((option) => option.classList.contains("is-selected")));
    selectQuickReplyOption(menu, currentIndex + (event.key === "ArrowDown" ? 1 : -1));
    return;
  }
  if (event.key !== "Enter") return;
  const mentionOption = mentionMenu ? selectedMentionOption(mentionMenu) : null;
  if (mentionOption) {
    event.preventDefault();
    insertMention(textarea, decodeURIComponent(mentionOption.dataset.mentionText || ""));
    return;
  }
  const quickReplyOption = menu ? selectedQuickReplyOption(menu) : null;
  if (quickReplyOption) {
    event.preventDefault();
    applyQuickReplyButton(quickReplyOption);
    return;
  }
  const appliedAt = Number(textarea.dataset.quickReplyJustApplied || "0");
  if (appliedAt && Date.now() - appliedAt < 1200) {
    event.preventDefault();
    textarea.dataset.quickReplyJustApplied = "";
    return;
  }
  event.preventDefault();
  const form = textarea.closest("form");
  const attachment = form ? form.querySelector("#attachment_input") : null;
  if (textarea.value.trim() || (attachment && attachment.files.length)) {
    form.requestSubmit();
  }
});

document.addEventListener("click", (event) => {
  const quickButton = event.target.closest("[data-quick-text]");
  if (quickButton) {
    applyQuickReplyButton(quickButton);
    return;
  }

  const mentionButton = event.target.closest("[data-mention-text]");
  if (mentionButton) {
    const textarea = document.querySelector("#message_text");
    if (textarea) insertMention(textarea, decodeURIComponent(mentionButton.dataset.mentionText || ""));
    return;
  }

  const attachButton = event.target.closest("[data-attach-button]");
  if (attachButton) {
    const input = document.querySelector("#attachment_input");
    if (input) input.click();
    return;
  }

  const emojiButton = event.target.closest("[data-emoji-button]");
  if (emojiButton) {
    const menu = document.querySelector("[data-emoji-menu]");
    if (menu) menu.classList.toggle("is-open");
    return;
  }

  const emojiOption = event.target.closest("[data-emoji-menu] button");
  if (emojiOption) {
    const textarea = document.querySelector("#message_text");
    if (textarea) insertAtCursor(textarea, emojiOption.textContent);
    const menu = document.querySelector("[data-emoji-menu]");
    if (menu) menu.classList.remove("is-open");
  }
});

let audioRecorder = null;
let audioChunks = [];

document.addEventListener("click", async (event) => {
  const audioButton = event.target.closest("[data-audio-button]");
  if (!audioButton) return;

  const recordingChip = document.querySelector("[data-recording-chip]");
  const attachmentInput = document.querySelector("#attachment_input");
  if (audioRecorder && audioRecorder.state === "recording") {
    audioRecorder.stop();
    audioButton.classList.remove("is-recording");
    if (recordingChip) recordingChip.hidden = true;
    return;
  }

  if (!navigator.mediaDevices || !window.MediaRecorder) {
    alert("Gravacao de audio nao esta disponivel neste navegador.");
    return;
  }

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  audioChunks = [];
  audioRecorder = new MediaRecorder(stream);
  audioRecorder.addEventListener("dataavailable", (recorderEvent) => {
    if (recorderEvent.data.size) audioChunks.push(recorderEvent.data);
  });
  audioRecorder.addEventListener("stop", () => {
    stream.getTracks().forEach((track) => track.stop());
    const blob = new Blob(audioChunks, { type: "audio/webm" });
    const file = new File([blob], `audio-${Date.now()}.webm`, { type: "audio/webm" });
    const transfer = new DataTransfer();
    transfer.items.add(file);
    if (attachmentInput) {
      attachmentInput.files = transfer.files;
      attachmentInput.dispatchEvent(new Event("change", { bubbles: true }));
    }
  });
  audioRecorder.start();
  audioButton.classList.add("is-recording");
  if (recordingChip) recordingChip.hidden = false;
});
