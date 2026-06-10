/* Garbanzo Books — interactive reader runtime (controller).
   Reads the story JSON embedded in #story-data and renders one page at a time: full-bleed
   image, embedded text, a storybook page-flip, and playable games. Designed to feel great
   on a tablet. Every game is always winnable — no dead ends.

   ARCHITECTURE
     reader.js     this file: window.GB, the game registry, and the page controller (GB.boot)
     gx.core.js    the game framework: audio / juice / scene / dnd / steps / rewards / ui kit
     gx.board.js   the board-game library (quizzes, on-art play, drag & drop, music, custom DSL)
     gx.arcade.js  REAL arcade games on the Kaplay engine (fullscreen, physics, sprites)
     reader.boot.js loaded last; calls GB.boot() once everything is registered.

   Games register with GB.define(type, {icon, rich, arcade, render}). The controller renders
   each game in a "play card" sheet over the dimmed art; arcade games escalate from the sheet
   to a fullscreen overlay. GB.boot() is re-runnable (the test harness relies on per-load
   isolation), so all mutable reader state lives inside it. */
(function () {
  "use strict";
  const GB = (window.GB = window.GB || {});

  // ---------- tiny DOM + data helpers (shared by the whole runtime) ----------
  GB.h = (tag, cls, html) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  };
  GB.esc = (s) =>
    String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  GB.shuffle = (arr) => {
    const a = (arr || []).slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  };
  // Accept "🍎" or {emoji, label} (or {label}) anywhere a payload names a thing.
  GB.skin = (x, fallbackEmoji) => {
    if (x == null) return { emoji: fallbackEmoji || "⭐", label: "" };
    if (typeof x !== "object") return { emoji: String(x), label: "" };
    return { emoji: x.emoji || fallbackEmoji || "⭐", label: x.label || "" };
  };
  GB.label = (x) => (x && x.label != null ? x.label : x);
  GB.coord = (x) => (x && x.at ? x.at : x);

  // ---------- game registry ----------
  // GB.define(type, def) — def: { icon, rich, arcade, render(ctx) }.
  GB.defs = GB.defs || {};
  GB.define = (type, def) => {
    GB.defs[type] = typeof def === "function" ? { render: def } : def;
  };
  GB.def = (type) => GB.defs[type] || GB.defs._default;

  // ---------- teardown hooks ----------
  // Anything that mounts outside the game sheet (e.g. the arcade fullscreen overlay)
  // registers a teardown; the controller flushes them on page change / sheet close.
  GB.onTeardown = (fn) => (GB._teardowns = GB._teardowns || []).push(fn);
  GB.teardown = () => {
    (GB._teardowns || []).splice(0).forEach((fn) => {
      try { fn(); } catch (e) { /* teardown must never break the reader */ }
    });
  };

  /* =====================================================================
     BOOT — the page controller. Re-run per load; reads #story-data, wires
     the reader, and renders page 0.
     ===================================================================== */
  GB.boot = function () {
    const dataEl = document.getElementById("story-data");
    if (!dataEl) return;
    const story = JSON.parse(dataEl.textContent);
    GB.story = story;
    const pages = story.pages || [];
    const byNumber = {};
    pages.forEach((p, i) => { byNumber[p.number] = i; });

    const reader = document.querySelector(".reader") || document.body;
    const stage = document.getElementById("stage");
    const interactionBox = document.getElementById("interaction");
    const pageNoEl = document.getElementById("pageno");
    const prevBtn = document.getElementById("prev");
    const nextBtn = document.getElementById("next");
    let idx = 0;
    let animating = false;

    const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    GB.reduceMotion = reduceMotion;

    const { h, esc } = GB;

    // ---------- build one page node (image + embedded text) ----------
    function buildPage(page) {
      const figure = h("div", "page-stage");
      const img = document.createElement("img");
      img.src = (page.image && page.image.file) || "";
      img.alt = (page.image && page.image.alt) || "";
      img.loading = "eager";
      figure.appendChild(img);
      figure.appendChild(h("div", "page-shade")); // depth/shadow used during flip

      if (page.text) {
        const layout = page.layout || {};
        const pos = "pos-" + (layout.text_position || "lower-third");
        const align = layout.text_align ? "align-" + layout.text_align : "";
        const overlay = h("div", `page-text ${pos} ${align}`);
        overlay.appendChild(h("div", layout.scrim === false ? "" : "scrim", esc(page.text)));
        figure.appendChild(overlay);
      }
      return figure;
    }

    // ---------- dynamic text fit ----------
    // Long passages must never come out huge or swallow the illustration. Two
    // mechanisms combine so this holds on any screen:
    //   1. Content-aware start size — a text-heavy page renders at a smaller
    //      font than a sparse one, REGARDLESS of geometry, so a full page never
    //      looks huge even on a big monitor where it would technically "fit".
    //   2. Geometry cap — the box may occupy at most a share of the page; if the
    //      start size still overflows, shrink further, and scroll as a last resort.
    function fitText(figure) {
      if (!figure) return;
      const overlay = figure.querySelector(".page-text");
      const box = overlay && overlay.firstElementChild; // .scrim, or the plain text div
      if (!box) return;

      overlay.style.fontSize = ""; // reset so we read the CSS / age-band base
      box.style.maxHeight = "none";
      box.style.overflowY = "";
      const base = parseFloat(getComputedStyle(overlay).fontSize) || 20;

      // 1) Content-aware start size: scale down from the base as the passage grows,
      //    from ~one sentence (LO) to a very full page (HI).
      const chars = (box.textContent || "").trim().length;
      const LO = 140, HI = 620;
      const t = Math.max(0, Math.min(1, (chars - LO) / (HI - LO)));
      let size = base * (1 - 0.4 * t); // down to 60% of base for the fullest pages
      overlay.style.fontSize = size + "px";

      const stageH = stage.clientHeight;
      if (!stageH) return; // no layout yet (e.g. early render): start size is enough

      // 2) Geometry cap. Centered title text gets a little less room than a
      //    bottom/top caption so it never buries the focal art.
      const share = overlay.classList.contains("pos-center") ? 0.42 : 0.48;
      const cap = Math.round(stageH * share);
      const min = Math.max(12, base * 0.55);

      let guard = 0;
      while (box.scrollHeight > cap && size > min && guard < 60) {
        size = Math.max(min, size - 1);
        overlay.style.fontSize = size + "px";
        guard++;
      }
      // Final safety net: hard-cap the height and scroll if a page is still huge.
      box.style.maxHeight = cap + "px";
      box.style.overflowY = box.scrollHeight > cap + 1 ? "auto" : "";
    }

    // ---------- render with page-flip ----------
    function render(dir) {
      const page = pages[idx];
      if (!page) return;
      GB.teardown(); // close any fullscreen game from the previous page

      const incoming = buildPage(page);
      const outgoing = stage.querySelector(".page-stage");

      if (reduceMotion || !outgoing || dir === 0) {
        stage.innerHTML = "";
        stage.appendChild(incoming);
      } else {
        animating = true;
        const forward = dir >= 0;
        // The turning page sits on top; the destination page waits beneath.
        if (forward) {
          stage.appendChild(incoming);             // new page underneath
          outgoing.classList.add("flip-out-next"); // old page curls away
        } else {
          incoming.classList.add("flip-in-prev");  // new page flips down on top
          stage.appendChild(incoming);
        }
        const turner = forward ? outgoing : incoming;
        const done = () => {
          if (outgoing && outgoing.parentNode === stage) outgoing.remove();
          incoming.classList.remove("flip-in-prev");
          animating = false;
        };
        turner.addEventListener("animationend", done, { once: true });
        setTimeout(done, 900); // safety net
      }

      fitText(incoming); // shrink long text so the art is never fully covered
      GB._fitCurrent = () => fitText(stage.querySelector(".page-stage"));

      renderExtras(page);
      interactionBox.innerHTML = "";
      reader.classList.remove("has-game");
      removePlayButton();
      if (page.interaction) addPlayButton(page);
      if (GB.reward) GB.reward.onPage(story, page, idx, pages.length, extrasBox);

      pageNoEl.textContent = `${idx + 1} / ${pages.length}`;
      prevBtn.disabled = idx === 0;
      nextBtn.disabled = idx === pages.length - 1;
      showControls();
    }

    // glossary + grown-up tip live in a slim info strip (kept out of the art)
    let extrasBox = document.getElementById("extras");
    if (!extrasBox) {
      extrasBox = h("div", "extras");
      extrasBox.id = "extras";
      stage.parentNode.insertBefore(extrasBox, interactionBox);
    }

    // Optional-game launcher: a "Play" button shows in the corner of the stage when the
    // current page has a game; its icon comes from the game's registry metadata.
    let playBtn = null;
    function removePlayButton() { if (playBtn) { playBtn.remove(); playBtn = null; } }
    function addPlayButton(page) {
      removePlayButton();
      const def = GB.def(page.interaction.type) || {};
      const icon = def.icon || "🎲";
      playBtn = h("button", "play-game-btn",
        `<span class="play-icon">${esc(icon)}</span><span class="play-label">Play game</span>`);
      playBtn.type = "button";
      playBtn.setAttribute("aria-label", "Play the game on this page");
      playBtn.onclick = (e) => {
        e.stopPropagation();
        if (!page.interaction) return;
        if (!interactionBox.firstChild) {
          renderInteraction(page.interaction, page);
          reader.classList.add("has-game");
        }
        const sheet = interactionBox.querySelector(".interaction");
        if (sheet && sheet.scrollIntoView) sheet.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
        removePlayButton();
      };
      stage.appendChild(playBtn);
    }

    function renderExtras(page) {
      extrasBox.innerHTML = "";
      if (page.vocabulary && page.vocabulary.length) {
        const g = h("div", "glossary");
        g.appendChild(h("span", "glossary-label", "New words: "));
        page.vocabulary.forEach((w) => g.appendChild(h("span", "chip", esc(w))));
        extrasBox.appendChild(g);
      }
      if (page.reading_notes) {
        extrasBox.appendChild(h("div", "reading-note", "Grown-up tip: " + esc(page.reading_notes)));
      }
    }

    function go(n) {
      if (animating) return;
      const target = Math.max(0, Math.min(pages.length - 1, n));
      if (target === idx && stage.querySelector(".page-stage")) return;
      const dir = target === idx ? 0 : target > idx ? 1 : -1;
      idx = target;
      render(dir);
    }
    function gotoNumber(num) { if (byNumber[num] != null) go(byNumber[num]); }
    GB.go = go;
    GB.gotoNumber = gotoNumber;

    /* =====================================================================
       INTERACTION SHELL
       Each game gets a fresh play card. ctx.win() celebrates + unlocks Next;
       ctx.nope() gives gentle feedback. Every game is winnable; never traps.
       ===================================================================== */
    function closeGame() {
      GB.teardown();
      interactionBox.innerHTML = "";
      reader.classList.remove("has-game");
      const p = pages[idx];
      if (p && p.interaction) addPlayButton(p);
    }
    // Tapping the dimmed art around the card closes the game.
    interactionBox.addEventListener("click", (e) => { if (e.target === interactionBox) closeGame(); });

    function renderInteraction(it, page) {
      const box = h("div", "interaction");
      const head = h("div", "game-head");
      head.appendChild(h("h4", "game-title", "🎲 " + esc(it.prompt || "Let's play!")));
      const closeBtn = h("button", "game-close", "✕");
      closeBtn.type = "button";
      closeBtn.setAttribute("aria-label", "Back to the story");
      closeBtn.onclick = closeGame;
      head.appendChild(closeBtn);
      box.appendChild(head);

      const body = h("div", "game-body");
      const fb = h("div", "feedback");
      let won = false;

      const ctx = {
        box, body, fb, it, page,
        data: it.data || {},
        h, esc: GB.esc, shuffle: GB.shuffle, skin: GB.skin, label: GB.label, coord: GB.coord,
        goto: gotoNumber,
        scene: GB.scene, dnd: GB.dnd, ui: GB.ui, audio: GB.audio, juice: GB.juice, arcade: GB.arcade,
        win() {
          if (won) return;
          won = true;
          fb.className = "feedback good";
          fb.textContent = (it.feedback && it.feedback.correct) || "Great job! 🎉";
          box.classList.add("solved");
          if (GB.audio) GB.audio.chime(true);
          if (GB.juice) GB.juice.confetti();
          if (GB.reward) GB.reward.earnFor(story, it, page);
          const cont = h("button", "btn continue-btn", idx < pages.length - 1 ? "Keep reading ›" : "The end 🌟");
          cont.onclick = () => {
            if (idx >= pages.length - 1 && GB.reward) GB.reward.renderCollection(extrasBox, story);
            else go(idx + 1);
          };
          body.appendChild(cont);
        },
        nope(msg) {
          fb.className = "feedback try";
          fb.textContent = msg || (it.feedback && it.feedback.try_again) || "So close — try again!";
          if (GB.audio) GB.audio.chime(false);
          box.classList.remove("shake");
          void box.offsetWidth;
          box.classList.add("shake");
        },
        // One hint, or a progressive ladder; onSolve (optional) is the gentle auto-solve rung.
        hint(hints, onSolve) {
          if (GB.ui) GB.ui.hintLadder(body, Array.isArray(hints) ? hints : hints ? [hints] : [], onSolve);
        },
      };

      if (Array.isArray(it.steps) && it.steps.length && GB.steps) {
        GB.steps.run(ctx, it.steps);
      } else {
        GB.def(it.type).render(ctx);
      }

      box.appendChild(body);
      box.appendChild(fb);
      interactionBox.appendChild(box);
    }

    /* =====================================================================
       IMMERSIVE TABLET UX: tap-zones, auto-hiding controls
       ===================================================================== */
    // tap left/right thirds of the art to turn the page; middle toggles chrome
    stage.addEventListener("click", (e) => {
      if (animating) return;
      const r = stage.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width;
      if (x < 0.3) go(idx - 1);
      else if (x > 0.7) go(idx + 1);
      else toggleControls();
    });

    let hideTimer = null;
    function showControls() {
      reader.classList.remove("controls-hidden");
      clearTimeout(hideTimer);
      hideTimer = setTimeout(() => reader.classList.add("controls-hidden"), 3500);
    }
    function toggleControls() {
      reader.classList.toggle("controls-hidden");
      if (!reader.classList.contains("controls-hidden")) showControls();
    }
    ["mousemove", "touchstart", "keydown"].forEach((ev) =>
      document.addEventListener(ev, showControls, { passive: true }));

    prevBtn.onclick = (e) => { e.stopPropagation(); go(idx - 1); };
    nextBtn.onclick = (e) => { e.stopPropagation(); go(idx + 1); };
    document.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      const a = document.activeElement;
      if (a && (a.tagName === "INPUT" || interactionBox.contains(a))) return; // let games use arrows
      if (e.key === "ArrowRight") go(idx + 1);
      if (e.key === "ArrowLeft") go(idx - 1);
    });

    // Dyslexia-friendly toggle (shared with site).
    const dys = document.getElementById("dyslexia-toggle");
    if (dys) dys.onclick = () => document.body.classList.toggle("dyslexia");

    // Re-fit the text when the stage changes size (resize / orientation /
    // boxed↔immersive breakpoint), so the cap tracks the new page height.
    let fitTimer = null;
    window.addEventListener("resize", () => {
      clearTimeout(fitTimer);
      fitTimer = setTimeout(() => { if (GB._fitCurrent) GB._fitCurrent(); }, 120);
    }, { passive: true });

    render(0);
  };
})();
