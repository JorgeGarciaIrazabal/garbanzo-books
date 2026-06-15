// ---------------------------------------------------- streaming "thinking" (collapsible, live)
// The agent's reasoning streams in as its own event type. We render each reasoning part as a
// <details> section: collapsed by default, with the live tail visible in the summary so you can
// SEE it thinking without expanding — or click to watch the full stream.
function addThinking() {
  if (!messagesEl) return null;
  const d = document.createElement("details");
  d.className = "msg think";
  d.innerHTML = '<summary><span class="think-label">💭 Thinking…</span>' +
    '<span class="think-tail"></span></summary><pre class="think-body"></pre>';
  d._txt = "";
  d._t0 = Date.now();
  messagesEl.appendChild(d);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return d;
}
function updateThinking(d, done) {
  if (!d) return;
  const body = d.querySelector(".think-body");
  if (body) {
    body.textContent = d._txt || "";
    if (d.open) body.scrollTop = body.scrollHeight; // follow the stream when expanded
  }
  const tail = d.querySelector(".think-tail");
  if (tail && !done) {
    const t = (d._txt || "").replace(/\s+/g, " ").trim();
    tail.textContent = t.slice(-90);
  }
  if (done) {
    const lab = d.querySelector(".think-label");
    const secs = d._t0 ? Math.max(1, Math.round((Date.now() - d._t0) / 1000)) : null;
    if (lab) lab.textContent = secs ? `💭 Thought for ${secs}s` : "💭 Thought";
    if (tail) tail.textContent = "";
    d.classList.add("done");
  }
  if (messagesEl && !done) messagesEl.scrollTop = messagesEl.scrollHeight;
}
// Called when normal text/tools resume (or the turn ends): close out any live thinking sections.
function finishThinking(state) {
  if (!state || !state.thinkEls) return;
  for (const el of state.thinkEls.values()) {
    if (el && !el._done) { el._done = true; updateThinking(el, true); }
  }
}

// ------------------------------------------------------------ expandable tool rows (input/output)
// Each agent tool call is a <details> row: the one-line summary you had before, but click it to
// see the full command/input and (once finished) the tool's output.
function addToolRow() {
  if (!messagesEl) return null;
  const d = document.createElement("details");
  d.className = "msg tool";
  d.innerHTML = '<summary class="tool-sum"></summary>' +
    '<div class="tool-detail"><pre class="tool-in hidden"></pre><pre class="tool-out hidden"></pre></div>';
  messagesEl.appendChild(d);
  return d;
}
function setToolPre(el, sel, label, text) {
  const pre = el ? el.querySelector(sel) : null;
  if (!pre) return;
  pre.classList.remove("hidden");
  pre.dataset.label = label;
  pre.textContent = text;
}
// Pretty form of the tool input: bash → the actual command; everything else → compact JSON.
function toolInputText(ev) {
  try {
    const o = JSON.parse(ev.input);
    if (o && typeof o === "object") {
      if (o.command) return "$ " + o.command;
      return JSON.stringify(o, null, 2);
    }
  } catch (e) { /* not JSON — show as-is */ }
  return ev.input;
}

function addMsg(role, text, cls) {
  if (!messagesEl) return null;
  const el = document.createElement("div");
  el.className = "msg " + (cls || role);
  if (role !== "system" && role !== "tool") {
    const r = document.createElement("div");
    r.className = "role";
    r.textContent = role === "user" ? "you" : role === "assistant" ? "🫘 studio" : role;
    el.appendChild(r);
  }
  const body = document.createElement("div");
  body.className = "body";
  body.textContent = text;
  el.appendChild(body);
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return body;
}

function setBusy(b) {
  busy = b;
  const send = $("#send");
  if (send) {
    send.disabled = b;
    send.innerHTML = b ? '<span class="spinner"></span>Working…' : "Send ▸";
  }
  const stop = $("#stop");
  if (stop) stop.classList.toggle("hidden", !b);
}

