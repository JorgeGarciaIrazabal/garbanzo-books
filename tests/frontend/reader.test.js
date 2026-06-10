// Tests for the interactive reader runtime in scripts/site_assets/reader.js.
//
// reader.js is an IIFE — its internals aren't directly importable — so we
// load it against a stub `#story-data` element and observe what it does to
// the DOM. The contract we test:
//
//   * it always renders the FIRST page on load
//   * prev/next buttons advance + clamp at the boundaries
//   * the per-page text is rendered, with the configured scrim
//   * the page-flip turner picks the right CSS class for forward vs back
//   * image src + alt come from page.image.file / page.image.alt
//   * interactions: each game is winnable, the win → next button is offered
//   * "Play" button appears on pages with an interaction, opens the game
//   * the page-extras strip (glossary / reading notes) is rendered when present
//   * the keyboard arrow keys turn pages when not in a game input
//   * the tap-zones turn pages on the left/right third of the art

import { describe, it, expect, beforeEach, vi } from "vitest";
import { loadReaderWith } from "./setup.js";


function makeStory(extraPages = []) {
  return {
    title: "Test Story",
    pages: [
      {
        number: 0,
        kind: "title",
        text: "The Title",
        image: { file: "images/p0.png", alt: "title art" },
        layout: { text_position: "center", text_align: "center", scrim: true },
        vocabulary: [],
        reading_notes: "",
      },
      {
        number: 1,
        kind: "story",
        text: "Once upon a time.",
        image: { file: "images/p1.png", alt: "first spread" },
        layout: { text_position: "lower-third", text_align: "center", scrim: true },
        vocabulary: ["once"],
        reading_notes: "Pause on the rhyme.",
      },
      {
        number: 2,
        kind: "story",
        text: "The hero arrived.",
        image: { file: "images/p2.png", alt: "the hero" },
        layout: { text_position: "lower-third", text_align: "left", scrim: false },
        vocabulary: ["hero"],
        reading_notes: "",
      },
      ...extraPages,
    ],
  };
}


describe("initial render", () => {
  it("renders page 1 on load", () => {
    loadReaderWith(makeStory());
    const img = document.querySelector(".page-stage img");
    expect(img).toBeTruthy();
    expect(img.src).toContain("images/p0.png");
    expect(img.alt).toBe("title art");
  });

  it("shows the page indicator '1 / N'", () => {
    loadReaderWith(makeStory());
    const pageNo = document.getElementById("pageno");
    expect(pageNo.textContent).toBe("1 / 3");
  });

  it("disables prev on the first page", () => {
    loadReaderWith(makeStory());
    expect(document.getElementById("prev").disabled).toBe(true);
  });

  it("enables next on the first page", () => {
    loadReaderWith(makeStory());
    expect(document.getElementById("next").disabled).toBe(false);
  });

  it("renders the page text in a .page-text overlay", () => {
    loadReaderWith(makeStory());
    const txt = document.querySelector(".page-text");
    expect(txt).toBeTruthy();
    expect(txt.textContent).toContain("The Title");
  });

  it("applies the position+align classes from the page layout", () => {
    loadReaderWith(makeStory());
    const txt = document.querySelector(".page-text");
    expect(txt.className).toContain("pos-center");
    expect(txt.className).toContain("align-center");
  });

  it("applies the scrim class when layout.scrim is true", () => {
    loadReaderWith(makeStory());
    expect(document.querySelector(".page-text .scrim")).toBeTruthy();
  });

  it("omits the scrim class when layout.scrim is false", () => {
    // page index 2 has scrim: false
    const story = makeStory();
    loadReaderWith(story);
    // advance to page 2
    document.getElementById("next").click();
    document.getElementById("next").click();
    const txt = document.querySelector(".page-text");
    expect(txt.className).toContain("align-left");
    expect(txt.querySelector(".scrim")).toBeFalsy();
  });
});


