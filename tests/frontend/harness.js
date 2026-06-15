// Loads the pure helpers from app.js into a test-accessible namespace.
//
// Approach:
//   * Read app.js, strip the bottom side effects (welcome addMsg + loadModels,
//     loadLibrary, etc.).
//   * Build one big "script body" string that ends with function declarations
//     for `__get` and `__set`.
//   * Run that body via `new Function(...)` to create a fresh closure where
//     the module-scope `let` variables (libraryWorlds, ttsOn, kidsMode, …)
//     persist across `__set` calls.
//   * The "let" declarations work fine inside a function body — they're
//     function-scoped, not module-scoped, so the parser is happy and the
//     closure works.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = resolve(__dirname, "..", "..", "ui", "public");
// The console is split across ordered classic scripts that share one global lexical scope
// (mirrors the <script> tags in index.html — see app.core.js). Concatenating them in this order
// reproduces the single-scope page exactly, so the helpers harness below works unchanged.
export const APP_SCRIPTS = [
  "app.core.js", "app.voice.js", "app.kids.js", "app.render.js", "app.messages.js",
  "app.stream.js", "app.forms.js", "app.debug.js", "app.library.js", "app.actions.js",
  "app.boot.js",
];
export const APP_JS = resolve(PUBLIC_DIR, "app.core.js"); // kept for back-compat imports

// The reader runtime; load in this exact order (mirrors scripts/build_site.py
// READER_SCRIPTS). reader.boot.js (last) calls GB.boot(). The Kaplay engine is lazy-loaded
// at runtime and never executes in jsdom (no WebGL), so it is not part of the harness.
const ASSET_DIR = resolve(__dirname, "..", "..", "scripts", "site_assets");
export const READER_SCRIPTS = [
  "reader.js", "gx.core.js", "gx.board.js", "gx.arcade.js", "reader.boot.js",
];
export const READER_JS = resolve(ASSET_DIR, "reader.js"); // kept for back-compat imports

// Strip the bottom side effects. Anchor on the stable English "Welcome" string.
// Concatenate the ordered console scripts into one source (same effect as the page's ordered
// <script> tags — they share a single global scope).
const APP_SRC = APP_SCRIPTS.map((f) => readFileSync(resolve(PUBLIC_DIR, f), "utf-8")).join("\n");
const cutMarker = 'addMsg("system", "Welcome to the studio.';
const cutAt = APP_SRC.indexOf(cutMarker);
if (cutAt < 0) throw new Error("Couldn't locate app.js bottom side-effects block");
const helpers = APP_SRC.slice(0, cutAt) + " /* bottom side-effects stripped for tests */\n";

// Build a function body that re-evaluates the helpers, then exposes a getter
// and a setter for module-scope variables. The settable keys must match the
// exact `let` names defined in app.js.
const BODY = `
${helpers}
function __get() {
  return {
    escapeHtml, mdInline, renderMarkdown, mdToSpeech,
    extractForm, detectStage, fieldOptions, guessEmoji, progressLine,
    stallNotice, STALL_WARN_SECS,
    STAGE_RE, FORMS, EMOJI_KEYWORDS, EMOJI_FALLBACK,
    AGE_BANDS, TONES, ART,
    TARGET_YEARS, READING_LEVELS, YEAR_HINT, READING_HINT, fieldHtml,
  };
}
function __set(key, value) {
  switch (key) {
    case "libraryWorlds": libraryWorlds = value; break;
    case "ttsOn": ttsOn = value; break;
    case "kidsMode": kidsMode = value; break;
    case "busy": busy = value; break;
    case "sessionId": sessionId = value; break;
    case "currentAbort": currentAbort = value; break;
    default: throw new Error("__gbSet__ unknown key: " + key);
  }
}
return { __get, __set };
`;

// new Function gives us an isolated lexical scope where the `let`s persist
// across invocations of __get and __set.
const factory = new Function(BODY);
const api = factory();
const { __get, __set } = api;

export function gbGet() { return __get(); }
export function gbSet(key, value) { __set(key, value); }

// ----- reader.js harness: load it against a fresh document --------------------
export function loadReaderWith(story) {
  // Reset body to avoid state from previous tests
  document.body.innerHTML = "";
  const dataEl = document.createElement("script");
  dataEl.id = "story-data";
  dataEl.type = "application/json";
  dataEl.textContent = JSON.stringify(story);
  document.body.appendChild(dataEl);
  const shell = document.createElement("div");
  shell.className = "reader";
  shell.innerHTML = `
    <div id="stage"></div>
    <div id="interaction"></div>
    <span class="pageno" id="pageno"></span>
    <button id="prev">‹</button>
    <button id="next">›</button>
  `;
  document.body.appendChild(shell);
  // Inject a matchMedia override BEFORE the reader.js IIFE so the page-flip
  // animation is skipped (animation events are unreliable in jsdom). The
  // override mirrors what jsdom provides by default (it returns true for
  // reduce), but installing it as a *replacement* avoids any timing/identity
  // differences with jsdom's internal copy.
  // Concatenate the ordered reader files into one script (same effect as the page's
  // ordered <script> tags). Reset window.GB so each load starts from a clean registry.
  delete window.GB;
  const src = READER_SCRIPTS.map((f) => readFileSync(resolve(ASSET_DIR, f), "utf-8")).join("\n;\n");
  const stub = `window.matchMedia = window.matchMedia || function (q) {
    return { matches: q.indexOf("reduce") >= 0,
             addListener: function() {}, removeListener: function() {} };
  };
`;
  const sc = document.createElement("script");
  sc.textContent = stub + src;
  document.body.appendChild(sc);
  return shell;
}
