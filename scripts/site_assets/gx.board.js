/* gx.board — the board-game library: quizzes, on-the-art play, true drag-and-drop, drawing,
   spatial puzzles, word play, music/rhythm, memory, and the declarative `custom` DSL.
   Each game registers with GB.define(type, {icon, render}) and receives the shell ctx
   (see reader.js). Every game is always winnable; on-art games degrade to a tap/chip
   fallback when a page has no illustration (placeholder builds). */
(function () {
  "use strict";
  const GB = window.GB;
  const h = GB.h, esc = GB.esc, shuffle = GB.shuffle, label = GB.label, coord = GB.coord;
  const def = GB.define;
  const line = (ctx, text) => ctx.body.appendChild(h("p", "game-line", text));

  def("_default", { icon: "🎲", render(ctx) {
    const b = h("button", "btn", "I did it!");
    b.onclick = ctx.win;
    ctx.body.appendChild(b);
  } });

  /* ============================ QUIZ FAMILY ============================ */
  def("rhyme-complete", { icon: "🎤", render: (ctx) => GB.ui.quiz(ctx) });
  def("comprehension-question", { icon: "❓", render: (ctx) => GB.ui.quiz(ctx) });
  def("riddle", { icon: "🤔", render: (ctx) => GB.ui.quiz(ctx) });

  def("odd-one-out", { icon: "🧐", render(ctx) {
    line(ctx, "Tap the one that doesn't belong:");
    GB.ui.answerRow(ctx, ctx.data.items || [], ctx.data.answer);
    ctx.hint(ctx.data.hint);
  } });

  def("pattern", { icon: "🔁", render(ctx) {
    const data = ctx.data;
    const strip = h("div", "pattern-strip");
    (data.sequence || []).forEach((s) => strip.appendChild(h("span", "pat-cell", esc(s))));
    strip.appendChild(h("span", "pat-cell pat-q", "?"));
    ctx.body.appendChild(strip);
    line(ctx, "What comes next?");
    const opts = data.options || (data.distractors ? [data.answer, ...data.distractors] : [data.answer]);
    const wrap = GB.ui.answerRow(ctx, opts, data.answer);
    wrap.addEventListener("click", (e) => {
      if (e.target.classList && e.target.classList.contains("correct")) {
        const q = strip.querySelector(".pat-q");
        if (q) { q.textContent = e.target.textContent; q.classList.remove("pat-q"); }
      }
    });
    ctx.hint(data.hint);
  } });

  def("counting", { icon: "🔢", render(ctx) {
    line(ctx, `How many ${esc(ctx.data.what || "things")}?`);
    const row = h("div", "count-row");
    const input = h("input", "num-input");
    input.type = "number";
    input.inputMode = "numeric";
    input.min = "0";
    const b = h("button", "btn", "Check");
    const check = () => (Number(input.value) === Number(ctx.data.answer) ? ctx.win() : ctx.nope());
    b.onclick = check;
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") check(); });
    row.appendChild(input);
    row.appendChild(b);
    ctx.body.appendChild(row);
  } });

  def("choice", { icon: "🔀", render(ctx) {
    const wrap = h("div", "options");
    (ctx.data.options || []).forEach((o) => {
      const b = h("button", "opt big", esc(o.label));
      b.onclick = () => ctx.goto(o.goto);
      wrap.appendChild(b);
    });
    ctx.body.appendChild(wrap);
  } });

  /* ============================ FIND / ATTENTION ============================ */
  def("seek-and-find", { icon: "🔍", render(ctx) {
    const items = ctx.data.items || [];
    const wrap = h("div", "chip-row");
    items.forEach((item) => {
      const c = h("button", "find-item", "🔍 " + esc(label(item)));
      c.onclick = () => {
        c.classList.toggle("found");
        if (wrap.querySelectorAll(".found").length === items.length) ctx.win();
      };
      wrap.appendChild(c);
    });
    ctx.body.appendChild(wrap);
  } });

  def("sound-hunt", { icon: "🔊", render(ctx) {
    const data = ctx.data;
    const targets = new Set((data.words || []).map((w) => String(w).toLowerCase()));
    line(ctx, `Find the words with the /${esc(data.sound || "")}/ sound:`);
    const wrap = h("div", "chip-row");
    shuffle([...(data.words || []), ...(data.decoys || [])]).forEach((w) => {
      const c = h("button", "hunt-word", esc(w));
      c.onclick = () => {
        if (c.classList.contains("found") || c.classList.contains("wrong")) return;
        if (targets.has(String(w).toLowerCase())) {
          c.classList.add("found");
          if (wrap.querySelectorAll(".found").length === targets.size) ctx.win();
        } else {
          c.classList.add("wrong");
          ctx.nope();
          setTimeout(() => c.classList.remove("wrong"), 600);
        }
      };
      wrap.appendChild(c);
    });
    ctx.body.appendChild(wrap);
  } });

  def("spot-the-difference", { icon: "🔬", render(ctx) {
    const { data, page } = ctx;
    const spots = data.spots || [];
    line(ctx, `Find all ${esc(data.count || spots.length)} differences — tap them!`);
    if (spots.length && page && page.image && page.image.file) {
      const frame = h("div", "spot-frame");
      const img = document.createElement("img");
      img.src = page.image.file;
      img.alt = "";
      frame.appendChild(img);
      let found = 0;
      spots.forEach((s) => {
        const spot = h("button", "spot");
        spot.style.left = (s.x || 0) + "%";   // spot-the-difference is legacy-percent
        spot.style.top = (s.y || 0) + "%";
        if (s.r) spot.style.width = spot.style.height = s.r + "%";
        spot.onclick = () => {
          if (spot.classList.contains("got")) return;
          spot.classList.add("got");
          if (++found >= spots.length) ctx.win();
        };
        frame.appendChild(spot);
      });
      frame.addEventListener("click", (e) => { if (e.target === frame || e.target === img) ctx.nope("Look closely!"); });
      ctx.body.appendChild(frame);
    } else {
      const b = h("button", "btn", "I found them all!");
      b.onclick = ctx.win;
      ctx.body.appendChild(b);
    }
  } });

  /* ============================ ON THE ART (GB.scene) ============================ */
  // Find every named thing hidden in the illustration by tapping its spot.
  def("hidden-object", { icon: "🔎", render(ctx) {
    const items = ctx.data.items || [];
    line(ctx, "Find them all — tap them in the picture!");
    const list = h("div", "chip-row");
    const chips = items.map((it) => {
      const c = h("span", "find-item", "🔍 " + esc(label(it)));
      list.appendChild(c);
      return c;
    });
    ctx.body.appendChild(list);
    const scene = ctx.scene.create(ctx.body, ctx.page);
    if (!scene.hasImage) { // fallback: tap the chips
      let found = 0;
      chips.forEach((c) => {
        c.style.cursor = "pointer";
        c.onclick = () => {
          if (c.classList.contains("found")) return;
          c.classList.add("found");
          if (++found >= items.length) ctx.win();
        };
      });
      return;
    }
    let found = 0;
    items.forEach((it, i) => {
      scene.hotspot({ at: coord(it), r: it.r, label: label(it), onHit(spot) {
        chips[i].classList.add("found");
        GB.juice.burstAt(spot, { count: 8 });
        GB.audio.sfx("reveal");
        if (++found >= items.length) ctx.win();
      } });
    });
    (ctx.data.decoys || []).forEach((d) => {
      scene.hotspot({ at: coord(d), r: d.r, onHit: () => ctx.nope("Not there — keep looking!") });
    });
    scene.missTaps(() => ctx.nope("Look closely!"));
  } });

  // Find things one at a time (the caption calls out the next target).
  def("find-in-scene", { icon: "🔎", render(ctx) {
    const items = ctx.data.items || [];
    const caption = h("p", "game-line", "");
    ctx.body.appendChild(caption);
    const scene = ctx.scene.create(ctx.body, ctx.page);
    let i = 0;
    const ask = () => {
      if (i >= items.length) return ctx.win();
      caption.textContent = `Find: ${label(items[i])} 🔍`;
    };
    if (!scene.hasImage) {
      const row = h("div", "chip-row");
      shuffle(items).forEach((it) => {
        const b = h("button", "find-item", "🔍 " + esc(label(it)));
        b.onclick = () => {
          if (label(it) === label(items[i])) { b.classList.add("found"); i++; ask(); }
          else ctx.nope("That's not it yet!");
        };
        row.appendChild(b);
      });
      ctx.body.appendChild(row);
      return ask();
    }
    items.forEach((it, n) => {
      scene.hotspot({ at: coord(it), r: it.r, label: label(it), onHit(spot) {
        if (n === i) { GB.juice.burstAt(spot); i++; ask(); }
        else { spot.classList.remove("got"); ctx.nope(`Find ${label(items[i])} first!`); }
      } });
    });
    ask();
  } });

  // Tap the one right thing on the picture.
  def("tap-on-art", { icon: "👆", render(ctx) {
    const data = ctx.data;
    line(ctx, data.hint || "Tap it in the picture!");
    const scene = ctx.scene.create(ctx.body, ctx.page);
    if (!scene.hasImage || !data.target) {
      const b = h("button", "btn", "👆 " + esc(label(data.target) || "Tap!"));
      b.onclick = ctx.win;
      ctx.body.appendChild(b);
      return;
    }
    scene.hotspot({ at: coord(data.target), r: data.target.r, label: label(data.target), onHit(spot) {
      GB.juice.burstAt(spot);
      ctx.win();
    } });
    scene.missTaps(() => ctx.nope("Not quite — try again!"));
  } });

  // Tap glowing hotspots to reveal a caption for each (exploration, no fail).
  def("hotspot-reveal", { icon: "✨", render(ctx) {
    const spots = ctx.data.hotspots || [];
    line(ctx, "Tap the sparkles to discover what's hiding!");
    const scene = ctx.scene.create(ctx.body, ctx.page);
    const caption = h("div", "reveal-caption");
    ctx.body.appendChild(caption);
    let seen = 0;
    const reveal = (s) => {
      caption.textContent = (s.icon ? s.icon + " " : "") + (s.reveal || "");
      GB.audio.sfx("reveal");
      if (++seen >= spots.length) ctx.win();
    };
    if (!scene.hasImage) {
      const row = h("div", "chip-row");
      spots.forEach((s) => {
        const b = h("button", "opt", esc(s.icon || "✨"));
        b.onclick = () => { b.classList.add("correct"); reveal(s); };
        row.appendChild(b);
      });
      ctx.body.appendChild(row);
      return;
    }
    spots.forEach((s) => scene.hotspot({ at: coord(s), r: s.r, glow: true, label: s.reveal, onHit: () => reveal(s) }));
  } });

  // Drag items onto the right spots ON the art.
  def("place-on-scene", { icon: "📍", render(ctx) {
    const items = ctx.data.items || [], slots = ctx.data.slots || [];
    line(ctx, "Drag each thing where it belongs!");
    const field = ctx.dnd.create();
    const scene = ctx.scene.create(ctx.body, ctx.page);
    if (!scene.hasImage) {
      return binsFallback(ctx,
        items.map((it) => ({ label: label(it), bin: it.accepts || it.slot })),
        slots.map((s) => ({ label: s.label, key: s.accepts || s.label })));
    }
    let placed = 0;
    slots.forEach((s) => {
      const z = scene.dropTarget({ at: coord(s), r: s.r, label: s.label });
      field.dropzone(z, { accepts: s.accepts || s.label, onDrop() { if (++placed >= items.length) ctx.win(); return true; } });
    });
    const tray = h("div", "chip-row");
    ctx.body.appendChild(tray);
    shuffle(items).forEach((it) => {
      const chip = h("button", "gb-chip", (it.icon ? it.icon + " " : "") + esc(label(it)));
      field.draggable(chip, { id: label(it), group: it.accepts || it.slot, label: label(it) });
      tray.appendChild(chip);
    });
  } });

  /* ============================ DRAG-AND-DROP SUITE ============================ */
  // Shared fallback when pointer DnD / scene isn't available: tap-select into bins.
  function binsFallback(ctx, items, bins) {
    GB.def("sorting").render(Object.assign({}, ctx, { data: { items, bins } }));
  }

  def("sorting", { icon: "🧺", render(ctx) {
    const items = shuffle((ctx.data.items || []).map((x, i) => ({ label: label(x), bin: x.bin, id: i })));
    const bins = ctx.data.bins || [];
    line(ctx, "Tap an item, then tap where it belongs:");
    const tray = h("div", "chip-row sort-tray");
    const binRow = h("div", "bin-row");
    let selected = null, placed = 0;
    items.forEach((it) => {
      const c = h("button", "sort-item", esc(it.label));
      c.onclick = () => {
        tray.querySelectorAll(".sel").forEach((x) => x.classList.remove("sel"));
        c.classList.add("sel");
        selected = { it, c };
      };
      tray.appendChild(c);
    });
    bins.forEach((bn, bi) => {
      const name = label(bn);
      const key = bn.key != null ? bn.key : name;
      const bin = h("div", "bin");
      bin.appendChild(h("div", "bin-label", esc(name)));
      const slot = h("div", "bin-slot");
      bin.appendChild(slot);
      bin.onclick = () => {
        if (!selected) return;
        const want = String(selected.it.bin);
        if (want === String(key) || want === String(bi) || want === String(name)) {
          slot.appendChild(h("span", "chip placed", esc(selected.it.label)));
          selected.c.remove();
          selected = null;
          if (++placed === items.length) ctx.win();
        } else {
          ctx.nope("Not that bucket — try another!");
        }
      };
      binRow.appendChild(bin);
    });
    ctx.body.appendChild(tray);
    ctx.body.appendChild(binRow);
  } });

  def("drag-sort", { icon: "🧺", render(ctx) {
    const items = (ctx.data.items || []).map((x) => ({ label: label(x), bin: x.bin }));
    const bins = (ctx.data.bins || []).map((b) => ({ label: label(b), key: b.key != null ? b.key : label(b) }));
    line(ctx, "Drag each one into its basket!");
    const field = ctx.dnd.create();
    const binRow = h("div", "bin-row");
    ctx.body.appendChild(binRow);
    let placed = 0;
    bins.forEach((b) => {
      const bin = h("div", "bin");
      bin.appendChild(h("div", "bin-label", esc(b.label)));
      const slot = h("div", "bin-slot");
      bin.appendChild(slot);
      field.dropzone(slot, { accepts: String(b.key), onDrop() { if (++placed >= items.length) ctx.win(); return true; } });
      binRow.appendChild(bin);
    });
    const tray = h("div", "chip-row");
    ctx.body.appendChild(tray);
    shuffle(items).forEach((it) => {
      const chip = h("button", "gb-chip", esc(it.label));
      field.draggable(chip, { id: it.label, group: String(it.bin), label: it.label });
      tray.appendChild(chip);
    });
  } });

  def("drag-match", { icon: "🔗", render(ctx) {
    const pairs = ctx.data.pairs || [];
    line(ctx, "Drag each one to its match!");
    const field = ctx.dnd.create();
    const grid = h("div", "match-grid");
    const lefts = h("div", "match-col chip-row"), rights = h("div", "match-col");
    let matched = 0;
    pairs.forEach((pr, i) => {
      const z = h("div", "bin");
      z.appendChild(h("div", "bin-label", esc(pr[1])));
      const slot = h("div", "bin-slot");
      z.appendChild(slot);
      field.dropzone(slot, { accepts: "p" + i, onDrop() { if (++matched >= pairs.length) ctx.win(); return true; } });
      rights.appendChild(z);
    });
    shuffle(pairs.map((pr, i) => ({ v: pr[0], k: i }))).forEach((o) => {
      const chip = h("button", "gb-chip", esc(o.v));
      field.draggable(chip, { id: o.v, group: "p" + o.k, label: o.v });
      lefts.appendChild(chip);
    });
    grid.appendChild(lefts);
    grid.appendChild(rights);
    ctx.body.appendChild(grid);
  } });

  def("word-match", { icon: "🔗", render: (ctx) => GB.ui.matchGame(ctx, "Match each one to its pair:") });

  // Jigsaw: drag scrambled pieces of the page art into their slots.
  def("jigsaw", { icon: "🧩", render(ctx) {
    const rows = ctx.data.rows || 2, cols = ctx.data.cols || 3;
    const img = ctx.page && ctx.page.image && ctx.page.image.file;
    line(ctx, "Put the picture back together!");
    const field = ctx.dnd.create();
    const board = h("div", "jigsaw-board");
    board.style.gridTemplateColumns = `repeat(${cols},1fr)`;
    const N = rows * cols;
    for (let i = 0; i < N; i++) {
      const s = h("div", "jigsaw-slot");
      s.dataset.idx = i;
      field.dropzone(s, { accepts: "j" + i, onDrop() {
        if (board.querySelectorAll(".jigsaw-piece.placed").length >= N) ctx.win();
        return true;
      } });
      board.appendChild(s);
    }
    ctx.body.appendChild(board);
    const tray = h("div", "jigsaw-tray");
    ctx.body.appendChild(tray);
    shuffle(Array.from({ length: N }, (_, i) => i)).forEach((i) => {
      const r = Math.floor(i / cols), c = i % cols;
      const piece = h("button", "jigsaw-piece");
      if (img) {
        piece.style.backgroundImage = `url(${img})`;
        piece.style.backgroundSize = `${cols * 100}% ${rows * 100}%`;
        piece.style.backgroundPosition =
          `${cols > 1 ? (c * 100) / (cols - 1) : 0}% ${rows > 1 ? (r * 100) / (rows - 1) : 0}%`;
      } else {
        piece.textContent = i + 1;
      }
      field.draggable(piece, { id: "j" + i, group: "j" + i, label: "piece " + (i + 1) });
      tray.appendChild(piece);
    });
  } });

  // Dress up / build: drag parts onto the figure's zones (free-play, always wins).
  def("dress-up", { icon: "👒", render(ctx) {
    const parts = ctx.data.parts || [], zones = ctx.data.zones || [];
    line(ctx, "Dress up your character — drag the bits on!");
    const field = ctx.dnd.create();
    const fig = h("div", "dressup-figure", esc(ctx.data.base || "🧍"));
    let placed = 0;
    zones.forEach((z) => {
      const d = h("div", "dressup-zone");
      d.style.left = GB.scene.norm(coord(z).x) * 100 + "%";
      d.style.top = GB.scene.norm(coord(z).y) * 100 + "%";
      d.dataset.zone = z.label;
      field.dropzone(d, { accepts: z.label, onDrop(node) {
        d.textContent = node.textContent;
        if (++placed >= Math.min(parts.length, zones.length)) ctx.win();
        return true;
      } });
      fig.appendChild(d);
    });
    ctx.body.appendChild(fig);
    const tray = h("div", "chip-row");
    ctx.body.appendChild(tray);
    shuffle(parts).forEach((p) => {
      const chip = h("button", "gb-chip", (p.icon ? p.icon + " " : "") + esc(p.label));
      field.draggable(chip, { id: p.label, group: p.zone, label: p.label });
      tray.appendChild(chip);
    });
    const done = h("button", "btn ghost", "Looks great!");
    done.onclick = ctx.win;
    ctx.body.appendChild(done);
  } });

  // Feed the creature: drag the GOOD things into its mouth; bad things bounce back.
  def("feed-the-thing", { icon: "🍪", render(ctx) {
    const good = (ctx.data.good || []).map(String), bad = (ctx.data.bad || []).map(String);
    line(ctx, "Feed it only the yummy things!");
    const field = ctx.dnd.create();
    const mouth = h("div", "feed-mouth", esc(ctx.data.target_icon || "😋"));
    let fed = 0;
    field.dropzone(mouth, {
      accepts: (n) => n.dataset.group === "good",
      onDrop(n) { n.remove(); if (++fed >= good.length) ctx.win(); return true; },
    });
    ctx.body.appendChild(mouth);
    const tray = h("div", "chip-row");
    ctx.body.appendChild(tray);
    shuffle([
      ...good.map((g) => ({ v: g, ok: true })),
      ...bad.map((b) => ({ v: b, ok: false })),
    ]).forEach((o) => {
      const chip = h("button", "gb-chip", esc(o.v));
      field.draggable(chip, { id: o.v, group: o.ok ? "good" : "bad", label: o.v });
      tray.appendChild(chip);
    });
  } });

  def("drag-order", { icon: "📋", render: (ctx) => GB.ui.orderGame(ctx) });
  def("memory", { icon: "🃏", render: (ctx) => (ctx.data.pairs ? GB.ui.memoryGame(ctx) : GB.ui.orderGame(ctx)) });

  def("tap-to-reveal", { icon: "🎴", render(ctx) {
    const cards = ctx.data.cards || (ctx.data.items || []).map((x) => ({ front: "?", back: x }));
    const grid = h("div", "card-grid");
    let revealed = 0;
    cards.forEach((c) => {
      const card = h("button", "flip-card",
        `<span class="fc-front">${esc(c.front || "❔")}</span><span class="fc-back">${esc(c.back != null ? c.back : c)}</span>`);
      card.onclick = () => {
        if (card.classList.contains("flipped")) return;
        card.classList.add("flipped");
        if (++revealed >= cards.length) ctx.win();
      };
      grid.appendChild(card);
    });
    ctx.body.appendChild(grid);
  } });

  /* ============================ DRAW / REVEAL (canvas) ============================ */
  // Shared finger-paint canvas: calls onInk(totalDistance) as the child draws.
  function paintCanvas(w, hgt, { lineWidth = 14, color = "#6b8f71", erase = false }, onInk) {
    const cv = document.createElement("canvas");
    cv.width = w;
    cv.height = hgt;
    const g = cv.getContext("2d");
    if (erase) {
      g.fillStyle = "#c9bfa8";
      g.fillRect(0, 0, w, hgt);
      g.globalCompositeOperation = "destination-out";
    } else {
      g.strokeStyle = color;
    }
    g.lineWidth = lineWidth;
    g.lineCap = g.lineJoin = "round";
    let drawing = false, last = null, inked = 0;
    const pos = (e) => {
      const r = cv.getBoundingClientRect();
      const t = e.touches ? e.touches[0] : e;
      return { x: ((t.clientX - r.left) * cv.width) / r.width, y: ((t.clientY - r.top) * cv.height) / r.height };
    };
    const start = (e) => { drawing = true; last = pos(e); e.preventDefault(); };
    const move = (e) => {
      if (!drawing) return;
      const p = pos(e);
      g.beginPath();
      g.moveTo(last.x, last.y);
      g.lineTo(p.x, p.y);
      g.stroke();
      inked += Math.hypot(p.x - last.x, p.y - last.y);
      last = p;
      e.preventDefault();
      onInk(inked, cv);
    };
    const end = () => { drawing = false; };
    cv.addEventListener("mousedown", start);
    cv.addEventListener("mousemove", move);
    window.addEventListener("mouseup", end);
    cv.addEventListener("touchstart", start, { passive: false });
    cv.addEventListener("touchmove", move, { passive: false });
    cv.addEventListener("touchend", end);
    return cv;
  }

  def("trace-letter", { icon: "✍️", render(ctx) {
    line(ctx, `Trace the letter — as in ${esc(ctx.data.word || "")}:`);
    const wrap = h("div", "trace-wrap");
    wrap.appendChild(h("div", "trace-ghost", esc(ctx.data.letter || "?")));
    let done = false;
    const cv = paintCanvas(280, 280, {}, (inked) => { if (!done && inked > 600) { done = true; ctx.win(); } });
    cv.className = "trace-canvas";
    wrap.appendChild(cv);
    ctx.body.appendChild(wrap);
  } });

  def("scratch-reveal", { icon: "🪙", render(ctx) {
    line(ctx, "Scratch to see what's hidden!");
    const wrap = h("div", "scratch-wrap");
    wrap.appendChild(h("div", "scratch-under", esc(ctx.data.reveal || "🎁")));
    const threshold = ((ctx.data.threshold || 0.5) * 300 * 180) / 1200;
    let done = false;
    const cv = paintCanvas(300, 180, { erase: true, lineWidth: 34 }, (inked, canvas) => {
      if (!done && inked > threshold) { done = true; canvas.classList.add("done"); ctx.win(); }
    });
    cv.className = "scratch-canvas";
    wrap.appendChild(cv);
    ctx.body.appendChild(wrap);
  } });

  // Connect the dots in order to reveal a hidden line drawing.
  def("connect-dots", { icon: "🐾", render(ctx) {
    const data = ctx.data;
    const dots = (data.dots || []).slice().sort((a, b) => (a.n || 0) - (b.n || 0));
    line(ctx, "Connect the dots " + (data.order === "letter" ? "A, B, C…" : "1, 2, 3…"));
    const wrap = h("div", "dots-wrap");
    const img = ctx.page && ctx.page.image && ctx.page.image.file;
    if (img) {
      const bg = document.createElement("img");
      bg.src = img;
      bg.className = "dots-bg";
      bg.alt = "";
      wrap.appendChild(bg);
    }
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 100 100");
    svg.setAttribute("class", "dots-svg");
    svg.setAttribute("preserveAspectRatio", "none");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    path.setAttribute("class", "dots-line");
    path.setAttribute("points", "");
    svg.appendChild(path);
    wrap.appendChild(svg);
    let next = 0;
    const pts = [];
    dots.forEach((d, i) => {
      const p = coord(d);
      const b = h("button", "dot");
      b.style.left = GB.scene.norm(p.x) * 100 + "%";
      b.style.top = GB.scene.norm(p.y) * 100 + "%";
      b.textContent = data.order === "letter" ? String.fromCharCode(65 + i) : i + 1;
      b.onclick = () => {
        if (i !== next) return ctx.nope(`Find dot ${next + 1} next!`);
        b.classList.add("dot-on");
        pts.push(`${GB.scene.norm(p.x) * 100},${GB.scene.norm(p.y) * 100}`);
        path.setAttribute("points", pts.join(" "));
        next++;
        GB.audio.sfx("tick");
        if (next >= dots.length) { GB.juice.confetti(); ctx.win(); }
      };
      wrap.appendChild(b);
    });
    ctx.body.appendChild(wrap);
  } });

  def("coloring", { icon: "🎨", render(ctx) {
    const palette = ctx.data.palette || ["#e07a8b", "#7a9cc6", "#6b8f71", "#f0c419", "#d98a5b", "#9b6bd9"];
    const regions = ctx.data.regions || ["sky", "ground", "tree", "sun", "house"];
    let color = palette[0];
    const pal = h("div", "palette");
    palette.forEach((col) => {
      const sw = h("button", "pal-swatch");
      sw.style.background = col;
      sw.onclick = () => {
        color = col;
        pal.querySelectorAll(".sel").forEach((x) => x.classList.remove("sel"));
        sw.classList.add("sel");
      };
      pal.appendChild(sw);
    });
    pal.firstChild.classList.add("sel");
    const grid = h("div", "color-grid");
    regions.forEach((name) => {
      const rg = h("button", "color-region", esc(name));
      rg.onclick = () => {
        rg.style.background = color;
        rg.style.color = "#fff";
        rg.dataset.done = "1";
        if (grid.querySelectorAll("[data-done]").length === regions.length) ctx.win();
      };
      grid.appendChild(rg);
    });
    ctx.body.appendChild(pal);
    ctx.body.appendChild(grid);
    const b = h("button", "btn ghost", "I like my picture!");
    b.onclick = ctx.win;
    ctx.body.appendChild(b);
  } });

  /* ============================ SPATIAL / LOGIC ============================ */
  def("maze", { icon: "🌀", render(ctx) {
    const data = ctx.data;
    // Accept "#"/"." char grids OR space-separated grids with letter markers
    // (B/#/X = wall, S = start, E = end, everything else = open path).
    let grid = data.grid;
    if (typeof grid === "string") grid = grid.split(/\r?\n/);
    const isWall = (ch) => ch === "#" || ch === "B" || ch === "X" || ch === "x";
    grid = (grid || ["..", ".."])
      .map((r) => String(r).trim())
      .filter((r) => r.length)
      .map((r) => (/\s/.test(r) ? r.split(/\s+/) : r.split("")));
    const rows = grid.length, cols = Math.max(...grid.map((r) => r.length));
    grid = grid.map((r) => {
      while (r.length < cols) r.push(".");
      return r.map((ch) => (isWall(ch) ? "#" : ch));
    });
    let start = (data.start || [0, 0]).slice();
    let end = (data.end || [rows - 1, cols - 1]).slice();
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      if (grid[r][c] === "S") { start = [r, c]; grid[r][c] = "."; }
      if (grid[r][c] === "E") { end = [r, c]; grid[r][c] = "."; }
    }
    if (end[0] >= rows || end[1] >= cols) end = [rows - 1, cols - 1];
    if (grid[start[0]][start[1]] === "#") grid[start[0]][start[1]] = ".";
    let pos = [start[0], start[1]];
    line(ctx, "Use the arrows (or swipe / arrow keys) to reach 🎯");
    const board = h("div", "maze");
    board.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
    const cells = [];
    for (let r = 0; r < rows; r++) {
      cells[r] = [];
      for (let c = 0; c < cols; c++) {
        const cell = h("div", "maze-cell" + (grid[r][c] === "#" ? " wall" : ""));
        if (r === end[0] && c === end[1]) cell.appendChild(h("span", "maze-goal", "🎯"));
        board.appendChild(cell);
        cells[r][c] = cell;
      }
    }
    const hero = h("div", "maze-hero", esc(data.hero || "🐾"));
    const place = () => {
      cells[pos[0]][pos[1]].appendChild(hero);
      if (pos[0] === end[0] && pos[1] === end[1]) ctx.win();
    };
    const move = (dr, dc) => {
      const nr = pos[0] + dr, nc = pos[1] + dc;
      if (nr < 0 || nc < 0 || nr >= rows || nc >= cols) return;
      if (grid[nr][nc] === "#") return GB.juice.shake(board);
      pos = [nr, nc];
      place();
    };
    ctx.body.appendChild(board);
    place();
    const pad = h("div", "dpad");
    [["↑", -1, 0], ["←", 0, -1], ["→", 0, 1], ["↓", 1, 0]].forEach(([sym, dr, dc]) => {
      const b = h("button", "dpad-btn dpad-" + sym, sym);
      b.onclick = () => move(dr, dc);
      pad.appendChild(b);
    });
    ctx.body.appendChild(pad);
    board.tabIndex = 0;
    board.addEventListener("keydown", (e) => {
      const m = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }[e.key];
      if (m && document.contains(board)) { e.preventDefault(); e.stopPropagation(); move(m[0], m[1]); }
    });
    let sx = 0, sy = 0;
    board.addEventListener("touchstart", (e) => { sx = e.touches[0].clientX; sy = e.touches[0].clientY; }, { passive: true });
    board.addEventListener("touchend", (e) => {
      const dx = e.changedTouches[0].clientX - sx, dy = e.changedTouches[0].clientY - sy;
      if (Math.abs(dx) > Math.abs(dy)) move(0, dx > 0 ? 1 : -1);
      else move(dy > 0 ? 1 : -1, 0);
    });
  } });

  // Sliding-tile puzzle of the page art (one blank; shuffled by valid moves = solvable).
  def("sliding-puzzle", { icon: "🖼️", render(ctx) {
    const data = ctx.data;
    const n = data.size || data.rows || 3;
    const cols = data.cols || n, rows = data.rows || n;
    const img = ctx.page && ctx.page.image && ctx.page.image.file;
    line(ctx, "Slide the tiles to fix the picture!");
    const N = rows * cols, blank = N - 1;
    let order = Array.from({ length: N }, (_, i) => i);
    const neighbors = (p) => {
      const r = Math.floor(p / cols), c = p % cols, out = [];
      if (r > 0) out.push(p - cols);
      if (r < rows - 1) out.push(p + cols);
      if (c > 0) out.push(p - 1);
      if (c < cols - 1) out.push(p + 1);
      return out;
    };
    let bpos = blank;
    for (let s = 0; s < N * 12; s++) {
      const nb = neighbors(bpos);
      const t = nb[Math.floor(Math.random() * nb.length)];
      [order[bpos], order[t]] = [order[t], order[bpos]];
      bpos = t;
    }
    const board = h("div", "slide-board");
    board.style.gridTemplateColumns = `repeat(${cols},1fr)`;
    const solved = () => order.every((v, i) => v === i);
    function paint() {
      board.innerHTML = "";
      order.forEach((val, pos) => {
        const tile = h("div", "slide-tile");
        if (val === blank) {
          tile.classList.add("blank");
        } else {
          const r = Math.floor(val / cols), c = val % cols;
          if (img) {
            tile.style.backgroundImage = `url(${img})`;
            tile.style.backgroundSize = `${cols * 100}% ${rows * 100}%`;
            tile.style.backgroundPosition =
              `${cols > 1 ? (c * 100) / (cols - 1) : 0}% ${rows > 1 ? (r * 100) / (rows - 1) : 0}%`;
          } else {
            tile.textContent = val + 1;
          }
          tile.onclick = () => {
            const bp = order.indexOf(blank);
            if (neighbors(pos).includes(bp)) {
              order[bp] = val;
              order[pos] = blank;
              GB.audio.sfx("tick");
              paint();
              if (solved()) { GB.juice.confetti(); ctx.win(); }
            }
          };
        }
        board.appendChild(tile);
      });
    }
    ctx.body.appendChild(board);
    paint();
    ctx.hint([data.hint || "Slide tiles next to the gap."], () => {
      order = Array.from({ length: N }, (_, i) => i);
      paint();
      ctx.win();
    });
  } });

  def("balance-scale", { icon: "⚖️", render(ctx) {
    const data = ctx.data;
    const weigh = (side) => (Array.isArray(side) ? side.length : Number(side) || 0);
    line(ctx, "Which side is heavier? Tap it!");
    const ans = data.answer != null
      ? String(data.answer)
      : weigh(data.left) === weigh(data.right) ? "equal" : weigh(data.left) > weigh(data.right) ? "left" : "right";
    const scale = h("div", "scale-row");
    [["left", data.left], ["right", data.right]].forEach(([side, items]) => {
      const pan = h("button", "scale-pan");
      pan.appendChild(h("div", "pan-items", esc(Array.isArray(items) ? items.join(" ") : "⚖️ " + (items || ""))));
      pan.onclick = () => {
        if (side === ans) { pan.classList.add("correct"); ctx.win(); }
        else {
          pan.classList.add("wrong");
          ctx.nope("Look again — which has more?");
          setTimeout(() => pan.classList.remove("wrong"), 600);
        }
      };
      scale.appendChild(pan);
    });
    ctx.body.appendChild(scale);
    if (ans === "equal") {
      const eq = h("button", "btn", "They're equal!");
      eq.onclick = ctx.win;
      ctx.body.appendChild(eq);
    }
  } });

  /* ============================ WORD / PHONICS ============================ */
  // Tap letters in order to build the word (extra letters allowed as distractors).
  function buildWord(ctx, letters, answer) {
    const target = String(answer).toUpperCase().replace(/\s+/g, "");
    const slots = h("div", "word-slots");
    let built = "";
    const paint = () => {
      slots.innerHTML = "";
      for (let i = 0; i < target.length; i++) slots.appendChild(h("span", "word-slot", esc(built[i] || "")));
    };
    paint();
    ctx.body.appendChild(slots);
    const tray = h("div", "chip-row");
    ctx.body.appendChild(tray);
    const pool = (letters && letters.length ? letters : target.split("")).map(String);
    shuffle(pool).forEach((ltr) => {
      const b = h("button", "gb-chip letter", esc(ltr.toUpperCase()));
      b.onclick = () => {
        if (b.disabled) return;
        if (ltr.toUpperCase() === target[built.length]) {
          built += ltr.toUpperCase();
          b.disabled = true;
          b.classList.add("placed");
          GB.audio.sfx("tick");
          paint();
          if (built === target) ctx.win();
        } else {
          ctx.nope("Try a different letter!");
        }
      };
      tray.appendChild(b);
    });
    ctx.hint([ctx.data.hint || `It starts with ${target[0]}.`], () => { built = target; paint(); ctx.win(); });
  }
  def("word-build", { icon: "🔤", render(ctx) { line(ctx, "Spell the word!"); buildWord(ctx, ctx.data.letters, ctx.data.answer); } });
  def("anagram", { icon: "🔡", render(ctx) {
    line(ctx, "Unscramble the letters!");
    buildWord(ctx, ctx.data.scrambled != null ? String(ctx.data.scrambled).split("") : null, ctx.data.answer);
  } });

  def("fill-the-blank", { icon: "✏️", render(ctx) {
    const data = ctx.data;
    line(ctx, esc(String(data.sentence || "").replace("___", "______")));
    if (data.options && data.options.length) {
      const opts = data.options.includes(data.answer) ? data.options : [...data.options, data.answer];
      GB.ui.answerRow(ctx, opts, data.answer);
    } else {
      buildWord(ctx, null, data.answer);
    }
  } });

  /* ============================ MUSIC / RHYTHM ============================ */
  def("melody", { icon: "🎵", render(ctx) {
    const data = ctx.data;
    const notes = (data.notes || data.sequence || ["C", "E", "G"]).map(String);
    const padNames = data.pads || [...new Set(notes)];
    line(ctx, "Listen to the tune, then tap it back!");
    const listen = h("button", "btn", "🔊 Play the tune");
    let canPlay = true;
    const flash = (pad) => { pad.classList.add("lit"); setTimeout(() => pad.classList.remove("lit"), 240); };
    const keyboard = h("div", "melody-pads");
    let step = 0;
    const padEls = padNames.map((n) => {
      const pad = h("button", "melody-pad", esc(n));
      pad.onclick = () => {
        GB.audio.tone(GB.audio.freqOf(n), 0.4, 0);
        flash(pad);
        if (n === notes[step]) {
          if (++step >= notes.length) ctx.win();
        } else {
          step = 0;
          ctx.nope("Oops — listen again and start over!");
        }
      };
      keyboard.appendChild(pad);
      return pad;
    });
    listen.onclick = () => {
      if (!canPlay) return;
      canPlay = false;
      GB.audio.playSequence(notes, {
        tempo: 0.5, dur: 0.42,
        onNote: (i, n) => { const pad = padEls[padNames.indexOf(n)]; if (pad) flash(pad); },
        onDone: () => { canPlay = true; },
      });
    };
    ctx.body.appendChild(listen);
    ctx.body.appendChild(keyboard);
  } });

  // Tap along to the beat (toddler-friendly; counts taps, always wins).
  def("rhythm-tap", { icon: "🥁", render(ctx) {
    const data = ctx.data;
    const pattern = data.pattern || [1, 1, 1, 1];
    const beats = pattern.filter(Boolean).length || pattern.length;
    line(ctx, "Listen, then tap the drum to the beat!");
    const listen = h("button", "btn", "🔊 Hear the beat");
    listen.onclick = () => {
      let t = 0;
      pattern.forEach((b) => {
        if (b) GB.audio.tone(196, 0.12, t, "triangle");
        t += data.tempo ? 60 / data.tempo : 0.4;
      });
    };
    ctx.body.appendChild(listen);
    const meter = h("div", "rhythm-meter");
    for (let i = 0; i < beats; i++) meter.appendChild(h("span", "beat-dot"));
    const drum = h("button", "drum-pad", "🥁");
    let taps = 0;
    drum.onclick = () => {
      GB.audio.tone(160, 0.12, 0, "triangle");
      GB.juice.squash(drum);
      const dots = meter.querySelectorAll(".beat-dot");
      if (dots[taps]) dots[taps].classList.add("on");
      if (++taps >= beats) ctx.win();
    };
    ctx.body.appendChild(meter);
    ctx.body.appendChild(drum);
  } });

  // Song builder: tap notes into a strip, hear your tune (free-play, always wins).
  def("song-builder", { icon: "🎶", render(ctx) {
    const palette = ctx.data.palette || ["C", "D", "E", "G", "A"];
    const bars = ctx.data.bars || 6;
    line(ctx, "Build a tune — tap notes into the strip!");
    const strip = h("div", "song-strip");
    const song = [];
    for (let i = 0; i < bars; i++) strip.appendChild(h("div", "song-cell"));
    ctx.body.appendChild(strip);
    const pal = h("div", "melody-pads");
    let cur = 0;
    palette.forEach((n) => {
      const pad = h("button", "melody-pad", esc(n));
      pad.onclick = () => {
        GB.audio.tone(GB.audio.freqOf(n), 0.3);
        if (cur < bars) {
          strip.children[cur].textContent = n;
          strip.children[cur].classList.add("filled");
          song[cur] = n;
          cur++;
        }
      };
      pal.appendChild(pad);
    });
    ctx.body.appendChild(pal);
    const play = h("button", "btn", "▶ Play my song");
    play.onclick = () => GB.audio.playSequence(song.filter(Boolean), { tempo: 0.4 });
    ctx.body.appendChild(play);
    const done = h("button", "btn ghost", "I love my song! 🎶");
    done.onclick = ctx.win;
    ctx.body.appendChild(done);
  } });

  // Watch the sequence light up, then repeat it (Simon, visual).
  def("sequence-recall", { icon: "🧠", render(ctx) {
    const seq = (ctx.data.sequence || []).map(String);
    const padNames = ctx.data.pads || [...new Set(seq)];
    line(ctx, "Watch the order, then tap it back!");
    const watch = h("button", "btn", "👀 Show me");
    const grid = h("div", "melody-pads");
    const padEls = {};
    padNames.forEach((p, i) => {
      const pad = h("button", "melody-pad seq-pad", esc(p));
      pad.style.setProperty("--h", (i * 67) % 360);
      padEls[p] = pad;
      grid.appendChild(pad);
    });
    let step = 0, canTap = false;
    const flashPad = (p, t) => setTimeout(() => {
      const pad = padEls[p];
      if (!pad) return;
      pad.classList.add("lit");
      GB.audio.tone(330 + 40 * padNames.indexOf(p), 0.25);
      setTimeout(() => pad.classList.remove("lit"), 320);
    }, t);
    watch.onclick = () => {
      canTap = false;
      step = 0;
      let t = 200;
      seq.forEach((p) => { flashPad(p, t); t += 450; });
      setTimeout(() => { canTap = true; }, t);
    };
    Object.keys(padEls).forEach((p) => {
      padEls[p].onclick = () => {
        if (!canTap) return;
        GB.juice.flash(padEls[p]);
        if (p === seq[step]) {
          if (++step >= seq.length) ctx.win();
        } else {
          step = 0;
          ctx.nope("Oops — watch again!");
        }
      };
    });
    ctx.body.appendChild(watch);
    ctx.body.appendChild(grid);
  } });

  /* ============================ CUSTOM DSL ============================ */
  // A declarative game an author (or LLM) invents as DATA: `elements` (draggables /
  // dropzones / hotspots / targets / toggles) + a `win` condition. No code, no fail state —
  // winnable by construction; a hint ladder + auto-solve is the final backstop.
  def("custom", { icon: "⭐", render(ctx) {
    const data = ctx.data || {};
    const elements = (data.elements || []).filter((e) => e && e.id);
    const onArt = data.stage === "scene" || elements.some((e) => e.at);

    // ---- state ----
    const placements = {}; // draggableId -> zoneId
    const hits = {};       // hotspot/target id -> true
    const toggles = {};    // toggle id -> bool
    const tapOrder = [];   // ids tapped, in order (for ordered)
    let seqPos = 0;        // for sequence (Simon) mode
    let solved = false;

    // ---- surface ----
    const scene = onArt ? ctx.scene.create(ctx.body, ctx.page) : null;
    let tray, zonesRow;
    if (!scene) {
      const board = h("div", "custom-board");
      zonesRow = h("div", "bin-row custom-zones");
      tray = h("div", "chip-row custom-tray");
      board.appendChild(zonesRow);
      board.appendChild(tray);
      ctx.body.appendChild(board);
    }
    const field = ctx.dnd.create();
    const faceOf = (e) => (e.emoji ? e.emoji + " " : "") + (e.label != null ? e.label : e.id);

    // ---- win evaluation ----
    function evalCond(cond) {
      if (!cond || typeof cond !== "object") return false;
      if (cond.all) return cond.all.every(evalCond);
      if (cond.any) return cond.any.some(evalCond);
      if (cond.not) return !evalCond(cond.not);
      switch (cond.mode) {
        case "all-placed": {
          // Every PLACEABLE draggable is placed; unplaceable draggables are decoys (e.g.
          // the junk you must NOT pack), so they don't block the win.
          const drags = elements.filter((e) => e.kind === "draggable");
          const zones = elements.filter((e) => e.kind === "dropzone" || e.kind === "target");
          const canPlace = (d) => zones.some((z) => {
            const a = z.accepts;
            return !a || !a.length || a.includes(d.group) || a.includes(d.id);
          });
          const placeable = drags.filter(canPlace);
          return placeable.length > 0 && placeable.every((e) => placements[e.id]);
        }
        case "matched-pairs":
          return (cond.pairs || []).every((pr) => placements[pr[0]] === pr[1]);
        case "all-found": {
          const want = cond.targets ||
            elements.filter((e) => e.kind === "hotspot" || e.kind === "target").map((e) => e.id);
          return want.every((id) => hits[id]);
        }
        case "ordered": {
          const want = (cond.order || []).join("|");
          return want.length > 0 &&
            tapOrder.filter((id) => (cond.order || []).includes(id)).join("|") === want;
        }
        case "sequence":
          return (cond.steps || []).length > 0 && seqPos >= (cond.steps || []).length;
        case "toggled-all": {
          const st = cond.state || {};
          const keys = Object.keys(st);
          return keys.length > 0 && keys.every((id) => !!toggles[id] === !!st[id]);
        }
        default:
          return false; // unknown predicate → not yet satisfied (never throws)
      }
    }
    const check = () => {
      if (!solved && evalCond(data.win)) { solved = true; ctx.win(); }
    };

    // ---- element interactions ----
    const seqStep = (e) => {
      if (!data.win || data.win.mode !== "sequence") return;
      const steps = data.win.steps || [];
      if (e.id === steps[seqPos]) seqPos++;
      else if (steps.includes(e.id)) {
        seqPos = e.id === steps[0] ? 1 : 0;
        ctx.nope("Oops — start the sequence again!");
      }
    };
    const tap = (e) => { tapOrder.push(e.id); seqStep(e); check(); };
    const hit = (e) => { hits[e.id] = true; tapOrder.push(e.id); seqStep(e); GB.audio.sfx("reveal"); check(); };

    // ---- render elements: draggables first, then zones / hotspots / toggles ----
    elements.forEach((e) => {
      if (e.kind !== "draggable") return;
      const node = h("button", "gb-chip", esc(faceOf(e)));
      field.draggable(node, { id: e.id, group: e.group, label: e.label || e.id });
      if (scene && e.at) scene.placeItem(node, e.at);
      else if (scene) ctx.body.appendChild(node);
      else tray.appendChild(node);
    });
    elements.forEach((e) => {
      if (e.kind === "dropzone" || e.kind === "target") {
        const onDrop = (node) => {
          placements[node.dataset.id] = e.id;
          check();
          return true;
        };
        if (scene) {
          const z = scene.dropTarget({ at: e.at, r: e.r, label: e.label != null ? e.label : e.id });
          field.dropzone(z, { accepts: e.accepts || e.id, onDrop: (node) => { GB.juice.flash(z); return onDrop(node); } });
        } else {
          const bin = h("div", "bin");
          bin.appendChild(h("div", "bin-label", esc(e.label != null ? e.label : e.id)));
          const slot = h("div", "bin-slot");
          bin.appendChild(slot);
          field.dropzone(slot, { accepts: e.accepts || e.id, onDrop });
          zonesRow.appendChild(bin);
        }
      } else if (e.kind === "hotspot") {
        if (scene) {
          scene.hotspot({ at: e.at, r: e.r, label: e.label || e.id, glow: true, onHit: () => hit(e) });
        } else {
          const b = h("button", "opt", esc(faceOf(e)));
          b.onclick = () => { b.classList.add("correct"); hit(e); };
          ctx.body.appendChild(b);
        }
      } else if (e.kind === "toggle") {
        const b = h("button", "opt toggle", esc(faceOf(e)));
        b.onclick = () => {
          toggles[e.id] = !toggles[e.id];
          b.classList.toggle("on", toggles[e.id]);
          GB.audio.sfx("tick");
          check();
        };
        ctx.body.appendChild(b);
      } else if (e.kind === "tile" && !scene) {
        const b = h("button", "opt", esc(faceOf(e)));
        b.onclick = () => tap(e);
        ctx.body.appendChild(b);
      }
    });

    // ---- always-winnable backstop: hint ladder whose last rung auto-solves ----
    const hints = data.hints || (data.hint ? [data.hint] : []);
    ctx.hint(hints, () => {
      if (solved) return;
      solved = true;
      GB.juice.confetti();
      ctx.win();
    });
  } });
})();
