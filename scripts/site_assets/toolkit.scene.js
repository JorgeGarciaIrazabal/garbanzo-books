/* GB.scene — an interactive overlay layered on top of the page illustration, so games play
   ON the art instead of as chip rows below it. Coordinates are NORMALIZED 0..1 (origin
   top-left). A legacy percent value (anything > 1) is auto-converted, so existing
   percent-based data keeps working. Degrades to a plain board when the page has no image. */
(function () {
  "use strict";
  var GB = (window.GB = window.GB || {});
  var el = function (t, c, h) { return GB.el(t, c, h); };

  // Normalize a coordinate component: >1 is treated as a percent (legacy).
  function norm(v) { v = Number(v) || 0; return v > 1 ? v / 100 : v; }
  function pct(v) { return (norm(v) * 100).toFixed(3) + "%"; }

  function create(body, page, opts) {
    opts = opts || {};
    var frame = el("div", "scene-frame");
    var hasImg = page && page.image && page.image.file;
    if (hasImg) {
      var img = document.createElement("img");
      img.src = page.image.file; img.alt = (page.image && page.image.alt) || "";
      frame.appendChild(img);
    } else {
      frame.classList.add("scene-board"); // neutral playfield for placeholder builds
    }
    var overlay = el("div", "scene-overlay");
    frame.appendChild(overlay);
    body.appendChild(frame);

    function toLocal(clientX, clientY) {
      var r = frame.getBoundingClientRect();
      return { x: (clientX - r.left) / r.width, y: (clientY - r.top) / r.height };
    }
    // Touch-target floor: ensure a hotspot is at least ~44px regardless of small r.
    function sizeStyle(node, r) {
      var rr = norm(r || 0.09);
      node.style.width = (rr * 100).toFixed(2) + "%";
      node.style.aspectRatio = "1";
      node.style.minWidth = "44px"; node.style.minHeight = "44px";
    }

    var api = {
      frame: frame, overlay: overlay, hasImage: !!hasImg, toLocal: toLocal,
      hotspot: function (o) {
        var h = el("button", "scene-hotspot");
        if (o.label) h.setAttribute("aria-label", o.label);
        var p = o.at || o; // accept {at:{x,y}} or {x,y}
        h.style.left = pct(p.x); h.style.top = pct(p.y);
        sizeStyle(h, o.r);
        if (o.glow) h.classList.add("glow");
        h.onclick = function (e) {
          e.stopPropagation();
          if (h.classList.contains("got")) return;
          h.classList.add("got");
          if (o.onHit) o.onHit(h, e);
        };
        overlay.appendChild(h);
        return h;
      },
      placeItem: function (node, at) {
        node.classList.add("scene-item");
        node.style.left = pct(at.x); node.style.top = pct(at.y);
        overlay.appendChild(node);
        return node;
      },
      dropTarget: function (o) {
        var z = el("div", "scene-target");
        var p = o.at || o;
        z.style.left = pct(p.x); z.style.top = pct(p.y);
        sizeStyle(z, o.r);
        if (o.label) z.appendChild(el("span", "scene-target-label", GB.esc(o.label)));
        overlay.appendChild(z);
        return z;
      },
      missTaps: function (onMiss) {
        frame.addEventListener("click", function (e) {
          if (e.target === frame || e.target === overlay || (e.target.tagName === "IMG")) onMiss(e);
        });
      }
    };
    return api;
  }

  GB.scene = { create: create, norm: norm };
})();
