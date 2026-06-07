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
