/* GB.games["custom"] — a declarative game interpreter. An author (or an LLM) describes a
   game as DATA: a list of `elements` (draggables / dropzones / hotspots / targets / toggles)
   and a `win` condition. The interpreter renders it using the toolkit and fires win() when
   the condition is met. There is NO author code and NO fail state in the model, so a custom
   game is winnable by construction; a hint ladder + auto-solve is the final backstop.

   data = {
     spec:"v1", stage:"scene"|"board", board:{image?},
     elements:[ {id, kind, label?, emoji?, at?:{x,y}, r?, accepts?:[ids|groups], group?, order?} ],
     win:{ mode:"all-placed"|"matched-pairs"|"ordered"|"sequence"|"all-found"|"toggled-all"|"expression", … },
     hint? | hints?:[…]
   }                                                                                       */
(function () {
  "use strict";
  var GB = (window.GB = window.GB || {});
  var el = function (t, c, h) { return GB.el(t, c, h); };
  var esc = function (s) { return GB.esc(s); };

  GB.registerGame("custom", function (ctx) {
    var data = ctx.data || {};
    var elements = (data.elements || []).filter(function (e) { return e && e.id; });
    var byId = {}; elements.forEach(function (e) { byId[e.id] = e; });
    var onArt = data.stage === "scene" || elements.some(function (e) { return e.at; });

    // ---- state ----
    var placements = {}; // draggableId -> zoneId
    var hits = {};       // hotspot/target id -> true
    var toggles = {};    // toggle id -> bool
    var tapOrder = [];   // ids tapped, in order (for ordered)
    var seqPos = 0;      // for sequence (Simon) mode
    var solved = false;

    // ---- surface ----
    var scene = (onArt && ctx.scene) ? ctx.scene.create(ctx.body, ctx.page) : null;
    var board, tray, zonesRow;
    if (!scene) {
      board = el("div", "custom-board");
      tray = el("div", "chip-row custom-tray");
      zonesRow = el("div", "bin-row custom-zones");
      board.appendChild(zonesRow); board.appendChild(tray);
      ctx.body.appendChild(board);
    }
    var field = ctx.dnd ? ctx.dnd.create() : null;

    function faceOf(e) { return (e.emoji ? e.emoji + " " : "") + (e.label != null ? e.label : e.id); }

    // ---- win evaluation ----
    function evalCond(cond) {
      if (!cond || typeof cond !== "object") return false;
      var mode = cond.mode;
      if (cond.all) return cond.all.every(evalCond);
      if (cond.any) return cond.any.some(evalCond);
      if (cond.not) return !evalCond(cond.not);
      switch (mode) {
        case "all-placed": {
          // Every PLACEABLE draggable is placed; unplaceable draggables are decoys (e.g. the
          // junk you must NOT pack), so they don't block the win.
          var dz = elements.filter(function (e) { return e.kind === "draggable"; });
          var zonesEl = elements.filter(function (e) { return e.kind === "dropzone" || e.kind === "target"; });
          var canPlace = function (d) {
            return zonesEl.some(function (z) {
              var a = z.accepts;
              return !a || !a.length || a.indexOf(d.group) >= 0 || a.indexOf(d.id) >= 0;
            });
          };
          var placeable = dz.filter(canPlace);
          return placeable.length > 0 && placeable.every(function (e) { return placements[e.id]; });
        }
        case "matched-pairs":
          return (cond.pairs || []).every(function (pr) { return placements[pr[0]] === pr[1]; });
        case "all-found":
          return (cond.targets || elements.filter(function (e) { return e.kind === "hotspot" || e.kind === "target"; }).map(function (e) { return e.id; }))
            .every(function (id) { return hits[id]; });
        case "ordered": {
          var want = (cond.order || []).join("|");
          return tapOrder.filter(function (id) { return (cond.order || []).indexOf(id) >= 0; }).join("|") === want && want.length > 0;
        }
        case "sequence":
          return seqPos >= (cond.steps || []).length && (cond.steps || []).length > 0;
        case "toggled-all": {
          var st = cond.state || {};
          return Object.keys(st).length > 0 && Object.keys(st).every(function (id) { return !!toggles[id] === !!st[id]; });
        }
        default: return false; // unknown predicate → not yet satisfied (never throws)
      }
    }
    function check() {
      if (solved) return;
      if (evalCond(data.win)) { solved = true; ctx.win(); }
    }

    // ---- render elements ----
    function makeDraggable(e) {
      var node = el("button", "gb-chip", esc(faceOf(e)));
      if (field) {
        field.draggable(node, {
          id: e.id, group: e.group, label: e.label || e.id
        });
      } else {
        node.onclick = function () { tap(e); };
      }
      return node;
    }
    function makeZone(e) {
      var label = e.label != null ? e.label : e.id;
      if (scene) {
        var z = scene.dropTarget({ at: e.at, r: e.r, label: label });
        if (field) field.dropzone(z, { accepts: e.accepts || e.id, onDrop: function (node) { placements[node.dataset.id] = e.id; if (GB.juice) GB.juice.flash(z); check(); return true; } });
        return z;
      }
      var bin = el("div", "bin");
      bin.appendChild(el("div", "bin-label", esc(label)));
      var slot = el("div", "bin-slot"); bin.appendChild(slot);
      if (field) field.dropzone(slot, { accepts: e.accepts || e.id, relocate: true, onDrop: function (node) { placements[node.dataset.id] = e.id; check(); return true; } });
      zonesRow.appendChild(bin);
      return bin;
    }
    function makeHotspot(e) {
      if (scene) {
        return scene.hotspot({ at: e.at, r: e.r, label: e.label || e.id, glow: true, onHit: function () { hit(e); } });
      }
      var b = el("button", "opt", esc(faceOf(e)));
      b.onclick = function () { b.classList.add("correct"); hit(e); };
      ctx.body.appendChild(b);
      return b;
    }
    function makeToggle(e) {
      var b = el("button", "opt toggle", esc(faceOf(e)));
      b.onclick = function () { toggles[e.id] = !toggles[e.id]; b.classList.toggle("on", toggles[e.id]); if (GB.audio) GB.audio.sfx("tick"); check(); };
      (scene ? null : ctx.body).appendChild(b);
      if (scene) ctx.body.appendChild(b);
      return b;
    }
    function tap(e) { tapOrder.push(e.id); seqStep(e); check(); }
    function hit(e) { hits[e.id] = true; tapOrder.push(e.id); seqStep(e); if (GB.audio) GB.audio.sfx("reveal"); check(); }
    function seqStep(e) {
      if (!data.win || data.win.mode !== "sequence") return;
      var steps = data.win.steps || [];
      if (e.id === steps[seqPos]) seqPos++;
      else if (steps.indexOf(e.id) >= 0) { seqPos = (e.id === steps[0]) ? 1 : 0; ctx.nope("Oops — start the sequence again!"); }
    }

    // Draggables first into the tray (board) or onto the art (scene), then zones/hotspots.
    elements.forEach(function (e) {
      if (e.kind === "draggable") {
        var node = makeDraggable(e);
        if (scene && e.at) scene.placeItem(node, e.at); else if (!scene) tray.appendChild(node);
        else ctx.body.appendChild(node);
      }
    });
    elements.forEach(function (e) {
      if (e.kind === "dropzone" || e.kind === "target") makeZone(e);
      else if (e.kind === "hotspot") makeHotspot(e);
      else if (e.kind === "toggle") makeToggle(e);
    });

    // ---- always-winnable backstop: hint ladder whose last rung auto-solves ----
    function autoSolve() {
      if (solved) return;
      solved = true;
      if (GB.juice) GB.juice.confetti();
      ctx.win();
    }
    var hints = data.hints || (data.hint ? [data.hint] : []);
    if (GB.shared && GB.shared.hintLadder) GB.shared.hintLadder(ctx.body, hints, autoSolve);
    else if (hints.length) ctx.hintBtn(hints[0]);
  });
})();
