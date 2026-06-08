/* GB.shared — reusable game sub-renderers (quiz / match / order / memory) and the
   always-winnable helpers (a progressive hint ladder whose final rung gently auto-solves,
   plus a winnable guard games can opt into). */
(function () {
  "use strict";
  var GB = (window.GB = window.GB || {});
  var el = function (t, c, h) { return GB.el(t, c, h); };
  var esc = function (s) { return GB.esc(s); };
  var shuffle = function (a) { return GB.shuffle(a); };

  // shared quiz (one correct answer among options)
  function quiz(ctx) {
    var body = ctx.body, data = ctx.data, it = ctx.it, win = ctx.win, nope = ctx.nope, hintBtn = ctx.hintBtn;
    var answer = it.type === "comprehension-question" ? (data.options || [])[data.answer_index] : data.answer;
    var opts = data.options || (data.distractors ? [data.answer].concat(data.distractors) : [data.answer]);
    if (it.type === "rhyme-complete" && data.sentence) body.appendChild(el("p", "game-line", esc(data.sentence.replace("___", "______"))));
    if ((it.type === "riddle" || it.type === "comprehension-question" || it.type === "quiz") && (data.question)) body.appendChild(el("p", "game-line", esc(data.question)));
    var wrap = el("div", "options");
    shuffle(opts).forEach(function (o) {
      var b = el("button", "opt", esc(o));
      b.onclick = function () {
        if (String(o) === String(answer)) { b.classList.add("correct"); win(); }
        else { b.classList.add("wrong"); nope(); setTimeout(function () { b.classList.remove("wrong"); }, 600); }
      };
      wrap.appendChild(b);
    });
    body.appendChild(wrap); hintBtn(data.hint);
  }

  // shared connect-the-pairs matcher (click left, then right)
  function matchGame(ctx, line) {
    var body = ctx.body, data = ctx.data, win = ctx.win, nope = ctx.nope;
    var pairs = data.pairs || [];
    body.appendChild(el("p", "game-line", line));
    var grid = el("div", "match-grid");
    var lefts = el("div", "match-col"), rights = el("div", "match-col");
    var selL = null, done = 0;
    pairs.forEach(function (pr, i) {
      var a = el("button", "match-cell", esc(pr[0])); a.dataset.k = i;
      a.onclick = function () { if (a.classList.contains("matched")) return; lefts.querySelectorAll(".sel").forEach(function (x) { x.classList.remove("sel"); }); a.classList.add("sel"); selL = a; };
      lefts.appendChild(a);
    });
    shuffle(pairs.map(function (pr, i) { return { v: pr[1], k: i }; })).forEach(function (r) {
      var b = el("button", "match-cell", esc(r.v)); b.dataset.k = r.k;
      b.onclick = function () {
        if (b.classList.contains("matched") || !selL) return;
        if (selL.dataset.k === b.dataset.k) { selL.classList.add("matched"); b.classList.add("matched"); selL.classList.remove("sel"); selL = null; done++; if (done === pairs.length) win(); }
        else { b.classList.add("wrong"); nope(); setTimeout(function () { b.classList.remove("wrong"); }, 500); }
      };
      rights.appendChild(b);
    });
    grid.appendChild(lefts); grid.appendChild(rights); body.appendChild(grid);
  }

  // shared put-in-order game (up/down arrows — the accessible fallback drag-order also keeps)
  function orderGame(ctx) {
    var body = ctx.body, data = ctx.data, win = ctx.win, nope = ctx.nope;
    var correct = data.sequence || [];
    var cur = shuffle(correct);
    if (correct.length > 1 && cur.join("|") === correct.join("|")) cur = shuffle(correct);
    body.appendChild(el("p", "game-line", "Put these in the right order:"));
    var list = el("div", "order-list");
    function paint() {
      list.innerHTML = "";
      cur.forEach(function (item, i) {
        var row = el("div", "order-row");
        row.appendChild(el("span", "order-text", esc(item)));
        var ups = el("div", "order-btns");
        var up = el("button", "order-arrow", "↑"); up.disabled = i === 0; up.onclick = function () { var t = cur[i - 1]; cur[i - 1] = cur[i]; cur[i] = t; paint(); };
        var dn = el("button", "order-arrow", "↓"); dn.disabled = i === cur.length - 1; dn.onclick = function () { var t = cur[i + 1]; cur[i + 1] = cur[i]; cur[i] = t; paint(); };
        ups.appendChild(up); ups.appendChild(dn); row.appendChild(ups); list.appendChild(row);
      });
    }
    paint();
    var check = el("button", "btn", "Check my order");
    check.onclick = function () { cur.join("|") === correct.join("|") ? win() : nope("Not quite — keep arranging!"); };
    body.appendChild(list); body.appendChild(check);
  }

  // shared memory card-match game (flip two cards, find the matching pair)
  function memoryGame(ctx) {
    var body = ctx.body, data = ctx.data, win = ctx.win;
    var pairs = data.pairs || [];
    body.appendChild(el("p", "game-line", "Flip two cards to find a matching pair:"));
    var cards = [];
    pairs.forEach(function (pr, i) { cards.push({ pid: i, face: pr[0] }); cards.push({ pid: i, face: pr[1] }); });
    var grid = el("div", "card-grid");
    var first = null, lock = false, matched = 0;
    shuffle(cards).forEach(function (c) {
      var card = el("button", "flip-card");
      card.innerHTML = '<span class="fc-front">❔</span><span class="fc-back">' + esc(c.face) + '</span>';
      card.dataset.pid = c.pid;
      card.onclick = function () {
        if (lock || card.classList.contains("flipped") || card.classList.contains("matched")) return;
        card.classList.add("flipped");
        if (!first) { first = card; return; }
        if (first.dataset.pid === card.dataset.pid) {
          first.classList.add("matched"); card.classList.add("matched"); first = null; matched++;
          if (matched === pairs.length) win();
        } else {
          lock = true; var a = first, b = card; first = null;
          setTimeout(function () { a.classList.remove("flipped"); b.classList.remove("flipped"); lock = false; }, 850);
        }
      };
      grid.appendChild(card);
    });
    body.appendChild(grid);
  }

  // Progressive hint ladder. Each press reveals the next hint; after the last hint a gentle
  // "Show me" appears that calls onSolve() — the always-winnable backstop, never a dead end.
  function hintLadder(body, hints, onSolve) {
    hints = (hints || []).filter(Boolean);
    if (!hints.length && !onSolve) return;
    var i = 0;
    var panel = el("div", "hint"); panel.hidden = true;
    var btn = el("button", "btn ghost hint-btn", "💡 Hint");
    btn.onclick = function () {
      if (i < hints.length) {
        panel.hidden = false; panel.textContent = hints[i]; i++;
        if (i >= hints.length && onSolve) btn.textContent = "✨ Show me";
        else if (i >= hints.length) btn.disabled = true;
      } else if (onSolve) {
        onSolve();
      }
    };
    body.appendChild(btn); body.appendChild(panel);
  }

  // Opt-in winnable guard: after maxTries gentle fails, offer the auto-solve.
  function guaranteeWinnable(ctx, opts) {
    opts = opts || {};
    var max = opts.maxTries || 4;
    var tries = 0, offered = false;
    return {
      fail: function (msg) {
        ctx.nope(msg); tries++;
        if (tries >= max && !offered && opts.solve) {
          offered = true;
          var b = el("button", "btn ghost", "✨ Show me");
          b.onclick = function () { opts.solve(); };
          ctx.body.appendChild(b);
        }
      }
    };
  }

  GB.shared = {
    quiz: quiz, matchGame: matchGame, orderGame: orderGame, memoryGame: memoryGame,
    hintLadder: hintLadder, guaranteeWinnable: guaranteeWinnable
  };
})();
