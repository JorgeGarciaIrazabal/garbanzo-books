// --------------------------------------------------------------------- confirm popup + deleting
// A small modal confirm — returns a Promise<bool>. Closes on Cancel, ✕, backdrop click or Escape
// (all → false); the danger button resolves true. Used before any destructive delete.
function confirmDialog({ title, body, confirmLabel = "Delete", danger = true } = {}) {
  return new Promise((resolve) => {
    const ov = document.createElement("div");
    ov.className = "char-overlay confirm-overlay";
    ov.innerHTML = `<div class="confirm-card" role="alertdialog" aria-label="${escapeHtml(title || "Confirm")}">
      <button class="kids-x cc-x" title="Close">✕</button>
      <h3 class="confirm-title">${escapeHtml(title || "Are you sure?")}</h3>
      <div class="confirm-body">${body || ""}</div>
      <div class="confirm-actions">
        <button type="button" class="btn ghost small confirm-cancel">Cancel</button>
        <button type="button" class="btn small ${danger ? "danger" : ""} confirm-ok">${escapeHtml(confirmLabel)}</button>
      </div>
    </div>`;
    document.body.appendChild(ov);
    const done = (val) => {
      if (ov._esc) document.removeEventListener("keydown", ov._esc);
      ov.remove();
      resolve(val);
    };
    ov.addEventListener("click", (e) => { if (e.target === ov) done(false); });
    ov.querySelector(".cc-x").onclick = () => done(false);
    ov.querySelector(".confirm-cancel").onclick = () => done(false);
    ov.querySelector(".confirm-ok").onclick = () => done(true);
    ov._esc = (e) => { if (e.key === "Escape") done(false); };
    document.addEventListener("keydown", ov._esc);
    const ok = ov.querySelector(".confirm-ok");
    if (ok) ok.focus();
  });
}

// Permanently delete a story (its whole dir) or a whole world. Both confirm first, then call the
// server (which runs scripts/delete_content.py and rebuilds both previews), then refresh the UI.
async function deleteStory(btn) {
  const wslug = btn.dataset.w, sslug = btn.dataset.s, title = btn.dataset.title || sslug;
  if (!wslug || !sslug || btn.disabled) return;
  const ok = await confirmDialog({
    title: "Delete this story?",
    body: `<p>“<strong>${escapeHtml(title)}</strong>” will be <strong>permanently deleted</strong> — its text and all its images. This cannot be undone.</p>`,
    confirmLabel: "🗑 Delete story",
  });
  if (!ok) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  let data = null;
  try {
    const res = await fetch("/api/story/delete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ world: wslug, story: sslug }),
    });
    data = await res.json();
  } catch (e) { data = { ok: false, output: String((e && e.message) || e) }; }
  if (!data.ok) {
    btn.disabled = false; btn.textContent = "🗑";
    addMsg("system", "⚠ Could not delete **" + sslug + "**:\n\n```\n" + String(data.output || "").trim() + "\n```", "system");
    return;
  }
  addMsg("system", "🗑 Deleted story **" + escapeHtml(title) + "**.", "system");
  loadLibrary(); refreshPreview(); refreshPublicPreview(); refreshPublishStatus();
}

async function deleteWorld(btn) {
  const wslug = btn.dataset.w, title = btn.dataset.title || wslug;
  if (!wslug || btn.disabled) return;
  const w = libraryWorlds.find(x => x.slug === wslug);
  const ns = w ? w.stories.length : 0, nc = w ? w.characters.length : 0;
  const ok = await confirmDialog({
    title: "Delete this whole world?",
    body: `<p>“<strong>${escapeHtml(title)}</strong>” and <strong>everything inside it</strong>` +
      ` — ${nc} character${nc === 1 ? "" : "s"} and ${ns} ${ns === 1 ? "story" : "stories"}` +
      ` — will be <strong>permanently deleted</strong>. This cannot be undone.</p>`,
    confirmLabel: "🗑 Delete world",
  });
  if (!ok) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Deleting…';
  let data = null;
  try {
    const res = await fetch("/api/world/delete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ world: wslug }),
    });
    data = await res.json();
  } catch (e) { data = { ok: false, output: String((e && e.message) || e) }; }
  if (!data.ok) {
    btn.disabled = false; btn.textContent = "🗑 Delete world";
    addMsg("system", "⚠ Could not delete world **" + wslug + "**:\n\n```\n" + String(data.output || "").trim() + "\n```", "system");
    return;
  }
  addMsg("system", "🗑 Deleted world **" + escapeHtml(title) + "** and everything in it.", "system");
  loadLibrary(); refreshPreview(); refreshPublicPreview(); refreshPublishStatus();
}

// Run a build/validate/quality job and show its status + output IN PLACE (next to the button
// that launched it) instead of dumping raw output into the chat. Each job has a status chip
// (#job-<key>-status), a collapsible output panel (#job-<key>) and a <pre> (#job-<key>-out).
// The panel pops open automatically on failure so problems are never hidden.
async function runJob(key, endpoint, opts) {
  opts = opts || {};
  const btn = $("#btn-" + key);
  const wrap = $("#job-" + key);
  const status = $("#job-" + key + "-status");
  const out = $("#job-" + key + "-out");
  if (btn) {
    if (!btn.dataset.label) btn.dataset.label = btn.textContent;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Running…';
  }
  if (status) { status.textContent = "running…"; status.className = "step-status running"; }
  show(wrap);
  let data = null;
  try {
    const res = await fetch(endpoint, { method: "POST" });
    data = await res.json();
  } catch (e) {
    data = { ok: false, output: "⚠ " + ((e && e.message) || String(e)) };
  }
  const ok = !!(data && data.ok);
  if (status) {
    status.textContent = ok ? "✓ " + (opts.okLabel || "done") : "✗ " + (opts.failLabel || "failed");
    status.className = "step-status " + (ok ? "ok" : "fail");
  }
  if (out) out.textContent = String((data && data.output) || "").trim() || "(no output)";
  if (wrap) wrap.open = !ok; // pop the output open on failure; tuck it away on success
  if (btn) { btn.disabled = false; btn.textContent = btn.dataset.label; }
  loadLibrary();
  if (opts.onDone) opts.onDone(data);
}
