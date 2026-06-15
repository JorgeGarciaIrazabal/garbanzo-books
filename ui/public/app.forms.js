// ================================================================================ guided forms
const AGE_BANDS = ["0-3", "3-5", "5-7", "7-9"];

// Two separate knobs for a story (see schemas/story.schema.json):
//  • target_year — what the story is ABOUT: one age (in years) the humor/stakes/themes are
//    pitched at. CONTENT, not word difficulty.
//  • reading level — who READS the words: the ability band that drives sentence length,
//    words per page, and word choice.
const TARGET_YEARS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"];
const YEAR_HINT = "What the story is ABOUT: humor, stakes and themes pitched at a kid this many years old. One number, not a range. It does NOT change how hard the words are — that's the reading level.";
const READING_LEVELS = [
  { value: "0-3", label: "0–3 · Lap baby", desc: "A grown-up reads aloud; the child listens and points. Very few words, lots of rhythm and repetition." },
  { value: "3-5", label: "3–5 · Pre-reader", desc: "Read-aloud for preschoolers. Simple words they can echo and predict; short, musical sentences." },
  { value: "5-7", label: "5–7 · Beginning reader", desc: "They read it themselves (or nearly). Short sentences, easy decodable words, generous repetition." },
  { value: "7-9", label: "7–9 · Confident reader", desc: "Reads independently. Longer sentences, richer vocabulary, a few stretch words." },
  { value: "9-12", label: "9–12 · Independent reader", desc: "Near chapter-book language: complex sentences and ambitious vocabulary." },
];
const READING_HINT = "Who will READ the words: sets sentence length, words per page and word choice. For a bedtime read-aloud pick the listener's level, not the grown-up's.";
const READ_MODES = [
  { value: "auto", label: "Auto (by age)", desc: "Read-aloud for ages ≤5, solo from 6." },
  { value: "read_aloud", label: "Read-aloud (a grown-up voices it)", desc: "Rich, juicy words welcome; more words per page — the grown-up does the decoding." },
  { value: "solo", label: "Solo reader (the child decodes it)", desc: "High-frequency / decodable words, stretch words rare, fewer words per page (e.g. age 5 ≈ 25 vs ≈ 55)." },
];
const READ_MODE_HINT = "WHO turns the words into sound. The single biggest lever on how hard individual words may be — and it tightens words-per-page for a solo reader. Set it for ages ~4–8 (e.g. a 5-year-old solo reader vs a 5-year-old bedtime read-aloud).";

const TONES = ["gentle & cozy", "funny & playful", "adventurous", "magical & dreamy", "reassuring (bedtime)", "silly & energetic"];
const ART = ["soft watercolor storybook", "bold flat cartoon", "dreamy pastel", "cut-paper collage", "crayon / hand-drawn", "retro mid-century"];

const FORMS = {
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
      { name: "year", label: "Target age (years)", type: "select", options: TARGET_YEARS, default: "6", hint: YEAR_HINT },
      { name: "reading", label: "Reading level", type: "select", options: READING_LEVELS, default: "5-7", hint: READING_HINT },
      { name: "readmode", label: "Read mode", type: "select", options: READ_MODES, default: "auto", hint: READ_MODE_HINT },
      { name: "about", label: "Plot / theme", type: "textarea", required: true, placeholder: "losing a first tooth" },
      { name: "interactions", label: "Interaction focus (optional)", type: "text", placeholder: "rhyme, seek-and-find, a choice" },
    ],
    build: (v) => [
      `Write a new STORY in the world "${v.world}":`,
      `• Starring: ${v.characters}`,
      `• Target age (CONTENT): ${v.year} — pitch the humor, stakes and themes at a ${v.year}-year-old`,
      `• Reading level (WORDS): ${v.reading} band — scaffold the story with --age ${v.reading} --year ${v.year}`,
      `• Read mode: ${v.readmode === "auto" ? "auto (default by age)" : v.readmode} — ${v.readmode === "solo" ? "the child decodes every word: high-frequency/decodable words, fewer words per page" : v.readmode === "read_aloud" ? "a grown-up voices it: rich words welcome, more words per page" : "let the age decide (read-aloud ≤5, solo from 6)"}${v.readmode === "auto" ? "" : ` — scaffold with --read-mode ${v.readmode}`}`,
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
  // Options may be plain strings or {value, label, desc}: desc shows under the select for
  // whichever option is chosen (wired up in openForm).
  const norm = (o) => (typeof o === "object" && o !== null) ? o : { value: o, label: o };
  let input;
  if (f.type === "textarea") {
    input = `<textarea id="${id}" name="${f.name}" rows="2" placeholder="${escapeHtml(f.placeholder || "")}" ${req}></textarea>`;
  } else if (f.type === "select") {
    const opts = f.options.map(norm);
    const hasDesc = opts.some(o => o.desc);
    input = `<select id="${id}" name="${f.name}"${hasDesc ? ' data-descsel' : ''}>` +
      opts.map(o => `<option value="${escapeHtml(o.value)}" data-desc="${escapeHtml(o.desc || "")}" ${o.value === f.default ? "selected" : ""}>${escapeHtml(o.label)}</option>`).join("") +
      `</select>` +
      (hasDesc ? `<div class="opt-desc" data-descfor="${escapeHtml(f.name)}"></div>` : "");
  } else if (f.type === "world") {
    const opts = worldOptionsHtml();
    input = opts
      ? `<select id="${id}" name="${f.name}" ${req}>${opts}</select>`
      : `<input id="${id}" name="${f.name}" type="text" placeholder="world slug (none yet — make a world first)" ${req}>`;
  } else {
    input = `<input id="${id}" name="${f.name}" type="text" placeholder="${escapeHtml(f.placeholder || "")}" ${req}>`;
  }
  // An optional `hint` renders a little ? badge whose popup explains what the field is FOR
  // (pure CSS on hover/focus — see .hint/.hint-pop in styles.css).
  const hint = f.hint
    ? ` <span class="hint" tabindex="0" role="note" aria-label="${escapeHtml(f.hint)}">?<span class="hint-pop">${escapeHtml(f.hint)}</span></span>`
    : "";
  return `<label class="field"><span>${escapeHtml(f.label)}${hint}</span>${input}</label>`;
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
    // Keep each described select's helper line in sync with the chosen option.
    form.querySelectorAll("select[data-descsel]").forEach(sel => {
      const line = form.querySelector(`.opt-desc[data-descfor="${sel.name}"]`);
      const sync = () => {
        const o = sel.options[sel.selectedIndex];
        if (line) line.textContent = (o && o.dataset.desc) || "";
      };
      sel.addEventListener("change", sync);
      sync();
    });
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
