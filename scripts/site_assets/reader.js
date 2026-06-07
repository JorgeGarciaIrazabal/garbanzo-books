/* Garbanzo Books — interactive reader runtime.
   Reads the story JSON embedded in #story-data and renders one page at a time with a
   full-bleed image, embedded text, a storybook page-flip turn, and playable mini-games.
   Designed to feel great on a tablet. Every game is always winnable — no dead ends. */
(function () {
  "use strict";
  const dataEl = document.getElementById("story-data");
  if (!dataEl) return;
  const story = JSON.parse(dataEl.textContent);
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

  // ---------- tiny DOM helpers ----------
  function el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
  function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
    return a;
  }

  // ---------- sound (Web Audio) for music games + soft feedback ----------
  let _audio = null;
  function audio() {
    if (_audio == null) { try { _audio = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { _audio = false; } }
    if (_audio && _audio.state === "suspended") _audio.resume();
    return _audio || null;
  }
  const NOTE_FREQ = { C: 261.6, "C#": 277.2, D: 293.7, "D#": 311.1, E: 329.6, F: 349.2, "F#": 370.0, G: 392.0, "G#": 415.3, A: 440.0, "A#": 466.2, B: 493.9, C2: 523.3, D2: 587.3, E2: 659.3, F2: 698.5, G2: 784.0 };
  function freqOf(note) {
    if (typeof note === "number") return note;
    const n = String(note).trim();
    return NOTE_FREQ[n] || NOTE_FREQ[n.toUpperCase()] || 440;
  }
  function tone(freq, dur, when, type) {
    const ctx = audio(); if (!ctx) return;
    const t0 = ctx.currentTime + (when || 0);
    const osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.type = type || "sine"; osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(0.25, t0 + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + (dur || 0.4));
    osc.connect(gain); gain.connect(ctx.destination);
    osc.start(t0); osc.stop(t0 + (dur || 0.4) + 0.05);
  }
  function chime(ok) {
    if (ok) { tone(523.3, 0.16, 0); tone(659.3, 0.16, 0.12); tone(784.0, 0.30, 0.24); }
    else { tone(311.1, 0.18, 0); tone(247.0, 0.22, 0.12); }
  }

  // ---------- confetti celebration ----------
  function confetti() {
    if (reduceMotion) return;
    const colors = ["#6b8f71", "#d98a5b", "#f0c419", "#7a9cc6", "#e07a8b"];
    const layer = el("div", "confetti");
    for (let i = 0; i < 36; i++) {
      const bit = el("i");
      bit.style.left = Math.random() * 100 + "%";
      bit.style.background = colors[i % colors.length];
      bit.style.animationDelay = (Math.random() * 0.25) + "s";
      bit.style.transform = "rotate(" + (Math.random() * 360) + "deg)";
      layer.appendChild(bit);
    }
    reader.appendChild(layer);
    setTimeout(() => layer.remove(), 1800);
  }

  // ---------- build one page node (image + embedded text) ----------
  function buildPage(page) {
    const figure = el("div", "page-stage");
    const img = document.createElement("img");
    img.src = page.image && page.image.file ? page.image.file : "";
    img.alt = (page.image && page.image.alt) || "";
    img.loading = "eager";
    figure.appendChild(img);
    figure.appendChild(el("div", "page-shade")); // depth/shadow used during flip

    if (page.text) {
      const layout = page.layout || {};
      const pos = "pos-" + (layout.text_position || "lower-third");
      const align = layout.text_align ? "align-" + layout.text_align : "";
      const overlay = el("div", "page-text " + pos + " " + align);
      const inner = layout.scrim === false ? el("div", "", esc(page.text)) : el("div", "scrim", esc(page.text));
      overlay.appendChild(inner);
      figure.appendChild(overlay);
    }
    return figure;
  }

  // ---------- render with page-flip ----------
  function render(dir) {
    const page = pages[idx];
    if (!page) return;

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
        stage.appendChild(incoming);            // new page underneath
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

    renderExtras(page);
    interactionBox.innerHTML = "";
    reader.classList.remove("has-game");
    removePlayButton();
    if (page.interaction) addPlayButton(page);

    pageNoEl.textContent = (idx + 1) + " / " + pages.length;
    prevBtn.disabled = idx === 0;
    nextBtn.disabled = idx === pages.length - 1;
    showControls();
  }

  // glossary + grown-up tip live in a slim info strip (kept out of the art)
  let extrasBox = document.getElementById("extras");
  if (!extrasBox) { extrasBox = el("div", "extras"); extrasBox.id = "extras"; stage.parentNode.insertBefore(extrasBox, interactionBox); }

  // Optional-game launcher: a small "Play" button shows in the corner of the stage
  // when the current page has an interaction; tapping it opens the game sheet.
  let playBtn = null;
  function removePlayButton() { if (playBtn) { playBtn.remove(); playBtn = null; } }
  function addPlayButton(page) {
    removePlayButton();
    playBtn = el("button", "play-game-btn", '<span class="play-icon">🎮</span><span class="play-label">Play game</span>');
    playBtn.type = "button";
    playBtn.setAttribute("aria-label", "Play the game on this page");
    playBtn.onclick = (e) => {
      e.stopPropagation();
      if (!page.interaction) return;
      if (!interactionBox.firstChild) {
        renderInteraction(page.interaction, page);
        reader.classList.add("has-game");
      } else {
        reader.classList.remove("sheet-min");
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
      const g = el("div", "glossary");
      g.appendChild(el("span", "glossary-label", "New words: "));
      page.vocabulary.forEach(w => g.appendChild(el("span", "chip", esc(w))));
      extrasBox.appendChild(g);
    }
    if (page.reading_notes) {
      extrasBox.appendChild(el("div", "reading-note", "Grown-up tip: " + esc(page.reading_notes)));
    }
  }

  function go(n) {
    if (animating) return;
    const target = Math.max(0, Math.min(pages.length - 1, n));
    if (target === idx && stage.querySelector(".page-stage")) return;
    const dir = target === idx ? 0 : (target > idx ? 1 : -1);
    idx = target;
    render(dir);
  }
  function gotoNumber(num) { if (byNumber[num] != null) go(byNumber[num]); }

  /* =====================================================================
     GAME ENGINE
     Each game gets a fresh card. Helpers: win() celebrates + unlocks Next;
     nope() gives gentle feedback. Every game is winnable and never traps.
     ===================================================================== */
  function renderInteraction(it, page) {
    const box = el("div", "interaction");
    box.appendChild(el("button", "sheet-handle", "▾"));
    if (it.skill) box.appendChild(el("span", "skill-tag", esc(it.skill)));
    box.appendChild(el("h4", "game-title", "🎲 " + esc(it.prompt || "Let's play!")));

    const body = el("div", "game-body");
    const fb = el("div", "feedback");
    const data = it.data || {};
    let won = false;

    const win = () => {
      if (won) return; won = true;
      fb.className = "feedback good"; fb.textContent = (it.feedback && it.feedback.correct) || "Great job! 🎉";
      box.classList.add("solved"); chime(true); confetti();
      const cont = el("button", "btn continue-btn", idx < pages.length - 1 ? "Keep reading ›" : "The end 🌟");
      cont.onclick = () => go(idx + 1);
      body.appendChild(cont);
    };
    const nope = (msg) => {
      fb.className = "feedback try"; fb.textContent = msg || (it.feedback && it.feedback.try_again) || "So close — try again!";
      chime(false);
      box.classList.remove("shake"); void box.offsetWidth; box.classList.add("shake");
    };
    const hintBtn = (text) => {
      if (!text) return;
      const h = el("button", "btn ghost hint-btn", "💡 Hint");
      const hp = el("div", "hint"); hp.hidden = true; hp.textContent = text;
      h.onclick = () => { hp.hidden = !hp.hidden; };
      body.appendChild(h); body.appendChild(hp);
    };

    const G = GAMES[it.type] || GAMES._default;
    G({ box, body, data, it, page, win, nope, hintBtn });

    box.appendChild(body);
    box.appendChild(fb);
    box.querySelector(".sheet-handle").onclick = () => reader.classList.toggle("sheet-min");
    interactionBox.appendChild(box);
    reader.classList.remove("sheet-min");
  }

  const GAMES = {
    // --- find every named thing (toggle list) ---
    "seek-and-find": ({ body, data, win }) => {
      const items = data.items || [];
      const wrap = el("div", "chip-row");
      items.forEach(item => {
        const c = el("button", "find-item", "🔍 " + esc(item));
        c.onclick = () => { c.classList.toggle("found"); if (wrap.querySelectorAll(".found").length === items.length) win(); };
        wrap.appendChild(c);
      });
      body.appendChild(wrap);
    },

    // --- phonics: tap the words with the target sound ---
    "sound-hunt": ({ body, data, win, nope }) => {
      const targets = new Set((data.words || []).map(w => String(w).toLowerCase()));
      body.appendChild(el("p", "game-line", "Find the words with the /" + esc(data.sound || "") + "/ sound:"));
      const wrap = el("div", "chip-row");
      shuffle((data.words || []).concat(data.decoys || [])).forEach(w => {
        const c = el("button", "hunt-word", esc(w));
        c.onclick = () => {
          if (c.classList.contains("found") || c.classList.contains("wrong")) return;
          if (targets.has(String(w).toLowerCase())) { c.classList.add("found"); if (wrap.querySelectorAll(".found").length === targets.size) win(); }
          else { c.classList.add("wrong"); nope(); setTimeout(() => c.classList.remove("wrong"), 600); }
        };
        wrap.appendChild(c);
      });
      body.appendChild(wrap);
    },

    // --- pick the right answer (rhyme / comprehension / riddle / quiz) ---
    "rhyme-complete": (ctx) => quiz(ctx),
    "comprehension-question": (ctx) => quiz(ctx),
    "riddle": (ctx) => quiz(ctx),
    "odd-one-out": ({ body, data, win, nope, hintBtn }) => {
      body.appendChild(el("p", "game-line", "Tap the one that doesn't belong:"));
      const wrap = el("div", "options");
      shuffle(data.items || []).forEach(o => {
        const b = el("button", "opt", esc(o));
        b.onclick = () => {
          if (String(o) === String(data.answer)) { b.classList.add("correct"); win(); }
          else { b.classList.add("wrong"); nope(); setTimeout(() => b.classList.remove("wrong"), 600); }
        };
        wrap.appendChild(b);
      });
      body.appendChild(wrap); hintBtn(data.hint);
    },

    // --- count things ---
    "counting": ({ body, data, win, nope }) => {
      body.appendChild(el("p", "game-line", "How many " + esc(data.what || "things") + "?"));
      const row = el("div", "count-row");
      const input = el("input", "num-input"); input.type = "number"; input.inputMode = "numeric"; input.min = "0";
      const b = el("button", "btn", "Check");
      const check = () => { Number(input.value) === Number(data.answer) ? win() : nope(); };
      b.onclick = check; input.addEventListener("keydown", e => { if (e.key === "Enter") check(); });
      row.appendChild(input); row.appendChild(b); body.appendChild(row);
    },

    // --- connect each word to its match (click left, then right) ---
    "word-match": (ctx) => matchGame(ctx, "Match each one to its pair:"),

    // --- branching choice ---
    "choice": ({ body, data }) => {
      const wrap = el("div", "options");
      (data.options || []).forEach(o => {
        const b = el("button", "opt big", esc(o.label));
        b.onclick = () => gotoNumber(o.goto);
        wrap.appendChild(b);
      });
      body.appendChild(wrap);
    },

    // --- finger-trace a letter on a canvas ---
    "trace-letter": ({ body, data, win }) => {
      body.appendChild(el("p", "game-line", "Trace the letter — as in " + esc(data.word || "") + ":"));
      const wrap = el("div", "trace-wrap");
      const ghost = el("div", "trace-ghost", esc(data.letter || "?"));
      const cv = document.createElement("canvas"); cv.className = "trace-canvas"; cv.width = 280; cv.height = 280;
      const ctx2 = cv.getContext("2d");
      ctx2.lineWidth = 14; ctx2.lineCap = "round"; ctx2.lineJoin = "round"; ctx2.strokeStyle = "#6b8f71";
      let drawing = false, last = null, painted = 0;
      const pos = e => { const r = cv.getBoundingClientRect(); const t = e.touches ? e.touches[0] : e; return { x: (t.clientX - r.left) * cv.width / r.width, y: (t.clientY - r.top) * cv.height / r.height }; };
      const start = e => { drawing = true; last = pos(e); e.preventDefault(); };
      const move = e => {
        if (!drawing) return;
        const p = pos(e); ctx2.beginPath(); ctx2.moveTo(last.x, last.y); ctx2.lineTo(p.x, p.y); ctx2.stroke();
        painted += Math.hypot(p.x - last.x, p.y - last.y); last = p; e.preventDefault();
        if (painted > 600) win();
      };
      const end = () => { drawing = false; };
      cv.addEventListener("mousedown", start); cv.addEventListener("mousemove", move); window.addEventListener("mouseup", end);
      cv.addEventListener("touchstart", start, { passive: false }); cv.addEventListener("touchmove", move, { passive: false }); cv.addEventListener("touchend", end);
      wrap.appendChild(ghost); wrap.appendChild(cv); body.appendChild(wrap);
    },

    // --- spot the differences (clickable hotspots over a copy of the art) ---
    "spot-the-difference": ({ body, data, page, win, nope }) => {
      const spots = data.spots || [];
      const total = data.count || spots.length;
      body.appendChild(el("p", "game-line", "Find all " + esc(total) + " differences — tap them!"));
      if (spots.length && page && page.image && page.image.file) {
        const frame = el("div", "spot-frame");
        const img = document.createElement("img"); img.src = page.image.file; img.alt = "";
        frame.appendChild(img);
        let found = 0;
        spots.forEach(s => {
          const h = el("button", "spot");
          h.style.left = (s.x || 0) + "%"; h.style.top = (s.y || 0) + "%";
          if (s.r) { h.style.width = h.style.height = s.r + "%"; }
          h.onclick = () => { if (h.classList.contains("got")) return; h.classList.add("got"); found++; if (found >= spots.length) win(); };
          frame.appendChild(h);
        });
        // a couple of decoy taps elsewhere give gentle "try again"
        frame.addEventListener("click", e => { if (e.target === frame || e.target === img) nope("Look closely!"); });
        body.appendChild(frame);
      } else {
        const b = el("button", "btn", "I found them all!"); b.onclick = win; body.appendChild(b);
      }
    },

    // --- put the steps in order (move up/down) ---
    "drag-order": (ctx) => orderGame(ctx),
    "memory": (ctx) => { (ctx.data.pairs ? memoryGame : orderGame)(ctx); },

    // --- flip cards to reveal what's hidden ---
    "tap-to-reveal": ({ body, data, win }) => {
      const cards = data.cards || (data.items || []).map(x => ({ front: "?", back: x }));
      const grid = el("div", "card-grid");
      let revealed = 0;
      cards.forEach(c => {
        const card = el("button", "flip-card");
        card.innerHTML = '<span class="fc-front">' + esc(c.front || "❔") + '</span><span class="fc-back">' + esc(c.back != null ? c.back : c) + '</span>';
        card.onclick = () => { if (card.classList.contains("flipped")) return; card.classList.add("flipped"); revealed++; if (revealed >= cards.length) win(); };
        grid.appendChild(card);
      });
      body.appendChild(grid);
    },

    // --- sort items into the right buckets (logic) ---
    "sorting": ({ body, data, win, nope }) => {
      const items = shuffle((data.items || []).map((x, i) => ({ label: x.label != null ? x.label : x, bin: x.bin, id: i })));
      const bins = data.bins || [];
      body.appendChild(el("p", "game-line", "Tap an item, then tap where it belongs:"));
      const tray = el("div", "chip-row sort-tray");
      const binRow = el("div", "bin-row");
      let selected = null, placed = 0;
      const chips = items.map(it => {
        const c = el("button", "sort-item", esc(it.label));
        c.onclick = () => { tray.querySelectorAll(".sel").forEach(x => x.classList.remove("sel")); c.classList.add("sel"); selected = { it, c }; };
        tray.appendChild(c); return c;
      });
      bins.forEach((bn, bi) => {
        const name = bn.label != null ? bn.label : bn;
        const key = bn.key != null ? bn.key : name;
        const bin = el("div", "bin"); bin.appendChild(el("div", "bin-label", esc(name)));
        const slot = el("div", "bin-slot"); bin.appendChild(slot);
        bin.onclick = () => {
          if (!selected) return;
          if (String(selected.it.bin) === String(key) || String(selected.it.bin) === String(bi) || String(selected.it.bin) === String(name)) {
            slot.appendChild(el("span", "chip placed", esc(selected.it.label)));
            selected.c.remove(); selected = null; placed++;
            if (placed === items.length) win();
          } else { nope("Not that bucket — try another!"); }
        };
        binRow.appendChild(bin);
      });
      body.appendChild(tray); body.appendChild(binRow);
    },

    // --- what comes next in the pattern? ---
    "pattern": ({ body, data, win, nope, hintBtn }) => {
      const seq = data.sequence || [];
      const strip = el("div", "pattern-strip");
      seq.forEach(s => strip.appendChild(el("span", "pat-cell", esc(s))));
      strip.appendChild(el("span", "pat-cell pat-q", "?"));
      body.appendChild(strip);
      body.appendChild(el("p", "game-line", "What comes next?"));
      const opts = data.options || (data.distractors ? [data.answer].concat(data.distractors) : [data.answer]);
      const wrap = el("div", "options");
      shuffle(opts).forEach(o => {
        const b = el("button", "opt", esc(o));
        b.onclick = () => {
          if (String(o) === String(data.answer)) { b.classList.add("correct"); strip.querySelector(".pat-q").textContent = o; strip.querySelector(".pat-q").classList.remove("pat-q"); win(); }
          else { b.classList.add("wrong"); nope(); setTimeout(() => b.classList.remove("wrong"), 600); }
        };
        wrap.appendChild(b);
      });
      body.appendChild(wrap); hintBtn(data.hint);
    },

    // --- music: listen, then play the tune back (Simon-style) ---
    "melody": ({ body, data, win, nope }) => {
      const notes = (data.notes || data.sequence || ["C", "E", "G"]).map(String);
      const pads = data.pads || Array.from(new Set(notes));
      body.appendChild(el("p", "game-line", "Listen to the tune, then tap it back!"));
      const listen = el("button", "btn", "🔊 Play the tune");
      let canPlay = true;
      listen.onclick = () => {
        if (!canPlay) return; canPlay = false; let t = 0;
        notes.forEach((n, i) => { tone(freqOf(n), 0.42, t); const pad = padEls[pads.indexOf(n)]; if (pad) setTimeout(() => flash(pad), t * 1000); t += 0.5; });
        setTimeout(() => { canPlay = true; }, t * 1000 + 200);
      };
      body.appendChild(listen);
      const keyboard = el("div", "melody-pads");
      let step = 0;
      const flash = pad => { pad.classList.add("lit"); setTimeout(() => pad.classList.remove("lit"), 240); };
      const padEls = pads.map(n => {
        const pad = el("button", "melody-pad", esc(n));
        pad.onclick = () => {
          tone(freqOf(n), 0.4, 0); flash(pad);
          if (n === notes[step]) { step++; if (step >= notes.length) win(); }
          else { step = 0; nope("Oops — listen again and start over!"); }
        };
        keyboard.appendChild(pad); return pad;
      });
      body.appendChild(keyboard);
    },

    // --- maze: guide the character to the goal ---
    "maze": ({ body, data, win }) => {
      // Accept "#"/"." char grids OR space-separated grids with letter markers
      // (B/#/X = wall, S = start, E = end, everything else = open path).
      let grid = data.grid;
      if (typeof grid === "string") grid = grid.split(/\r?\n/);
      grid = (grid || ["..", ".."]).map(r => String(r).trim()).filter(r => r.length)
        .map(r => /\s/.test(r) ? r.split(/\s+/) : r.split(""));
      const isWall = ch => ch === "#" || ch === "B" || ch === "X" || ch === "x";
      const rows = grid.length, cols = Math.max.apply(null, grid.map(r => r.length));
      grid = grid.map(r => { while (r.length < cols) r.push("."); return r.map(ch => isWall(ch) ? "#" : ch); });
      const start = (data.start || [0, 0]).slice();
      let end = (data.end || [rows - 1, cols - 1]).slice();
      // S/E markers in the grid win over start/end arrays
      for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
        if (grid[r][c] === "S") { start[0] = r; start[1] = c; grid[r][c] = "."; }
        if (grid[r][c] === "E") { end = [r, c]; grid[r][c] = "."; }
      }
      if (end[0] >= rows || end[1] >= cols) end = [rows - 1, cols - 1];
      if (isWall(grid[start[0]][start[1]])) grid[start[0]][start[1]] = ".";
      let pos = [start[0], start[1]];
      body.appendChild(el("p", "game-line", "Use the arrows (or swipe / arrow keys) to reach 🎯"));
      const board = el("div", "maze");
      board.style.gridTemplateColumns = "repeat(" + cols + ", 1fr)";
      const cells = [];
      for (let r = 0; r < rows; r++) { cells[r] = []; for (let c = 0; c < cols; c++) {
        const cell = el("div", "maze-cell" + (grid[r][c] === "#" ? " wall" : ""));
        if (r === end[0] && c === end[1]) cell.appendChild(el("span", "maze-goal", "🎯"));
        board.appendChild(cell); cells[r][c] = cell;
      } }
      const hero = el("div", "maze-hero", "🐾");
      function place() { const cell = cells[pos[0]][pos[1]]; cell.appendChild(hero); if (pos[0] === end[0] && pos[1] === end[1]) win(); }
      function move(dr, dc) {
        const nr = pos[0] + dr, nc = pos[1] + dc;
        if (nr < 0 || nc < 0 || nr >= rows || nc >= cols) return;
        if (grid[nr][nc] === "#") { board.classList.remove("bump"); void board.offsetWidth; board.classList.add("bump"); return; }
        pos = [nr, nc]; place();
      }
      body.appendChild(board); place();
      const pad = el("div", "dpad");
      [["↑", -1, 0], ["←", 0, -1], ["→", 0, 1], ["↓", 1, 0]].forEach(([lbl, dr, dc]) => {
        const b = el("button", "dpad-btn dpad-" + lbl, lbl); b.onclick = () => move(dr, dc); pad.appendChild(b);
      });
      body.appendChild(pad);
      const keyh = e => { const m = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }[e.key]; if (m && interactionBox.contains(board)) { e.preventDefault(); e.stopPropagation(); move(m[0], m[1]); } };
      board.tabIndex = 0; board.addEventListener("keydown", keyh);
      // swipe
      let sx = 0, sy = 0;
      board.addEventListener("touchstart", e => { sx = e.touches[0].clientX; sy = e.touches[0].clientY; }, { passive: true });
      board.addEventListener("touchend", e => {
        const dx = e.changedTouches[0].clientX - sx, dy = e.changedTouches[0].clientY - sy;
        if (Math.abs(dx) > Math.abs(dy)) move(0, dx > 0 ? 1 : -1); else move(dy > 0 ? 1 : -1, 0);
      });
    },

    // --- creative free play: color the picture by tapping ---
    "coloring": ({ body, data, win }) => {
      const palette = data.palette || ["#e07a8b", "#7a9cc6", "#6b8f71", "#f0c419", "#d98a5b", "#9b6bd9"];
      const regions = data.regions || ["sky", "ground", "tree", "sun", "house"];
      let color = palette[0];
      const pal = el("div", "palette");
      palette.forEach(col => { const sw = el("button", "pal-swatch"); sw.style.background = col; sw.onclick = () => { color = col; pal.querySelectorAll(".sel").forEach(x => x.classList.remove("sel")); sw.classList.add("sel"); }; pal.appendChild(sw); });
      pal.firstChild.classList.add("sel");
      const grid = el("div", "color-grid");
      regions.forEach(name => { const r = el("button", "color-region", esc(name)); r.onclick = () => { r.style.background = color; r.style.color = "#fff"; r.dataset.done = "1"; if (grid.querySelectorAll('[data-done]').length === regions.length) win(); }; grid.appendChild(r); });
      body.appendChild(pal); body.appendChild(grid);
      const b = el("button", "btn ghost", "I like my picture!"); b.onclick = win; body.appendChild(b);
    },

    _default: ({ body, win }) => { const b = el("button", "btn", "I did it!"); b.onclick = win; body.appendChild(b); }
  };

  // shared quiz (one correct answer among options)
  function quiz({ box, body, data, it, win, nope, hintBtn }) {
    const answer = it.type === "comprehension-question" ? (data.options || [])[data.answer_index] : data.answer;
    let opts = data.options || (data.distractors ? [data.answer].concat(data.distractors) : [data.answer]);
    if (it.type === "rhyme-complete" && data.sentence) body.appendChild(el("p", "game-line", esc(data.sentence.replace("___", "______"))));
    if ((it.type === "riddle" || it.type === "comprehension-question") && data.question) body.appendChild(el("p", "game-line", esc(data.question)));
    const wrap = el("div", "options");
    shuffle(opts).forEach(o => {
      const b = el("button", "opt", esc(o));
      b.onclick = () => { if (String(o) === String(answer)) { b.classList.add("correct"); win(); } else { b.classList.add("wrong"); nope(); setTimeout(() => b.classList.remove("wrong"), 600); } };
      wrap.appendChild(b);
    });
    body.appendChild(wrap); hintBtn(data.hint);
  }

  // shared connect-the-pairs matcher
  function matchGame({ body, data, win, nope }, line) {
    const pairs = data.pairs || [];
    body.appendChild(el("p", "game-line", line));
    const grid = el("div", "match-grid");
    const lefts = el("div", "match-col"), rights = el("div", "match-col");
    let selL = null, done = 0;
    pairs.forEach((pr, i) => {
      const a = el("button", "match-cell", esc(pr[0])); a.dataset.k = i;
      a.onclick = () => { if (a.classList.contains("matched")) return; lefts.querySelectorAll(".sel").forEach(x => x.classList.remove("sel")); a.classList.add("sel"); selL = a; };
      lefts.appendChild(a);
    });
    shuffle(pairs.map((pr, i) => ({ v: pr[1], k: i }))).forEach(r => {
      const b = el("button", "match-cell", esc(r.v)); b.dataset.k = r.k;
      b.onclick = () => {
        if (b.classList.contains("matched") || !selL) return;
        if (selL.dataset.k === b.dataset.k) { selL.classList.add("matched"); b.classList.add("matched"); selL.classList.remove("sel"); selL = null; done++; if (done === pairs.length) win(); }
        else { b.classList.add("wrong"); nope(); setTimeout(() => b.classList.remove("wrong"), 500); }
      };
      rights.appendChild(b);
    });
    grid.appendChild(lefts); grid.appendChild(rights); body.appendChild(grid);
  }

  // shared put-in-order game
  function orderGame({ body, data, win, nope }) {
    const correct = data.sequence || [];
    let cur = shuffle(correct);
    if (correct.length > 1 && cur.join("|") === correct.join("|")) cur = shuffle(correct);
    body.appendChild(el("p", "game-line", "Put these in the right order:"));
    const list = el("div", "order-list");
    function paint() {
      list.innerHTML = "";
      cur.forEach((item, i) => {
        const row = el("div", "order-row");
        row.appendChild(el("span", "order-text", esc(item)));
        const ups = el("div", "order-btns");
        const up = el("button", "order-arrow", "↑"); up.disabled = i === 0; up.onclick = () => { [cur[i - 1], cur[i]] = [cur[i], cur[i - 1]]; paint(); };
        const dn = el("button", "order-arrow", "↓"); dn.disabled = i === cur.length - 1; dn.onclick = () => { [cur[i + 1], cur[i]] = [cur[i], cur[i + 1]]; paint(); };
        ups.appendChild(up); ups.appendChild(dn); row.appendChild(ups); list.appendChild(row);
      });
    }
    paint();
    const check = el("button", "btn", "Check my order");
    check.onclick = () => { cur.join("|") === correct.join("|") ? win() : nope("Not quite — keep arranging!"); };
    body.appendChild(list); body.appendChild(check);
  }

  // shared memory card-match game (flip two cards, find the matching pair)
  function memoryGame({ body, data, win }) {
    const pairs = data.pairs || [];
    body.appendChild(el("p", "game-line", "Flip two cards to find a matching pair:"));
    const cards = [];
    pairs.forEach((pr, i) => { cards.push({ pid: i, face: pr[0] }); cards.push({ pid: i, face: pr[1] }); });
    const grid = el("div", "card-grid");
    let first = null, lock = false, matched = 0;
    shuffle(cards).forEach(c => {
      const card = el("button", "flip-card");
      card.innerHTML = '<span class="fc-front">❔</span><span class="fc-back">' + esc(c.face) + '</span>';
      card.dataset.pid = c.pid;
      card.onclick = () => {
        if (lock || card.classList.contains("flipped") || card.classList.contains("matched")) return;
        card.classList.add("flipped");
        if (!first) { first = card; return; }
        if (first.dataset.pid === card.dataset.pid) {
          first.classList.add("matched"); card.classList.add("matched"); first = null; matched++;
          if (matched === pairs.length) win();
        } else {
          lock = true; const a = first, b = card; first = null;
          setTimeout(() => { a.classList.remove("flipped"); b.classList.remove("flipped"); lock = false; }, 850);
        }
      };
      grid.appendChild(card);
    });
    body.appendChild(grid);
  }

  /* =====================================================================
     IMMERSIVE TABLET UX: tap-zones, auto-hiding controls
     ===================================================================== */
  // tap left/right thirds of the art to turn the page; middle toggles chrome
  stage.addEventListener("click", e => {
    if (animating) return;
    const r = stage.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width;
    if (x < 0.30) go(idx - 1);
    else if (x > 0.70) go(idx + 1);
    else toggleControls();
  });

  let hideTimer = null;
  function showControls() {
    reader.classList.remove("controls-hidden");
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => reader.classList.add("controls-hidden"), 3500);
  }
  function toggleControls() { reader.classList.toggle("controls-hidden"); if (!reader.classList.contains("controls-hidden")) showControls(); }
  ["mousemove", "touchstart", "keydown"].forEach(ev => document.addEventListener(ev, showControls, { passive: true }));

  prevBtn.onclick = (e) => { e.stopPropagation(); go(idx - 1); };
  nextBtn.onclick = (e) => { e.stopPropagation(); go(idx + 1); };
  document.addEventListener("keydown", e => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const a = document.activeElement;
    if (a && (a.tagName === "INPUT" || interactionBox.contains(a))) return; // let games use arrows
    if (e.key === "ArrowRight") go(idx + 1);
    if (e.key === "ArrowLeft") go(idx - 1);
  });

  // Dyslexia-friendly toggle (shared with site).
  const dys = document.getElementById("dyslexia-toggle");
  if (dys) dys.onclick = () => document.body.classList.toggle("dyslexia");

  render(0);
})();
