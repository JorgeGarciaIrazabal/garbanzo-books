// Garbanzo Books Studio — front-end. Talks to the FastAPI server, which drives the workspace
// via OpenCode + a local Ollama model and the python scripts.
//
// Three things this file is careful about:
//  1) Guided FORMS — most studio actions are a few fields, not an essay. Forms assemble a clean
//     prompt for you; the free-form box at the bottom still works for anything else.
//  2) Live PROGRESS — a busy/idle heartbeat + elapsed timer + the latest tool line, so you can
//     see OpenCode is actually moving even during long silent steps (e.g. image generation).
//  3) Null-safety — every DOM lookup is guarded, so a missing node can never abort a stream
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

// ================================================== voice (local, natural — Kokoro TTS / Whisper)
// Speech is done by LOCAL models on the server (no API key, nothing leaves the box):
//   TTS = Kokoro-82M via POST /api/tts → a WAV we play here.
//   STT = faster-whisper via POST /api/stt ← we record the mic with MediaRecorder and upload it.
// The browser only needs MediaRecorder + getUserMedia for voice input; for read-aloud it just
// plays audio. Capabilities are fetched from /api/voice; controls disable gracefully if missing.
let voiceCaps = { tts: false, stt: false, voices: [], default_voice: "af_heart" };
const Voice = {
  get supportTTS() { return !!voiceCaps.tts; },
  // STT needs the model on the server AND mic recording in this browser.
  get supportSTT() {
    return !!voiceCaps.stt && !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  },
};
async function loadVoiceCaps() {
  try {
    const r = await fetch("/api/voice");
    voiceCaps = Object.assign(voiceCaps, await r.json());
  } catch (e) { /* leave defaults (disabled) */ }
  // Kick a background warm-up so the first read-aloud / mic tap doesn't pay the cold-load.
  if (voiceCaps.tts || voiceCaps.stt) { fetch("/api/voice/warm", { method: "POST" }).catch(() => {}); }
  applyVoiceCaps();
}
function applyVoiceCaps() {
  const bt = $("#btn-tts");
  if (bt) { bt.disabled = !Voice.supportTTS; if (!Voice.supportTTS) bt.title = "Local read-aloud isn't installed — run `uv sync --group tts`."; }
  const mic = $("#mic");
  if (mic) {
    mic.classList.toggle("unsupported", !Voice.supportSTT);
    mic.title = Voice.supportSTT ? "Speak your message" : "Voice input needs mic permission + `uv sync --group tts`.";
  }
}

// ---- TTS playback: synthesize on the server, play the returned WAV here --------------------------
let ttsAudio = null;  // the <audio> currently playing (so we can stop it)
let ttsToken = 0;     // bumped on every stop/new request so stale synths are ignored on arrival
function stopSpeaking() {
  ttsToken++;
  if (ttsAudio) {
    try { ttsAudio.pause(); } catch (e) {}
    if (ttsAudio.src) { try { URL.revokeObjectURL(ttsAudio.src); } catch (e) {} }
    ttsAudio = null;
  }
}
async function speak(text, opts) {
  if (!Voice.supportTTS) { if (opts && opts.onend) opts.onend(); return; }
  const t = String(text || "").trim();
  if (!t) { if (opts && opts.onend) opts.onend(); return; }
  stopSpeaking();
  const my = ttsToken;
  try {
    const res = await fetch("/api/tts", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: t, voice: (opts && opts.voice) || voiceCaps.default_voice, speed: (opts && opts.speed) || 0.95 }),
    });
    if (!res.ok) throw new Error("tts " + res.status);
    const blob = await res.blob();
    if (my !== ttsToken) return; // a newer speak()/stopSpeaking() superseded us while synthesizing
    const url = URL.createObjectURL(blob);
    const a = new Audio(url);
    ttsAudio = a;
    a.onended = a.onerror = () => {
      if (ttsAudio === a) { try { URL.revokeObjectURL(url); } catch (e) {} ttsAudio = null; }
      if (opts && opts.onend) opts.onend();
    };
    a.play().catch(() => { if (opts && opts.onend) opts.onend(); });
  } catch (e) { if (opts && opts.onend) opts.onend(); }
}

// Append a small 🔊 replay button to a finished assistant bubble (no-op if TTS is unsupported).
function addSpeakButton(bubble) {
  if (!Voice.supportTTS || !bubble) return;
  const text = mdToSpeech(bubble._md);
  if (!text || bubble.querySelector(".speakbtn")) return;
  const b = document.createElement("button");
  b.className = "speakbtn";
  b.type = "button";
  b.textContent = "🔊 Read aloud";
  b.onclick = () => {
    b.classList.add("speaking");
    speak(text, { onend: () => b.classList.remove("speaking") });
  };
  bubble.appendChild(b);
}

