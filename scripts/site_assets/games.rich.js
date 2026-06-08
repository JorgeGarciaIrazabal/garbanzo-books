/* GB.games — the RICH game library: in-scene play on the art, true drag-and-drop, drawing,
   spatial puzzles, word play, music/rhythm, and memory. Built on the toolkit (GB.scene /
   GB.dnd / GB.audio / GB.juice / GB.shared). Every game is always winnable; on-art games
   degrade to a tap/chip fallback when a page has no illustration (placeholder builds). */
(function () {
  "use strict";
  var GB = (window.GB = window.GB || {});
  var el = function (t, c, h) { return GB.el(t, c, h); };
  var esc = function (s) { return GB.esc(s); };
  var shuffle = function (a) { return GB.shuffle(a); };
  var reg = function (type, fn) { GB.registerGame(type, fn); };
  function label(x) { return x && x.label != null ? x.label : x; }
  function coord(x) { return x && x.at ? x.at : x; }

  // ============================================================ ON-THE-ART (GB.scene)

  // Find every named thing hidden in the illustration by tapping its spot.
  reg("hidden-object", function (ctx) {
    var data = ctx.data, win = ctx.win, nope = ctx.nope;
    var items = data.items || [];
    ctx.body.appendChild(el("p", "game-line", "Find them all — tap them in the picture!"));
    var list = el("div", "chip-row"); var chips = [];
    items.forEach(function (it) { var c = el("span", "find-item", "🔍 " + esc(label(it))); list.appendChild(c); chips.push(c); });
    ctx.body.appendChild(list);
    var scene = ctx.scene && ctx.scene.create(ctx.body, ctx.page);
    if (!scene || !scene.hasImage) { // fallback: tap the chips
      var found0 = 0;
      chips.forEach(function (c) { c.style.cursor = "pointer"; c.onclick = function () { if (c.classList.contains("found")) return; c.classList.add("found"); if (++found0 >= items.length) win(); }; });
      return;
    }
    var found = 0;
    items.forEach(function (it, i) {
      scene.hotspot({ at: coord(it), r: it.r, label: label(it), onHit: function (h) { chips[i].classList.add("found"); if (GB.juice) GB.juice.burstAt(h, { count: 8 }); if (GB.audio) GB.audio.sfx("reveal"); if (++found >= items.length) win(); } });
    });
    (data.decoys || []).forEach(function (d) { scene.hotspot({ at: coord(d), r: d.r, onHit: function () { nope("Not there — keep looking!"); } }); });
    scene.missTaps(function () { nope("Look closely!"); });
  });

  // Find things one at a time (the prompt calls out the next target).
  reg("find-in-scene", function (ctx) {
    var data = ctx.data, win = ctx.win, nope = ctx.nope;
    var items = data.items || [];
    var caption = el("p", "game-line", "");
    ctx.body.appendChild(caption);
    var scene = ctx.scene && ctx.scene.create(ctx.body, ctx.page);
    var i = 0;
    function ask() { if (i >= items.length) return win(); caption.textContent = "Find: " + label(items[i]) + " 🔍"; }
    if (!scene || !scene.hasImage) {
      var row = el("div", "chip-row");
      shuffle(items).forEach(function (it) { var b = el("button", "find-item", "🔍 " + esc(label(it))); b.onclick = function () { if (label(it) === label(items[i])) { b.classList.add("found"); i++; ask(); } else nope("That's not it yet!"); }; row.appendChild(b); });
      ctx.body.appendChild(row); ask(); return;
    }
    items.forEach(function (it, idx) {
      scene.hotspot({ at: coord(it), r: it.r, label: label(it), onHit: function (h) {
        if (idx === i) { if (GB.juice) GB.juice.burstAt(h); i++; ask(); } else { h.classList.remove("got"); nope("Find " + label(items[i]) + " first!"); }
      } });
    });
    ask();
  });

  // Tap the one right thing on the picture.
  reg("tap-on-art", function (ctx) {
    var data = ctx.data, win = ctx.win, nope = ctx.nope;
    ctx.body.appendChild(el("p", "game-line", data.hint || "Tap it in the picture!"));
    var scene = ctx.scene && ctx.scene.create(ctx.body, ctx.page);
    if (!scene || !scene.hasImage || !data.target) { var b = el("button", "btn", "👆 " + esc(label(data.target) || "Tap!")); b.onclick = win; ctx.body.appendChild(b); return; }
    scene.hotspot({ at: coord(data.target), r: data.target.r, label: label(data.target), onHit: function (h) { if (GB.juice) GB.juice.burstAt(h); win(); } });
    scene.missTaps(function () { nope("Not quite — try again!"); });
  });

  // Tap glowing hotspots to reveal a caption for each (exploration, no fail).
  reg("hotspot-reveal", function (ctx) {
    var data = ctx.data, win = ctx.win;
    var spots = data.hotspots || [];
    ctx.body.appendChild(el("p", "game-line", "Tap the sparkles to discover what's hiding!"));
    var scene = ctx.scene && ctx.scene.create(ctx.body, ctx.page);
    var caption = el("div", "reveal-caption"); ctx.body.appendChild(caption);
    var seen = 0;
    function reveal(s) { caption.textContent = (s.icon ? s.icon + " " : "") + (s.reveal || ""); if (GB.audio) GB.audio.sfx("reveal"); if (++seen >= spots.length) win(); }
    if (!scene || !scene.hasImage) { var row = el("div", "chip-row"); spots.forEach(function (s) { var b = el("button", "opt", esc(s.icon || "✨")); b.onclick = function () { b.classList.add("correct"); reveal(s); }; row.appendChild(b); }); ctx.body.appendChild(row); return; }
    spots.forEach(function (s) { scene.hotspot({ at: coord(s), r: s.r, glow: true, label: s.reveal, onHit: function () { reveal(s); } }); });
  });

  // Drag items onto the right spots ON the art.
  reg("place-on-scene", function (ctx) {
    var data = ctx.data, win = ctx.win;
    var items = data.items || [], slots = data.slots || [];
    ctx.body.appendChild(el("p", "game-line", "Drag each thing where it belongs!"));
    var field = ctx.dnd && ctx.dnd.create();
    var scene = ctx.scene && ctx.scene.create(ctx.body, ctx.page);
    var placed = 0, need = items.length;
    if (!field || !scene || !scene.hasImage) { return dragBinsFallback(ctx, items.map(function (it) { return { label: label(it), bin: it.accepts || it.slot }; }), slots.map(function (s) { return { label: s.label, key: s.accepts || s.label }; }), win); }
    slots.forEach(function (s) { var z = scene.dropTarget({ at: coord(s), r: s.r, label: s.label }); field.dropzone(z, { accepts: s.accepts || s.label, onDrop: function () { if (++placed >= need) win(); return true; } }); });
    var tray = el("div", "chip-row"); ctx.body.appendChild(tray);
    shuffle(items).forEach(function (it) { var chip = el("button", "gb-chip", (it.icon ? it.icon + " " : "") + esc(label(it))); field.draggable(chip, { id: label(it), group: it.accepts || it.slot, label: label(it) }); tray.appendChild(chip); });
  });

  // ============================================================ DRAG-AND-DROP SUITE

  // Shared fallback for drag games when pointer DnD / scene isn't available: tap-select bins.
  function dragBinsFallback(ctx, items, bins, win) {
    var nope = ctx.nope;
    var data = { items: items, bins: bins };
    GB.games["sorting"]({ body: ctx.body, data: data, win: win, nope: nope });
  }

  // Drag items into the right bins (true drag).
  reg("drag-sort", function (ctx) {
    var data = ctx.data, win = ctx.win;
    var items = (data.items || []).map(function (x) { return { label: label(x), bin: x.bin }; });
    var bins = (data.bins || []).map(function (b) { return { label: label(b), key: b.key != null ? b.key : label(b) }; });
    ctx.body.appendChild(el("p", "game-line", "Drag each one into its basket!"));
    var field = ctx.dnd && ctx.dnd.create();
    if (!field) return dragBinsFallback(ctx, items, bins, win);
    var binRow = el("div", "bin-row"); ctx.body.appendChild(binRow);
    var placed = 0;
    bins.forEach(function (b) { var bin = el("div", "bin"); bin.appendChild(el("div", "bin-label", esc(b.label))); var slot = el("div", "bin-slot"); bin.appendChild(slot); field.dropzone(slot, { accepts: String(b.key), onDrop: function () { if (++placed >= items.length) win(); return true; } }); binRow.appendChild(bin); });
    var tray = el("div", "chip-row"); ctx.body.appendChild(tray);
    shuffle(items).forEach(function (it) { var chip = el("button", "gb-chip", esc(it.label)); field.draggable(chip, { id: it.label, group: String(it.bin), label: it.label }); tray.appendChild(chip); });
  });

  // Drag each left item onto its matching right target.
  reg("drag-match", function (ctx) {
    var data = ctx.data, win = ctx.win;
    var pairs = data.pairs || [];
    ctx.body.appendChild(el("p", "game-line", "Drag each one to its match!"));
    var field = ctx.dnd && ctx.dnd.create();
    if (!field) return GB.shared.matchGame(ctx, "Match each one to its pair:");
    var grid = el("div", "match-grid"); var lefts = el("div", "match-col chip-row"); var rights = el("div", "match-col");
    var matched = 0;
    pairs.forEach(function (pr, i) { var z = el("div", "bin"); z.appendChild(el("div", "bin-label", esc(pr[1]))); var slot = el("div", "bin-slot"); z.appendChild(slot); field.dropzone(slot, { accepts: "p" + i, onDrop: function () { if (++matched >= pairs.length) win(); return true; } }); rights.appendChild(z); });
    shuffle(pairs.map(function (pr, i) { return { v: pr[0], k: i }; })).forEach(function (o) { var chip = el("button", "gb-chip", esc(o.v)); field.draggable(chip, { id: o.v, group: "p" + o.k, label: o.v }); lefts.appendChild(chip); });
    grid.appendChild(lefts); grid.appendChild(rights); ctx.body.appendChild(grid);
  });

  // Jigsaw: drag scrambled pieces of the page art into their slots.
  reg("jigsaw", function (ctx) {
    var data = ctx.data, win = ctx.win;
    var rows = data.rows || 2, cols = data.cols || 3;
    var img = ctx.page && ctx.page.image && ctx.page.image.file;
    ctx.body.appendChild(el("p", "game-line", "Put the picture back together!"));
    var field = ctx.dnd && ctx.dnd.create();
    var board = el("div", "jigsaw-board"); board.style.gridTemplateColumns = "repeat(" + cols + ",1fr)";
    var slots = [];
    for (var i = 0; i < rows * cols; i++) { var s = el("div", "jigsaw-slot"); s.dataset.idx = i; if (field) field.dropzone(s, { accepts: "j" + i, onDrop: function () { if (board.querySelectorAll(".jigsaw-piece.placed").length >= rows * cols) win(); return true; } }); board.appendChild(s); slots.push(s); }
    ctx.body.appendChild(board);
    var tray = el("div", "jigsaw-tray"); ctx.body.appendChild(tray);
    var order = shuffle(Array.apply(null, { length: rows * cols }).map(function (_, i) { return i; }));
    order.forEach(function (i) {
      var r = Math.floor(i / cols), c = i % cols;
      var piece = el("button", "jigsaw-piece");
      if (img) { piece.style.backgroundImage = "url(" + img + ")"; piece.style.backgroundSize = (cols * 100) + "% " + (rows * 100) + "%"; piece.style.backgroundPosition = (cols > 1 ? (c * 100 / (cols - 1)) : 0) + "% " + (rows > 1 ? (r * 100 / (rows - 1)) : 0) + "%"; }
      else piece.textContent = i + 1;
      if (field) field.draggable(piece, { id: "j" + i, group: "j" + i, label: "piece " + (i + 1) });
      else piece.onclick = function () { piece.classList.add("placed"); if (tray.querySelectorAll(".jigsaw-piece:not(.placed)").length === 0) win(); };
      tray.appendChild(piece);
    });
    if (!field) ctx.body.appendChild(el("p", "reading-note", "(Tap each piece to set it.)"));
  });

  // Dress up / build: drag parts onto the figure's zones (free-play, always wins).
  reg("dress-up", function (ctx) {
    var data = ctx.data, win = ctx.win;
    var parts = data.parts || [], zones = data.zones || [];
    ctx.body.appendChild(el("p", "game-line", "Dress up your character — drag the bits on!"));
    var field = ctx.dnd && ctx.dnd.create();
    var fig = el("div", "dressup-figure", esc(data.base || "🧍"));
    zones.forEach(function (z) { var d = el("div", "dressup-zone"); d.style.left = (GB.scene.norm(coord(z).x) * 100) + "%"; d.style.top = (GB.scene.norm(coord(z).y) * 100) + "%"; d.dataset.zone = z.label; if (field) field.dropzone(d, { accepts: z.label, onDrop: function (n) { d.textContent = n.textContent; placed++; if (placed >= Math.min(parts.length, zones.length)) win(); return true; } }); fig.appendChild(d); });
    ctx.body.appendChild(fig);
    var placed = 0;
    var tray = el("div", "chip-row"); ctx.body.appendChild(tray);
    shuffle(parts).forEach(function (p) { var chip = el("button", "gb-chip", (p.icon ? p.icon + " " : "") + esc(p.label)); if (field) field.draggable(chip, { id: p.label, group: p.zone, label: p.label }); else chip.onclick = function () { chip.classList.add("placed"); if (++placed >= parts.length) win(); }; tray.appendChild(chip); });
    var done = el("button", "btn ghost", "Looks great!"); done.onclick = win; ctx.body.appendChild(done);
  });

  // Feed the creature: drag the GOOD things into its mouth; bad things bounce back.
  reg("feed-the-thing", function (ctx) {
    var data = ctx.data, win = ctx.win, nope = ctx.nope;
    var good = (data.good || []).map(String), bad = (data.bad || []).map(String);
    ctx.body.appendChild(el("p", "game-line", "Feed it only the yummy things!"));
    var field = ctx.dnd && ctx.dnd.create();
    var mouth = el("div", "feed-mouth", esc(data.target_icon || "😋"));
    var fed = 0;
    if (field) field.dropzone(mouth, { accepts: function (n) { return n.dataset.group === "good"; }, onDrop: function (n) { n.remove(); if (++fed >= good.length) win(); return true; } });
    ctx.body.appendChild(mouth);
    var tray = el("div", "chip-row"); ctx.body.appendChild(tray);
    shuffle(good.map(function (g) { return { v: g, ok: true }; }).concat(bad.map(function (b) { return { v: b, ok: false }; }))).forEach(function (o) {
      var chip = el("button", "gb-chip", esc(o.v));
      if (field) field.draggable(chip, { id: o.v, group: o.ok ? "good" : "bad", label: o.v });
      else chip.onclick = function () { if (o.ok) { chip.remove(); if (++fed >= good.length) win(); } else nope("Yuck — not that one!"); };
      tray.appendChild(chip);
    });
  });

  // ============================================================ DRAW / REVEAL (canvas)

  // Connect the dots in order to reveal a hidden line drawing.
  reg("connect-dots", function (ctx) {
    var data = ctx.data, win = ctx.win, nope = ctx.nope;
    var dots = (data.dots || []).slice().sort(function (a, b) { return (a.n || 0) - (b.n || 0); });
    ctx.body.appendChild(el("p", "game-line", "Connect the dots " + (data.order === "letter" ? "A, B, C…" : "1, 2, 3…")));
    var wrap = el("div", "dots-wrap");
    var img = ctx.page && ctx.page.image && ctx.page.image.file;
    if (img) { var bg = document.createElement("img"); bg.src = img; bg.className = "dots-bg"; bg.alt = ""; wrap.appendChild(bg); }
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); svg.setAttribute("viewBox", "0 0 100 100"); svg.setAttribute("class", "dots-svg"); svg.setAttribute("preserveAspectRatio", "none");
    var path = document.createElementNS("http://www.w3.org/2000/svg", "polyline"); path.setAttribute("class", "dots-line"); path.setAttribute("points", ""); svg.appendChild(path);
    wrap.appendChild(svg);
    var next = 0, pts = [];
    dots.forEach(function (d, i) {
      var p = coord(d); var b = el("button", "dot"); b.style.left = (GB.scene.norm(p.x) * 100) + "%"; b.style.top = (GB.scene.norm(p.y) * 100) + "%"; b.textContent = data.order === "letter" ? String.fromCharCode(65 + i) : (i + 1);
      b.onclick = function () {
        if (i === next) { b.classList.add("dot-on"); pts.push((GB.scene.norm(p.x) * 100) + "," + (GB.scene.norm(p.y) * 100)); path.setAttribute("points", pts.join(" ")); next++; if (GB.audio) GB.audio.sfx("tick"); if (next >= dots.length) { if (GB.juice) GB.juice.confetti(); win(); } }
        else nope("Find dot " + (next + 1) + " next!");
      };
      wrap.appendChild(b);
    });
    ctx.body.appendChild(wrap);
  });

  // Scratch / scrub to reveal what's hidden underneath.
  reg("scratch-reveal", function (ctx) {
    var data = ctx.data, win = ctx.win;
    ctx.body.appendChild(el("p", "game-line", "Scratch to see what's hidden!"));
    var wrap = el("div", "scratch-wrap");
    var under = el("div", "scratch-under", esc(data.reveal || "🎁"));
    var cv = document.createElement("canvas"); cv.className = "scratch-canvas"; cv.width = 300; cv.height = 180;
    var g = cv.getContext("2d"); g.fillStyle = "#c9bfa8"; g.fillRect(0, 0, cv.width, cv.height); g.globalCompositeOperation = "destination-out"; g.lineWidth = 34; g.lineCap = "round";
    var drawing = false, last = null, cleared = 0, threshold = (data.threshold || 0.5) * cv.width * cv.height / 1200;
    function pos(e) { var r = cv.getBoundingClientRect(); var t = e.touches ? e.touches[0] : e; return { x: (t.clientX - r.left) * cv.width / r.width, y: (t.clientY - r.top) * cv.height / r.height }; }
    function start(e) { drawing = true; last = pos(e); e.preventDefault(); }
    function move(e) { if (!drawing) return; var p = pos(e); g.beginPath(); g.moveTo(last.x, last.y); g.lineTo(p.x, p.y); g.stroke(); cleared += Math.hypot(p.x - last.x, p.y - last.y); last = p; e.preventDefault(); if (cleared > threshold) { cv.classList.add("done"); win(); } }
    function end() { drawing = false; }
    cv.addEventListener("mousedown", start); cv.addEventListener("mousemove", move); window.addEventListener("mouseup", end);
    cv.addEventListener("touchstart", start, { passive: false }); cv.addEventListener("touchmove", move, { passive: false }); cv.addEventListener("touchend", end);
    wrap.appendChild(under); wrap.appendChild(cv); ctx.body.appendChild(wrap);
  });

  // ============================================================ PUZZLE / SPATIAL

  // Sliding-tile puzzle of the page art (one blank; slide to unscramble).
  reg("sliding-puzzle", function (ctx) {
    var data = ctx.data, win = ctx.win;
    var n = data.size || data.rows || 3; var cols = data.cols || n, rows = data.rows || n;
    var img = ctx.page && ctx.page.image && ctx.page.image.file;
    ctx.body.appendChild(el("p", "game-line", "Slide the tiles to fix the picture!"));
    var N = rows * cols;
    var order = []; for (var i = 0; i < N; i++) order.push(i); // index N-1 is the blank
    var blank = N - 1;
    // shuffle by valid moves to guarantee solvable
    var bpos = blank;
    function neighbors(p) { var r = Math.floor(p / cols), c = p % cols, out = []; if (r > 0) out.push(p - cols); if (r < rows - 1) out.push(p + cols); if (c > 0) out.push(p - 1); if (c < cols - 1) out.push(p + 1); return out; }
    for (var s = 0; s < N * 12; s++) { var nb = neighbors(bpos); var t = nb[Math.floor(Math.random() * nb.length)]; var tmp = order[bpos]; order[bpos] = order[t]; order[t] = tmp; bpos = t; }
    var board = el("div", "slide-board"); board.style.gridTemplateColumns = "repeat(" + cols + ",1fr)";
    function paint() {
      board.innerHTML = "";
      order.forEach(function (val, pos) {
        var tile = el("div", "slide-tile");
        if (val === blank) { tile.classList.add("blank"); }
        else {
          var r = Math.floor(val / cols), c = val % cols;
          if (img) { tile.style.backgroundImage = "url(" + img + ")"; tile.style.backgroundSize = (cols * 100) + "% " + (rows * 100) + "%"; tile.style.backgroundPosition = (cols > 1 ? (c * 100 / (cols - 1)) : 0) + "% " + (rows > 1 ? (r * 100 / (rows - 1)) : 0) + "%"; }
          else tile.textContent = val + 1;
          tile.onclick = function () { var bp = order.indexOf(blank); if (neighbors(pos).indexOf(bp) >= 0) { order[bp] = val; order[pos] = blank; if (GB.audio) GB.audio.sfx("tick"); paint(); check(); } };
        }
        board.appendChild(tile);
      });
    }
    function solved() { for (var k = 0; k < N; k++) if (order[k] !== k) return false; return true; }
    function check() { if (solved()) { if (GB.juice) GB.juice.confetti(); win(); } }
    ctx.body.appendChild(board); paint();
    GB.shared.hintLadder(ctx.body, [data.hint || "Slide tiles next to the gap."], function () { order = []; for (var k = 0; k < N; k++) order.push(k); paint(); win(); });
  });

  // Balance scale: tap the heavier pan (sneaky math / reasoning).
  reg("balance-scale", function (ctx) {
    var data = ctx.data, win = ctx.win, nope = ctx.nope;
    function weigh(side) { return Array.isArray(side) ? side.length : Number(side) || 0; }
    ctx.body.appendChild(el("p", "game-line", "Which side is heavier? Tap it!"));
    var ans = data.answer != null ? String(data.answer) : (weigh(data.left) === weigh(data.right) ? "equal" : (weigh(data.left) > weigh(data.right) ? "left" : "right"));
    var scale = el("div", "scale-row");
    [["left", data.left], ["right", data.right]].forEach(function (pr) {
      var pan = el("button", "scale-pan");
      pan.appendChild(el("div", "pan-items", esc(Array.isArray(pr[1]) ? pr[1].join(" ") : ("⚖️ " + (pr[1] || "")))));
      pan.onclick = function () { if (pr[0] === ans) { pan.classList.add("correct"); win(); } else { pan.classList.add("wrong"); nope("Look again — which has more?"); setTimeout(function () { pan.classList.remove("wrong"); }, 600); } };
      scale.appendChild(pan);
    });
    ctx.body.appendChild(scale);
    if (ans === "equal") { var eq = el("button", "btn", "They're equal!"); eq.onclick = win; ctx.body.appendChild(eq); }
  });

  // ============================================================ WORD / PHONICS

  // Tap letters in order to build the word (extra letters allowed as distractors).
  function buildWord(ctx, letters, answer, blanksLabel) {
    var win = ctx.win, nope = ctx.nope;
    var target = String(answer).toUpperCase().replace(/\s+/g, "");
    var slots = el("div", "word-slots");
    var built = "";
    function paint() { slots.innerHTML = ""; for (var i = 0; i < target.length; i++) slots.appendChild(el("span", "word-slot", esc(built[i] || ""))); }
    paint(); ctx.body.appendChild(slots);
    var tray = el("div", "chip-row"); ctx.body.appendChild(tray);
    var pool = (letters && letters.length ? letters : target.split("")).map(String);
    shuffle(pool).forEach(function (ltr) {
      var b = el("button", "gb-chip letter", esc(ltr.toUpperCase()));
      b.onclick = function () {
        if (b.disabled) return;
        if (ltr.toUpperCase() === target[built.length]) { built += ltr.toUpperCase(); b.disabled = true; b.classList.add("placed"); if (GB.audio) GB.audio.sfx("tick"); paint(); if (built === target) win(); }
        else nope("Try a different letter!");
      };
      tray.appendChild(b);
    });
    GB.shared.hintLadder(ctx.body, [ctx.data.hint || ("It starts with " + target[0] + ".")], function () { built = target; paint(); win(); });
  }
  reg("word-build", function (ctx) { ctx.body.appendChild(el("p", "game-line", "Spell the word!")); buildWord(ctx, ctx.data.letters, ctx.data.answer); });
  reg("anagram", function (ctx) { ctx.body.appendChild(el("p", "game-line", "Unscramble the letters!")); buildWord(ctx, (ctx.data.scrambled != null ? String(ctx.data.scrambled).split("") : null), ctx.data.answer); });

  // Fill the blank: choose (or build) the missing word.
  reg("fill-the-blank", function (ctx) {
    var data = ctx.data, win = ctx.win, nope = ctx.nope;
    ctx.body.appendChild(el("p", "game-line", esc(String(data.sentence || "").replace("___", "______"))));
    if (data.options && data.options.length) {
      var wrap = el("div", "options");
      shuffle(data.options.concat(data.options.indexOf(data.answer) < 0 ? [data.answer] : [])).forEach(function (o) {
        var b = el("button", "opt", esc(o));
        b.onclick = function () { if (String(o) === String(data.answer)) { b.classList.add("correct"); win(); } else { b.classList.add("wrong"); nope(); setTimeout(function () { b.classList.remove("wrong"); }, 600); } };
        wrap.appendChild(b);
      });
      ctx.body.appendChild(wrap);
    } else { buildWord(ctx, null, data.answer); }
  });

  // ============================================================ MUSIC / RHYTHM

  // Tap along to the beat (toddler-friendly; counts taps, always wins).
  reg("rhythm-tap", function (ctx) {
    var data = ctx.data, win = ctx.win;
    var pattern = (data.pattern || [1, 1, 1, 1]);
    var beats = pattern.filter(function (b) { return b; }).length || pattern.length;
    ctx.body.appendChild(el("p", "game-line", "Listen, then tap the drum to the beat!"));
    var listen = el("button", "btn", "🔊 Hear the beat");
    listen.onclick = function () { var t = 0; pattern.forEach(function (b) { if (b && GB.audio) GB.audio.tone(196, 0.12, t, "triangle"); t += (data.tempo ? 60 / data.tempo : 0.4); }); };
    ctx.body.appendChild(listen);
    var drum = el("button", "drum-pad", "🥁"); var taps = 0;
    var meter = el("div", "rhythm-meter"); for (var i = 0; i < beats; i++) meter.appendChild(el("span", "beat-dot"));
    drum.onclick = function () { if (GB.audio) GB.audio.tone(160, 0.12, 0, "triangle"); if (GB.juice) GB.juice.squash(drum); var dots = meter.querySelectorAll(".beat-dot"); if (dots[taps]) dots[taps].classList.add("on"); taps++; if (taps >= beats) win(); };
    ctx.body.appendChild(meter); ctx.body.appendChild(drum);
  });

  // Song builder: tap notes into a strip, hear your tune (free-play, always wins).
  reg("song-builder", function (ctx) {
    var data = ctx.data, win = ctx.win;
    var palette = data.palette || ["C", "D", "E", "G", "A"];
    var bars = data.bars || 6;
    ctx.body.appendChild(el("p", "game-line", "Build a tune — tap notes into the strip!"));
    var strip = el("div", "song-strip"); var song = [];
    for (var i = 0; i < bars; i++) { var cell = el("div", "song-cell"); cell.dataset.i = i; strip.appendChild(cell); }
    ctx.body.appendChild(strip);
    var pal = el("div", "melody-pads");
    var cur = 0;
    palette.forEach(function (n) { var pad = el("button", "melody-pad", esc(n)); pad.onclick = function () { if (GB.audio) GB.audio.tone(GB.audio.freqOf(n), 0.3); if (cur < bars) { strip.children[cur].textContent = n; strip.children[cur].classList.add("filled"); song[cur] = n; cur++; } }; pal.appendChild(pad); });
    ctx.body.appendChild(pal);
    var play = el("button", "btn", "▶ Play my song"); play.onclick = function () { if (GB.audio) GB.audio.playSequence(song.filter(Boolean), { tempo: 0.4 }); }; ctx.body.appendChild(play);
    var done = el("button", "btn ghost", "I love my song! 🎶"); done.onclick = win; ctx.body.appendChild(done);
  });

  // ============================================================ MEMORY

  // Watch the sequence light up, then repeat it (Simon, visual).
  reg("sequence-recall", function (ctx) {
    var data = ctx.data, win = ctx.win, nope = ctx.nope;
    var seq = (data.sequence || []).map(String);
    var pads = data.pads || seq.filter(function (v, i, a) { return a.indexOf(v) === i; });
    ctx.body.appendChild(el("p", "game-line", "Watch the order, then tap it back!"));
    var watch = el("button", "btn", "👀 Show me");
    var grid = el("div", "melody-pads");
    var padEls = {};
    pads.forEach(function (p, i) { var pad = el("button", "melody-pad seq-pad", esc(p)); pad.style.setProperty("--h", (i * 67) % 360); padEls[p] = pad; grid.appendChild(pad); });
    var step = 0, canTap = false;
    function flash(p, t) { setTimeout(function () { var pad = padEls[p]; if (pad) { pad.classList.add("lit"); if (GB.audio) GB.audio.tone(330 + 40 * pads.indexOf(p), 0.25); setTimeout(function () { pad.classList.remove("lit"); }, 320); } }, t); }
    watch.onclick = function () { canTap = false; step = 0; var t = 200; seq.forEach(function (p) { flash(p, t); t += 450; }); setTimeout(function () { canTap = true; }, t); };
    Object.keys(padEls).forEach(function (p) { padEls[p].onclick = function () { if (!canTap) return; if (GB.juice) GB.juice.flash(padEls[p]); if (p === seq[step]) { step++; if (step >= seq.length) win(); } else { step = 0; nope("Oops — watch again!"); } }; });
    ctx.body.appendChild(watch); ctx.body.appendChild(grid);
  });
})();