// Stop the running turn so the user can redirect. Aborts the client stream immediately and tells
// the server to abort the OpenCode agent loop; the session then accepts a new (redirecting) prompt.
async function stopWorkflow() {
  if (!busy) return;
  const sid = sessionId;
  if (currentAbort) { try { currentAbort.abort(); } catch (e) {} }
  if (sid) {
    try {
      await fetch("/api/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: sid }),
      });
    } catch (e) {}
  }
  addMsg("system", "⏹ Stopped. Type a new message to redirect (the current step may finish first).", "system");
}

// ----------------------------------------------------------------------- live activity / progress
let activityTimer = null;
let activityStart = 0;
function startActivity(text) {
  activityStart = Date.now();
  setText("#activity-text", text || "Working…");
  show($("#activity"));
  if (!activityTimer) activityTimer = setInterval(tickElapsed, 1000);
  tickElapsed();
  startProgressPoll();
}
function tickElapsed() {
  const s = Math.round((Date.now() - activityStart) / 1000);
  setText("#activity-elapsed", s + "s");
}
function setActivity(text) { if (text) setText("#activity-text", text); }
function stopActivity() {
  if (activityTimer) { clearInterval(activityTimer); activityTimer = null; }
  stopProgressPoll();
  hide($("#activity"));
}

// Script-level progress: long scripts (image generation…) run inside the agent's bash
// tool, whose output only reaches us when the command FINISHES. They publish per-unit
// progress to a side-channel file instead; while the activity strip is up we poll
// /api/progress and show "🎨 illustrating 7/16 — page 07" with a live bar. The endpoint
// reports inactive when no script is publishing, so normal chat activity is untouched.
let progressPollTimer = null;
const TASK_ICON = { illustrating: "🎨", building: "🔨", validating: "✓" };
function progressLine(p) {
  const ico = TASK_ICON[p.task] || "⚙️";
  const total = Math.max(1, p.total || 1);
  const filled = Math.round(10 * (p.done || 0) / total);
  const bar = "▰".repeat(filled) + "▱".repeat(10 - filled);
  return `${ico} ${p.task} ${bar} ${p.done}/${p.total}${p.detail ? " — " + p.detail : ""}`;
}
function startProgressPoll() {
  if (progressPollTimer) return;
  progressPollTimer = setInterval(async () => {
    try {
      const r = await fetch("/api/progress");
      const p = await r.json();
      if (p && p.active && p.total) setActivity(progressLine(p));
    } catch (e) { /* non-fatal — the strip just keeps its last text */ }
  }, 2000);
}
function stopProgressPoll() {
  if (progressPollTimer) { clearInterval(progressPollTimer); progressPollTimer = null; }
}

// How to phrase "no events for N seconds". Under 3 minutes this is normal local-model
// slowness; past it the odds shift toward genuinely stuck (a hung Ollama stream), so the
// tone escalates and `warn` styles the strip. Pure → unit-tested.
const STALL_WARN_SECS = 180;
function stallNotice(seconds) {
  const s = seconds || 0;
  const mins = Math.floor(s / 60), rem = s % 60;
  const span = mins ? mins + "m" + (rem ? " " + rem + "s" : "") : rem + "s";
  if (s >= STALL_WARN_SECS) {
    return { warn: true, span,
      text: "🛑 No progress for " + span + " — the model looks stuck. ⏹ Stop is safe: " +
            "finished steps are already saved on disk." };
  }
  return { warn: false, span,
    text: "⏳ Still generating — " + span + " without news (long writes are slow on " +
          "local models). ⏹ Stop to redirect." };
}

// --------------------------------------------------------------------------------- quick replies
const QUICK_REPLIES = [
  { label: "✅ Looks good — continue", send: "Looks good — please continue with the next step." },
  { label: "👀 Show me what you have", send: "Show me what you've built so far (a quick summary)." },
  { label: "✏️ Change something…", focus: true },
];
function showQuickReplies() {
  const box = $("#quickreplies");
  if (!box || !sessionId) return;
  box.innerHTML = "";
  for (const qr of QUICK_REPLIES) {
    const b = document.createElement("button");
    b.className = "qr";
    b.textContent = qr.label;
    b.onclick = () => {
      if (qr.focus) { const p = $("#prompt"); if (p) p.focus(); return; }
      hide(box);
      streamChat(qr.send);
    };
    box.appendChild(b);
  }
  show(box);
}
function hideQuickReplies() { hide($("#quickreplies")); }
