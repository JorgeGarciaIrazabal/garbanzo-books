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
  // Any substantive event means the agent is alive again — clear the stuck warning so a
  // LATER stall episode in the same turn can alert once more.
  if (ev.type !== "stall" && ev.type !== "status") {
    state.stallWarned = false;
    const act = $("#activity");
    if (act) act.classList.remove("warn");
  }
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
    case "stall": {
      // The server's watchdog: no OpenCode events for ev.seconds — usually the model
      // streaming one long generation (a big page batch, a long reply), past 3 minutes
      // more likely genuinely stuck. The strip escalates; the first time a turn crosses
      // the line we also drop ONE chat notice so it can't be missed.
      if (!activityTimer) startActivity("Working…");
      const n = stallNotice(ev.seconds);
      setActivity(n.text);
      const act = $("#activity");
      if (act) act.classList.toggle("warn", n.warn);
      if (n.warn && !state.stallWarned) {
        state.stallWarned = true;
        addMsg("system",
          "⚠️ The agent hasn't produced anything for **" + n.span + "** — it may be stuck " +
          "(a hung model stream, or one very large generation). It's safe to ⏹ **Stop** and " +
          "send *“continue where you left off”* — every completed step is already saved to disk.",
          "system");
      }
      break;
    }
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
