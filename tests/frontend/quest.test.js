// Tests for the COMPOSED arcade game — `arcade-quest` (scripts/site_assets/gx.quest.js).
//
// jsdom has no WebGL, so — like the arcade-suite tests — these pin the part that must
// NEVER break: the type is registered (intro card renders), the ▶ Play button degrades
// to the calm quest fallback (winnable, no dead end), decoys/dodge-things read as
// try-again rather than a win, and a broken payload also lands in the fallback instead
// of stranding the reader. (The Kaplay path runs in a real browser / the Game Lab.)
import { describe, it, expect } from "vitest";
import { loadReaderWith } from "./setup.js";

function makeStory(extraPages = []) {
  return {
    title: "Quest Test",
    pages: [
      { number: 0, kind: "title", text: "T", image: { file: "images/p0.png", alt: "a" },
        layout: { text_position: "center" }, vocabulary: [], reading_notes: "" },
      { number: 1, kind: "story", text: "one", image: { file: "images/p1.png", alt: "b" },
        layout: { text_position: "lower-third" }, vocabulary: [], reading_notes: "" },
      ...extraPages,
    ],
  };
}

const QUEST = {
  type: "arcade-quest",
  prompt: "Rescue the dumplings!",
  data: {
    stage: { view: "sky", scroll: true, bands: ["☁️"], floor: "🍜" },
    hero: { skin: { emoji: "🐉", label: "Nudo" }, control: "flap" },
    actors: [
      { name: "dumplings", skin: ["🥟", "🥠"], role: "rescue", motion: "fall", from: "top", count: 3 },
      { name: "chili", skin: "🌶️", role: "dodge", motion: "sine", from: "right", count: 2 },
    ],
    waves: [
      { line: "The cart tips!", spawn: [{ name: "dumplings", count: 3 }] },
      { line: "Second gust!", spawn: [{ name: "dumplings", count: 3 }, { name: "chili", count: 2 }] },
    ],
    finale: { kind: "reach", skin: "🍜", line: "The Great Noodle Bowl!" },
    goal: 6,
    speed: "gentle",
    how: "Tap to flap — scoop the dumplings!",
    avoid_line: "Not the chili!",
  },
  feedback: { correct: "Dumplings home! 🐉", try_again: "Flap, flap!" },
};

function openQuest(interaction) {
  const story = makeStory([{
    number: 2, kind: "story", text: "Go!", image: { file: "images/p2.png", alt: "c" },
    layout: { text_position: "lower-third" }, vocabulary: [], reading_notes: "",
    interaction,
  }]);
  loadReaderWith(story);
  document.getElementById("next").click();
  document.getElementById("next").click(); // page 0 → 1 → 2 (the quest page)
  const play = document.querySelector(".play-game-btn");
  if (play) play.click();
}

describe("arcade-quest (the composed game)", () => {
  it("registers with an intro card and the quest icon on the Play button", () => {
    loadReaderWith(makeStory([{
      number: 2, kind: "story", text: "Go!", image: { file: "images/p2.png", alt: "c" },
      layout: { text_position: "lower-third" }, vocabulary: [], reading_notes: "",
      interaction: QUEST,
    }]));
    document.getElementById("next").click();
    document.getElementById("next").click();
    // the reader's corner Play button wears the quest's registry icon…
    expect(document.querySelector(".play-game-btn .play-icon").textContent).toBe("🗺️");
    document.querySelector(".play-game-btn").click();
    // …and the sheet shows the composed game's intro card
    const intro = document.querySelector(".arcade-intro");
    expect(intro).toBeTruthy();
    expect(intro.textContent).toContain("flap"); // the how-to line from the payload
    expect(intro.querySelector(".arcade-play")).toBeTruthy();
  });

  it("without WebGL, ▶ Play degrades to the calm fallback — winnable, no overlay", () => {
    openQuest(QUEST);
    document.querySelector(".arcade-play").click();
    expect(document.querySelector(".arcade-intro")).toBeFalsy();   // intro gone
    expect(document.querySelector(".arcade-overlay")).toBeFalsy(); // no engine overlay
    const cells = document.querySelectorAll(".calm-cell");
    expect(cells.length).toBeGreaterThanOrEqual(6);                // the wave targets
    // rescue-role skins are the tap targets
    const emojis = Array.from(cells).map((c) => c.textContent);
    expect(emojis.filter((e) => e === "🥟" || e === "🥠").length).toBeGreaterThanOrEqual(3);
  });

  it("the calm fallback is winnable by tapping the targets", () => {
    openQuest(QUEST);
    document.querySelector(".arcade-play").click();
    // Tap only the good cells until the win — decoys must not be required.
    const good = Array.from(document.querySelectorAll(".calm-cell"))
      .filter((c) => c.textContent === "🥟" || c.textContent === "🥠");
    good.forEach((c) => c.click());
    expect(document.querySelector(".continue-btn")).toBeTruthy();
    expect(document.querySelector(".feedback").textContent).toContain("Dumplings home!");
  });

  it("tapping a dodge-thing in the fallback gives try-again, never a win", () => {
    openQuest(QUEST);
    document.querySelector(".arcade-play").click();
    const chili = Array.from(document.querySelectorAll(".calm-cell"))
      .find((c) => c.textContent === "🌶️");
    expect(chili).toBeTruthy();
    chili.click();
    expect(document.querySelector(".continue-btn")).toBeFalsy();
    expect(document.querySelector(".feedback").className).toContain("try");
  });

  it("a minimal quest payload (no stage/waves) still plays", () => {
    openQuest({
      type: "arcade-quest", prompt: "Gather the stars!",
      data: {
        hero: { skin: "🦉", control: "steer" },
        actors: [{ name: "stars", skin: "⭐", role: "collect", motion: "fall", count: 3 }],
        finale: { kind: "reach", skin: "🌙" },
      },
    });
    document.querySelector(".arcade-play").click();
    const cells = document.querySelectorAll(".calm-cell");
    expect(cells.length).toBeGreaterThanOrEqual(3);
    cells.forEach((c) => c.click());
    expect(document.querySelector(".continue-btn")).toBeTruthy();
  });

  it("a payload with no countable role still renders an intro (validator flags it; the runtime never strands the kid)", () => {
    // The Python validator fails this payload upstream; the runtime contract is only
    // "never a dead end": the intro card still renders.
    openQuest({
      type: "arcade-quest", prompt: "Dodgy!",
      data: {
        hero: { skin: "🦊" },
        actors: [{ name: "rocks", skin: "🪨", role: "dodge", motion: "march", count: 3 }],
        finale: { kind: "bigOne", skin: "🐻" },
      },
    });
    expect(document.querySelector(".arcade-intro")).toBeTruthy();
    // And the fallback stays winnable via the finale skin
    document.querySelector(".arcade-play").click();
    const cells = document.querySelectorAll(".calm-cell");
    expect(cells.length).toBeGreaterThan(0);
    cells.forEach((c) => c.click());
    expect(document.querySelector(".continue-btn")).toBeTruthy();
  });

  it("a malformed quest payload never breaks the reader", () => {
    // Missing finale etc. — schema-invalid, but the runtime must render something.
    expect(() =>
      openQuest({ type: "arcade-quest", prompt: "Broken", data: { hero: { skin: "🐉" } } })
    ).not.toThrow();
    expect(document.querySelector(".arcade-intro")).toBeTruthy();
  });
});