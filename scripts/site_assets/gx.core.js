/* gx.core — the game framework: everything games share.
     GB.audio   oscillator-synth sound kit (no audio files; works offline)
     GB.juice   feedback effects (confetti, bursts, squash, haptics) — reduced-motion safe
     GB.scene   interactive overlay ON the page illustration (normalized 0..1 coords)
     GB.dnd     true pointer drag-and-drop with snapping + keyboard fallback
     GB.steps   multi-beat sequencer (interaction.steps)
     GB.reward  cross-page sticker collection (sessionStorage, private-mode safe)
     GB.ui      shared game builders: options quiz, pair matcher, ordering, memory,
                hint ladder (whose last rung gently auto-solves — the always-winnable
                backstop), winnable guard.
   Loaded after reader.js (which owns window.GB + the registry), before the game files. */
(function () {
  "use strict";
  const GB = (window.GB = window.GB || {});
  const h = GB.h, esc = GB.esc, shuffle = GB.shuffle;

  /* ================================ AUDIO ================================ */
  let _audio = null;
  function audioCtx() {
    if (_audio == null) {
      try { _audio = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { _audio = false; }
    }
    if (_audio && _audio.state === "suspended") _audio.resume();
    return _audio || null;
  }
  const NOTE_FREQ = {
    C: 261.6, "C#": 277.2, D: 293.7, "D#": 311.1, E: 329.6, F: 349.2, "F#": 370.0,
    G: 392.0, "G#": 415.3, A: 440.0, "A#": 466.2, B: 493.9,
    C2: 523.3, D2: 587.3, E2: 659.3, F2: 698.5, G2: 784.0,
  };
  const freqOf = (note) => {
    if (typeof note === "number") return note;
    const n = String(note).trim();
    return NOTE_FREQ[n] || NOTE_FREQ[n.toUpperCase()] || 440;
  };
  function tone(freq, dur, when, type) {
    const c = audioCtx();
    if (!c) return;
    const t0 = c.currentTime + (when || 0);
    const osc = c.createOscillator(), gain = c.createGain();
    osc.type = type || "sine";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(0.25, t0 + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + (dur || 0.4));
    osc.connect(gain);
    gain.connect(c.destination);
    osc.start(t0);
    osc.stop(t0 + (dur || 0.4) + 0.05);
  }
  function chime(ok) {
    if (ok) { tone(523.3, 0.16, 0); tone(659.3, 0.16, 0.12); tone(784.0, 0.3, 0.24); }
    else { tone(311.1, 0.18, 0); tone(247.0, 0.22, 0.12); }
  }
  function sfx(name) {
    switch (name) {
      case "pickup": tone(523.3, 0.08, 0, "triangle"); break;
      case "drop": tone(392.0, 0.1, 0, "triangle"); break;
      case "reveal": tone(659.3, 0.12, 0, "sine"); tone(880.0, 0.14, 0.08, "sine"); break;
      case "tick": tone(880.0, 0.05, 0, "square"); break;
      case "win": chime(true); break;
      case "nope": chime(false); break;
      case "pop": tone(740.0, 0.07, 0, "triangle"); break;
      case "bonk": tone(180.0, 0.16, 0, "sawtooth"); tone(140.0, 0.2, 0.08, "sawtooth"); break;
      case "whoosh": tone(620.0, 0.1, 0, "triangle"); tone(420.0, 0.14, 0.06, "triangle"); break;
      case "jump": tone(330.0, 0.08, 0, "square"); tone(520.0, 0.1, 0.06, "square"); break;
      default: tone(523.3, 0.1, 0); break;
    }
  }
  // Play a sequence of notes at a tempo; onNote(i, n) fires as each plays (to light a pad).
  function playSequence(notes, opts = {}) {
    const tempo = opts.tempo || 0.5; // seconds per note
    const dur = opts.dur || tempo * 0.85;
    let t = 0;
    (notes || []).forEach((n, i) => {
      tone(freqOf(n), dur, t, opts.type);
      if (opts.onNote) setTimeout(() => opts.onNote(i, n), t * 1000);
      t += tempo;
    });
    if (opts.onDone) setTimeout(opts.onDone, t * 1000 + 120);
    return t; // total seconds
  }
  GB.audio = { ctx: audioCtx, tone, chime, freqOf, sfx, playSequence, NOTE_FREQ };

  /* ================================ JUICE ================================ */
  // Every effect respects prefers-reduced-motion: motion is skipped but END STATES are
  // always applied by the caller via a class, never via a keyframe alone.
  const COLORS = ["#6b8f71", "#d98a5b", "#f0c419", "#7a9cc6", "#e07a8b"];
  const reduced = () => !!GB.reduceMotion;

  function confetti() {
    if (reduced()) return;
    const host = document.querySelector(".reader") || document.body;
    const layer = h("div", "confetti");
    for (let i = 0; i < 36; i++) {
      const bit = h("i");
      bit.style.left = Math.random() * 100 + "%";
      bit.style.background = COLORS[i % COLORS.length];
      bit.style.animationDelay = Math.random() * 0.25 + "s";
      bit.style.transform = `rotate(${Math.random() * 360}deg)`;
      layer.appendChild(bit);
    }
    host.appendChild(layer);
    setTimeout(() => layer.remove(), 1800);
  }
  function burst(x, y, opts = {}) {
    if (reduced()) return;
    const n = opts.count || 14;
    const colors = opts.colors || COLORS;
    const layer = h("div", "gb-burst");
    for (let i = 0; i < n; i++) {
      const ang = (Math.PI * 2 * i) / n + Math.random() * 0.5;
      const dist = 40 + Math.random() * 60;
      const p = h("i", null, opts.emoji ? esc(opts.emoji) : "");
      if (!opts.emoji) p.style.background = colors[i % colors.length];
      p.style.left = x + "px";
      p.style.top = y + "px";
      p.style.setProperty("--dx", (Math.cos(ang) * dist).toFixed(1) + "px");
      p.style.setProperty("--dy", (Math.sin(ang) * dist).toFixed(1) + "px");
      layer.appendChild(p);
    }
    document.body.appendChild(layer);
    setTimeout(() => layer.remove(), 900);
  }
  function burstAt(node, opts) {
    if (!node || reduced()) return;
    const r = node.getBoundingClientRect();
    burst(r.left + r.width / 2, r.top + r.height / 2, opts);
  }
  const pulseClass = (node, cls, ms) => {
    if (!node || reduced()) return;
    node.classList.remove(cls);
    void node.offsetWidth;
    node.classList.add(cls);
    setTimeout(() => node.classList.remove(cls), ms);
  };
  GB.juice = {
    confetti, burst, burstAt,
    squash: (n) => pulseClass(n, "gb-squash", 400),
    shake: (n) => pulseClass(n, "shake", 450),
    nudge: (n) => pulseClass(n, "gb-nudge", 400),
    flash(node) {
      if (!node) return;
      node.classList.add("lit");
      setTimeout(() => node.classList.remove("lit"), 240);
    },
    haptic(pattern) {
      if (reduced()) return;
      try { if (navigator.vibrate) navigator.vibrate(pattern || 12); } catch (e) {}
    },
  };

  /* ================================ SCENE ================================ */
  // An interactive overlay layered on top of the page illustration, so games play ON the
  // art. Coordinates are NORMALIZED 0..1, origin top-left; a legacy percent value (>1) is
  // auto-converted. Degrades to a plain board when the page has no image.
  const norm = (v) => { v = Number(v) || 0; return v > 1 ? v / 100 : v; };
  const pct = (v) => (norm(v) * 100).toFixed(3) + "%";

  function sceneCreate(body, page) {
    const frame = h("div", "scene-frame");
    const hasImg = !!(page && page.image && page.image.file);
    if (hasImg) {
      const img = document.createElement("img");
      img.src = page.image.file;
      img.alt = (page.image && page.image.alt) || "";
      frame.appendChild(img);
    } else {
      frame.classList.add("scene-board"); // neutral playfield for placeholder builds
    }
    const overlay = h("div", "scene-overlay");
    frame.appendChild(overlay);
    body.appendChild(frame);

    // Touch-target floor: a hotspot is at least ~44px regardless of a small r.
    function sizeStyle(node, r) {
      node.style.width = (norm(r || 0.09) * 100).toFixed(2) + "%";
      node.style.aspectRatio = "1";
      node.style.minWidth = "44px";
      node.style.minHeight = "44px";
    }

    return {
      frame, overlay, hasImage: hasImg,
      toLocal(clientX, clientY) {
        const r = frame.getBoundingClientRect();
        return { x: (clientX - r.left) / r.width, y: (clientY - r.top) / r.height };
      },
      hotspot(o) {
        const spot = h("button", "scene-hotspot");
        if (o.label) spot.setAttribute("aria-label", o.label);
        const p = o.at || o;
        spot.style.left = pct(p.x);
        spot.style.top = pct(p.y);
        sizeStyle(spot, o.r);
        if (o.glow) spot.classList.add("glow");
        spot.onclick = (e) => {
          e.stopPropagation();
          if (spot.classList.contains("got")) return;
          spot.classList.add("got");
          if (o.onHit) o.onHit(spot, e);
        };
        overlay.appendChild(spot);
        return spot;
      },
      placeItem(node, at) {
        node.classList.add("scene-item");
        node.style.left = pct(at.x);
        node.style.top = pct(at.y);
        overlay.appendChild(node);
        return node;
      },
      dropTarget(o) {
        const z = h("div", "scene-target");
        const p = o.at || o;
        z.style.left = pct(p.x);
        z.style.top = pct(p.y);
        sizeStyle(z, o.r);
        if (o.label) z.appendChild(h("span", "scene-target-label", esc(o.label)));
        overlay.appendChild(z);
        return z;
      },
      missTaps(onMiss) {
        frame.addEventListener("click", (e) => {
          if (e.target === frame || e.target === overlay || e.target.tagName === "IMG") onMiss(e);
        });
      },
    };
  }
  GB.scene = { create: sceneCreate, norm };

  /* ================================ DND ================================ */
  // True pointer drag-and-drop with snapping + a mandatory keyboard fallback. Call
  // GB.dnd.create() for an isolated drag field. Keyboard: focus a piece, Enter to pick
  // up, Arrows/Tab to cycle the highlighted target, Enter to drop, Esc to cancel.
  function dndAccepts(zone, node) {
    const a = zone.opts.accepts;
    if (a == null) return true;
    if (typeof a === "function") return !!a(node);
    const g = node.dataset && node.dataset.group;
    const id = node.dataset && node.dataset.id;
    if (Array.isArray(a)) return a.indexOf(g) >= 0 || a.indexOf(id) >= 0;
    return String(a) === String(g) || String(a) === String(id);
  }
  function dndCreate() {
    const zones = [];
    let picked = null;   // keyboard: currently lifted draggable
    let kbTarget = -1;   // keyboard: highlighted zone index

    const clearHighlights = () => zones.forEach((z) => z.node.classList.remove("over", "kb-target"));

    function tryDrop(node, zoneEntry) {
      // onDrop returns true to accept (we relocate + snap), false to reject (nudge).
      const ok = zoneEntry.opts.onDrop ? zoneEntry.opts.onDrop(node, zoneEntry.node) : true;
      if (ok) {
        node.classList.add("placed");
        node.removeAttribute("tabindex");
        if (zoneEntry.opts.relocate !== false) {
          zoneEntry.node.appendChild(node);
          node.style.transform = node.style.left = node.style.top = node.style.position = "";
        }
        node.classList.add("gb-snap");
        setTimeout(() => node.classList.remove("gb-snap"), 350);
        GB.audio.sfx("drop");
        GB.juice.burstAt(node, { count: 8 });
        return true;
      }
      GB.juice.nudge(node);
      GB.audio.sfx("nope");
      return false;
    }

    function zoneAtPoint(node, x, y) {
      for (const z of zones) {
        const r = z.node.getBoundingClientRect();
        if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom && dndAccepts(z, node)) return z;
      }
      return null;
    }

    function draggable(node, opts = {}) {
      node.classList.add("gb-draggable");
      node.style.touchAction = "none";
      if (opts.group != null) node.dataset.group = opts.group;
      if (opts.id != null) node.dataset.id = opts.id;
      node.tabIndex = 0;
      node.setAttribute("role", "button");
      if (opts.label) node.setAttribute("aria-label", opts.label);

      // ---- pointer drag ----
      let dragging = false, startX = 0, startY = 0;
      node.addEventListener("pointerdown", (e) => {
        if (node.classList.contains("placed") && opts.lockPlaced !== false) return;
        dragging = true;
        startX = e.clientX;
        startY = e.clientY;
        node.classList.add("gb-dragging");
        try { node.setPointerCapture(e.pointerId); } catch (err) {}
        GB.audio.sfx("pickup");
        GB.juice.haptic(8);
        e.preventDefault();
      });
      node.addEventListener("pointermove", (e) => {
        if (!dragging) return;
        node.style.transform = `translate(${e.clientX - startX}px,${e.clientY - startY}px)`;
        const z = zoneAtPoint(node, e.clientX, e.clientY);
        clearHighlights();
        if (z) z.node.classList.add("over");
      });
      node.addEventListener("pointerup", (e) => {
        if (!dragging) return;
        dragging = false;
        node.classList.remove("gb-dragging");
        clearHighlights();
        const z = zoneAtPoint(node, e.clientX, e.clientY);
        if (!z || !tryDrop(node, z)) node.style.transform = "";
      });
      node.addEventListener("pointercancel", () => {
        dragging = false;
        node.classList.remove("gb-dragging");
        node.style.transform = "";
        clearHighlights();
      });

      // ---- keyboard fallback ----
      function cycleTarget(dir) {
        if (!zones.length) return;
        let tries = 0;
        do {
          kbTarget = (kbTarget + dir + zones.length) % zones.length;
          tries++;
        } while (!dndAccepts(zones[kbTarget], node) && tries <= zones.length);
        clearHighlights();
        if (zones[kbTarget]) zones[kbTarget].node.classList.add("kb-target");
      }
      function releaseKb() {
        node.classList.remove("gb-picked");
        picked = null;
        kbTarget = -1;
        clearHighlights();
      }
      node.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          if (picked !== node) {
            picked = node;
            kbTarget = -1;
            node.classList.add("gb-picked");
            cycleTarget(1);
          } else if (kbTarget >= 0 && zones[kbTarget]) {
            const z = zones[kbTarget];
            releaseKb();
            tryDrop(node, z);
          }
        } else if (picked === node && (e.key === "ArrowRight" || e.key === "ArrowDown" || e.key === "Tab")) {
          e.preventDefault();
          cycleTarget(1);
        } else if (picked === node && (e.key === "ArrowLeft" || e.key === "ArrowUp")) {
          e.preventDefault();
          cycleTarget(-1);
        } else if (e.key === "Escape") {
          releaseKb();
        }
      });
      return node;
    }

    function dropzone(node, opts) {
      node.classList.add("gb-dropzone");
      zones.push({ node, opts: opts || {} });
      return node;
    }

    return { draggable, dropzone, zones };
  }
  GB.dnd = { create: dndCreate };

  /* ================================ UI KIT ================================ */
  // Shared builders so individual games stay tiny. All of them are always winnable.
  const ui = {};

  // Progressive hint ladder. Each press reveals the next hint; after the last hint a gentle
  // "Show me" appears that calls onSolve() — the always-winnable backstop, never a dead end.
  ui.hintLadder = function (body, hints, onSolve) {
    hints = (hints || []).filter(Boolean);
    if (!hints.length && !onSolve) return;
    let i = 0;
    const panel = h("div", "hint");
    panel.hidden = true;
    const btn = h("button", "btn ghost hint-btn", "💡 Hint");
    btn.onclick = () => {
      if (i < hints.length) {
        panel.hidden = false;
        panel.textContent = hints[i];
        i++;
        if (i >= hints.length && onSolve) btn.textContent = "✨ Show me";
        else if (i >= hints.length) btn.disabled = true;
      } else if (onSolve) {
        onSolve();
      }
    };
    body.appendChild(btn);
    body.appendChild(panel);
  };

  // Opt-in winnable guard: after maxTries gentle fails, offer the auto-solve.
  ui.guaranteeWinnable = function (ctx, opts = {}) {
    const max = opts.maxTries || 4;
    let tries = 0, offered = false;
    return {
      fail(msg) {
        ctx.nope(msg);
        tries++;
        if (tries >= max && !offered && opts.solve) {
          offered = true;
          const b = h("button", "btn ghost", "✨ Show me");
          b.onclick = () => opts.solve();
          ctx.body.appendChild(b);
        }
      },
    };
  };

  // A row of answer buttons; the right one wins, wrong ones nope + reset.
  ui.answerRow = function (ctx, options, answer, { big } = {}) {
    const wrap = h("div", "options");
    shuffle(options).forEach((o) => {
      const b = h("button", "opt" + (big ? " big" : ""), esc(o));
      b.onclick = () => {
        if (String(o) === String(answer)) {
          b.classList.add("correct");
          ctx.win();
        } else {
          b.classList.add("wrong");
          ctx.nope();
          setTimeout(() => b.classList.remove("wrong"), 600);
        }
      };
      wrap.appendChild(b);
    });
    ctx.body.appendChild(wrap);
    return wrap;
  };

  // Quiz (one correct answer among options) — shared by rhyme/riddle/comprehension/pattern.
  ui.quiz = function (ctx) {
    const { data, it } = ctx;
    const answer = it.type === "comprehension-question" ? (data.options || [])[data.answer_index] : data.answer;
    const opts = data.options || (data.distractors ? [data.answer, ...data.distractors] : [data.answer]);
    if (it.type === "rhyme-complete" && data.sentence)
      ctx.body.appendChild(h("p", "game-line", esc(data.sentence.replace("___", "______"))));
    if (data.question && ["riddle", "comprehension-question", "quiz"].includes(it.type))
      ctx.body.appendChild(h("p", "game-line", esc(data.question)));
    ui.answerRow(ctx, opts, answer);
    ctx.hint(data.hint);
  };

  // Connect-the-pairs matcher (click left, then right).
  ui.matchGame = function (ctx, line) {
    const pairs = ctx.data.pairs || [];
    ctx.body.appendChild(h("p", "game-line", line));
    const grid = h("div", "match-grid");
    const lefts = h("div", "match-col"), rights = h("div", "match-col");
    let selL = null, done = 0;
    pairs.forEach((pr, i) => {
      const a = h("button", "match-cell", esc(pr[0]));
      a.dataset.k = i;
      a.onclick = () => {
        if (a.classList.contains("matched")) return;
        lefts.querySelectorAll(".sel").forEach((x) => x.classList.remove("sel"));
        a.classList.add("sel");
        selL = a;
      };
      lefts.appendChild(a);
    });
    shuffle(pairs.map((pr, i) => ({ v: pr[1], k: i }))).forEach((r) => {
      const b = h("button", "match-cell", esc(r.v));
      b.dataset.k = r.k;
      b.onclick = () => {
        if (b.classList.contains("matched") || !selL) return;
        if (selL.dataset.k === b.dataset.k) {
          selL.classList.add("matched");
          b.classList.add("matched");
          selL.classList.remove("sel");
          selL = null;
          if (++done === pairs.length) ctx.win();
        } else {
          b.classList.add("wrong");
          ctx.nope();
          setTimeout(() => b.classList.remove("wrong"), 500);
        }
      };
      rights.appendChild(b);
    });
    grid.appendChild(lefts);
    grid.appendChild(rights);
    ctx.body.appendChild(grid);
  };

  // Put-in-order (up/down arrows — also the accessible fallback for drag-order).
  ui.orderGame = function (ctx) {
    const correct = ctx.data.sequence || [];
    let cur = shuffle(correct);
    if (correct.length > 1 && cur.join("|") === correct.join("|")) cur = shuffle(correct);
    ctx.body.appendChild(h("p", "game-line", "Put these in the right order:"));
    const list = h("div", "order-list");
    function paint() {
      list.innerHTML = "";
      cur.forEach((item, i) => {
        const row = h("div", "order-row");
        row.appendChild(h("span", "order-text", esc(item)));
        const btns = h("div", "order-btns");
        const up = h("button", "order-arrow", "↑");
        up.disabled = i === 0;
        up.onclick = () => { [cur[i - 1], cur[i]] = [cur[i], cur[i - 1]]; paint(); };
        const dn = h("button", "order-arrow", "↓");
        dn.disabled = i === cur.length - 1;
        dn.onclick = () => { [cur[i + 1], cur[i]] = [cur[i], cur[i + 1]]; paint(); };
        btns.appendChild(up);
        btns.appendChild(dn);
        row.appendChild(btns);
        list.appendChild(row);
      });
    }
    paint();
    const check = h("button", "btn", "Check my order");
    check.onclick = () => (cur.join("|") === correct.join("|") ? ctx.win() : ctx.nope("Not quite — keep arranging!"));
    ctx.body.appendChild(list);
    ctx.body.appendChild(check);
  };

  // Memory card-match (flip two cards, find the pair).
  ui.memoryGame = function (ctx) {
    const pairs = ctx.data.pairs || [];
    ctx.body.appendChild(h("p", "game-line", "Flip two cards to find a matching pair:"));
    const cards = [];
    pairs.forEach((pr, i) => { cards.push({ pid: i, face: pr[0] }); cards.push({ pid: i, face: pr[1] }); });
    const grid = h("div", "card-grid");
    let first = null, lock = false, matched = 0;
    shuffle(cards).forEach((c) => {
      const card = h("button", "flip-card",
        `<span class="fc-front">❔</span><span class="fc-back">${esc(c.face)}</span>`);
      card.dataset.pid = c.pid;
      card.onclick = () => {
        if (lock || card.classList.contains("flipped") || card.classList.contains("matched")) return;
        card.classList.add("flipped");
        if (!first) { first = card; return; }
        if (first.dataset.pid === card.dataset.pid) {
          first.classList.add("matched");
          card.classList.add("matched");
          first = null;
          if (++matched === pairs.length) ctx.win();
        } else {
          lock = true;
          const a = first, b = card;
          first = null;
          setTimeout(() => { a.classList.remove("flipped"); b.classList.remove("flipped"); lock = false; }, 850);
        }
      };
      grid.appendChild(card);
    });
    ctx.body.appendChild(grid);
  };
  GB.ui = ui;

  /* ================================ STEPS ================================ */
  // Multi-beat sequencer: an interaction with `steps:[…]` plays each sub-game in turn; the
  // parent win() fires only after the last beat. Each beat is itself always winnable.
  GB.steps = {
    run(parentCtx, steps) {
      steps = (steps || []).filter(Boolean);
      if (!steps.length) return parentCtx.win();
      const body = parentCtx.body;

      const dots = h("div", "steps-progress");
      steps.forEach(() => dots.appendChild(h("span", "step-dot")));
      body.appendChild(dots);
      const stage = h("div", "step-beat");
      body.appendChild(stage);

      let i = 0;
      function paintDots() {
        dots.querySelectorAll(".step-dot").forEach((d, k) => {
          d.classList.toggle("done", k < i);
          d.classList.toggle("now", k === i);
        });
      }
      function renderStep() {
        paintDots();
        stage.classList.remove("step-in");
        void stage.offsetWidth;
        stage.classList.add("step-in");
        stage.innerHTML = "";
        const step = steps[i];
        if (step.prompt) stage.appendChild(h("p", "game-line step-prompt", esc(step.prompt)));
        const sub = h("div", "step-body");
        stage.appendChild(sub);
        const subCtx = Object.assign({}, parentCtx, {
          body: sub,
          data: step.data || {},
          it: step,
          win() {
            i++;
            if (i >= steps.length) parentCtx.win();
            else { GB.audio.sfx("reveal"); renderStep(); }
          },
          hint(hints, onSolve) { ui.hintLadder(sub, Array.isArray(hints) ? hints : hints ? [hints] : [], onSolve); },
        });
        GB.def(step.type).render(subCtx);
      }
      renderStep();
    },
  };

  /* ================================ REWARDS ================================ */
  // Cross-page collectible arc: each solved game drops a sticker into a corner tray; the
  // last page shows the collection (with outlined placeholders for skipped games).
  // sessionStorage so a fresh visit starts fresh; all storage guarded (private mode safe).
  const mem = {}; // in-memory fallback when storage is unavailable
  const keyFor = (story) => "gb:rewards:" + ((story && (story.slug || story.title)) || "book");
  function loadState(story) {
    const k = keyFor(story);
    try {
      const raw = sessionStorage.getItem(k);
      if (raw) return JSON.parse(raw);
    } catch (e) {}
    return mem[k] || { earned: {} };
  }
  function saveState(story, state) {
    const k = keyFor(story);
    mem[k] = state;
    try { sessionStorage.setItem(k, JSON.stringify(state)); } catch (e) {}
  }
  // Sticker emoji: author's reward.emoji, else the game's registry icon.
  const iconFor = (it) => (it.reward && it.reward.emoji) || (GB.def(it.type) || {}).icon || "⭐";
  const pagesWithGames = (story) => ((story && story.pages) || []).filter((p) => p.interaction);

  function updateTray(story, pop) {
    const host = document.getElementById("stage") || document.body;
    const state = loadState(story);
    const count = Object.keys(state.earned).length;
    const total = pagesWithGames(story).length;
    let tray = host.querySelector(".reward-tray");
    if (!tray) {
      tray = h("div", "reward-tray");
      tray.setAttribute("aria-live", "polite");
      tray.setAttribute("aria-label", "Sticker collection");
      host.appendChild(tray);
    }
    tray.innerHTML = "";
    tray.appendChild(h("span", "reward-star", "⭐"));
    tray.appendChild(h("span", "reward-count", `${count}/${total}`));
    if (pop && !GB.reduceMotion) {
      tray.classList.remove("pop");
      void tray.offsetWidth;
      tray.classList.add("pop");
    }
  }

  GB.reward = {
    iconFor,
    // Called by the shell's win() — records a sticker for this page (idempotent).
    earnFor(story, it, page) {
      const state = loadState(story);
      const id = (it.reward && it.reward.id) || "p" + (page && page.number);
      if (!state.earned[id]) {
        state.earned[id] = {
          icon: iconFor(it),
          label: (it.reward && it.reward.label) || it.prompt || "Sticker",
          page: page && page.number,
        };
        saveState(story, state);
      }
      updateTray(story, true);
    },
    // Called by render() on each page — mounts/refreshes the corner tray.
    onPage(story) { if (pagesWithGames(story).length) updateTray(story); },
    // The end-of-book collection grid.
    renderCollection(container, story) {
      if (!container) return;
      const existing = container.querySelector(".reward-collection");
      if (existing) existing.remove();
      const state = loadState(story);
      const wrap = h("div", "reward-collection");
      wrap.appendChild(h("h3", "reward-title", "Look what you found! 🌟"));
      const grid = h("div", "reward-grid");
      pagesWithGames(story).forEach((p) => {
        const it = p.interaction;
        const got = state.earned[(it.reward && it.reward.id) || "p" + p.number];
        const badge = h("div", "reward-badge" + (got ? "" : " empty"));
        badge.appendChild(h("span", "reward-emoji", got ? esc(got.icon) : "·"));
        badge.appendChild(h("span", "reward-label", esc(got ? got.label : "Keep playing!")));
        grid.appendChild(badge);
      });
      wrap.appendChild(grid);
      container.appendChild(wrap);
      if (!GB.reduceMotion) wrap.classList.add("pop");
    },
  };
})();
