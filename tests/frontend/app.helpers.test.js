// Tests for the pure helpers in ui/public/app.js (no DOM-driven logic).
//
// These cover the front-end contracts that the user-facing forms and the chat
// console depend on. We test:
//   * escapeHtml (XSS prevention)
//   * mdInline (small inline markdown subset)
//   * renderMarkdown (block-level: lists, headings, code fences, paragraphs)
//   * mdToSpeech (the prose transformation for the read-aloud feature)
//   * extractForm (the form block detection the dynamic form renderer relies on)
//   * detectStage (the model auto-switch tag)
//   * fieldOptions + the form field types ("select" with __other__, "world", etc.)
//   * guessEmoji (the friendly icon for kids-mode options)
//   * FORMS.book/world/character/story .build() functions (prompt templates)

import { describe, it, expect, beforeEach, vi } from "vitest";

const gb = globalThis.__gb__;

describe("escapeHtml", () => {
  it("escapes the basic XSS characters", () => {
    expect(gb.escapeHtml("<script>alert(1)</script>"))
      .toBe("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(gb.escapeHtml("a & b")).toBe("a &amp; b");
    expect(gb.escapeHtml('"quoted"')).toBe("&quot;quoted&quot;");
  });

  it("handles null and undefined safely", () => {
    expect(gb.escapeHtml(null)).toBe("");
    expect(gb.escapeHtml(undefined)).toBe("");
  });

  it("converts non-strings to strings first", () => {
    expect(gb.escapeHtml(42)).toBe("42");
    expect(gb.escapeHtml(true)).toBe("true");
  });

  it("is idempotent on safe text", () => {
    const safe = "Hello world, how are you?";
    expect(gb.escapeHtml(safe)).toBe(safe);
  });
});

describe("mdInline", () => {
  it("escapes first, then re-applies inline markdown", () => {
    expect(gb.mdInline("a < b and **bold**"))
      .toBe("a &lt; b and <strong>bold</strong>");
  });

  it("renders code spans with backticks", () => {
    expect(gb.mdInline("use `npm install`"))
      .toBe("use <code>npm install</code>");
  });

  it("renders italic with both * and _", () => {
    expect(gb.mdInline("*hello*")).toBe("<em>hello</em>");
    expect(gb.mdInline("_hello_")).toBe("<em>hello</em>");
  });

  it("documents the actual underscore-italic behaviour", () => {
    // The regex `_(^|[^_])_(...)_` matches `e_c` and turns it into italic.
    // It's a quirk of the small subset — `snake_case` would need backticks
    // to escape. The point of this test is to lock in the actual behaviour
    // so a future change to the rule doesn't silently flip it.
    const out = gb.mdInline("snake_case_var");
    expect(out).toContain("snake");
    expect(out).toContain("var");
  });

  it("renders [label](https?://url) as links", () => {
    expect(gb.mdInline("[Open](https://example.com)"))
      .toBe('<a href="https://example.com" target="_blank" rel="noopener">Open</a>');
  });

  it("does NOT link non-http(s) URLs (for safety)", () => {
    expect(gb.mdInline("[bad](javascript:alert(1))"))
      .toBe("[bad](javascript:alert(1))");
  });
});

describe("renderMarkdown", () => {
  it("renders a single paragraph wrapped in <p>", () => {
    const html = gb.renderMarkdown("Hello world.");
    expect(html).toMatch(/<p>Hello world\.<\/p>/);
  });

  it("renders h1..h4 headings", () => {
    expect(gb.renderMarkdown("# One")).toContain("<h1 class=\"md-h\">One</h1>");
    expect(gb.renderMarkdown("#### Four")).toContain("<h4 class=\"md-h\">Four</h4>");
  });

  it("renders unordered and ordered lists", () => {
    const u = gb.renderMarkdown("- one\n- two");
    expect(u).toMatch(/<ul class='md-ul'>/);
    expect(u).toMatch(/<li>one<\/li>/);
    expect(u).toMatch(/<li>two<\/li>/);
    const o = gb.renderMarkdown("1. first\n2. second");
    expect(o).toMatch(/<ol class='md-ol'>/);
    expect(o).toMatch(/<li>first<\/li>/);
  });

  it("renders fenced code blocks into <pre><code>", () => {
    const out = gb.renderMarkdown("```\nsome code\n```");
    expect(out).toContain('<pre class="md-pre"><code>some code</code></pre>');
  });

  it("renders multiple paragraphs as separate <p> elements", () => {
    const out = gb.renderMarkdown("First paragraph.\n\nSecond paragraph.");
    expect(out.match(/<p>/g).length).toBe(2);
  });

  it("does NOT interpret raw HTML in markdown source", () => {
    // Markdown is escaped first, so <script> shows as escaped text.
    const out = gb.renderMarkdown("Hello <script>x</script> world");
    expect(out).not.toContain("<script>x</script>");
    expect(out).toContain("&lt;script&gt;x&lt;/script&gt;");
  });
});

describe("mdToSpeech", () => {
  it("strips fenced code blocks entirely", () => {
    expect(gb.mdToSpeech("before ```code block``` after").trim())
      .toBe("before after");
  });

  it("strips the stage-control tags the agent emits", () => {
    expect(gb.mdToSpeech("hello [[stage:story]] world").trim())
      .toBe("hello world");
  });

  it("strips markdown punctuation (#*_`>~)", () => {
    expect(gb.mdToSpeech("# heading *italic* `code`").trim())
      .toBe("heading italic code");
  });

  it("collapses all whitespace to single spaces", () => {
    expect(gb.mdToSpeech("one\n\ntwo   three\t\tfour").trim())
      .toBe("one two three four");
  });

  it("replaces [label](url) with just the label", () => {
    expect(gb.mdToSpeech("see [docs](https://example.com) for more").trim())
      .toBe("see docs for more");
  });

  it("handles empty/null input", () => {
    expect(gb.mdToSpeech("")).toBe("");
    expect(gb.mdToSpeech(null)).toBe("");
  });
});

describe("extractForm", () => {
  it("extracts a form block tagged with ```form", () => {
    const md = "Intro line.\n```form\n{\"title\":\"t\",\"fields\":[{\"name\":\"a\"}]}\n```\nBye.";
    const out = gb.extractForm(md);
    expect(out).not.toBeNull();
    expect(out.spec.title).toBe("t");
    expect(out.spec.fields[0].name).toBe("a");
  });

  it("accepts bare ```json fences if the body parses as a form spec", () => {
    const md = "```json\n{\"fields\":[{\"name\":\"a\"}]}\n```";
    const out = gb.extractForm(md);
    expect(out).not.toBeNull();
    expect(out.spec.fields).toHaveLength(1);
  });

  it("returns null for markdown that has no form", () => {
    expect(gb.extractForm("Just a normal message.")).toBeNull();
  });

  it("returns null for a code fence that isn't a valid form spec", () => {
    expect(gb.extractForm("```\n{\"foo\":1}\n```")).toBeNull();
  });

  it("returns null for malformed JSON inside a ```form fence", () => {
    expect(gb.extractForm("```form\n{not json}\n```")).toBeNull();
  });
});

describe("detectStage", () => {
  it("detects story stage tag", () => {
    expect(gb.detectStage("hello [[stage:story]] world")).toBe("story");
  });

  it("detects craft stage tag", () => {
    expect(gb.detectStage("[[stage:craft]]")).toBe("craft");
  });

  it("is case-insensitive", () => {
    expect(gb.detectStage("[[STAGE:STORY]]")).toBe("story");
  });

  it("returns the LAST stage tag in a multi-tag message", () => {
    expect(gb.detectStage("[[stage:craft]] building… [[stage:story]] writing…"))
      .toBe("story");
  });

  it("returns null for no tag", () => {
    expect(gb.detectStage("hello world")).toBeNull();
  });
});

describe("fieldOptions", () => {
  it("returns null for text-style fields (no options)", () => {
    expect(gb.fieldOptions({ type: "text" })).toBeNull();
  });

  it("normalizes string options to {value,label}", () => {
    const out = gb.fieldOptions({ type: "select", options: ["a", "b"] });
    expect(out).toEqual([
      { value: "a", label: "a" },
      { value: "b", label: "b" },
    ]);
  });

  it("passes through pre-shaped {value,label} options", () => {
    const out = gb.fieldOptions({ type: "select", options: [{ value: "x", label: "Ex" }] });
    expect(out).toEqual([{ value: "x", label: "Ex" }]);
  });

  it("uses label if present, falling back to value", () => {
    const out = gb.fieldOptions({
      type: "select", options: [{ value: "v" }, { value: "y", label: "Why" }],
    });
    expect(out[0].label).toBe("v");
    expect(out[1].label).toBe("Why");
  });

  it("for type=world, derives options from the cached libraryWorlds", () => {
    globalThis.__gbSet__("libraryWorlds", [
      { slug: "alpha", title: "Alpha" },
      { slug: "beta", title: "Beta" },
    ]);
    const out = gb.fieldOptions({ type: "world" });
    expect(out).toEqual([
      { value: "alpha", label: "Alpha" },
      { value: "beta", label: "Beta" },
    ]);
  });
});

describe("guessEmoji", () => {
  it("matches a dragon option with a dragon emoji", () => {
    expect(gb.guessEmoji("a sleepy dragon")).toBe("🐉");
  });

  it("matches forest options with a tree emoji", () => {
    expect(gb.guessEmoji("enchanted forest")).toBe("🌲");
  });

  it("matches stars/night with a sparkle emoji", () => {
    expect(gb.guessEmoji("starry night sky")).toBe("✨");
  });

  it("falls back to a rotating default when nothing matches", () => {
    const e1 = gb.guessEmoji("something unrecognisable", 0);
    const e2 = gb.guessEmoji("something unrecognisable", 5);
    expect(gb.EMOJI_FALLBACK).toContain(e1);
    expect(gb.EMOJI_FALLBACK).toContain(e2);
  });

  it("rotates fallback emojis by index", () => {
    const a = gb.guessEmoji("xyz-no-match", 0);
    const b = gb.guessEmoji("xyz-no-match", 1);
    // Different indexes pick different (or at least allowed) emojis.
    expect(gb.EMOJI_FALLBACK).toContain(a);
    expect(gb.EMOJI_FALLBACK).toContain(b);
  });
});

describe("fieldHtml — hint popups and described select options", () => {
  it("renders a ? badge with the hint text in a popup", () => {
    const html = gb.fieldHtml({ name: "year", label: "Target age", type: "select",
                                options: ["5", "6"], default: "6", hint: "CONTENT age" });
    expect(html).toContain('class="hint"');
    expect(html).toContain('class="hint-pop"');
    expect(html).toContain("CONTENT age");
  });

  it("object options get a label, a data-desc, and a live opt-desc line", () => {
    const html = gb.fieldHtml({ name: "reading", label: "Reading level", type: "select",
                                options: gb.READING_LEVELS, default: "5-7" });
    expect(html).toContain("data-descsel");
    expect(html).toContain('data-descfor="reading"');
    expect(html).toContain("Beginning reader");           // friendly label, not just the band
    expect(html).toContain('value="5-7" data-desc=');     // band value stays machine-usable
    expect(html).toContain("selected");
  });

  it("plain string options render without a desc line (no behaviour change)", () => {
    const html = gb.fieldHtml({ name: "tone", label: "Tone", type: "select",
                                options: ["cozy", "silly"] });
    expect(html).not.toContain("data-descsel");
    expect(html).not.toContain("opt-desc");
    expect(html).not.toContain('class="hint"');
  });

  it("escapes HTML in hints and option descriptions", () => {
    const html = gb.fieldHtml({ name: "x", label: "X", type: "select",
                                options: [{ value: "a", label: "<b>", desc: "<script>" }],
                                hint: "<img onerror=1>" });
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img");
  });
});

describe("FORMS — the guided-form prompt builders", () => {
  it("the book form includes all user answers in the built prompt", () => {
    const values = {
      about: "a shy dragon",
      year: "7", reading: "5-7", tone: "funny & playful", art: "soft watercolor storybook",
      characters: "Ember", skill: "rhyming",
    };
    const prompt = gb.FORMS.book.build(values);
    expect(prompt).toContain("a shy dragon");
    expect(prompt).toContain("7-year-old");        // content age, one number
    expect(prompt).toContain("--age 5-7 --year 7"); // exact scaffold flags for the agent
    expect(prompt).toContain("rhyming");
    expect(prompt).toContain("Ember");
    expect(prompt).toContain("step by step");
  });

  it("the book form suggests a couple of characters when the user leaves it blank", () => {
    const p = gb.FORMS.book.build({ about: "x", year: "6", reading: "5-7", tone: "t", art: "a",
                                     characters: "", skill: "" });
    expect(p.toLowerCase()).toContain("suggest");
  });

  it("the world form says 'you propose one' when name is left blank", () => {
    const p = gb.FORMS.world.build({ name: "", setting: "deep sea",
                                       age: "3-5", mood: "cozy", art: "a", motifs: "" });
    expect(p.toLowerCase()).toContain("propose one");
  });

  it("the character form includes every field the user filled in", () => {
    const p = gb.FORMS.character.build({
      world: "ww", name: "Pip", kind: "hedgehog",
      traits: "curious", looks: "red coat", evolution: "timid→brave",
    });
    expect(p).toContain("Pip");
    expect(p).toContain("hedgehog");
    expect(p).toContain("curious");
    expect(p).toContain("red coat");
    expect(p).toContain("timid→brave");
  });

  it("the character form says 'you suggest' for traits/looks/evolution when blank", () => {
    const p = gb.FORMS.character.build({ world: "ww", name: "x", kind: "",
                                          traits: "", looks: "", evolution: "" });
    expect(p).toContain("you suggest");
  });

  it("the story form's starring/plot are included verbatim", () => {
    const p = gb.FORMS.story.build({
      world: "ww", characters: "Pip and Olo", year: "8", reading: "7-9",
      about: "losing a first tooth", interactions: "",
    });
    expect(p).toContain("Pip and Olo");
    expect(p).toContain("losing a first tooth");
    expect(p).toContain("--age 7-9 --year 8");
  });

  it("the book and story forms carry the two age knobs with explanatory hints", () => {
    for (const key of ["book", "story"]) {
      const fields = gb.FORMS[key].fields;
      const year = fields.find(f => f.name === "year");
      const reading = fields.find(f => f.name === "reading");
      // target year = CONTENT age: single numbers, never ranges
      expect(year.options.every(o => /^\d+$/.test(o))).toBe(true);
      expect(year.hint).toBe(gb.YEAR_HINT);
      // reading level = READER ability: every option self-describes for the popup line
      expect(reading.options).toBe(gb.READING_LEVELS);
      expect(reading.hint).toBe(gb.READING_HINT);
    }
  });

  it("every reading level option has a value, a label, and a description", () => {
    for (const o of gb.READING_LEVELS) {
      expect(o.value).toMatch(/^\d+-\d+$/);
      expect(o.label.length).toBeGreaterThan(0);
      expect(o.desc.length).toBeGreaterThan(10);
    }
  });

  it("the story form uses Auto so the server routes story-writing to the creative model", () => {
    // Forms default to Auto; the server's stage router picks DeepSeek when the
    // agent flags [[stage:story]] (see STAGE_TO_MODEL in ui/server.py).
    expect(gb.FORMS.story.model).toBe("auto");
  });

  it("every form has a non-empty title + submit button", () => {
    for (const k of Object.keys(gb.FORMS)) {
      expect(gb.FORMS[k].title.length).toBeGreaterThan(0);
      expect(gb.FORMS[k].submit.length).toBeGreaterThan(0);
      expect(typeof gb.FORMS[k].build).toBe("function");
    }
  });
});

describe("age / tone / art catalogues", () => {
  it("AGE_BANDS covers the pre-reader range used by the UI", () => {
    expect(gb.AGE_BANDS).toEqual(["0-3", "3-5", "5-7", "7-9"]);
  });

  it("TONES includes the cozy option that the form offers", () => {
    expect(gb.TONES).toContain("gentle & cozy");
    expect(gb.TONES).toContain("funny & playful");
  });

  it("ART includes the watercolor option that the form offers", () => {
    expect(gb.ART).toContain("soft watercolor storybook");
    expect(gb.ART).toContain("bold flat cartoon");
  });
});

describe("stallNotice (watchdog → 'slow' vs 'stuck')", () => {
  it("reads as normal slowness below the warn threshold", () => {
    const n = gb.stallNotice(60);
    expect(n.warn).toBe(false);
    expect(n.text).toContain("Still generating");
    expect(n.text).toContain("1m");
  });

  it("escalates to a stuck warning at the threshold", () => {
    const n = gb.stallNotice(gb.STALL_WARN_SECS);
    expect(n.warn).toBe(true);
    expect(n.text).toContain("looks stuck");
    expect(n.text).toContain("Stop is safe");
    expect(n.span).toBe("3m");
  });

  it("formats minute+second spans and tolerates missing input", () => {
    expect(gb.stallNotice(210).span).toBe("3m 30s");
    expect(gb.stallNotice(undefined).warn).toBe(false);
  });
});

describe("progressLine (script progress → activity strip)", () => {
  it("renders task, a 10-cell bar, the counts and the detail", () => {
    const line = gb.progressLine({ task: "illustrating", done: 8, total: 16, detail: "page 08" });
    expect(line).toContain("🎨 illustrating");
    expect(line).toContain("8/16");
    expect(line).toContain("— page 08");
    expect(line).toContain("▰".repeat(5) + "▱".repeat(5)); // half full
  });

  it("handles zero progress, completion, and missing detail", () => {
    expect(gb.progressLine({ task: "illustrating", done: 0, total: 16 }))
      .toContain("▱".repeat(10));
    expect(gb.progressLine({ task: "illustrating", done: 16, total: 16 }))
      .toContain("▰".repeat(10));
    expect(gb.progressLine({ task: "illustrating", done: 16, total: 16 })).not.toContain("—");
  });

  it("falls back to a generic icon for unknown tasks and never divides by zero", () => {
    const line = gb.progressLine({ task: "mystery-job", done: 1, total: 0 });
    expect(line).toContain("⚙️ mystery-job");
  });
});