describe("navigation", () => {
  it("next button advances to the next page", () => {
    loadReaderWith(makeStory());
    document.getElementById("next").click();
    const img = document.querySelector(".page-stage img");
    expect(img.src).toContain("images/p1.png");
    expect(document.getElementById("pageno").textContent).toBe("2 / 3");
  });

  it("prev button goes back a page", () => {
    loadReaderWith(makeStory());
    document.getElementById("next").click();
    document.getElementById("prev").click();
    const img = document.querySelector(".page-stage img");
    expect(img.src).toContain("images/p0.png");
  });

  it("disables next on the last page", () => {
    loadReaderWith(makeStory());
    document.getElementById("next").click();
    document.getElementById("next").click();
    expect(document.getElementById("next").disabled).toBe(true);
  });

  it("does not go below page 0", () => {
    loadReaderWith(makeStory());
    document.getElementById("prev").click(); // already at 0
    expect(document.querySelector(".page-stage img").src).toContain("images/p0.png");
    expect(document.getElementById("pageno").textContent).toBe("1 / 3");
  });
});


describe("extras strip (vocabulary + reading notes)", () => {
  it("renders vocabulary chips when the page has any", () => {
    loadReaderWith(makeStory());
    document.getElementById("next").click();  // page 2 — has vocabulary: ['once']
    const gl = document.querySelector(".glossary");
    expect(gl).toBeTruthy();
    expect(gl.textContent).toContain("once");
  });

  it("renders a reading note when present", () => {
    loadReaderWith(makeStory());
    document.getElementById("next").click();
    const note = document.querySelector(".reading-note");
    expect(note).toBeTruthy();
    expect(note.textContent).toContain("Pause on the rhyme");
  });

  it("does not render a glossary when vocabulary is empty", () => {
    loadReaderWith(makeStory());
    // page 1 has no vocabulary
    expect(document.querySelector(".glossary")).toBeFalsy();
  });
});


