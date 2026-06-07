// Shared test setup for the Studio's frontend tests.
//
// app.js is a top-level script that runs side effects (addMsg, loadModels,
// loadLibrary, …) on load. We don't want those — we just want the pure
// helpers. The harness.js module does the heavy lifting: it re-evaluates
// the app.js source in a Function closure with the bottom side effects
// stripped, then exposes a getter + setter for module-scope variables.

import { afterEach, beforeEach, vi } from "vitest";
import { gbGet, gbSet, loadReaderWith, APP_JS, READER_JS } from "./harness.js";

// Expose __gb__ + __gbSet__ on globalThis so test files can use them.
globalThis.__gb__ = gbGet();
globalThis.__gbSet__ = gbSet;

// ----- a tiny DOM scaffold so the side effects in app.js are no-ops -----------
globalThis.fetch = vi.fn(() => Promise.resolve({
  ok: true, status: 200, json: () => Promise.resolve({}),
  text: () => Promise.resolve(""),
  body: new ReadableStream(),
}));

// reader.js evaluates `prefers-reduced-motion` at IIFE-load time and stores
// the result in a closure-local `reduceMotion` flag. The flip animation
// trusts that flag — so to make tests deterministic we have to install this
// stub BEFORE the reader is loaded. We do it at module level.
if (!window.matchMedia) {
  window.matchMedia = (q) => ({
    matches: q.includes("reduce"),
    addListener() {}, removeListener() {},
  });
}

// ----- jsdom doesn't implement AudioContext by default; stub it ---------------
beforeEach(() => {
  if (!globalThis.AudioContext) {
    globalThis.AudioContext = class {
      constructor() { this.currentTime = 0; this.state = "running"; this.destination = {}; }
      createOscillator() {
        return { type: "sine", frequency: { value: 0 }, connect() {}, start() {}, stop() {} };
      }
      createGain() {
        return { gain: { setValueAtTime() {}, exponentialRampToValueAtTime() {} },
                 connect() {} };
      }
      resume() {}
    };
  }
  // The matchMedia stub is installed at module level above; this is a no-op
  // (we leave it here so the original test-loop behaviour is unchanged).
  if (!window.matchMedia) {
    window.matchMedia = (q) => ({ matches: false, addListener() {}, removeListener() {} });
  }
});

afterEach(() => {
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

export { loadReaderWith, APP_JS, READER_JS };
