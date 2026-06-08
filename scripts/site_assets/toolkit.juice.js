/* GB.juice — feedback effects (particles, squash/stretch, shake, haptics).
   Every effect respects prefers-reduced-motion: when reduced, motion is skipped but any
   END STATE (e.g. a piece landing) is still applied by the caller via a class, never via a
   keyframe alone — so reduced-motion users never see things stuck mid-animation. */
(function () {
  "use strict";
  var GB = (window.GB = window.GB || {});
  var el = function (t, c, h) { return GB.el(t, c, h); };
  var COLORS = ["#6b8f71", "#d98a5b", "#f0c419", "#7a9cc6", "#e07a8b"];

  function reduced() { return !!GB.reduceMotion; }

  // Full-screen celebration (kept identical to the original confetti()).
  function confetti() {
    if (reduced()) return;
    var reader = document.querySelector(".reader") || document.body;
    var layer = el("div", "confetti");
    for (var i = 0; i < 36; i++) {
      var bit = el("i");
      bit.style.left = Math.random() * 100 + "%";
      bit.style.background = COLORS[i % COLORS.length];
      bit.style.animationDelay = (Math.random() * 0.25) + "s";
      bit.style.transform = "rotate(" + (Math.random() * 360) + "deg)";
      layer.appendChild(bit);
    }
    reader.appendChild(layer);
    setTimeout(function () { layer.remove(); }, 1800);
  }

  // A localized particle burst at a screen point (x,y in viewport px).
  function burst(x, y, opts) {
    if (reduced()) return;
    opts = opts || {};
    var n = opts.count || 14;
    var colors = opts.colors || COLORS;
    var emoji = opts.emoji;
    var layer = el("div", "gb-burst");
    for (var i = 0; i < n; i++) {
      var ang = (Math.PI * 2 * i) / n + Math.random() * 0.5;
      var dist = 40 + Math.random() * 60;
      var p = el("i", null, emoji ? GB.esc(emoji) : "");
      if (!emoji) p.style.background = colors[i % colors.length];
      p.style.left = x + "px"; p.style.top = y + "px";
      p.style.setProperty("--dx", (Math.cos(ang) * dist).toFixed(1) + "px");
      p.style.setProperty("--dy", (Math.sin(ang) * dist).toFixed(1) + "px");
      layer.appendChild(p);
    }
    document.body.appendChild(layer);
    setTimeout(function () { layer.remove(); }, 900);
  }

  // Fire a burst centered on an element.
  function burstAt(node, opts) {
    if (!node || reduced()) return;
    var r = node.getBoundingClientRect();
    burst(r.left + r.width / 2, r.top + r.height / 2, opts);
  }

  function squash(node) {
    if (!node || reduced()) return;
    node.classList.remove("gb-squash"); void node.offsetWidth; node.classList.add("gb-squash");
    setTimeout(function () { node.classList.remove("gb-squash"); }, 400);
  }
  function shake(node) {
    if (!node || reduced()) return;
    node.classList.remove("shake"); void node.offsetWidth; node.classList.add("shake");
    setTimeout(function () { node.classList.remove("shake"); }, 450);
  }
  function nudge(node) {
    if (!node || reduced()) return;
    node.classList.remove("gb-nudge"); void node.offsetWidth; node.classList.add("gb-nudge");
    setTimeout(function () { node.classList.remove("gb-nudge"); }, 400);
  }
  function flash(node) {
    if (!node) return;
    node.classList.add("lit"); setTimeout(function () { node.classList.remove("lit"); }, 240);
  }
  function haptic(pattern) {
    if (reduced()) return;
    try { if (navigator && navigator.vibrate) navigator.vibrate(pattern || 12); } catch (e) {}
  }

  GB.juice = {
    confetti: confetti, burst: burst, burstAt: burstAt,
    squash: squash, shake: shake, nudge: nudge, flash: flash, haptic: haptic
  };
})();
