// Garbanzo Books Studio — front-end. Talks to the FastAPI server, which drives the workspace
// via OpenCode + a local Ollama model and the python scripts.
//
// The console is split across ordered CLASSIC scripts (NOT ES modules) that share one global
// lexical scope — the same pattern the reader uses (reader.js + gx.*.js). index.html loads them
// in this exact order, and each file just adds functions/vars to the shared scope; nothing is
// imported/exported. Cross-file references are fine because every call happens at runtime, after
// all scripts have loaded (the wiring in app.boot.js runs last). Load order / ownership:
//   app.core.js     — $, escapeHtml & DOM helpers, app state, session persistence, model picker
//   app.voice.js    — Kokoro TTS / Whisper STT, recorder, kids/tts toggles, emoji, fieldOptions
//   app.kids.js     — the big one-question-at-a-time kids wizard
//   app.render.js   — tiny markdown reader + agent-driven (dynamic) form blocks
//   app.messages.js — chat bubbles, thinking/tool rows, busy state, activity strip, quick replies
//   app.stream.js   — streamChat() + the SSE event handler
//   app.forms.js    — the guided form definitions (world/character/story) + form rendering
//   app.debug.js    — the debug tab (live event log + full conversation)
//   app.library.js  — the bookshelf, character cards, preview refresh, publish status/flip
//   app.actions.js  — confirm popup + destructive delete + the build/validate/quality job runner
//   app.boot.js     — DOM wiring (event listeners) + the initial loads (runs last)
// This file (app.core.js) is the foundation every other file builds on.
//
// Two things the whole console is careful about:
//  1) Live PROGRESS — a busy/idle heartbeat + elapsed timer + the latest tool line, so you can
//     see OpenCode is actually moving even during long silent steps (e.g. image generation).
//  2) Null-safety — every DOM lookup is guarded, so a missing node can never abort a stream
//     ("Cannot set properties of null").

const $ = (s) => document.querySelector(s);
const messagesEl = $("#messages");
let sessionId = null;
let busy = false;
let currentAbort = null; // AbortController for the in-flight chat stream (for the Stop button)
let libraryWorlds = []; // cached for the world <select> in forms

// Session persistence: a refresh used to lose the whole studio conversation. We keep the
// OpenCode sessionId + a lightweight (role,text) transcript in localStorage so a reload
// resumes where you left off. "New session" clears it.
const GB_SESS_KEY = "gb_session";
let transcript = []; // [{role, text}] of user/assistant turns, capped
function persistSession() {
  try { localStorage.setItem(GB_SESS_KEY, JSON.stringify({ id: sessionId, msgs: transcript.slice(-40) })); } catch (e) { /* storage full/blocked — non-fatal */ }
}
function pushMsg(role, text) {
  if (!text) return;
  transcript.push({ role, text });
  if (transcript.length > 50) transcript = transcript.slice(-50);
  persistSession();
}
function clearSession() {
  transcript = [];
  try { localStorage.removeItem(GB_SESS_KEY); } catch (e) { /* non-fatal */ }
}
function clearChat() {
  // Stop anything in flight so the cleared UI can't get clobbered by late events.
  if (currentAbort) { try { currentAbort.abort(); } catch (e) { /* non-fatal */ } }
  if (messagesEl) messagesEl.innerHTML = "";
  hideQuickReplies();
  closeForm();
  sessionId = null;
  clearSession();
  setText("#conn", "fresh session");
  // sessionId is null now, so the next Send starts a brand-new OpenCode session.
  // (Legacy checkbox — kept null-safe for older markup.)
  const ns = $("#newsess"); if (ns) ns.checked = true;
  addMsg("system", "🧹 Fresh page — what shall we make next?", "system");
}
function restoreSession() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(GB_SESS_KEY) || "null"); } catch (e) { saved = null; }
  if (!saved || !Array.isArray(saved.msgs) || !saved.msgs.length) return false;
  sessionId = saved.id || null;
  transcript = saved.msgs.slice(-40);
  if (messagesEl) messagesEl.innerHTML = ""; // drop the fresh-load welcome before replaying
  for (const m of saved.msgs) {
    if (m.role === "assistant") {
      const b = addMsg("assistant", "");
      if (b) { b._md = m.text; renderAssistant(b); }
    } else {
      addMsg(m.role, m.text, m.role === "system" ? "system" : undefined);
    }
  }
  addMsg("system", "↩ Resumed your previous session — keep going, or hit “🧹 New chat” to start fresh.", "system");
  if (sessionId) setText("#conn", "resumed " + String(sessionId).slice(0, 8));
  return true;
}