// Convert the agent's markdown to plain prose worth reading aloud (drop code/form blocks & symbols).
function mdToSpeech(md) {
  let s = String(md || "");
  s = s.replace(/```[\s\S]*?```/g, " ");           // code & form fences — never read these
  s = s.replace(STAGE_RE, " ");                      // hidden stage tags
  s = s.replace(/[#*_`>~]/g, "");                    // markdown punctuation
  s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");     // links → just the label
  s = s.replace(/\s+/g, " ").trim();
  return s;
}

// Record the mic, then transcribe on the server with faster-whisper. Returns a handle immediately;
// getUserMedia + recording start asynchronously. onState(state, text?) reports the lifecycle:
//   "recording" → "transcribing" → "result" (with text) | "error".
// Call .stop() to end recording (which triggers transcription); .cancel() to abort with no STT.
function makeRecorder({ onState } = {}) {
  let mr = null, stream = null, chunks = [], canceled = false;
  const emit = (s, text) => { if (onState) onState(s, text); };
  stopSpeaking(); // don't record our own read-aloud
  (async () => {
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
    catch (e) { emit("error"); return; }
    if (canceled) { stream.getTracks().forEach(t => t.stop()); return; }
    try { mr = new MediaRecorder(stream); }
    catch (e) { stream.getTracks().forEach(t => t.stop()); emit("error"); return; }
    mr.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    mr.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      if (canceled) return;
      emit("transcribing");
      try {
        const blob = new Blob(chunks, { type: (mr && mr.mimeType) || "audio/webm" });
        const r = await fetch("/api/stt", { method: "POST", headers: { "Content-Type": blob.type || "application/octet-stream" }, body: blob });
        const d = await r.json();
        emit("result", (d && d.text) || "");
      } catch (e) { emit("error"); }
    };
    mr.start();
    emit("recording");
  })();
  return {
    stop() { if (mr && mr.state !== "inactive") { try { mr.stop(); } catch (e) {} } },
    cancel() {
      canceled = true;
      if (mr && mr.state !== "inactive") { try { mr.stop(); } catch (e) {} }
      else if (stream) { stream.getTracks().forEach(t => t.stop()); }
    },
  };
}

// ---- toggles (persisted) -----------------------------------------------------------------------
let ttsOn = localStorage.getItem("gb_tts") === "1";
let kidsMode = localStorage.getItem("gb_kids") === "1";
function syncToggle(sel, on) { const b = $(sel); if (b) b.setAttribute("aria-pressed", on ? "true" : "false"); }

// Friendly emoji for an option/label — keyword match first, then a cheerful rotating fallback.
const EMOJI_KEYWORDS = [
  [/forest|wood|tree/, "🌲"], [/beach|coral|sea|ocean|under ?water|wave|reef/, "🐚"],
  [/mountain|peak|hill|cliff/, "⛰️"], [/star|night|moon|sky|space|cosmic/, "✨"],
  [/flower|meadow|garden|bloom|grass/, "🌸"], [/snow|ice|winter|frost/, "❄️"],
  [/desert|sand|dune/, "🏜️"], [/castle|kingdom|palace/, "🏰"], [/city|town/, "🏙️"],
  [/dragon/, "🐉"], [/mouse|mice/, "🐭"], [/bunny|rabbit|hare/, "🐰"], [/cat|kitt/, "🐱"],
  [/dog|puppy|pup/, "🐶"], [/fox/, "🦊"], [/bird/, "🐦"], [/fish/, "🐟"], [/octopus|squid/, "🐙"],
  [/bear/, "🐻"], [/owl/, "🦉"], [/robot/, "🤖"], [/turtle/, "🐢"], [/whale|dolphin/, "🐳"],
  [/water ?color|paint/, "🎨"], [/cartoon|flat|bold/, "🖍️"], [/pastel|dream/, "🌈"],
  [/collage|cut.?paper/, "✂️"], [/crayon|hand.?drawn/, "🖍️"], [/retro|mid.?century/, "📻"],
  [/funny|silly|play/, "😄"], [/cozy|gentle|calm|bedtime|sleep|reassur/, "🌙"],
  [/adventur|brave|explore/, "🗺️"], [/magic|dreamy/, "🪄"], [/energetic/, "⚡"],
  [/rhyme/, "🎵"], [/seek|find|hunt|spot/, "🔍"], [/choice|choose|branch/, "🔀"],
  [/sight ?word|phonic|vowel|read/, "📖"], [/none|skip|no /, "➖"], [/other/, "✏️"],
];
const EMOJI_FALLBACK = ["🌟", "🍀", "🎈", "🌼", "🦋", "🐝", "🍓", "🪁", "🎀", "🧩", "🎪", "🌻"];
function guessEmoji(text, i) {
  const s = String(text || "").toLowerCase();
  for (const [re, e] of EMOJI_KEYWORDS) if (re.test(s)) return e;
  return EMOJI_FALLBACK[(i || 0) % EMOJI_FALLBACK.length];
}

// Normalize a form field's options to [{value,label}] — supports plain strings, {value,label},
// and the special "world" field type (pulled from the loaded library).
function fieldOptions(f) {
  if (f.type === "world") return libraryWorlds.map(w => ({ value: w.slug, label: w.title || w.slug }));
  if (Array.isArray(f.options)) return f.options.map(o => (o && typeof o === "object") ? { value: o.value, label: o.label || o.value } : { value: o, label: o });
  return null;
}

// ================================================================ kids mode — one-question wizard
// Renders a form (agent-driven OR a chip form) as a full-screen, one-question-at-a-time flow with
// big icon buttons, the question auto-read aloud, and a tap-to-talk answer for every step.
let kidsRec = null;          // the in-flight mic recorder for the current wizard step (if any)
let kidsReadSeq = 0;         // bumped to cancel an in-flight "read question + options" sequence
function closeKidsWizard() {
  kidsReadSeq++;             // cancel any chained read-aloud so it can't speak after we close
  if (kidsRec) { try { kidsRec.cancel(); } catch (e) {} kidsRec = null; }
  stopSpeaking();
  const ov = $("#kids-overlay");
  if (ov) ov.remove();
}
function openKidsWizard(spec, onComplete, leadText) {
  closeKidsWizard();
  const fields = (Array.isArray(spec.fields) ? spec.fields : []).filter(Boolean);
  if (!fields.length) { if (onComplete) onComplete({}); return; }
  const values = {};
  let idx = 0;
  const ov = document.createElement("div");
  ov.className = "kids-overlay";
  ov.id = "kids-overlay";
  ov.innerHTML = `<div class="kids-card"><button class="kids-x" title="Close">✕</button>
    <div class="kids-progress"></div><div class="kids-step"></div></div>`;
  document.body.appendChild(ov);
  ov.querySelector(".kids-x").onclick = () => closeKidsWizard();

  function finish() {
    closeKidsWizard();
    if (onComplete) onComplete(values);
  }
  function go(n) { kidsReadSeq++; if (kidsRec) { try { kidsRec.cancel(); } catch (e) {} kidsRec = null; } idx = n; render(); }

  function render() {
    const f = fields[idx];
    const opts = fieldOptions(f);
    const label = f.label || f.name || "Your choice";
    const emoji = guessEmoji(label, idx);
    const prog = fields.map((_, i) => `<span class="pdot ${i < idx ? "done" : ""} ${i === idx ? "now" : ""}"></span>`).join("");
    const step = ov.querySelector(".kids-step");
    ov.querySelector(".kids-progress").innerHTML = prog;

    let body = `<div class="kids-emoji">${emoji}</div>
      <div class="kids-q-row"><div class="kids-q">${escapeHtml(label)}</div>
        <button class="kids-hear" title="Hear it again">🔊</button></div>`;

    if (opts) {
      body += `<div class="kids-options">` + opts.map((o, i) =>
        `<button class="kids-opt ${values[f.name] === o.value ? "sel" : ""}" data-val="${escapeHtml(o.value)}">
           <span class="oe">${guessEmoji(o.label, i)}</span><span class="ol">${escapeHtml(o.label)}</span>
           <span class="opt-hear" role="button" title="Hear it again" aria-label="Hear it again">🔊</span></button>`).join("") +
        `<button class="kids-opt other-opt"><span class="oe">✏️</span><span class="ol">Something else…</span></button></div>
         <div class="kids-other hidden"><input class="kids-text" placeholder="Type or say your own…">
           <button class="kids-talk" type="button"><span class="bigmic">🎤</span>Tap &amp; talk</button></div>`;
    } else {
      const ph = f.placeholder ? escapeHtml(f.placeholder) : "Type or say your answer…";
      body += `<input class="kids-text" placeholder="${ph}" value="${escapeHtml(values[f.name] || "")}">
        <div><button class="kids-talk" type="button"><span class="bigmic">🎤</span>Tap &amp; talk</button></div>`;
    }

    const last = idx === fields.length - 1;
    body += `<div class="kids-nav">
        <button class="kids-back" ${idx === 0 ? "disabled" : ""}>◀ Back</button>
        <button class="kids-next">${last ? "🎉 All done!" : "Next ▶"}</button>
      </div>`;
    if (!Voice.supportSTT) body += `<div class="kids-hint">Tip: turn on the microphone to talk — or just type your answer.</div>`;
    step.innerHTML = body;

    const spoken = (idx === 0 && leadText ? leadText + ". " : "") + label; // question (with lead-in on step 1)
    const hearBtn = step.querySelector(".kids-hear");
    const optButtons = Array.from(step.querySelectorAll(".kids-opt"));
    const clearReading = () => optButtons.forEach(b => b.classList.remove("reading"));
    const stopReading = () => { kidsReadSeq++; clearReading(); if (hearBtn) hearBtn.classList.remove("speaking"); };

    // Read a list of {el, text} items one after another, highlighting each element while it's
    // spoken. Bumping kidsReadSeq (on click/navigation/close) cancels the rest of the chain.
    function readItems(items) {
      if (!Voice.supportTTS || !items.length) return;
      const mine = ++kidsReadSeq;
      if (hearBtn) hearBtn.classList.add("speaking");
      let i = 0;
      const next = () => {
        if (mine !== kidsReadSeq) return;       // superseded — stop here
        clearReading();
        if (i >= items.length) { if (hearBtn) hearBtn.classList.remove("speaking"); return; }
        const it = items[i++];
        if (it.el) it.el.classList.add("reading");
        speak(it.text, { onend: () => { if (mine === kidsReadSeq) next(); } });
      };
      next();
    }
    const optText = (b) => { const s = b.querySelector(".ol"); return s ? s.textContent : (b.dataset.val || ""); };
    const sayQuestion = () => readItems([{ el: null, text: spoken }]);
    // The full auto-narration: the question, then each option in turn (with highlight).
    const sayAll = () => readItems([{ el: null, text: spoken }].concat(optButtons.map(b => ({ el: b, text: optText(b) }))));
    sayAll();
    if (hearBtn) hearBtn.onclick = sayAll;

    const textEl = step.querySelector(".kids-text");
    const otherWrap = step.querySelector(".kids-other");

    // each option: tap the 🔊 to re-hear just that one; tap the option body to pick it & move on
    step.querySelectorAll(".kids-opt[data-val]").forEach(b => {
      const hear = b.querySelector(".opt-hear");
      if (hear) hear.onclick = (e) => { e.stopPropagation(); readItems([{ el: b, text: optText(b) }]); };
      b.onclick = () => {
        stopReading();                   // stop any read-aloud in progress
        values[f.name] = b.dataset.val;
        stopSpeaking();
        if (last) finish(); else go(idx + 1);
      };
    });
    const otherBtn = step.querySelector(".other-opt");
    if (otherBtn) otherBtn.onclick = () => {
      stopReading(); stopSpeaking();   // stop the option narration
      if (otherWrap) { otherWrap.classList.remove("hidden"); const t = otherWrap.querySelector(".kids-text"); if (t) t.focus(); }
      step.querySelectorAll(".kids-opt").forEach(x => x.classList.remove("sel"));
      otherBtn.classList.add("sel");
    };

    // tap & talk → record the mic, transcribe on the server, drop the words into the text box
    const talk = step.querySelector(".kids-talk");
    const box = otherWrap ? otherWrap.querySelector(".kids-text") : textEl;
    const setTalk = (label, mic) => { if (talk) talk.innerHTML = `<span class="bigmic">${mic || "🎤"}</span>${label}`; };
    if (talk) talk.onclick = () => {
      if (!Voice.supportSTT) { if (box) box.focus(); return; }
      if (kidsRec) { kidsRec.stop(); return; }  // tap again to stop & transcribe
      stopReading(); stopSpeaking();   // stop any option narration before recording
      if (otherBtn) { step.querySelectorAll(".kids-opt").forEach(x => x.classList.remove("sel")); otherBtn.classList.add("sel"); if (otherWrap) otherWrap.classList.remove("hidden"); }
      kidsRec = makeRecorder({
        onState: (s, text) => {
          if (s === "recording") { talk.classList.add("rec"); setTalk("Listening… tap to stop", "●"); }
          else if (s === "transcribing") { talk.classList.remove("rec"); talk.classList.add("busy"); setTalk("Thinking…", "⏳"); }
          else { // result | error
            kidsRec = null; talk.classList.remove("rec", "busy"); setTalk("Tap &amp; talk");
            if (s === "result" && text && box) box.value = text;
          }
        },
      });
    };

    // navigation
    const readBox = () => { const v = box ? String(box.value || "").trim() : ""; if (v) values[f.name] = v; };
    step.querySelector(".kids-back").onclick = () => { if (idx > 0) { stopSpeaking(); go(idx - 1); } };
    step.querySelector(".kids-next").onclick = () => {
      readBox();
      if (f.required && !values[f.name]) { if (box) { box.classList.add("invalid"); box.focus(); } sayQuestion(); return; }
      stopSpeaking();
      if (last) finish(); else go(idx + 1);
    };
  }
  render();
}

// --------------------------------------------------------------------------- tiny markdown reader
// A small, safe subset renderer (escapes first, then re-applies a handful of constructs the agent
// actually uses): headings, **bold**, *italic*, `code`, ```fenced```, -/1. lists, [links](url).
function mdInline(t) {
  t = escapeHtml(t);
  t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
  t = t.replace(/(^|[^_])_([^_\n]+)_/g, "$1<em>$2</em>");
  t = t.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return t;
}
function renderMarkdown(src) {
  src = String(src == null ? "" : src);
  const blocks = [];
  src = src.replace(/```(\w*)\n?([\s\S]*?)```/g, (m, lang, code) => {
    blocks.push(`<pre class="md-pre"><code>${escapeHtml(code.replace(/\n$/, ""))}</code></pre>`);
    return ` B${blocks.length - 1} `;
  });
  const lines = src.split(/\r?\n/);
  let html = "", i = 0;
  const isList = (l) => /^\s*[-*]\s+/.test(l) || /^\s*\d+\.\s+/.test(l);
  while (i < lines.length) {
    const line = lines[i];
    const pb = line.match(/^ B(\d+) $/);
    if (pb) { html += blocks[+pb[1]] || ""; i++; continue; }
    if (/^\s*$/.test(line)) { i++; continue; }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) { const n = h[1].length; html += `<h${n} class="md-h">${mdInline(h[2])}</h${n}>`; i++; continue; }
    if (/^\s*[-*]\s+/.test(line)) {
      html += "<ul class='md-ul'>";
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { html += `<li>${mdInline(lines[i].replace(/^\s*[-*]\s+/, ""))}</li>`; i++; }
      html += "</ul>"; continue;
    }
    if (/^\s*\d+\.\s+/.test(line)) {
      html += "<ol class='md-ol'>";
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) { html += `<li>${mdInline(lines[i].replace(/^\s*\d+\.\s+/, ""))}</li>`; i++; }
      html += "</ol>"; continue;
    }
    const para = [line]; i++;
    while (i < lines.length && !/^\s*$/.test(lines[i]) && !isList(lines[i]) &&
           !/^(#{1,4})\s+/.test(lines[i]) && !/^ B\d+ $/.test(lines[i])) { para.push(lines[i]); i++; }
    html += `<p>${para.map(mdInline).join("<br>")}</p>`;
  }
  return html;
}
// Hidden control tag the agent emits to tell the console which model fits the upcoming step
// (story = creative/DeepSeek, craft = fast/MiniMax). Stripped from what the user sees.
const STAGE_RE = /\[\[stage:(story|craft|world|character|build|validate|research|done)\]\]/ig;
function detectStage(md) {
  const all = String(md || "").match(STAGE_RE);
  if (!all || !all.length) return null;
  const x = /stage:(\w+)/i.exec(all[all.length - 1]);
  return x ? x[1].toLowerCase() : null;
}

function renderAssistant(bubble) {
  if (!bubble) return;
  const md = (bubble._md || "").replace(STAGE_RE, "").trimEnd();
  const open = md.indexOf("```form");
  if (open >= 0 && !/```form[\s\S]*?```/.test(md)) {
    // form block has started streaming but isn't closed yet — don't show raw JSON, show a hint
    bubble.innerHTML = renderMarkdown(md.slice(0, open)) + '<p class="md-prep">📝 Preparing options…</p>';
  } else {
    bubble.innerHTML = renderMarkdown(md);
  }
}

// ------------------------------------------------------------------ agent-driven (dynamic) forms
// The agent asks for choices by emitting a ```form {…json…}``` block (see FORM PROTOCOL in the
// server brief). We pull it out of the message and render it as a real form right in the chat.
function extractForm(md) {
  const tagged = md.match(/```form\s*([\s\S]*?)```/);
  if (tagged) {
    try { const o = JSON.parse(tagged[1].trim()); if (o && Array.isArray(o.fields)) return { spec: o, raw: tagged[0] }; } catch (e) {}
  }
  const re = /```(?:json)?\s*([\s\S]*?)```/g; let m;
  while ((m = re.exec(md))) {
    try { const o = JSON.parse(m[1].trim()); if (o && Array.isArray(o.fields)) return { spec: o, raw: m[0] }; } catch (e) {}
  }
  return null;
}
function dynFieldHtml(f) {
  const label = escapeHtml(f.label || f.name || "");
  if (f.type === "textarea") {
    return `<label class="field"><span>${label}</span><textarea name="${escapeHtml(f.name)}" rows="2" placeholder="${escapeHtml(f.placeholder || "")}"></textarea></label>`;
  }
  if (f.type === "select" && Array.isArray(f.options)) {
    const opts = f.options.map(o => `<option value="${escapeHtml(o)}">${escapeHtml(o)}</option>`).join("") +
      `<option value="__other__">✏️ Other…</option>`;
    return `<label class="field"><span>${label}</span>` +
      `<select name="${escapeHtml(f.name)}" data-other>${opts}</select>` +
      `<input type="text" class="other hide" data-otherfor="${escapeHtml(f.name)}" placeholder="Type your own…"></label>`;
  }
  return `<label class="field"><span>${label}</span><input type="text" name="${escapeHtml(f.name)}" placeholder="${escapeHtml(f.placeholder || "")}"></label>`;
}
function renderInlineForm(spec) {
  if (!messagesEl) return;
  const fields = Array.isArray(spec.fields) ? spec.fields : [];
  const card = document.createElement("div");
  card.className = "msg assistant formcard";
  card.innerHTML =
    (spec.title ? `<div class="fc-title">${escapeHtml(spec.title)}</div>` : "") +
    (spec.intro ? `<div class="fc-intro">${escapeHtml(spec.intro)}</div>` : "") +
    `<form class="guided fc-form">` + fields.map(dynFieldHtml).join("") +
    `<div class="form-actions"><button type="submit" class="btn small">Send answers ▸</button></div></form>`;
  messagesEl.appendChild(card);
  const form = card.querySelector("form");
  if (!form) return;
  form.querySelectorAll("select[data-other]").forEach(sel => {
    sel.addEventListener("change", () => {
      const ti = form.querySelector(`[data-otherfor="${sel.name}"]`);
      if (ti) { ti.classList.toggle("hide", sel.value !== "__other__"); if (sel.value === "__other__") ti.focus(); }
    });
  });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const answers = [];
    for (const f of fields) {
      const el = form.querySelector(`[name="${f.name}"]`);
      let val = el ? String(el.value || "").trim() : "";
      if (el && el.tagName === "SELECT" && val === "__other__") {
        const ti = form.querySelector(`[data-otherfor="${f.name}"]`);
        val = ti ? String(ti.value || "").trim() : "";
      }
      answers.push(`• ${f.label || f.name}: ${val || "(no preference)"}`);
    }
    form.querySelectorAll("input,select,button,textarea").forEach(x => { x.disabled = true; });
    streamChat("Here are my answers:\n" + answers.join("\n"));
  });
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

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
}
function tickElapsed() {
  const s = Math.round((Date.now() - activityStart) / 1000);
  setText("#activity-elapsed", s + "s");
}
function setActivity(text) { if (text) setText("#activity-text", text); }
function stopActivity() {
  if (activityTimer) { clearInterval(activityTimer); activityTimer = null; }
  hide($("#activity"));
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

// --------------------------------------------------------------------------------------- streaming
async function streamChat(prompt) {
  if (busy) return;
  stopSpeaking();
  hideQuickReplies();
  closeForm();
  setBusy(true);
  startActivity("Sending…");
  // Ticking "New session" starts a clean transcript so the resumed history doesn't bleed in.
  if ($("#newsess") && $("#newsess").checked) clearSession();
  addMsg("user", prompt);
  pushMsg("user", prompt);
  const state = { curBubble: null, toolEls: new Map(), thinkEls: new Map() };
  currentAbort = new AbortController();
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, sessionId: ($("#newsess") && $("#newsess").checked) ? null : sessionId, model: currentModel(), kids: kidsMode }),
      signal: currentAbort.signal,
    });
    if (!res.ok || !res.body) {
      addMsg("system", "Server error: " + res.status + " " + (await res.text().catch(() => "")), "system");
      return;
    }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop();
      for (const part of parts) {
        const line = part.replace(/^data: /, "").trim();
        if (!line) continue;
        let ev;
        try { ev = JSON.parse(line); } catch { continue; }
        logDebugEvent(ev);
        handleEvent(ev, state);
      }
    }
  } catch (e) {
    // A user-initiated Stop aborts the fetch — that's expected, not an error.
    if (!(e && e.name === "AbortError")) {
      addMsg("system", "Connection error: " + (e && e.message ? e.message : e), "system");
    }
  } finally {
    currentAbort = null;
    setBusy(false);
    stopActivity();
    finishThinking(state); // close out any still-streaming thinking sections
    const ns = $("#newsess");
    if (ns && ns.checked) ns.checked = false; // continue the session next time
    // If the agent ended its turn with a ```form block, render it as a real form (and hide the
    // raw JSON from the message). Otherwise offer the generic quick-reply chips.
    let formShown = false;
    if (state.curBubble) {
      // Update the "currently using" chip from the server's resolved model + last stage tag.
      // (In Auto mode the server tells us which model it actually used for this turn — useful
      // for the chip even when the user has it pinned. The picker itself is NOT changed when
      // pinned; that only happens in Auto mode, below.)
      if (state.resolvedModel) resolvedModel = state.resolvedModel;
      paintStageChip();
      // Auto mode + a new stage tag from the agent → switch the picker to that tier for next time
      // (we don't override an explicit pin).
      if (currentModel() === M_AUTO && state.lastStage) {
        const want = state.lastStage === "story" ? M_CREATIVE
                   : state.lastStage === "research" ? M_SEARCH
                   : M_FAST;
        const labels = { [M_FAST]: "Nemotron (fast)", [M_CREATIVE]: "DeepSeek (creative)", [M_SEARCH]: "MiniMax (research)" };
        addMsg("system", `↻ Auto → next turn will use ${labels[want]} (the agent flagged [[stage:${state.lastStage}]]).`, "system");
      }
      const found = extractForm(state.curBubble._md || "");
      if (found) {
        state.curBubble._md = (state.curBubble._md || "").replace(found.raw, "").trim();
        renderAssistant(state.curBubble);
        if (kidsMode) {
          // one-question-at-a-time wizard; speak any lead-in text with the first question
          const lead = mdToSpeech(state.curBubble._md);
          openKidsWizard(found.spec, (values) => {
            const lines = (found.spec.fields || []).map(f => `• ${f.label || f.name}: ${values[f.name] || "(no preference)"}`);
            streamChat("Here are my answers:\n" + lines.join("\n"));
          }, lead);
        } else {
          renderInlineForm(found.spec);
        }
        formShown = true;
      }
      // read the reply aloud (skip when a form/wizard is up — the wizard speaks its own questions)
      if (!formShown) {
        addSpeakButton(state.curBubble);
        const plain = mdToSpeech(state.curBubble._md);
        if ((ttsOn || kidsMode) && plain) speak(plain);
      }
      // Persist the finished assistant turn (form JSON already stripped from _md above).
      if (state.curBubble._md) pushMsg("assistant", state.curBubble._md);
    }
    if (!formShown) showQuickReplies();
    loadLibrary();
    refreshPreview();
  }
}

