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
// Deploy: commit & push from the server — the push triggers the Pages workflow.
const btnDeploy = $("#btn-deploy");
if (btnDeploy) btnDeploy.onclick = () => runJob("deploy", "/api/deploy", {
  okLabel: "pushed — Pages is deploying", failLabel: "push failed",
});
const btnRefresh = $("#btn-refresh"); if (btnRefresh) btnRefresh.onclick = loadLibrary;
const btnCollapseAll = $("#btn-collapse-all"); if (btnCollapseAll) btnCollapseAll.onclick = () => setAllWorldsCollapsed(true);
const btnExpandAll = $("#btn-expand-all"); if (btnExpandAll) btnExpandAll.onclick = () => setAllWorldsCollapsed(false);
// Cast chips are re-rendered on every library refresh — delegate so one handler covers them all.
const libRoot = $("#library");
if (libRoot) libRoot.addEventListener("click", (e) => {
  // Publish/unpublish lives INSIDE the card link — swallow the navigation.
  const pub = e.target.closest(".pubbtn");
  if (pub) {
    e.preventDefault();
    e.stopPropagation();
    setStoryStatus(pub);
    return;
  }
  // Delete buttons (story is inside the card link; world sits in the header) — swallow navigation.
  const delS = e.target.closest(".delstory");
  if (delS) { e.preventDefault(); e.stopPropagation(); deleteStory(delS); return; }
  const delW = e.target.closest(".delworld");
  if (delW) { e.preventDefault(); e.stopPropagation(); deleteWorld(delW); return; }
  // Clicking anywhere on the world header (but not the delete button, handled above)
  // collapses/expands that world so the whole shelf is easy to scan.
  const head = e.target.closest(".world-head");
  if (head && head.dataset.w) { toggleWorldCollapsed(head.dataset.w); return; }
  const chip = e.target.closest(".castchip");
  if (!chip) return;
  const w = libraryWorlds.find(x => x.slug === chip.dataset.w);
  const c = w && (w.characters || []).find(x => (x.slug || x.name) === chip.dataset.c);
  if (w && c) openCharacterCard(w, c);
});
// Keyboard: the world header is a focusable button — Enter/Space toggles collapse.
if (libRoot) libRoot.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const head = e.target.closest(".world-head");
  if (head && head.dataset.w) { e.preventDefault(); toggleWorldCollapsed(head.dataset.w); }
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

addMsg("system", "Welcome to the studio. Build a book step by step — tap a card above to start a world, then add characters, then a story — or just type what you'd like to make.", "system");
restoreSession(); // replays a prior conversation (and replaces the welcome) if one was saved
loadModels();
loadVoiceCaps();
loadLibrary();
refreshPublishStatus();