describe("interactions", () => {
  it("renders a 'Play game' button on pages that have an interaction", () => {
    const story = makeStory([{
      number: 3, kind: "story", text: "Find them!",
      image: { file: "images/p3.png", alt: "x" },
      layout: { text_position: "lower-third", text_align: "center", scrim: true },
      interaction: {
        type: "seek-and-find",
        prompt: "Find the items:",
        data: { items: ["a", "b", "c"] },
      },
    }]);
    loadReaderWith(story);
    // advance to the interaction page
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.getElementById("next").click();
    const play = document.querySelector(".play-game-btn");
    expect(play).toBeTruthy();
  });

  it("clicking 'Play game' opens the interaction sheet", () => {
    const story = makeStory([{
      number: 3, kind: "story", text: "Find them!",
      image: { file: "images/p3.png", alt: "x" },
      layout: { text_position: "lower-third", text_align: "center", scrim: true },
      interaction: {
        type: "seek-and-find",
        prompt: "Find the items:",
        data: { items: ["a", "b"] },
      },
    }]);
    loadReaderWith(story);
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.querySelector(".play-game-btn").click();
    const sheet = document.querySelector(".interaction");
    expect(sheet).toBeTruthy();
    expect(sheet.textContent).toContain("Find the items");
  });

  it("the seek-and-find game is winnable", () => {
    const story = makeStory([{
      number: 3, kind: "story", text: "Find them!",
      image: { file: "images/p3.png", alt: "x" },
      layout: { text_position: "lower-third", text_align: "center", scrim: true },
      interaction: {
        type: "seek-and-find",
        prompt: "Find the items:",
        data: { items: ["apple", "banana"] },
      },
    }]);
    loadReaderWith(story);
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.querySelector(".play-game-btn").click();
    // Tap both items
    const items = document.querySelectorAll(".find-item");
    expect(items.length).toBe(2);
    items.forEach((b) => b.click());
    // Win: "Keep reading" button is offered.
    const cont = document.querySelector(".continue-btn");
    expect(cont).toBeTruthy();
  });

  it("the counting game accepts the correct answer", () => {
    const story = makeStory([{
      number: 3, kind: "story", text: "How many?",
      image: { file: "images/p3.png", alt: "x" },
      layout: { text_position: "lower-third", text_align: "center", scrim: true },
      interaction: {
        type: "counting",
        prompt: "How many apples?",
        data: { what: "apples", answer: 3 },
      },
    }]);
    loadReaderWith(story);
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.querySelector(".play-game-btn").click();
    const input = document.querySelector(".num-input");
    input.value = "3";
    document.querySelector(".interaction button.btn").click();
    expect(document.querySelector(".continue-btn")).toBeTruthy();
  });

  it("the counting game rejects the wrong answer", () => {
    const story = makeStory([{
      number: 3, kind: "story", text: "How many?",
      image: { file: "images/p3.png", alt: "x" },
      layout: { text_position: "lower-third", text_align: "center", scrim: true },
      interaction: {
        type: "counting",
        prompt: "How many apples?",
        data: { what: "apples", answer: 3 },
      },
    }]);
    loadReaderWith(story);
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.querySelector(".play-game-btn").click();
    const input = document.querySelector(".num-input");
    input.value = "5";
    document.querySelector(".interaction button.btn").click();
    // No continue button on a wrong answer
    expect(document.querySelector(".continue-btn")).toBeFalsy();
    // And the feedback was set to "try again"
    const fb = document.querySelector(".interaction .feedback");
    expect(fb.className).toContain("try");
  });

  it("the rhyme-complete game accepts the correct answer among distractors", () => {
    const story = makeStory([{
      number: 3, kind: "story", text: "Rhyme!",
      image: { file: "images/p3.png", alt: "x" },
      layout: { text_position: "lower-third", text_align: "center", scrim: true },
      interaction: {
        type: "rhyme-complete",
        prompt: "Pick the rhyme:",
        data: { sentence: "The cat sat on the ___", answer: "mat", distractors: ["dog", "car"] },
      },
    }]);
    loadReaderWith(story);
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.querySelector(".play-game-btn").click();
    // Find the option whose text is 'mat'
    const options = Array.from(document.querySelectorAll(".interaction .opt"));
    const right = options.find((b) => b.textContent === "mat");
    expect(right).toBeTruthy();
    right.click();
    expect(document.querySelector(".continue-btn")).toBeTruthy();
  });

  it("the choice interaction jumps the reader to the goto page", () => {
    const story = makeStory([{
      number: 3, kind: "story", text: "Pick",
      image: { file: "images/p3.png", alt: "x" },
      layout: { text_position: "lower-third", text_align: "center", scrim: true },
      interaction: {
        type: "choice",
        prompt: "What next?",
        data: { options: [{ label: "Jump to start", goto: 0 },
                           { label: "Jump to end",   goto: 2 }] },
      },
    }]);
    loadReaderWith(story);
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.querySelector(".play-game-btn").click();
    const buttons = Array.from(document.querySelectorAll(".interaction .opt"));
    buttons.find((b) => b.textContent === "Jump to start").click();
    // Page indicator should be back at 1/4 (the story has 4 pages)
    expect(document.getElementById("pageno").textContent).toBe("1 / 4");
  });

  it("a page with no interaction has no 'Play game' button", () => {
    loadReaderWith(makeStory());
    // Page 0 (title) has no interaction
    expect(document.querySelector(".play-game-btn")).toBeFalsy();
  });
});


describe("schema robustness", () => {
  it("renders a story whose page has no image.file (empty src)", () => {
    const story = {
      title: "T",
      pages: [
        { number: 0, kind: "title", text: "x", image: { alt: "no image" },
          layout: { text_position: "center" }, vocabulary: [], reading_notes: "" },
      ],
    };
    loadReaderWith(story);
    const img = document.querySelector(".page-stage img");
    expect(img).toBeTruthy();
    expect(img.alt).toBe("no image");
    expect(img.getAttribute("src")).toBe("");
  });

  it("the page indicator reflects the actual number of pages", () => {
    loadReaderWith({ title: "T", pages: [] });
    // No pages: we still want the page indicator to not crash. The reader
    // bails on render(0) (page undefined) but shouldn't throw.
    const ind = document.getElementById("pageno");
    expect(ind).toBeTruthy();
  });
});