const TOOL_ICON = { pending: "•", running: "•", completed: "✓", error: "✗" };
const TOOL_VERB = { bash: "ran", edit: "edited", write: "wrote", read: "read", glob: "searched", grep: "searched", webfetch: "fetched", list: "listed", task: "task", todowrite: "planned" };
function toolLine(ev) {
  const icon = TOOL_ICON[ev.status] || "•";
  const verb = TOOL_VERB[ev.tool] || ev.tool;
  return `${icon} ${verb}${ev.title ? ": " + ev.title : ""}`;
}

function handleEvent(ev, state) {
  switch (ev.type) {
    case "session":
      sessionId = ev.sessionId;
      setText("#conn", "session " + String(ev.sessionId || "").slice(0, 8));
      persistSession();
      break;
    case "model":
      // Server tells us which model it actually used for this turn (in Auto mode the agent's
      // stage tag from the previous turn decided it). Stash it so the chip can show it.
      if (ev.model) { state.resolvedModel = ev.model; resolvedModel = ev.model; }
      if (ev.stage) { state.lastStage = ev.stage; lastStage = ev.stage; }
      paintStageChip();
      break;
    case "stage":
      // Streamed as soon as the agent's [[stage:...]] tag is observed in the live text.
      if (ev.stage) { state.lastStage = ev.stage; lastStage = ev.stage; }
      paintStageChip();
      break;
    case "status":
      // busy/idle heartbeat from OpenCode
      if (ev.state === "busy") { if (!activityTimer) startActivity("Thinking…"); }
      break;
    case "reasoning": {
      // The agent's chain-of-thought, streamed live. Each reasoning part is its own
      // collapsible section; the tail also shows in the summary + activity strip.
      let el = state.thinkEls.get(ev.id);
      if (!el) {
        el = addThinking();
        if (!el) break;
        state.thinkEls.set(ev.id, el);
        state.curBubble = null; // text after thinking starts a fresh bubble
      }
      el._txt = (el._txt || "") + ev.text;
      updateThinking(el);
      const tail = (el._txt || "").replace(/\s+/g, " ").trim().slice(-70);
      setActivity(tail ? "💭 " + tail : "Thinking…");
      break;
    }
    case "assistant": {
      finishThinking(state); // prose resumed — the thinking section(s) are complete
      if (!state.curBubble) { state.curBubble = addMsg("assistant", ""); if (state.curBubble) state.curBubble._md = ""; }
      if (state.curBubble) { state.curBubble._md = (state.curBubble._md || "") + ev.text; renderAssistant(state.curBubble); }
      if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
      setActivity("Writing…");
      break;
    }
    case "tool": {
      // One expandable row per tool call; pending→running→completed update it in place.
      // The summary is the compact line; expand to see the full input and (later) output.
      finishThinking(state);
      let el = state.toolEls.get(ev.id);
      if (!el) {
        el = addToolRow();
        if (!el) break;
        state.toolEls.set(ev.id, el);
        state.curBubble = null; // text after a tool starts a fresh bubble
      }
      const sum = el.querySelector(".tool-sum");
      if (sum) sum.textContent = toolLine(ev);
      if (ev.input) setToolPre(el, ".tool-in", "input", toolInputText(ev));
      if (ev.error) setToolPre(el, ".tool-out", "error", ev.error);
      else if (ev.output) setToolPre(el, ".tool-out", "output", ev.output);
      el.classList.toggle("running", ev.status === "running" || ev.status === "pending");
      el.classList.toggle("done", ev.status === "completed");
      el.classList.toggle("err", ev.status === "error");
      if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
      // mirror the freshest action into the activity strip
      const verb = TOOL_VERB[ev.tool] || ev.tool;
      setActivity(`${verb}${ev.title ? ": " + ev.title : "…"}`);
      break;
    }
    case "result": if (ev.text) addMsg("system", ev.text, "system"); break;
    case "error": addMsg("system", "⚠ " + ev.text, "system"); break;
    case "done": break;
  }
}

