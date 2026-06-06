// Garbanzo Books Studio — front-end. Talks to the Node server, which drives the workspace
// via OpenCode + a local Ollama model and the python scripts.
const $ = (s) => document.querySelector(s);
const messagesEl = $("#messages");
let sessionId = null;
let busy = false;

function addMsg(role, text, cls) {
  const el = document.createElement("div");
  el.className = "msg " + (cls || role);
  if (role !== "system" && role !== "tool") {
    const r = document.createElement("div");
    r.className = "role";
    r.textContent = role;
    el.appendChild(r);
  }
  const body = document.createElement("div");
  body.textContent = text;
  el.appendChild(body);
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return body;
}

function setBusy(b) {
  busy = b;
  $("#send").disabled = b;
  $("#send").innerHTML = b ? '<span class="spinner"></span>Working…' : "Send ▸";
}

async function streamChat(prompt) {
  setBusy(true);
  addMsg("user", prompt);
  const state = { assistantBody: null, toolEls: new Map() };
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, sessionId: $("#newsess").checked ? null : sessionId }),
    });
    if (!res.ok || !res.body) {
      addMsg("system", "Server error: " + res.status + " " + (await res.text()), "system");
      setBusy(false);
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
    addMsg("system", "Connection error: " + e.message, "system");
  } finally {
    setBusy(false);
    if ($("#newsess").checked) $("#newsess").checked = false; // continue the session next time
    loadLibrary();
    refreshPreview();
  }
}

const TOOL_ICON = { pending: "•", running: "•", completed: "✓", error: "✗" };
const TOOL_VERB = { bash: "ran command", edit: "edited file", write: "wrote file", read: "read file", glob: "searched", grep: "searched", webfetch: "fetched", list: "listed" };
function handleEvent(ev, state) {
  switch (ev.type) {
    case "session":
      sessionId = ev.sessionId;
      $("#conn").textContent = "session " + (ev.sessionId || "").slice(0, 8);
      break;
    case "assistant":
      if (!state.assistantBody) state.assistantBody = addMsg("assistant", "");
      state.assistantBody.textContent += ev.text;
      messagesEl.scrollTop = messagesEl.scrollHeight;
      break;
    case "tool": {
      // One compact line per tool call; pending→running→completed update it in place.
      let el = state.toolEls.get(ev.id);
      if (!el) {
        el = addMsg("tool", "", "tool");
        state.toolEls.set(ev.id, el);
        state.assistantBody = null; // text after a tool starts a fresh bubble
      }
      const icon = TOOL_ICON[ev.status] || "•";
      const verb = TOOL_VERB[ev.tool] || ev.tool;
      el.firstChild.textContent = `${icon} ${verb}${ev.title ? ": " + ev.title : ""}`;
      el.classList.toggle("running", ev.status === "running" || ev.status === "pending");
      el.classList.toggle("done", ev.status === "completed");
      el.classList.toggle("err", ev.status === "error");
      messagesEl.scrollTop = messagesEl.scrollHeight;
      break;
    }
    case "result": if (ev.text) addMsg("system", ev.text, "system"); break;
    case "error": addMsg("system", "⚠ " + ev.text, "system"); break;
    case "done": break;
  }
}

// ---- Library ----
async function loadLibrary() {
  try {
    const res = await fetch("/api/library");
    const data = await res.json();
    renderLibrary(data.worlds || []);
  } catch (e) {
    $("#library").innerHTML = '<div class="empty">Could not load library: ' + e.message + "</div>";
  }
}

function pill(text, cls) { return `<span class="pill ${cls || ""}">${escapeHtml(text)}</span>`; }
function escapeHtml(s){return String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}

function renderLibrary(worlds) {
  if (!worlds.length) {
    $("#library").innerHTML = '<div class="empty">No worlds yet. Ask the studio to make a book ✨</div>';
    return;
  }
  $("#library").innerHTML = worlds.map(w => `
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
    addMsg("tool", (data.ok ? "✓ " : "✗ ") + label + "\n" + (data.output || ""), "tool");
    if (endpoint === "/api/build") refreshPreview();
    loadLibrary();
  } catch (e) { addMsg("system", "⚠ " + e.message, "system"); }
}

// ---- wire up ----
$("#composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const p = $("#prompt").value.trim();
  if (!p || busy) return;
  $("#prompt").value = "";
  streamChat(p);
});
$("#prompt").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { $("#composer").requestSubmit(); }
});
document.querySelectorAll(".chip-btn").forEach(b => b.onclick = () => { $("#prompt").value = b.dataset.q; $("#prompt").focus(); });
$("#btn-build").onclick = () => runScript("/api/build", "Build site");
$("#btn-validate").onclick = () => runScript("/api/validate", "Validate");
$("#btn-refresh").onclick = loadLibrary;
document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
  t.classList.add("active");
  $("#view-library").classList.toggle("hidden", t.dataset.tab !== "library");
  $("#view-preview").classList.toggle("hidden", t.dataset.tab !== "preview");
  if (t.dataset.tab === "preview") refreshPreview();
});

addMsg("system", "Welcome to the studio. Tell me what storybook to make, or try a quick action above.", "system");
loadLibrary();
