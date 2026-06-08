/* Garbanzo Books — interactive reader runtime (core controller).
   Reads the story JSON embedded in #story-data and renders one page at a time with a
   full-bleed image, embedded text, a storybook page-flip turn, and playable mini-games.
   Designed to feel great on a tablet. Every game is always winnable — no dead ends.

   ARCHITECTURE — this file owns window.GB and the page controller (GB.boot). The reusable
   game toolkit (GB.audio / GB.juice / GB.scene / GB.dnd / GB.steps / GB.reward / GB.shared)
   and the game library (GB.games, populated via GB.registerGame) load in separate files
   AFTER this one. The LAST file calls GB.boot(), so every game is registered before the
   first page renders. Keeping the controller inside GB.boot() (re-runnable) preserves the
   per-load isolation the old single-IIFE had — important for the test harness. */
(function () {
  "use strict";
  var GB = (window.GB = window.GB || {});

  // ---------- tiny DOM helpers (shared by the whole toolkit) ----------
  GB.el = function (tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  };
  GB.esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  };
  GB.shuffle = function (arr) {
    var a = (arr || []).slice();
    for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  };

  // ---------- game registry ----------
  GB.games = GB.games || {};
  GB.registerGame = function (type, fn) { GB.games[type] = fn; };

  /* =====================================================================
     BOOT — the page controller. Re-run per load; reads #story-data, wires
     the reader, and renders page 0. All mutable reader state lives here so
     each boot() starts fresh.
     ===================================================================== */
  GB.boot = function () {
    var dataEl = document.getElementById("story-data");
    if (!dataEl) return;
    var story = JSON.parse(dataEl.textContent);
    GB.story = story;
    var pages = story.pages || [];
    var byNumber = {};
    pages.forEach(function (p, i) { byNumber[p.number] = i; });

    var reader = document.querySelector(".reader") || document.body;
    var stage = document.getElementById("stage");
    var interactionBox = document.getElementById("interaction");
    var pageNoEl = document.getElementById("pageno");
    var prevBtn = document.getElementById("prev");
    var nextBtn = document.getElementById("next");
    var idx = 0;
    var animating = false;

    var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    GB.reduceMotion = reduceMotion;

    var el = GB.el, esc = GB.esc;

    // ---------- build one page node (image + embedded text) ----------
    function buildPage(page) {
      var figure = el("div", "page-stage");
      var img = document.createElement("img");
      img.src = page.image && page.image.file ? page.image.file : "";
      img.alt = (page.image && page.image.alt) || "";
      img.loading = "eager";
      figure.appendChild(img);
      figure.appendChild(el("div", "page-shade")); // depth/shadow used during flip

      if (page.text) {
        var layout = page.layout || {};
        var pos = "pos-" + (layout.text_position || "lower-third");
        var align = layout.text_align ? "align-" + layout.text_align : "";
        var overlay = el("div", "page-text " + pos + " " + align);
        var inner = layout.scrim === false ? el("div", "", esc(page.text)) : el("div", "scrim", esc(page.text));
        overlay.appendChild(inner);
        figure.appendChild(overlay);
      }
      return figure;
    }

    // ---------- render with page-flip ----------
    function render(dir) {
      var page = pages[idx];
      if (!page) return;

      var incoming = buildPage(page);
      var outgoing = stage.querySelector(".page-stage");

      if (reduceMotion || !outgoing || dir === 0) {
        stage.innerHTML = "";
        stage.appendChild(incoming);
      } else {
        animating = true;
        var forward = dir >= 0;
        // The turning page sits on top; the destination page waits beneath.
        if (forward) {
          stage.appendChild(incoming);            // new page underneath
          outgoing.classList.add("flip-out-next"); // old page curls away
        } else {
          incoming.classList.add("flip-in-prev");  // new page flips down on top
          stage.appendChild(incoming);
        }
        var turner = forward ? outgoing : incoming;
        var done = function () {
          if (outgoing && outgoing.parentNode === stage) outgoing.remove();
          incoming.classList.remove("flip-in-prev");
          animating = false;
        };
        turner.addEventListener("animationend", done, { once: true });
        setTimeout(done, 900); // safety net
      }

      renderExtras(page);
      interactionBox.innerHTML = "";
      reader.classList.remove("has-game");
      removePlayButton();
      if (page.interaction) addPlayButton(page);
      if (GB.reward) GB.reward.onPage(story, page, idx, pages.length, extrasBox);

      pageNoEl.textContent = (idx + 1) + " / " + pages.length;
      prevBtn.disabled = idx === 0;
      nextBtn.disabled = idx === pages.length - 1;
      showControls();
    }

    // glossary + grown-up tip live in a slim info strip (kept out of the art)
    var extrasBox = document.getElementById("extras");
    if (!extrasBox) { extrasBox = el("div", "extras"); extrasBox.id = "extras"; stage.parentNode.insertBefore(extrasBox, interactionBox); }

    // Optional-game launcher: a small "Play" button shows in the corner of the stage
    // when the current page has an interaction; tapping it opens the game sheet.
    var playBtn = null;
    function removePlayButton() { if (playBtn) { playBtn.remove(); playBtn = null; } }
    function addPlayButton(page) {
      removePlayButton();
      playBtn = el("button", "play-game-btn", '<span class="play-icon">🎮</span><span class="play-label">Play game</span>');
      playBtn.type = "button";
      playBtn.setAttribute("aria-label", "Play the game on this page");
      playBtn.onclick = function (e) {
        e.stopPropagation();
        if (!page.interaction) return;
        if (!interactionBox.firstChild) {
          renderInteraction(page.interaction, page);
          reader.classList.add("has-game");
        } else {
          reader.classList.remove("sheet-min");
        }
        var sheet = interactionBox.querySelector(".interaction");
        if (sheet && sheet.scrollIntoView) sheet.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
        removePlayButton();
      };
      stage.appendChild(playBtn);
    }
    function renderExtras(page) {
      extrasBox.innerHTML = "";
      if (page.vocabulary && page.vocabulary.length) {
        var g = el("div", "glossary");
        g.appendChild(el("span", "glossary-label", "New words: "));
        page.vocabulary.forEach(function (w) { g.appendChild(el("span", "chip", esc(w))); });
        extrasBox.appendChild(g);
      }
      if (page.reading_notes) {
        extrasBox.appendChild(el("div", "reading-note", "Grown-up tip: " + esc(page.reading_notes)));
      }
    }

    function go(n) {
      if (animating) return;
      var target = Math.max(0, Math.min(pages.length - 1, n));
      if (target === idx && stage.querySelector(".page-stage")) return;
      var dir = target === idx ? 0 : (target > idx ? 1 : -1);
      idx = target;
      render(dir);
    }
    function gotoNumber(num) { if (byNumber[num] != null) go(byNumber[num]); }
    GB.go = go; GB.gotoNumber = gotoNumber;

    /* =====================================================================
       INTERACTION SHELL
       Each game gets a fresh card. Helpers: win() celebrates + unlocks Next;
       nope() gives gentle feedback. Every game is winnable and never traps.
       ===================================================================== */
    function renderInteraction(it, page) {
      var box = el("div", "interaction");
      box.appendChild(el("button", "sheet-handle", "▾"));
      if (it.skill) box.appendChild(el("span", "skill-tag", esc(it.skill)));
      box.appendChild(el("h4", "game-title", "🎲 " + esc(it.prompt || "Let's play!")));

      var body = el("div", "game-body");
      var fb = el("div", "feedback");
      var data = it.data || {};
      var won = false;

      var win = function () {
        if (won) return; won = true;
        fb.className = "feedback good"; fb.textContent = (it.feedback && it.feedback.correct) || "Great job! 🎉";
        box.classList.add("solved");
        if (GB.audio) GB.audio.chime(true);
        if (GB.juice) GB.juice.confetti();
        if (GB.reward) GB.reward.earnFor(story, it, page);
        var cont = el("button", "btn continue-btn", idx < pages.length - 1 ? "Keep reading ›" : "The end 🌟");
        cont.onclick = function () {
          if (idx >= pages.length - 1 && GB.reward) GB.reward.renderCollection(extrasBox, story);
          else go(idx + 1);
        };
        body.appendChild(cont);
      };
      var nope = function (msg) {
        fb.className = "feedback try"; fb.textContent = msg || (it.feedback && it.feedback.try_again) || "So close — try again!";
        if (GB.audio) GB.audio.chime(false);
        box.classList.remove("shake"); void box.offsetWidth; box.classList.add("shake");
      };
      var hintBtn = function (text) {
        if (!text) return;
        // A single text hint, or a ladder of progressive hints.
        if (Array.isArray(text)) { if (GB.shared && GB.shared.hintLadder) return GB.shared.hintLadder(body, text); text = text[0]; }
        var h = el("button", "btn ghost hint-btn", "💡 Hint");
        var hp = el("div", "hint"); hp.hidden = true; hp.textContent = text;
        h.onclick = function () { hp.hidden = !hp.hidden; };
        body.appendChild(h); body.appendChild(hp);
      };

      var ctx = {
        box: box, body: body, data: data, it: it, page: page,
        win: win, nope: nope, hintBtn: hintBtn, gotoNumber: gotoNumber,
        scene: GB.scene, dnd: GB.dnd, juice: GB.juice, audio: GB.audio,
        steps: GB.steps, reward: GB.reward, shared: GB.shared
      };
      if (Array.isArray(it.steps) && it.steps.length && GB.steps) {
        GB.steps.run(ctx, it.steps);
      } else {
        var G = GB.games[it.type] || GB.games._default;
        G(ctx);
      }

      box.appendChild(body);
      box.appendChild(fb);
      box.querySelector(".sheet-handle").onclick = function () { reader.classList.toggle("sheet-min"); };
      interactionBox.appendChild(box);
      reader.classList.remove("sheet-min");
    }

    /* =====================================================================
       IMMERSIVE TABLET UX: tap-zones, auto-hiding controls
       ===================================================================== */
    // tap left/right thirds of the art to turn the page; middle toggles chrome
    stage.addEventListener("click", function (e) {
      if (animating) return;
      var r = stage.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width;
      if (x < 0.30) go(idx - 1);
      else if (x > 0.70) go(idx + 1);
      else toggleControls();
    });

    var hideTimer = null;
    function showControls() {
      reader.classList.remove("controls-hidden");
      clearTimeout(hideTimer);
      hideTimer = setTimeout(function () { reader.classList.add("controls-hidden"); }, 3500);
    }
    function toggleControls() { reader.classList.toggle("controls-hidden"); if (!reader.classList.contains("controls-hidden")) showControls(); }
    ["mousemove", "touchstart", "keydown"].forEach(function (ev) { document.addEventListener(ev, showControls, { passive: true }); });

    prevBtn.onclick = function (e) { e.stopPropagation(); go(idx - 1); };
    nextBtn.onclick = function (e) { e.stopPropagation(); go(idx + 1); };
    document.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      var a = document.activeElement;
      if (a && (a.tagName === "INPUT" || interactionBox.contains(a))) return; // let games use arrows
      if (e.key === "ArrowRight") go(idx + 1);
      if (e.key === "ArrowLeft") go(idx - 1);
    });

    // Dyslexia-friendly toggle (shared with site).
    var dys = document.getElementById("dyslexia-toggle");
    if (dys) dys.onclick = function () { document.body.classList.toggle("dyslexia"); };

    render(0);
  };
})();