// ================================================================================ guided forms
const AGE_BANDS = ["0-3", "3-5", "5-7", "7-9"];
const TONES = ["gentle & cozy", "funny & playful", "adventurous", "magical & dreamy", "reassuring (bedtime)", "silly & energetic"];
const ART = ["soft watercolor storybook", "bold flat cartoon", "dreamy pastel", "cut-paper collage", "crayon / hand-drawn", "retro mid-century"];

const FORMS = {
  book: {
    title: "✨ New storybook",
    submit: "Create book ▸",
    model: M_AUTO,
    fields: [
      { name: "about", label: "What's it about?", type: "textarea", required: true, placeholder: "a shy dragon who learns to share" },
      { name: "age", label: "Age band", type: "select", options: AGE_BANDS, default: "5-7" },
      { name: "tone", label: "Tone", type: "select", options: TONES },
      { name: "art", label: "Art-style vibe", type: "select", options: ART },
      { name: "characters", label: "Main character(s)", type: "text", placeholder: "e.g. Ember the dragon (or leave blank)" },
      { name: "skill", label: "Reading focus (optional)", type: "text", placeholder: "rhyming, sight words, short vowels…" },
    ],
    build: (v) => [
      "I'd like a brand-new interactive storybook. Here are the details:",
      `• About: ${v.about}`,
      `• Age band: ${v.age}`,
      `• Tone: ${v.tone}`,
      `• Art-style vibe: ${v.art}`,
      `• Main character(s): ${v.characters || "you suggest a couple"}`,
      `• Reading focus: ${v.skill || "age-appropriate"}`,
      "",
      "Please work step by step and confirm with me at each stage: build the WORLD first and check with me, then the CHARACTERS (with reference art), then write the STORY. Start now with a short plan and the world.",
    ].join("\n"),
  },
  world: {
    title: "🌍 New world",
    submit: "Create world ▸",
    model: M_AUTO,
    fields: [
      { name: "name", label: "Name idea (optional)", type: "text", placeholder: "e.g. The Whispering Woods" },
      { name: "setting", label: "Setting / premise", type: "textarea", required: true, placeholder: "an underwater city of curious octopus children" },
      { name: "age", label: "Primary age band", type: "select", options: AGE_BANDS, default: "5-7" },
      { name: "mood", label: "Mood", type: "select", options: TONES },
      { name: "art", label: "Art-style vibe", type: "select", options: ART },
      { name: "motifs", label: "Key motifs (optional)", type: "text", placeholder: "bioluminescence, kelp forests, pearls" },
    ],
    build: (v) => [
      "Create a new story WORLD (world bible + locked art style):",
      `• Name idea: ${v.name || "you propose one"}`,
      `• Setting / premise: ${v.setting}`,
      `• Primary age band: ${v.age}`,
      `• Mood: ${v.mood}`,
      `• Art-style vibe: ${v.art}`,
      `• Key motifs: ${v.motifs || "you suggest a few"}`,
      "",
      "Propose a short world summary + art style, scaffold ONLY the world, then stop and ask me to confirm before we design characters.",
    ].join("\n"),
  },
  character: {
    title: "🧸 New character",
    submit: "Create character ▸",
    model: M_AUTO,
    fields: [
      { name: "world", label: "World", type: "world", required: true },
      { name: "name", label: "Name", type: "text", required: true, placeholder: "Tilly" },
      { name: "kind", label: "Species / role", type: "text", placeholder: "a brave little mouse" },
      { name: "traits", label: "Personality traits", type: "text", placeholder: "curious, loyal, a bit reckless" },
      { name: "looks", label: "Appearance notes", type: "textarea", placeholder: "tiny grey mouse, red scarf, acorn-cap hat" },
      { name: "evolution", label: "Evolution idea (optional)", type: "text", placeholder: "timid → brave over the series" },
    ],
    build: (v) => [
      `Add a new CHARACTER to the world "${v.world}":`,
      `• Name: ${v.name}`,
      `• Species / role: ${v.kind || "you decide"}`,
      `• Personality traits: ${v.traits || "you suggest"}`,
      `• Appearance: ${v.looks || "design something that fits the world's art style"}`,
      `• Evolution idea: ${v.evolution || "a simple growth arc"}`,
      "",
      "Write a full character bible with a locked appearance_token and an evolution track, generate a reference sheet, then show me and ask if it looks good.",
    ].join("\n"),
  },
  story: {
    title: "📖 New story",
    submit: "Write story ▸",
    model: M_AUTO,
    fields: [
      { name: "world", label: "World", type: "world", required: true },
      { name: "characters", label: "Starring", type: "text", required: true, placeholder: "Pip and Olo" },
      { name: "age", label: "Age band", type: "select", options: AGE_BANDS, default: "5-7" },
      { name: "about", label: "Plot / theme", type: "textarea", required: true, placeholder: "losing a first tooth" },
      { name: "interactions", label: "Interaction focus (optional)", type: "text", placeholder: "rhyme, seek-and-find, a choice" },
    ],
    build: (v) => [
      `Write a new STORY in the world "${v.world}":`,
      `• Starring: ${v.characters}`,
      `• Age band: ${v.age}`,
      `• Plot / theme: ${v.about}`,
      `• Interaction focus: ${v.interactions || "a good mix for the age"}`,
      "",
      "Keep characters consistent with their bibles. Plan the spine and check with me before writing all the pages and generating images.",
    ].join("\n"),
  },
};

