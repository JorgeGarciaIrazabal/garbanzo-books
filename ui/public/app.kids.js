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
