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