let currentForm = null;

function worldOptionsHtml() {
  if (!libraryWorlds.length) return "";
  return libraryWorlds.map(w => `<option value="${escapeHtml(w.slug)}">${escapeHtml(w.title)} (${escapeHtml(w.slug)})</option>`).join("");
}

function fieldHtml(f) {
  const id = "f_" + f.name;
  const req = f.required ? "required" : "";
  let input;
  if (f.type === "textarea") {
    input = `<textarea id="${id}" name="${f.name}" rows="2" placeholder="${escapeHtml(f.placeholder || "")}" ${req}></textarea>`;
  } else if (f.type === "select") {
    input = `<select id="${id}" name="${f.name}">` +
      f.options.map(o => `<option value="${escapeHtml(o)}" ${o === f.default ? "selected" : ""}>${escapeHtml(o)}</option>`).join("") +
      `</select>`;
  } else if (f.type === "world") {
    const opts = worldOptionsHtml();
    input = opts
      ? `<select id="${id}" name="${f.name}" ${req}>${opts}</select>`
      : `<input id="${id}" name="${f.name}" type="text" placeholder="world slug (none yet — make a world first)" ${req}>`;
  } else {
    input = `<input id="${id}" name="${f.name}" type="text" placeholder="${escapeHtml(f.placeholder || "")}" ${req}>`;
  }
  return `<label class="field"><span>${escapeHtml(f.label)}</span>${input}</label>`;
}

