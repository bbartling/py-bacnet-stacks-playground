/** Open plain text in a new browser tab (Open-FDD py parity). */
function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function openTextPopup(title, text) {
  const popup = window.open("", "_blank");
  if (!popup) return false;
  const safe = escapeHtml(text);
  const safeTitle = escapeHtml(title);
  popup.document.write(
    `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${safeTitle}</title></head>` +
      `<body style="margin:0;background:#fff;color:#111;">` +
      `<pre style="margin:0;padding:1rem;font-family:ui-monospace,monospace;font-size:12px;` +
      `white-space:pre-wrap;word-break:break-word;">${safe}</pre></body></html>`
  );
  popup.document.close();
  return true;
}

async function openFetchedTextPopup(title, url) {
  const popup = window.open("", "_blank");
  if (!popup) return false;
  popup.document.write(
    `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title></head>` +
      `<body style="font-family:system-ui;padding:1rem;">Loading…</body></html>`
  );
  popup.document.close();
  const res = await fetch(url);
  const text = await res.text();
  openTextPopup(title, text);
  return true;
}

window.openTextPopup = openTextPopup;
window.openFetchedTextPopup = openFetchedTextPopup;
