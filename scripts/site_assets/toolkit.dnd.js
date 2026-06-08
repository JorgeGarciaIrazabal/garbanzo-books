/* GB.dnd — true pointer drag-and-drop with snapping + a mandatory keyboard fallback.
   Call GB.dnd.create() to get an isolated drag field (its own dropzones), then register
   draggables and dropzones on it. Pointer math is screen-space (follows the finger), so it
   is scale-correct on any zoom. Keyboard: focus a piece, Enter to pick up, Arrow/Tab to
   cycle the highlighted target, Enter to drop, Esc to cancel — so no game needs a pointer. */
(function () {
  "use strict";
  var GB = (window.GB = window.GB || {});
  var el = function (t, c, h) { return GB.el(t, c, h); };

  function accepts(zone, node) {
    var a = zone.opts.accepts;
    if (a == null) return true;
    if (typeof a === "function") return !!a(node);
    var g = node.dataset ? node.dataset.group : null;
    if (Array.isArray(a)) return a.indexOf(g) >= 0 || a.indexOf(node.dataset && node.dataset.id) >= 0;
    return String(a) === String(g) || String(a) === String(node.dataset && node.dataset.id);
  }

  function create() {
    var zones = [];
    var picked = null;      // keyboard: currently lifted draggable
    var kbTarget = -1;      // keyboard: highlighted zone index

    function clearHighlights() { zones.forEach(function (z) { z.node.classList.remove("over", "kb-target"); }); }

    function tryDrop(node, zoneEntry) {
      // onDrop returns true to accept (we relocate + snap), false to reject (nudge).
      var ok = zoneEntry.opts.onDrop ? zoneEntry.opts.onDrop(node, zoneEntry.node) : true;
      if (ok) {
        node.classList.add("placed"); node.removeAttribute("tabindex");
        if (zoneEntry.opts.relocate !== false) { zoneEntry.node.appendChild(node); node.style.transform = ""; node.style.left = ""; node.style.top = ""; node.style.position = ""; }
        node.classList.add("gb-snap"); setTimeout(function () { node.classList.remove("gb-snap"); }, 350);
        if (GB.audio) GB.audio.sfx("drop");
        if (GB.juice) GB.juice.burstAt(node, { count: 8 });
        return true;
      }
      if (GB.juice) GB.juice.nudge(node);
      if (GB.audio) GB.audio.sfx("nope");
      return false;
    }

    function zoneAtPoint(node, x, y) {
      for (var i = 0; i < zones.length; i++) {
        var r = zones[i].node.getBoundingClientRect();
        if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom && accepts(zones[i], node)) return zones[i];
      }
      return null;
    }

    function draggable(node, opts) {
      opts = opts || {};
      node.classList.add("gb-draggable");
      node.style.touchAction = "none";
      if (opts.group != null) node.dataset.group = opts.group;
      if (opts.id != null) node.dataset.id = opts.id;
      node.tabIndex = 0;
      node.setAttribute("role", "button");
      if (opts.label) node.setAttribute("aria-label", opts.label);

      // ---- pointer drag ----
      var dragging = false, startX = 0, startY = 0;
      node.addEventListener("pointerdown", function (e) {
        if (node.classList.contains("placed") && opts.lockPlaced !== false) return;
        dragging = true; startX = e.clientX; startY = e.clientY;
        node.classList.add("gb-dragging");
        try { node.setPointerCapture(e.pointerId); } catch (err) {}
        if (GB.audio) GB.audio.sfx("pickup");
        if (GB.juice) GB.juice.haptic(8);
        e.preventDefault();
      });
      node.addEventListener("pointermove", function (e) {
        if (!dragging) return;
        var dx = e.clientX - startX, dy = e.clientY - startY;
        node.style.transform = "translate(" + dx + "px," + dy + "px)";
        var z = zoneAtPoint(node, e.clientX, e.clientY);
        clearHighlights(); if (z) z.node.classList.add("over");
      });
      function endDrag(e) {
        if (!dragging) return;
        dragging = false; node.classList.remove("gb-dragging");
        clearHighlights();
        var z = zoneAtPoint(node, e.clientX, e.clientY);
        if (z) { if (!tryDrop(node, z)) node.style.transform = ""; }
        else { node.style.transform = ""; }
      }
      node.addEventListener("pointerup", endDrag);
      node.addEventListener("pointercancel", function () { dragging = false; node.classList.remove("gb-dragging"); node.style.transform = ""; clearHighlights(); });

      // ---- keyboard fallback ----
      node.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          if (picked !== node) { picked = node; kbTarget = -1; node.classList.add("gb-picked"); cycleTarget(0); }
          else if (kbTarget >= 0 && zones[kbTarget]) { var z = zones[kbTarget]; releaseKb(); tryDrop(node, z); }
        } else if (picked === node && (e.key === "ArrowRight" || e.key === "ArrowDown" || e.key === "Tab")) {
          e.preventDefault(); cycleTarget(1);
        } else if (picked === node && (e.key === "ArrowLeft" || e.key === "ArrowUp")) {
          e.preventDefault(); cycleTarget(-1);
        } else if (e.key === "Escape") { releaseKb(); }
      });
      function cycleTarget(dir) {
        if (!zones.length) return;
        var tries = 0;
        do { kbTarget = (kbTarget + dir + zones.length) % zones.length; tries++; } while (!accepts(zones[kbTarget], node) && tries <= zones.length);
        clearHighlights(); if (zones[kbTarget]) zones[kbTarget].node.classList.add("kb-target");
      }
      function releaseKb() { node.classList.remove("gb-picked"); picked = null; kbTarget = -1; clearHighlights(); }

      return node;
    }

    function dropzone(node, opts) {
      node.classList.add("gb-dropzone");
      var entry = { node: node, opts: opts || {} };
      zones.push(entry);
      return node;
    }

    return { draggable: draggable, dropzone: dropzone, zones: zones };
  }

  GB.dnd = { create: create };
})();