function openForm(key) {
  const def = FORMS[key];
  if (!def) return;
  currentForm = key;
  if (def.model) setModel(def.model); // e.g. the story form prefers the more-creative model
  setText("#form-title", def.title);
  const form = $("#guided-form");
  if (form) {
    form.innerHTML = def.fields.map(fieldHtml).join("") +
      `<div class="form-actions">
         <button type="button" class="btn ghost small" id="form-cancel">Cancel</button>
         <button type="submit" class="btn small">${escapeHtml(def.submit)}</button>
       </div>`;
    const cancel = $("#form-cancel");
    if (cancel) cancel.onclick = closeForm;
  }
  show($("#formwrap"));
  hideQuickReplies();
  const first = $("#guided-form [name]");
  if (first) first.focus();
}

function closeForm() {
  currentForm = null;
  hide($("#formwrap"));
}

function submitForm(e) {
  e.preventDefault();
  const def = FORMS[currentForm];
  if (!def) return;
  const form = $("#guided-form");
  const values = {};
  let missing = null;
  for (const f of def.fields) {
    const el = form ? form.querySelector(`[name="${f.name}"]`) : null;
    const val = el ? String(el.value || "").trim() : "";
    if (f.required && !val) { missing = missing || el; }
    values[f.name] = val;
  }
  if (missing) { missing.focus(); missing.classList.add("invalid"); return; }
  const prompt = def.build(values);
  closeForm();
  streamChat(prompt);
}

// ================================================================================== debug tab
// Two tools for seeing what's really going on:
//  1) a LIVE event log — every SSE event this browser receives, appended as it arrives;
//  2) the FULL conversation — fetched from the server (which proxies OpenCode), including
//     thinking, every tool call's input/output, and the raw JSON of each message.
const DEBUG_LOG_MAX = 600;
function logDebugEvent(ev) {
  const pre = $("#debug-events");
  if (!pre) return;
  let line = "";
  try { line = JSON.stringify(ev); } catch (e) { line = String(ev); }
  if (line.length > 500) line = line.slice(0, 500) + "…";
  pre.appendChild(document.createTextNode(line + "\n"));
  while (pre.childNodes.length > DEBUG_LOG_MAX) pre.removeChild(pre.firstChild);
  const auto = $("#debug-autoscroll");
  if (!auto || auto.checked) pre.scrollTop = pre.scrollHeight;
}

async function loadDebugConvo() {
  const box = $("#debug-convo");
  if (!box) return;
  if (!sessionId) {
    box.innerHTML = '<div class="empty">No session yet — send a message first.</div>';
    return;
  }
  box.innerHTML = '<div class="empty">Loading…</div>';
  try {
    const r = await fetch(`/api/session/${encodeURIComponent(sessionId)}/messages`);
    const data = await r.json();
    if (!r.ok) {
      box.innerHTML = `<div class="empty">⚠ ${escapeHtml((data && data.error) || ("HTTP " + r.status))}</div>`;
      return;
    }
    renderDebugConvo(box, Array.isArray(data) ? data : []);
  } catch (e) {
    box.innerHTML = `<div class="empty">⚠ ${escapeHtml(e.message || String(e))}</div>`;
  }
}

function renderDebugConvo(box, msgs) {
  if (!msgs.length) { box.innerHTML = '<div class="empty">No messages in this session.</div>'; return; }
  box.innerHTML = "";
  for (const m of msgs) {
    const info = m.info || m;             // OpenCode returns {info, parts}; tolerate flat too
    const parts = Array.isArray(m.parts) ? m.parts : [];
    const d = document.createElement("details");
    d.className = "dbg-msg " + (info.role === "user" ? "user" : "assistant");
    const when = info.time && info.time.created ? new Date(info.time.created).toLocaleTimeString() : "";
    const kinds = parts.map(p => p.type).filter(Boolean).join(" · ");
    const sum = document.createElement("summary");
    sum.innerHTML = `<b>${escapeHtml(info.role || "?")}</b> <span class="dbg-when">${escapeHtml(when)}</span> <em>${escapeHtml(kinds)}</em>`;
    d.appendChild(sum);
    for (const p of parts) {
      const pd = document.createElement("details");
      pd.className = "dbg-part";
      let label = p.type || "part", body = "";
      if (p.type === "text" || p.type === "reasoning") {
        body = p.text || "";
        if (p.type === "reasoning") label = "reasoning 💭";
      } else if (p.type === "tool") {
        const st = p.state || {};
        label = `tool: ${p.tool || "?"} (${st.status || "?"})`;
        body = "input:\n" + JSON.stringify(st.input || {}, null, 2) +
               (st.output ? "\n\noutput:\n" + String(st.output) : "") +
               (st.error ? "\n\nerror:\n" + String(st.error) : "");
      } else {
        body = JSON.stringify(p, null, 2);
      }
      pd.innerHTML = `<summary>${escapeHtml(label)}</summary>`;
      const pre = document.createElement("pre");
      pre.textContent = body;
      pd.appendChild(pre);
      d.appendChild(pd);
    }
    const raw = document.createElement("details");
    raw.className = "dbg-part raw";
    raw.innerHTML = "<summary>raw json</summary>";
    const rp = document.createElement("pre");
    try { rp.textContent = JSON.stringify(m, null, 2); } catch (e) { rp.textContent = String(m); }
    raw.appendChild(rp);
    d.appendChild(raw);
    box.appendChild(d);
  }
}

// ================================================================================= library
async function loadLibrary() {
  try {
    const res = await fetch("/api/library");
    const data = await res.json();
    libraryWorlds = data.worlds || [];
    renderLibrary(libraryWorlds, data.errors || []);
  } catch (e) {
    const lib = $("#library");
    if (lib) lib.innerHTML = '<div class="empty">Could not load library: ' + escapeHtml(e.message) + "</div>";
  }
}

function pill(text, cls) { return `<span class="pill ${cls || ""}">${escapeHtml(text)}</span>`; }

function renderLibrary(worlds, errors) {
  const lib = $("#library");
  if (!lib) return;
  // Shelf totals in the bar above the list.
  const counts = $("#lib-counts");
  if (counts) {
    const ns = worlds.reduce((a, w) => a + w.stories.length, 0);
    const np = worlds.reduce((a, w) => a + w.stories.filter(s => s.status === "published").length, 0);
    counts.textContent = worlds.length
      ? `${worlds.length} world${worlds.length === 1 ? "" : "s"} · ${ns} ${ns === 1 ? "story" : "stories"} · ${np} published`
      : "Everything on your shelves — drafts & published.";
  }
  // A malformed file no longer blanks the library — show the good worlds and warn about bad files.
  const banner = (errors && errors.length)
    ? `<div class="libwarn">⚠ ${errors.length} file(s) couldn't be read and were skipped:<ul>` +
        errors.map(e => `<li>${escapeHtml(e)}</li>`).join("") + `</ul></div>`
    : "";
  if (!worlds.length) {
    lib.innerHTML = banner + '<div class="empty">No worlds yet. Pick a guided form on the left to make your first book ✨</div>';
    return;
  }
  lib.innerHTML = banner + worlds.map(w => `
    <article class="world">
      ${(w.palette||[]).length ? `<div class="swatches">${w.palette.map(p=>`<span class="sw" title="${escapeHtml(p.name)}" style="background:${escapeHtml(p.hex)}"></span>`).join("")}</div>` : ""}
      <div class="world-head">
        <h3>${escapeHtml(w.title)}</h3>
        <span class="world-count">${w.stories.length} ${w.stories.length === 1 ? "story" : "stories"} · ${w.characters.length} cast</span>
      </div>
      <p class="tagline">${escapeHtml(w.tagline || w.premise || "")}</p>
      <div class="row">${(w.age_bands||[]).map(a=>pill(a,"age")).join("")}${(w.themes||[]).slice(0,4).map(t=>pill(t)).join("")}</div>
      <div class="subhead">Bookshelf</div>
      <div class="shelf">
      ${w.stories.map(s=>{
        const pub = s.status === "published";
        // A draft only lives in the studio preview build; a published story lives in BOTH the
        // studio preview and the public preview. Linking straight to the right build avoids
        // the user landing on a 404 (drafts are not in /publish-preview/).
        const readHref = pub
          ? `/publish-preview/story/${w.slug}/${s.slug}/index.html`
          : `/preview/story/${w.slug}/${s.slug}/index.html`;
        // Cover: page-00 art from the studio preview build; falls back to a paper cover.
        const coverSrc = `/preview/story/${encodeURIComponent(w.slug)}/${encodeURIComponent(s.slug)}/images/page-00.png`;
        return `
        <a class="bookcard ${pub ? "is-pub" : "is-draft"}" href="${readHref}" target="_blank"
           title="${escapeHtml(s.logline || s.title || "")}${pub ? "" : " (draft — opens the studio preview)"}">
          <span class="bookcover">
            <img src="${coverSrc}" alt="" loading="lazy" onerror="this.parentElement.classList.add('noimg')">
            <span class="ribbon ${pub ? "pub" : "draft"}">${pub ? "published" : "draft"}</span>
            ${s.logline ? `<span class="caption">${escapeHtml(s.logline)}</span>` : ""}
            <span class="readhint">Read ↗</span>
          </span>
          <span class="booktitle">${escapeHtml(s.title)}</span>
          <span class="bookmeta">${escapeHtml(s.age_band || "")} · ${s.pages} pages · ${s.interactions} ${s.interactions === 1 ? "game" : "games"}</span>
        </a>`;
      }).join("") || '<p class="tagline">No stories yet.</p>'}
      </div>
      <div class="subhead">Cast</div>
      <div class="cast">
      ${w.characters.map(c=>{
        // Reference art is copied into the preview build as refs/<slug>-model-sheet.png;
        // the onerror chain retries .svg, then falls back to a friendly bean.
        const av = (c.has_reference && c.slug)
          ? `<img src="/preview/world/${encodeURIComponent(w.slug)}/refs/${encodeURIComponent(c.slug)}-model-sheet.png" alt="" loading="lazy"
               onerror="if(this.dataset.f){this.closest('.castchip').classList.add('noimg');}else{this.dataset.f=1;this.src=this.src.replace('.png','.svg');}">`
          : "";
        return `<button type="button" class="castchip ${av ? "" : "noimg"}" data-w="${escapeHtml(w.slug)}" data-c="${escapeHtml(c.slug || c.name || "")}"
          title="${escapeHtml(c.one_liner || c.role || "")} — click for the character card">
          <span class="cast-avatar">${av}</span>
          <span class="cast-name">${escapeHtml(c.name)}${c.stages && c.stages.length > 1 ? ` <em>· ${c.stages.length} stages</em>` : ""}</span>
        </button>`;
      }).join("") || '<p class="tagline">No characters yet.</p>'}
      </div>
    </article>`).join("");
}

