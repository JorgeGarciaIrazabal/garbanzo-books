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
let libraryWorlds = []; // cached for the world <select> in forms

// ----------------------------------------------------------------- small DOM helpers (null-safe)
function show(el) { if (el) el.classList.remove("hidden"); }
function hide(el) { if (el) el.classList.add("hidden"); }
function setText(sel, text) { const el = $(sel); if (el) el.textContent = text; }
function escapeHtml(s){return String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}

function addMsg(role, text, cls) {
  if (!messagesEl) return null;
  const el = document.createElement("div");
  el.className = "msg " + (cls || role);
  if (role !== "system" && role !== "tool") {
    const r = document.createElement("div");
    r.className = "role";
    r.textContent = role;
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
  hideQuickReplies();
  closeForm();
  setBusy(true);
  startActivity("Sending…");
  addMsg("user", prompt);
  const state = { assistantBody: null, toolEls: new Map() };
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, sessionId: ($("#newsess") && $("#newsess").checked) ? null : sessionId }),
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
        handleEvent(ev, state);
      }
    }
  } catch (e) {
    addMsg("system", "Connection error: " + (e && e.message ? e.message : e), "system");
  } finally {
    setBusy(false);
    stopActivity();
    const ns = $("#newsess");
    if (ns && ns.checked) ns.checked = false; // continue the session next time
    showQuickReplies();
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
      break;
    case "status":
      // busy/idle heartbeat from OpenCode
      if (ev.state === "busy") { if (!activityTimer) startActivity("Thinking…"); }
      break;
    case "assistant": {
      if (!state.assistantBody) state.assistantBody = addMsg("assistant", "");
      if (state.assistantBody) state.assistantBody.textContent += ev.text;
      if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
      setActivity("Writing…");
      break;
    }
    case "tool": {
      // One compact line per tool call; pending→running→completed update it in place.
      let el = state.toolEls.get(ev.id);
      if (!el) {
        el = addMsg("tool", "", "tool");
        if (!el) break;
        state.toolEls.set(ev.id, el);
        state.assistantBody = null; // text after a tool starts a fresh bubble
      }
      el.textContent = toolLine(ev);
      const row = el.parentElement;
      if (row) {
        row.classList.toggle("running", ev.status === "running" || ev.status === "pending");
        row.classList.toggle("done", ev.status === "completed");
        row.classList.toggle("err", ev.status === "error");
      }
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

// ================================================================================= library
async function loadLibrary() {
  try {
    const res = await fetch("/api/library");
    const data = await res.json();
    libraryWorlds = data.worlds || [];
    renderLibrary(libraryWorlds);
  } catch (e) {
    const lib = $("#library");
    if (lib) lib.innerHTML = '<div class="empty">Could not load library: ' + escapeHtml(e.message) + "</div>";
  }
}

function pill(text, cls) { return `<span class="pill ${cls || ""}">${escapeHtml(text)}</span>`; }

function renderLibrary(worlds) {
  const lib = $("#library");
  if (!lib) return;
  if (!worlds.length) {
    lib.innerHTML = '<div class="empty">No worlds yet. Pick a guided form on the left to make your first book ✨</div>';
    return;
  }
  lib.innerHTML = worlds.map(w => `
    <div class="world">
      <h3>${escapeHtml(w.title)}</h3>
      <p class="tagline">${escapeHtml(w.tagline || w.premise || "")}</p>
      <div class="swatches">${(w.palette||[]).map(p=>`<span class="sw" title="${escapeHtml(p.name)}" style="background:${escapeHtml(p.hex)}"></span>`).join("")}</div>
      <div class="row">${(w.age_bands||[]).map(a=>pill(a,"age")).join("")}${(w.themes||[]).slice(0,4).map(t=>pill(t)).join("")}</div>
      <div class="subhead">Stories (${w.stories.length})</div>
      ${w.stories.map(s=>`
        <div class="story">
          <h4>${escapeHtml(s.title)}</h4>
          <p>${escapeHtml(s.logline||"")}</p>
          <div class="row">${pill(s.age_band,"age")}${pill(s.status, s.status==="published"?"pub":"draft")}${pill(s.pages+" pages")}${pill(s.interactions+" games")}</div>
          <a class="read" href="/preview/story/${w.slug}/${s.slug}/index.html" target="_blank">Read ↗</a>
        </div>`).join("") || '<p class="tagline">No stories yet.</p>'}
      <div class="subhead">Characters (${w.characters.length})</div>
      ${w.characters.map(c=>`
        <div class="char"><h4>${escapeHtml(c.name)} ${c.has_reference?"🎨":""}</h4>
        <p>${escapeHtml(c.one_liner||c.role||"")} ${c.stages&&c.stages.length>1?("· "+c.stages.length+" stages"):""}</p></div>`).join("")
        || '<p class="tagline">No characters yet.</p>'}
    </div>`).join("");
}

function refreshPreview() {
  const f = $("#preview");
  if (f) f.src = f.src.split("?")[0] + "?t=" + Date.now();
}

async function runScript(endpoint, label) {
  addMsg("system", "▸ " + label + "…", "system");
  try {
    const res = await fetch(endpoint, { method: "POST" });
    const data = await res.json();
    addMsg("tool", (data.ok ? "✓ " : "✗ ") + label + "\n" + (data.output || ""), "tool out");
    if (endpoint === "/api/build") refreshPreview();
    loadLibrary();
  } catch (e) { addMsg("system", "⚠ " + e.message, "system"); }
}

// ===================================================================================== wire up
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
if (promptEl) promptEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { if (composer) composer.requestSubmit(); }
});

document.querySelectorAll("#form-launchers .chip-btn").forEach(b => b.onclick = () => openForm(b.dataset.form));
const formClose = $("#form-close");
if (formClose) formClose.onclick = closeForm;
const guided = $("#guided-form");
if (guided) guided.addEventListener("submit", submitForm);

const btnBuild = $("#btn-build"); if (btnBuild) btnBuild.onclick = () => runScript("/api/build", "Build site");
const btnValidate = $("#btn-validate"); if (btnValidate) btnValidate.onclick = () => runScript("/api/validate", "Validate");
const btnRefresh = $("#btn-refresh"); if (btnRefresh) btnRefresh.onclick = loadLibrary;

document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
  t.classList.add("active");
  const lib = $("#view-library"), prev = $("#view-preview");
  if (lib) lib.classList.toggle("hidden", t.dataset.tab !== "library");
  if (prev) prev.classList.toggle("hidden", t.dataset.tab !== "preview");
  if (t.dataset.tab === "preview") refreshPreview();
});

addMsg("system", "Welcome to the studio. Pick a guided form on the left, or just type what you'd like to make.", "system");
loadLibrary();
