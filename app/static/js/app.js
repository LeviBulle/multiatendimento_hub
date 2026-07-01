function applyQuickReply(content) {
  const textarea = document.querySelector("#message_text");
  if (!textarea) return;
  textarea.value = content;
  textarea.focus();
}

function fillShortcut(shortcutMap) {
  const textarea = document.querySelector("#message_text");
  if (!textarea) return;
  const value = textarea.value.trim();
  if (shortcutMap[value]) {
    textarea.value = shortcutMap[value];
  }
}