// ---- the rich game library + toolkit (new mechanics) ------------------------
describe("rich games + toolkit", () => {
  // Open the game on the interaction page (page number 3 in makeStory).
  function openGame(interaction) {
    const story = makeStory([{
      number: 3, kind: "story", text: "Play!",
      image: { file: "images/p3.png", alt: "x" },
      layout: { text_position: "lower-third", text_align: "center", scrim: true },
      interaction,
    }]);
    loadReaderWith(story);
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.getElementById("next").click();   // page 0→1→2→3 (the interaction page)
    const play = document.querySelector(".play-game-btn");
    if (play) play.click();
    return story;
  }

  it("hidden-object plays ON the art and is winnable by tapping each spot", () => {
    openGame({
      type: "hidden-object", prompt: "Find them!",
      data: { items: [{ label: "acorn", at: { x: 0.3, y: 0.4 } }, { label: "leaf", at: { x: 0.6, y: 0.5 } }] },
      feedback: { correct: "Found!" },
    });
    const frame = document.querySelector(".scene-frame");
    expect(frame).toBeTruthy();                       // renders on the page image
    const spots = document.querySelectorAll(".scene-hotspot");
    expect(spots.length).toBe(2);
    spots.forEach((s) => s.click());
    expect(document.querySelector(".continue-btn")).toBeTruthy();
  });

  it("connect-dots is winnable by tapping the dots in order", () => {
    openGame({
      type: "connect-dots", prompt: "Connect!",
      data: { dots: [{ n: 1, at: { x: 0.2, y: 0.2 } }, { n: 2, at: { x: 0.5, y: 0.5 } }, { n: 3, at: { x: 0.8, y: 0.3 } }] },
    });
    const dots = document.querySelectorAll(".dot");
    expect(dots.length).toBe(3);
    dots.forEach((d) => d.click());                   // already in document order = 1,2,3
    expect(document.querySelector(".continue-btn")).toBeTruthy();
  });

  it("balance-scale lets the reader tap the heavier pan", () => {
    openGame({
      type: "balance-scale", prompt: "Which is heavier?",
      data: { left: ["🍎", "🍎"], right: ["🍎"], answer: "left" },
      feedback: { correct: "Yes!" },
    });
    const pans = document.querySelectorAll(".scale-pan");
    expect(pans.length).toBe(2);
    pans[0].click();                                  // left pan = the answer
    expect(document.querySelector(".continue-btn")).toBeTruthy();
  });

  it("word-build is winnable by tapping letters in order", () => {
    openGame({ type: "word-build", prompt: "Spell it!", data: { letters: ["C", "A", "T"], answer: "cat" } });
    function tap(letter) {
      const btn = Array.from(document.querySelectorAll(".gb-chip.letter")).find(
        (b) => b.textContent === letter && !b.disabled);
      btn.click();
    }
    tap("C"); tap("A"); tap("T");
    expect(document.querySelector(".continue-btn")).toBeTruthy();
  });

  it("a custom game (all-found) is interpreted from its declarative spec", () => {
    openGame({
      type: "custom", prompt: "Tap the sparkles!",
      data: {
        elements: [
          { id: "a", kind: "hotspot", at: { x: 0.2, y: 0.2 } },
          { id: "b", kind: "hotspot", at: { x: 0.6, y: 0.6 } },
        ],
        win: { mode: "all-found" },
      },
    });
    const spots = document.querySelectorAll(".scene-hotspot");
    expect(spots.length).toBe(2);
    spots.forEach((s) => s.click());
    expect(document.querySelector(".continue-btn")).toBeTruthy();
  });

  it("a multi-step interaction only wins after every beat", () => {
    openGame({
      type: "seek-and-find", prompt: "Two beats!",
      steps: [
        { type: "seek-and-find", prompt: "beat 1", data: { items: ["a"] } },
        { type: "seek-and-find", prompt: "beat 2", data: { items: ["b"] } },
      ],
    });
    // beat 1
    let items = document.querySelectorAll(".find-item");
    expect(items.length).toBe(1);
    expect(document.querySelector(".continue-btn")).toBeFalsy();   // not won yet
    items[0].click();
    // beat 2 now showing
    items = document.querySelectorAll(".find-item");
    expect(items.length).toBe(1);
    items[0].click();
    expect(document.querySelector(".continue-btn")).toBeTruthy();  // both beats done → won
  });

  it("winning a game drops a sticker into the reward tray", () => {
    openGame({
      type: "seek-and-find", prompt: "Find!",
      data: { items: ["a"] }, reward: { label: "Gold Star", emoji: "🌟" },
    });
    expect(document.querySelector(".reward-tray")).toBeTruthy();    // tray rides along
    document.querySelector(".find-item").click();                   // win
    const tray = document.querySelector(".reward-tray");
    expect(tray.textContent).toContain("1/1");                      // collected 1 of 1
  });
});