// Model ids (must match the server's MODELS / opencode.json). The studio's three tiers:
//   M_FAST     = Nemotron-3-Ultra    — default for craft / world / character / build / validate
//   M_CREATIVE = DeepSeek-V4-Pro     — used when the agent is writing the story
//   M_SEARCH   = MiniMax-M3          — used when the agent is doing information gathering
// Plus the "auto" sentinel: the server picks the right one per the agent's [[stage:...]] tag.
const M_FAST = "ollama/nemotron-3-ultra:cloud";
const M_CREATIVE = "ollama/deepseek-v4-pro:cloud";
const M_SEARCH = "ollama/minimax-m3:cloud";
const M_AUTO = "auto";
// stage → friendly label, for the live "currently using" chip next to the picker.
const STAGE_LABEL = {
  story: "story (DeepSeek)", craft: "craft (Nemotron)", world: "world (Nemotron)",
  character: "character (Nemotron)", build: "build (Nemotron)", validate: "validate (Nemotron)",
  research: "research (MiniMax)", done: "done (Nemotron)",
};
// Server-resolved model for the current/last turn (when in Auto mode), so the picker can show it.
let resolvedModel = null;
let lastStage = null;
function currentModel() { const s = $("#model-select"); return s && s.value ? s.value : M_AUTO; }
function setModel(id) {
  const s = $("#model-select");
  if (s && id && [...s.options].some(o => o.value === id)) s.value = id;
  paintStageChip();
}
function paintStageChip() {
  const chip = $("#stage-chip");
  if (!chip) return;
  const sel = $("#model-select");
  const v = sel ? sel.value : M_AUTO;
  if (v === M_AUTO) {
    const label = lastStage ? STAGE_LABEL[lastStage] || `auto (${lastStage})` : "auto (default → fast)";
    chip.textContent = `✨ ${label}`;
    chip.className = "stage-chip auto";
  } else {
    // Pinned — show what was picked, plus what Auto would have used right now.
    const autoLabel = lastStage ? STAGE_LABEL[lastStage] : "auto";
    const tip = (v !== (resolvedModel || v)) ? ` · auto would use ${autoLabel}` : "";
    chip.textContent = `📌 ${v.split("/").pop().replace(":cloud","")}${tip}`;
    chip.className = "stage-chip pinned";
  }
  chip.title = v === M_AUTO
    ? "Auto mode — the server picks the best model for the next step based on the stage tag the agent emits."
    : "Pinned — the studio always uses this model. Switch to Auto to let the studio pick per stage.";
}
async function loadModels() {
  const sel = $("#model-select");
  if (!sel) return;
  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    const models = data.models || [];
    // Put Auto first so it's the obvious default, then the rest in server order.
    const ordered = models.slice().sort((a, b) => {
      if (a.id === M_AUTO) return -1;
      if (b.id === M_AUTO) return 1;
      return 0;
    });
    sel.innerHTML = ordered.map(m => `<option value="${escapeHtml(m.id)}">${escapeHtml(m.label || m.id)}</option>`).join("");
    // Persisted user choice wins (so a user who explicitly pinned a model isn't overridden on reload).
    const saved = localStorage.getItem("gb_model");
    if (saved && ordered.some(m => m.id === saved)) sel.value = saved;
    else sel.value = M_AUTO;
    paintStageChip();
  } catch (e) {
    // Fallback so the picker still works if /api/models is unreachable.
    sel.innerHTML = `<option value="${M_AUTO}">✨ Auto (switch by stage) — recommended</option>` +
                    `<option value="${M_FAST}">Nemotron-3-Ultra — fast (default for craft)</option>` +
                    `<option value="${M_CREATIVE}">DeepSeek-V4-Pro — more creative</option>` +
                    `<option value="${M_SEARCH}">MiniMax-M3 — best for research</option>`;
    sel.value = M_AUTO;
    paintStageChip();
  }
}
// Persist the user's explicit picker choice so reloads don't reset it (Auto is also persisted).
function persistModelChoice() {
  try { localStorage.setItem("gb_model", currentModel()); } catch (e) { /* storage full/blocked — non-fatal */ }
}

// ----------------------------------------------------------------- small DOM helpers (null-safe)
function show(el) { if (el) el.classList.remove("hidden"); }
function hide(el) { if (el) el.classList.add("hidden"); }
function setText(sel, text) { const el = $(sel); if (el) el.textContent = text; }
function escapeHtml(s){return String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