// ------------------------------------------------------------ character card (library popup)
// Clicking a cast chip opens the character's bible as a pop-up card: reference art, who they
// are, personality, voice, and their evolution track. Pure read-only — closes on ✕, backdrop
// click, or Escape.
function closeCharacterCard() {
  const ov = $("#char-overlay");
  if (ov) {
    if (ov._esc) document.removeEventListener("keydown", ov._esc);
    ov.remove();
  }
}
function openCharacterCard(w, c) {
  closeCharacterCard();
  const pillRow = (items, cls) => (items && items.length)
    ? `<div class="row">${items.map(t => pill(t, cls)).join("")}</div>` : "";
  const listRows = (items) => (items && items.length)
    ? `<ul class="cc-list">${items.map(t => `<li>${escapeHtml(t)}</li>`).join("")}</ul>` : "";
  const section = (label, body) => body ? `<div class="cc-section"><div class="subhead">${label}</div>${body}</div>` : "";

  // Reference art from the studio preview build (refs/<slug>-<filename>); the onerror chain
  // retries .svg before giving up (some characters only have an svg sheet).
  const refName = c.reference || "model-sheet.png";
  const refSrc = `/preview/world/${encodeURIComponent(w.slug)}/refs/${encodeURIComponent((c.slug || "") + "-" + refName)}`;
  const art = c.has_reference
    ? `<div class="cc-art"><img src="${refSrc}" alt="${escapeHtml(c.name || "")} reference sheet"
         onerror="if(this.dataset.f){this.closest('.cc-art').classList.add('noimg');}else{this.dataset.f=1;this.src=this.src.replace(/\\.[a-z]+$/,'.svg');}"></div>`
    : `<div class="cc-art noimg"></div>`;

  const who = [c.species, c.pronouns, c.role].filter(Boolean).map(escapeHtml).join(" · ");
  const evo = (c.evolution && c.evolution.length)
    ? `<ol class="cc-evo">${c.evolution.map(st =>
        `<li><strong>${escapeHtml(st.stage || "")}</strong>${st.summary ? ` — ${escapeHtml(st.summary)}` : ""}</li>`).join("")}</ol>`
    : "";
  const phrases = (c.catchphrases && c.catchphrases.length)
    ? `<div class="cc-phrases">${c.catchphrases.map(p => `<span class="cc-phrase">“${escapeHtml(p)}”</span>`).join("")}</div>` : "";

  const ov = document.createElement("div");
  ov.className = "char-overlay";
  ov.id = "char-overlay";
  ov.innerHTML = `<div class="char-card" role="dialog" aria-label="${escapeHtml(c.name || "character")}">
    <button class="kids-x cc-x" title="Close">✕</button>
    ${art}
    <div class="cc-body">
      <div class="cc-head">
        <h3>${escapeHtml(c.name || "")}</h3>
        ${who ? `<span class="cc-who">${who}</span>` : ""}
      </div>
      ${c.one_liner ? `<p class="cc-oneliner">${escapeHtml(c.one_liner)}</p>` : ""}
      ${section("Personality", pillRow(c.traits))}
      ${section("Wants", c.motivation ? `<p class="cc-text">${escapeHtml(c.motivation)}</p>` : "")}
      ${section("Flaws &amp; quirks", listRows([].concat(c.flaws || [], c.quirks || [])))}
      ${section("How they talk", (c.speech_style ? `<p class="cc-text">${escapeHtml(c.speech_style)}</p>` : "") + phrases)}
      ${section("Evolution", evo)}
      <p class="cc-foot">from <strong>${escapeHtml(w.title || w.slug)}</strong> · <code>characters/${escapeHtml(c.slug || "")}.yaml</code></p>
    </div>
  </div>`;
  document.body.appendChild(ov);
  ov.addEventListener("click", (e) => { if (e.target === ov) closeCharacterCard(); });
  const x = ov.querySelector(".cc-x");
  if (x) x.onclick = closeCharacterCard;
  ov._esc = (e) => { if (e.key === "Escape") closeCharacterCard(); };
  document.addEventListener("keydown", ov._esc);
}

function refreshPreview() {
  const f = $("#preview");
  if (f) f.src = f.src.split("?")[0] + "?t=" + Date.now();
}
function refreshPublicPreview() {
  const f = $("#public-preview");
  if (f) f.src = f.src.split("?")[0] + "?t=" + Date.now();
}
async function refreshPublishStatus() {
  // Surface "last built 2m ago" on the public-preview tab and disable its iframe until a
  // build exists (so the user doesn't see a 404 iframe with no explanation).
  const badge = $("#public-badge");
  const frame = $("#public-preview");
  try {
    const r = await fetch("/api/publish/status");
    const s = await r.json();
    if (badge) {
      if (s.built) {
        const m = s.last_built_mtime ? Math.max(1, Math.round((Date.now()/1000 - s.last_built_mtime) / 60)) : null;
        badge.textContent = m != null ? `built ${m}m ago` : "built";
        badge.className = "badge pub ok";
      } else {
        badge.textContent = "no build yet — click Publish";
        badge.className = "badge pub empty";
      }
    }
    if (frame) {
      // A 404 iframe renders as the studio's 404 page inside; the badge tells the user
      // to click Publish first. We still load the iframe so the tab is ready to show
      // the result the moment they rebuild.
      frame.dataset.built = s.built ? "1" : "0";
    }
  } catch (e) { /* non-fatal — leave the badge as-is */ }
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

// ===================================================================================== wire up
const modelSelect = $("#model-select");
if (modelSelect) modelSelect.addEventListener("change", () => { persistModelChoice(); paintStageChip(); });
const composer = $("#composer");
if (composer) composer.addEventListener("submit", (e) => {
  e.preventDefault();
  const promptEl = $("#prompt");
  const p = promptEl ? promptEl.value.trim() : "";
  if (!p || busy) return;
  if (promptEl) promptEl.value = "";
  streamChat(p);
});
const promptEl = $("#prompt");
if (promptEl) {
  // Enter sends; Shift+Enter makes a new line (Cmd/Ctrl+Enter still works too).
  promptEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      if (composer) composer.requestSubmit();
    }
  });
  // Grow with the draft (capped) so longer prompts stay visible without manual resizing.
  promptEl.addEventListener("input", () => {
    promptEl.style.height = "auto";
    promptEl.style.height = Math.min(promptEl.scrollHeight + 2, 200) + "px";
  });
}