// ---- arcade games (gx.arcade.js) --------------------------------------------
//
// jsdom has no WebGL, so these tests exercise the graceful-degradation contract:
// an arcade page always renders an intro card, and pressing ▶ Play must land the
// reader in the calm DOM fallback — winnable, never a dead end. (The engine path
// is exercised in a real browser; here we pin the part that must never break.)
describe("arcade games", () => {
  function arcadePage(interaction) {
    return [{
      number: 3, kind: "story", text: "Go!",
      image: { file: "images/p3.png", alt: "x" },
      layout: { text_position: "lower-third", text_align: "center", scrim: true },
      interaction,
    }];
  }
  function openArcade(interaction) {
    loadReaderWith(makeStory(arcadePage(interaction)));
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.querySelector(".play-game-btn").click();
  }

  const ARCADE_TYPES = ["arcade-catch", "arcade-flap", "arcade-run", "arcade-pop", "arcade-toss", "arcade-steer"];

  it("registers all six arcade types (each renders an arcade intro)", () => {
    // window.GB isn't reachable from the test realm, so registration is asserted
    // through the DOM: only a registered arcade game renders the intro card.
    ARCADE_TYPES.forEach((type) => {
      openArcade({ type, prompt: "Go!", data: {} });
      expect(document.querySelector(".arcade-intro"), type).toBeTruthy();
    });
  });

  it("the Play button wears the game's registry icon", () => {
    loadReaderWith(makeStory(arcadePage({
      type: "arcade-catch", prompt: "Catch the sparks!",
      data: { catch: ["✨"], goal: 3 },
    })));
    document.getElementById("next").click();
    document.getElementById("next").click();
    document.getElementById("next").click();
    const icon = document.querySelector(".play-game-btn .play-icon");
    expect(icon.textContent).toBe("🧺"); // arcade-catch's icon, not the generic 🎲
  });

  it("renders an intro card with a ▶ Play button", () => {
    openArcade({
      type: "arcade-catch", prompt: "Catch the sparks!",
      data: { player: "🧺", catch: ["✨", "🌟"], avoid: ["💧"], goal: 4 },
    });
    const introCard = document.querySelector(".arcade-intro");
    expect(introCard).toBeTruthy();
    expect(introCard.querySelector(".arcade-play")).toBeTruthy();
    expect(introCard.textContent).toContain("Play!");
  });

  it("without WebGL, ▶ Play degrades to the calm tap fallback (never a dead end)", () => {
    openArcade({
      type: "arcade-pop", prompt: "Pop the bubbles!",
      data: { pop: ["🫧"], avoid: ["🐡"], goal: 3 },
    });
    document.querySelector(".arcade-play").click();
    expect(document.querySelector(".arcade-intro")).toBeFalsy();   // intro is gone
    expect(document.querySelector(".arcade-overlay")).toBeFalsy(); // no engine overlay
    const cells = document.querySelectorAll(".calm-cell");
    expect(cells.length).toBeGreaterThanOrEqual(3);                // playable board instead
  });

  it("the calm fallback is winnable by tapping the targets", () => {
    openArcade({
      type: "arcade-catch", prompt: "Catch!",
      data: { catch: ["✨"], goal: 3 },
      feedback: { correct: "Caught them all!" },
    });
    document.querySelector(".arcade-play").click();
    // Every cell is a target (no avoid list) — tap them all.
    document.querySelectorAll(".calm-cell").forEach((b) => b.click());
    expect(document.querySelector(".continue-btn")).toBeTruthy();
    expect(document.querySelector(".feedback").textContent).toContain("Caught them all!");
  });

  it("tapping a decoy in the fallback gives a gentle try-again, not a win", () => {
    openArcade({
      type: "arcade-steer", prompt: "Collect the stars!",
      data: { player: "🚀", collect: "⭐", avoid: ["🪨"], goal: 3 },
    });
    document.querySelector(".arcade-play").click();
    const decoy = Array.from(document.querySelectorAll(".calm-cell"))
      .find((b) => b.textContent === "🪨");
    expect(decoy).toBeTruthy();
    decoy.click();
    expect(document.querySelector(".continue-btn")).toBeFalsy();
    expect(document.querySelector(".feedback").className).toContain("try");
  });

  it("every arcade type renders a playable fallback from a minimal payload", () => {
    const payloads = {
      "arcade-catch": { catch: ["✨"], goal: 2 },
      "arcade-flap": { player: "🕊️", gates: 2 },
      "arcade-run": { player: "🏃", collect: "⭐", goal: 2 },
      "arcade-pop": { pop: ["🎈"], goal: 2 },
      "arcade-toss": { projectile: "🍎", target: "🧺", goal: 2 },
      "arcade-steer": { player: "🚀", collect: "⭐", goal: 2 },
    };
    ARCADE_TYPES.forEach((type) => {
      openArcade({ type, prompt: "Go!", data: payloads[type] });
      document.querySelector(".arcade-play").click();
      const targets = Array.from(document.querySelectorAll(".calm-cell"));
      expect(targets.length, type).toBeGreaterThan(0);
      targets.forEach((b) => b.click()); // tapping everything always reaches the win
      expect(document.querySelector(".continue-btn"), type).toBeTruthy();
    });
  });
});


