/* GB.games — the built-in game library. Each game is registered via GB.registerGame(type, fn)
   and receives a context: {box, body, data, it, page, win, nope, hintBtn, gotoNumber,
   scene, dnd, juice, audio, steps, reward, shared}. Every game is always winnable. */
(function () {
  "use strict";
  var GB = (window.GB = window.GB || {});
  var el = function (t, c, h) { return GB.el(t, c, h); };
  var esc = function (s) { return GB.esc(s); };
  var shuffle = function (a) { return GB.shuffle(a); };
  var reg = function (type, fn) { GB.registerGame(type, fn); };

  // --- find every named thing (toggle list) ---
  reg("seek-and-find", function (ctx) {
    var body = ctx.body, data = ctx.data, win = ctx.win;
    var items = data.items || [];
    var wrap = el("div", "chip-row");
    items.forEach(function (item) {
      var label = (item && item.label != null) ? item.label : item;
      var c = el("button", "find-item", "🔍 " + esc(label));
      c.onclick = function () { c.classList.toggle("found"); if (wrap.querySelectorAll(".found").length === items.length) win(); };
      wrap.appendChild(c);
    });
    body.appendChild(wrap);
  });

  // --- phonics: tap the words with the target sound ---
  reg("sound-hunt", function (ctx) {
    var body = ctx.body, data = ctx.data, win = ctx.win, nope = ctx.nope;
    var targets = {};
    (data.words || []).forEach(function (w) { targets[String(w).toLowerCase()] = true; });
    var targetCount = Object.keys(targets).length;
    body.appendChild(el("p", "game-line", "Find the words with the /" + esc(data.sound || "") + "/ sound:"));
    var wrap = el("div", "chip-row");
    shuffle((data.words || []).concat(data.decoys || [])).forEach(function (w) {
      var c = el("button", "hunt-word", esc(w));
      c.onclick = function () {
        if (c.classList.contains("found") || c.classList.contains("wrong")) return;
        if (targets[String(w).toLowerCase()]) { c.classList.add("found"); if (wrap.querySelectorAll(".found").length === targetCount) win(); }
        else { c.classList.add("wrong"); nope(); setTimeout(function () { c.classList.remove("wrong"); }, 600); }
      };
      wrap.appendChild(c);
    });
    body.appendChild(wrap);
  });

  // --- pick the right answer (rhyme / comprehension / riddle / quiz) ---
  reg("rhyme-complete", function (ctx) { GB.shared.quiz(ctx); });
  reg("comprehension-question", function (ctx) { GB.shared.quiz(ctx); });
  reg("riddle", function (ctx) { GB.shared.quiz(ctx); });

  reg("odd-one-out", function (ctx) {
    var body = ctx.body, data = ctx.data, win = ctx.win, nope = ctx.nope, hintBtn = ctx.hintBtn;
    body.appendChild(el("p", "game-line", "Tap the one that doesn't belong:"));
    var wrap = el("div", "options");
    shuffle(data.items || []).forEach(function (o) {
      var b = el("button", "opt", esc(o));
      b.onclick = function () {
        if (String(o) === String(data.answer)) { b.classList.add("correct"); win(); }
        else { b.classList.add("wrong"); nope(); setTimeout(function () { b.classList.remove("wrong"); }, 600); }
      };
      wrap.appendChild(b);
    });
    body.appendChild(wrap); hintBtn(data.hint);
  });

  // --- count things ---
  reg("counting", function (ctx) {
    var body = ctx.body, data = ctx.data, win = ctx.win, nope = ctx.nope;
    body.appendChild(el("p", "game-line", "How many " + esc(data.what || "things") + "?"));
    var row = el("div", "count-row");
    var input = el("input", "num-input"); input.type = "number"; input.inputMode = "numeric"; input.min = "0";
    var b = el("button", "btn", "Check");
    var check = function () { Number(input.value) === Number(data.answer) ? win() : nope(); };
    b.onclick = check; input.addEventListener("keydown", function (e) { if (e.key === "Enter") check(); });
    row.appendChild(input); row.appendChild(b); body.appendChild(row);
  });

  // --- connect each word to its match (click left, then right) ---
  reg("word-match", function (ctx) { GB.shared.matchGame(ctx, "Match each one to its pair:"); });

  // --- branching choice ---
  reg("choice", function (ctx) {
    var body = ctx.body, data = ctx.data;
    var wrap = el("div", "options");
    (data.options || []).forEach(function (o) {
      var b = el("button", "opt big", esc(o.label));
      b.onclick = function () { ctx.gotoNumber(o.goto); };
      wrap.appendChild(b);
    });
    body.appendChild(wrap);
  });

  // --- finger-trace a letter on a canvas ---
  reg("trace-letter", function (ctx) {
    var body = ctx.body, data = ctx.data, win = ctx.win;
    body.appendChild(el("p", "game-line", "Trace the letter — as in " + esc(data.word || "") + ":"));
    var wrap = el("div", "trace-wrap");
    var ghost = el("div", "trace-ghost", esc(data.letter || "?"));
    var cv = document.createElement("canvas"); cv.className = "trace-canvas"; cv.width = 280; cv.height = 280;
    var ctx2 = cv.getContext("2d");
    ctx2.lineWidth = 14; ctx2.lineCap = "round"; ctx2.lineJoin = "round"; ctx2.strokeStyle = "#6b8f71";
    var drawing = false, last = null, painted = 0;
    var pos = function (e) { var r = cv.getBoundingClientRect(); var t = e.touches ? e.touches[0] : e; return { x: (t.clientX - r.left) * cv.width / r.width, y: (t.clientY - r.top) * cv.height / r.height }; };
    var start = function (e) { drawing = true; last = pos(e); e.preventDefault(); };
    var move = function (e) {
      if (!drawing) return;
      var p = pos(e); ctx2.beginPath(); ctx2.moveTo(last.x, last.y); ctx2.lineTo(p.x, p.y); ctx2.stroke();
      painted += Math.hypot(p.x - last.x, p.y - last.y); last = p; e.preventDefault();
      if (painted > 600) win();
    };
    var end = function () { drawing = false; };
    cv.addEventListener("mousedown", start); cv.addEventListener("mousemove", move); window.addEventListener("mouseup", end);
    cv.addEventListener("touchstart", start, { passive: false }); cv.addEventListener("touchmove", move, { passive: false }); cv.addEventListener("touchend", end);
    wrap.appendChild(ghost); wrap.appendChild(cv); body.appendChild(wrap);
  });

  // --- spot the differences (clickable hotspots over a copy of the art) ---
  reg("spot-the-difference", function (ctx) {
    var body = ctx.body, data = ctx.data, page = ctx.page, win = ctx.win, nope = ctx.nope;
    var spots = data.spots || [];
    var total = data.count || spots.length;
    body.appendChild(el("p", "game-line", "Find all " + esc(total) + " differences — tap them!"));
    if (spots.length && page && page.image && page.image.file) {
      var frame = el("div", "spot-frame");
      var img = document.createElement("img"); img.src = page.image.file; img.alt = "";
      frame.appendChild(img);
      var found = 0;
      spots.forEach(function (s) {
        var h = el("button", "spot");
        h.style.left = (s.x || 0) + "%"; h.style.top = (s.y || 0) + "%";
        if (s.r) { h.style.width = h.style.height = s.r + "%"; }
        h.onclick = function () { if (h.classList.contains("got")) return; h.classList.add("got"); found++; if (found >= spots.length) win(); };
        frame.appendChild(h);
      });
      // a couple of decoy taps elsewhere give gentle "try again"
      frame.addEventListener("click", function (e) { if (e.target === frame || e.target === img) nope("Look closely!"); });
      body.appendChild(frame);
    } else {
      var b = el("button", "btn", "I found them all!"); b.onclick = win; body.appendChild(b);
    }
  });

  // --- put the steps in order (move up/down) ---
  reg("drag-order", function (ctx) { GB.shared.orderGame(ctx); });
  reg("memory", function (ctx) { (ctx.data.pairs ? GB.shared.memoryGame : GB.shared.orderGame)(ctx); });

  // --- flip cards to reveal what's hidden ---
  reg("tap-to-reveal", function (ctx) {
    var body = ctx.body, data = ctx.data, win = ctx.win;
    var cards = data.cards || (data.items || []).map(function (x) { return { front: "?", back: x }; });
    var grid = el("div", "card-grid");
    var revealed = 0;
    cards.forEach(function (c) {
      var card = el("button", "flip-card");
      card.innerHTML = '<span class="fc-front">' + esc(c.front || "❔") + '</span><span class="fc-back">' + esc(c.back != null ? c.back : c) + '</span>';
      card.onclick = function () { if (card.classList.contains("flipped")) return; card.classList.add("flipped"); revealed++; if (revealed >= cards.length) win(); };
      grid.appendChild(card);
    });
    body.appendChild(grid);
  });

  // --- sort items into the right buckets (logic, tap-select) ---
  reg("sorting", function (ctx) {
    var body = ctx.body, data = ctx.data, win = ctx.win, nope = ctx.nope;
    var items = shuffle((data.items || []).map(function (x, i) { return { label: x.label != null ? x.label : x, bin: x.bin, id: i }; }));
    var bins = data.bins || [];
    body.appendChild(el("p", "game-line", "Tap an item, then tap where it belongs:"));
    var tray = el("div", "chip-row sort-tray");
    var binRow = el("div", "bin-row");
    var selected = null, placed = 0;
    items.forEach(function (it2) {
      var c = el("button", "sort-item", esc(it2.label));
      c.onclick = function () { tray.querySelectorAll(".sel").forEach(function (x) { x.classList.remove("sel"); }); c.classList.add("sel"); selected = { it: it2, c: c }; };
      tray.appendChild(c);
    });
    bins.forEach(function (bn, bi) {
      var name = bn.label != null ? bn.label : bn;
      var key = bn.key != null ? bn.key : name;
      var bin = el("div", "bin"); bin.appendChild(el("div", "bin-label", esc(name)));
      var slot = el("div", "bin-slot"); bin.appendChild(slot);
      bin.onclick = function () {
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
  });

  // --- what comes next in the pattern? ---
  reg("pattern", function (ctx) {
    var body = ctx.body, data = ctx.data, win = ctx.win, nope = ctx.nope, hintBtn = ctx.hintBtn;
    var seq = data.sequence || [];
    var strip = el("div", "pattern-strip");
    seq.forEach(function (s) { strip.appendChild(el("span", "pat-cell", esc(s))); });
    strip.appendChild(el("span", "pat-cell pat-q", "?"));
    body.appendChild(strip);
    body.appendChild(el("p", "game-line", "What comes next?"));
    var opts = data.options || (data.distractors ? [data.answer].concat(data.distractors) : [data.answer]);
    var wrap = el("div", "options");
    shuffle(opts).forEach(function (o) {
      var b = el("button", "opt", esc(o));
      b.onclick = function () {
        if (String(o) === String(data.answer)) { b.classList.add("correct"); var q = strip.querySelector(".pat-q"); q.textContent = o; q.classList.remove("pat-q"); win(); }
        else { b.classList.add("wrong"); nope(); setTimeout(function () { b.classList.remove("wrong"); }, 600); }
      };
      wrap.appendChild(b);
    });
    body.appendChild(wrap); hintBtn(data.hint);
  });

  // --- music: listen, then play the tune back (Simon-style) ---
  reg("melody", function (ctx) {
    var body = ctx.body, data = ctx.data, win = ctx.win, nope = ctx.nope;
    var audio = ctx.audio || GB.audio;
    var notes = (data.notes || data.sequence || ["C", "E", "G"]).map(String);
    var pads = data.pads || notes.filter(function (v, i, a) { return a.indexOf(v) === i; });
    body.appendChild(el("p", "game-line", "Listen to the tune, then tap it back!"));
    var listen = el("button", "btn", "🔊 Play the tune");
    var canPlay = true;
    var flash = function (pad) { pad.classList.add("lit"); setTimeout(function () { pad.classList.remove("lit"); }, 240); };
    var padEls;
    listen.onclick = function () {
      if (!canPlay) return; canPlay = false;
      audio.playSequence(notes, { tempo: 0.5, dur: 0.42, onNote: function (i, n) { var pad = padEls[pads.indexOf(n)]; if (pad) flash(pad); }, onDone: function () { canPlay = true; } });
    };
    body.appendChild(listen);
    var keyboard = el("div", "melody-pads");
    var step = 0;
    padEls = pads.map(function (n) {
      var pad = el("button", "melody-pad", esc(n));
      pad.onclick = function () {
        audio.tone(audio.freqOf(n), 0.4, 0); flash(pad);
        if (n === notes[step]) { step++; if (step >= notes.length) win(); }
        else { step = 0; nope("Oops — listen again and start over!"); }
      };
      keyboard.appendChild(pad); return pad;
    });
    body.appendChild(keyboard);
  });

  // --- maze: guide the character to the goal ---
  reg("maze", function (ctx) {
    var body = ctx.body, data = ctx.data, win = ctx.win;
    // Accept "#"/"." char grids OR space-separated grids with letter markers
    // (B/#/X = wall, S = start, E = end, everything else = open path).
    var grid = data.grid;
    if (typeof grid === "string") grid = grid.split(/\r?\n/);
    grid = (grid || ["..", ".."]).map(function (r) { return String(r).trim(); }).filter(function (r) { return r.length; })
      .map(function (r) { return /\s/.test(r) ? r.split(/\s+/) : r.split(""); });
    var isWall = function (ch) { return ch === "#" || ch === "B" || ch === "X" || ch === "x"; };
    var rows = grid.length, cols = Math.max.apply(null, grid.map(function (r) { return r.length; }));
    grid = grid.map(function (r) { while (r.length < cols) r.push("."); return r.map(function (ch) { return isWall(ch) ? "#" : ch; }); });
    var start = (data.start || [0, 0]).slice();
    var end = (data.end || [rows - 1, cols - 1]).slice();
    // S/E markers in the grid win over start/end arrays
    for (var r = 0; r < rows; r++) for (var c = 0; c < cols; c++) {
      if (grid[r][c] === "S") { start[0] = r; start[1] = c; grid[r][c] = "."; }
      if (grid[r][c] === "E") { end = [r, c]; grid[r][c] = "."; }
    }
    if (end[0] >= rows || end[1] >= cols) end = [rows - 1, cols - 1];
    if (isWall(grid[start[0]][start[1]])) grid[start[0]][start[1]] = ".";
    var pos = [start[0], start[1]];
    body.appendChild(el("p", "game-line", "Use the arrows (or swipe / arrow keys) to reach 🎯"));
    var board = el("div", "maze");
    board.style.gridTemplateColumns = "repeat(" + cols + ", 1fr)";
    var cells = [];
    for (var rr = 0; rr < rows; rr++) { cells[rr] = []; for (var cc = 0; cc < cols; cc++) {
      var cell = el("div", "maze-cell" + (grid[rr][cc] === "#" ? " wall" : ""));
      if (rr === end[0] && cc === end[1]) cell.appendChild(el("span", "maze-goal", "🎯"));
      board.appendChild(cell); cells[rr][cc] = cell;
    } }
    var hero = el("div", "maze-hero", "🐾");
    function place() { var cell = cells[pos[0]][pos[1]]; cell.appendChild(hero); if (pos[0] === end[0] && pos[1] === end[1]) win(); }
    function move(dr, dc) {
      var nr = pos[0] + dr, nc = pos[1] + dc;
      if (nr < 0 || nc < 0 || nr >= rows || nc >= cols) return;
      if (grid[nr][nc] === "#") { board.classList.remove("bump"); void board.offsetWidth; board.classList.add("bump"); return; }
      pos = [nr, nc]; place();
    }
    body.appendChild(board); place();
    var pad = el("div", "dpad");
    [["↑", -1, 0], ["←", 0, -1], ["→", 0, 1], ["↓", 1, 0]].forEach(function (a) {
      var b = el("button", "dpad-btn dpad-" + a[0], a[0]); b.onclick = function () { move(a[1], a[2]); }; pad.appendChild(b);
    });
    body.appendChild(pad);
    var keyh = function (e) { var m = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }[e.key]; if (m && document.contains(board)) { e.preventDefault(); e.stopPropagation(); move(m[0], m[1]); } };
    board.tabIndex = 0; board.addEventListener("keydown", keyh);
    // swipe
    var sx = 0, sy = 0;
    board.addEventListener("touchstart", function (e) { sx = e.touches[0].clientX; sy = e.touches[0].clientY; }, { passive: true });
    board.addEventListener("touchend", function (e) {
      var dx = e.changedTouches[0].clientX - sx, dy = e.changedTouches[0].clientY - sy;
      if (Math.abs(dx) > Math.abs(dy)) move(0, dx > 0 ? 1 : -1); else move(dy > 0 ? 1 : -1, 0);
    });
  });

  // --- creative free play: color the picture by tapping ---
  reg("coloring", function (ctx) {
    var body = ctx.body, data = ctx.data, win = ctx.win;
    var palette = data.palette || ["#e07a8b", "#7a9cc6", "#6b8f71", "#f0c419", "#d98a5b", "#9b6bd9"];
    var regions = data.regions || ["sky", "ground", "tree", "sun", "house"];
    var color = palette[0];
    var pal = el("div", "palette");
    palette.forEach(function (col) { var sw = el("button", "pal-swatch"); sw.style.background = col; sw.onclick = function () { color = col; pal.querySelectorAll(".sel").forEach(function (x) { x.classList.remove("sel"); }); sw.classList.add("sel"); }; pal.appendChild(sw); });
    pal.firstChild.classList.add("sel");
    var grid = el("div", "color-grid");
    regions.forEach(function (name) { var rg = el("button", "color-region", esc(name)); rg.onclick = function () { rg.style.background = color; rg.style.color = "#fff"; rg.dataset.done = "1"; if (grid.querySelectorAll('[data-done]').length === regions.length) win(); }; grid.appendChild(rg); });
    body.appendChild(pal); body.appendChild(grid);
    var b = el("button", "btn ghost", "I like my picture!"); b.onclick = win; body.appendChild(b);
  });

  GB.registerGame("_default", function (ctx) { var b = el("button", "btn", "I did it!"); b.onclick = ctx.win; ctx.body.appendChild(b); });
})();