// A chip launches a guided form — in kids mode it runs as the big one-question wizard instead.
function launchForm(key) {
  const def = FORMS[key];
  if (!def) return;
  if (kidsMode) {
    if (def.model) setModel(def.model);
    openKidsWizard(def, (values) => streamChat(def.build(values)), def.title);
  } else {
    openForm(key);
  }
}
document.querySelectorAll("#form-launchers .chip-btn").forEach(b => b.onclick = () => launchForm(b.dataset.form));
const formClose = $("#form-close");
if (formClose) formClose.onclick = closeForm;
const guided = $("#guided-form");
if (guided) guided.addEventListener("submit", submitForm);

const btnStop = $("#stop"); if (btnStop) btnStop.onclick = stopWorkflow;
// Preview tab: rebuild the studio preview (with drafts) and refresh the iframe in place.
const btnBuild = $("#btn-build");
if (btnBuild) btnBuild.onclick = () => runJob("build", "/api/build", {
  okLabel: "built", failLabel: "build failed",
  onDone: (d) => { if (d && d.ok) refreshPreview(); },
});
// Publish tab, step 3: rebuild the public-only site (what GitHub Pages will deploy) and
// refresh the public iframe + the "built Nm ago" badge.
const btnPublish = $("#btn-publish");
if (btnPublish) btnPublish.onclick = () => runJob("publish", "/api/build/publish", {
  okLabel: "built", failLabel: "build failed",
  onDone: (d) => { if (d && d.ok) { refreshPublicPreview(); refreshPublishStatus(); } },
});
// Publish tab, steps 1–2: the QA gates.
const btnValidate = $("#btn-validate");
if (btnValidate) btnValidate.onclick = () => runJob("validate", "/api/validate", { okLabel: "passed", failLabel: "failing" });
// quality_report.py always exits 0 (it's a scorecard, not a gate) — label it honestly.
const btnQuality = $("#btn-quality");
if (btnQuality) btnQuality.onclick = () => runJob("quality", "/api/quality", { okLabel: "report ready", failLabel: "errored" });
const btnRefresh = $("#btn-refresh"); if (btnRefresh) btnRefresh.onclick = loadLibrary;
// Cast chips are re-rendered on every library refresh — delegate so one handler covers them all.
const libRoot = $("#library");
if (libRoot) libRoot.addEventListener("click", (e) => {
  const chip = e.target.closest(".castchip");
  if (!chip) return;
  const w = libraryWorlds.find(x => x.slug === chip.dataset.w);
  const c = w && (w.characters || []).find(x => (x.slug || x.name) === chip.dataset.c);
  if (w && c) openCharacterCard(w, c);
});
const btnClear = $("#btn-clear"); if (btnClear) btnClear.onclick = clearChat;
// Deploy step: copy-to-clipboard for the ship commands.
document.querySelectorAll(".copybtn").forEach(b => b.onclick = async () => {
  const src = document.getElementById(b.dataset.copy || "");
  const text = src ? src.textContent : "";
  if (!text) return;
  try { await navigator.clipboard.writeText(text); } catch (e) { return; }
  const old = b.textContent;
  b.textContent = "✓";
  setTimeout(() => { b.textContent = old; }, 1200);
});

// Collapse the workbench to a slim icon rail so the writing desk gets the full width.
// Clicking a rail icon expands the panel again on that tab. Persisted across reloads.
const panelToggle = $("#panel-toggle");
function setPanelCollapsed(on) {
  document.body.classList.toggle("panel-collapsed", on);
  try { localStorage.setItem("gb_panel", on ? "1" : "0"); } catch (e) { /* non-fatal */ }
  if (panelToggle) {
    panelToggle.textContent = on ? "⟪" : "⟫";
    panelToggle.title = on ? "Expand panel" : "Collapse panel";
  }
}
if (panelToggle) {
  panelToggle.onclick = () => setPanelCollapsed(!document.body.classList.contains("panel-collapsed"));
  setPanelCollapsed(localStorage.getItem("gb_panel") === "1");
}

document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
  if (document.body.classList.contains("panel-collapsed")) setPanelCollapsed(false);
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
  t.classList.add("active");
  const tab = t.dataset.tab;
  document.querySelectorAll(".tabview").forEach(v => v.classList.toggle("hidden", v.id !== "view-" + tab));
  if (tab === "preview") refreshPreview();
  if (tab === "public") { refreshPublicPreview(); refreshPublishStatus(); }
  if (tab === "debug") loadDebugConvo();
});
const btnDbgRefresh = $("#btn-debug-refresh"); if (btnDbgRefresh) btnDbgRefresh.onclick = loadDebugConvo;
const btnDbgClear = $("#btn-debug-clear");
if (btnDbgClear) btnDbgClear.onclick = () => { const pre = $("#debug-events"); if (pre) pre.textContent = ""; };

// ---- voice & kids-mode controls ---------------------------------------------------------------
// Read-aloud toggle: speak the studio's replies with the local Kokoro voice. The button's
// disabled state is finalized by applyVoiceCaps() once /api/voice resolves.
const btnTts = $("#btn-tts");
if (btnTts) {
  syncToggle("#btn-tts", ttsOn);
  btnTts.onclick = () => {
    ttsOn = !ttsOn;
    localStorage.setItem("gb_tts", ttsOn ? "1" : "0");
    syncToggle("#btn-tts", ttsOn);
    if (!ttsOn) stopSpeaking();
    else speak("Read aloud is on.");
  };
}
// Kids mode toggle: big one-question-at-a-time flow with talk & listen.
const btnKids = $("#btn-kids");
if (btnKids) {
  syncToggle("#btn-kids", kidsMode);
  btnKids.onclick = () => {
    kidsMode = !kidsMode;
    localStorage.setItem("gb_kids", kidsMode ? "1" : "0");
    syncToggle("#btn-kids", kidsMode);
    if (!kidsMode) closeKidsWizard();
    addMsg("system", kidsMode
      ? "🧒 Kids mode on — I'll ask one thing at a time with big buttons you can tap or talk to."
      : "Kids mode off.", "system");
    if (kidsMode && Voice.supportTTS) speak("Kids mode is on. Let's make a story together!");
  };
}
// Composer mic: record a message, transcribe it on the server (faster-whisper), drop it in the box.
// Tap to start, tap again to stop & transcribe.
let composerRec = null;
const micBtn = $("#mic");
if (micBtn) {
  micBtn.onclick = () => {
    const p = $("#prompt");
    if (!Voice.supportSTT) { addMsg("system", "🎤 Voice input needs microphone permission (and `uv sync --group tts` on the server).", "system"); return; }
    if (composerRec) { composerRec.stop(); return; }  // tap again → stop & transcribe
    const base = (p && p.value.trim()) ? p.value.trim() + " " : "";
    composerRec = makeRecorder({
      onState: (s, text) => {
        if (s === "recording") { micBtn.classList.add("rec"); micBtn.classList.remove("busy"); micBtn.textContent = "⏹"; }
        else if (s === "transcribing") { micBtn.classList.remove("rec"); micBtn.classList.add("busy"); micBtn.textContent = "⏳"; }
        else { // result | error
          composerRec = null; micBtn.classList.remove("rec", "busy"); micBtn.textContent = "🎤";
          if (s === "result" && text && p) { p.value = base + text; p.focus(); }
        }
      },
    });
  };
}

addMsg("system", "Welcome to the studio. Tap a card above to start a book, world, character or story — or just type what you'd like to make.", "system");
restoreSession(); // replays a prior conversation (and replaces the welcome) if one was saved
loadModels();
loadVoiceCaps();
loadLibrary();
refreshPublishStatus();