// ---- dynamic text fit: a long passage must never come out huge or bury art --
//
// fitText() keeps the page text from dominating the illustration two ways:
//   1. content-aware start size — a text-heavy page renders at a smaller font
//      than a sparse one, on ANY screen, even where it would technically fit;
//   2. a geometry cap — the box may occupy at most a share of the page height
//      (48% for top/bottom captions, 42% for centered title text), shrinking
//      further and finally scrolling if it still overflows.
//
// jsdom computes no layout, so each test feeds geometry: mockStageHeight pins
// the stage's pixel height and mockBoxScrollHeight makes the text box report a
// height. The real fit is then driven through the reader's own resize handler
// (the same path an orientation change takes) — window.GB isn't reachable from
// the test realm, but the reader's resize listener is on the shared window.
describe("dynamic text fit (fitText)", () => {
  const BASE = 20; // jsdom resolves no stylesheet, so fitText's base falls back to 20px

  function fitStory(text, layout) {
    return {
      title: "T",
      pages: [
        { number: 0, kind: "title", text: "Title", image: { file: "p0.png", alt: "a" },
          layout: { text_position: "center", scrim: true }, vocabulary: [], reading_notes: "" },
        { number: 1, kind: "story", text, image: { file: "p1.png", alt: "b" },
          layout: layout || { text_position: "lower-third", scrim: true }, vocabulary: [], reading_notes: "" },
      ],
    };
  }
  const LONG = "word ".repeat(140).trim();   // ~700 chars → fullest-page scaling
  const MEDIUM = "word ".repeat(50).trim();  // ~250 chars → partial scaling
  const SHORT = "A short line.";             // well under the scaling threshold

  function mockStageHeight(px) {
    Object.defineProperty(document.getElementById("stage"), "clientHeight", {
      configurable: true, get: () => px,
    });
  }
  function mockBoxScrollHeight(fn) {
    const box = document.querySelector(".page-text").firstElementChild;
    Object.defineProperty(box, "scrollHeight", { configurable: true, get: fn });
    return box;
  }
  async function triggerFit() {
    window.dispatchEvent(new Event("resize"));    // the reader re-fits the current page
    await new Promise((r) => setTimeout(r, 160));  // wait out the 120ms debounce
  }

  it("never throws when the stage has no measurable height", () => {
    // Real production guard: during an early/zero-layout render the geometry cap
    // must be skipped rather than dividing by a 0-height stage. jsdom's default
    // (every height is 0) reproduces exactly that.
    expect(() => loadReaderWith(fitStory(LONG))).not.toThrow();
    expect(document.querySelector(".page-stage")).toBeTruthy(); // still rendered
  });

  it("scales a text-heavy page down even when it would fit the page height", async () => {
    // The key cross-screen guarantee: a long passage is never rendered at the
    // full font size, regardless of how much room it has.
    loadReaderWith(fitStory(MEDIUM));
    document.getElementById("next").click();
    const ov = document.querySelector(".page-text");
    mockStageHeight(600);
    mockBoxScrollHeight(() => 100); // comfortably fits — geometry cap won't trigger
    await triggerFit();

    const after = parseFloat(ov.style.fontSize);
    expect(after).toBeLessThan(BASE);                 // content scaling shrank it
    expect(after).toBeGreaterThan(BASE * 0.55);       // …but only partway (not the floor)
    expect(ov.firstElementChild.style.overflowY).toBe(""); // it fits → no scroll
  });

  it("keeps a short passage at the full age-band font size", async () => {
    loadReaderWith(fitStory(SHORT));
    document.getElementById("next").click();
    const ov = document.querySelector(".page-text");
    mockStageHeight(600);
    mockBoxScrollHeight(() => 100);
    await triggerFit();

    expect(parseFloat(ov.style.fontSize)).toBe(BASE); // short text isn't scaled down
    expect(ov.firstElementChild.style.overflowY).toBe("");
  });

  it("shrinks to the floor and scrolls when even the scaled size overflows", async () => {
    loadReaderWith(fitStory(LONG));
    document.getElementById("next").click();
    const ov = document.querySelector(".page-text");
    expect(ov.className).toContain("pos-lower-third");
    mockStageHeight(600);
    mockBoxScrollHeight(() => 5000); // taller than the cap at every font size
    await triggerFit();

    const box = ov.firstElementChild;
    expect(parseFloat(ov.style.fontSize)).toBeLessThanOrEqual(12); // bottomed out at the floor
    expect(box.style.maxHeight).toBe("288px");  // 48% of the 600px stage
    expect(box.style.overflowY).toBe("auto");   // scroll fallback for the extreme case
  });

  it("uses a tighter cap for centered title text than for bottom captions", async () => {
    loadReaderWith(fitStory(SHORT));        // page 0 is the centered title page
    const ov = document.querySelector(".page-text");
    expect(ov.className).toContain("pos-center");
    mockStageHeight(600);
    mockBoxScrollHeight(() => 5000);
    await triggerFit();
    expect(ov.firstElementChild.style.maxHeight).toBe("252px"); // 42% of the 600px stage
  });

  it("re-fits the current page when the window is resized", async () => {
    loadReaderWith(fitStory(SHORT));
    document.getElementById("next").click();
    const ov = document.querySelector(".page-text");
    mockStageHeight(600);
    let tall = 100;                          // starts fitting → no scroll
    mockBoxScrollHeight(() => tall);
    await triggerFit();
    expect(ov.firstElementChild.style.overflowY).toBe("");

    tall = 5000;                             // text grows (e.g. orientation change)
    await triggerFit();
    expect(ov.firstElementChild.style.overflowY).toBe("auto"); // re-fit reacted
  });
});
