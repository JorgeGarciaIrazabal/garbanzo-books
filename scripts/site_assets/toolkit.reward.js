/* GB.reward — a cross-page collectible arc. Each solved game drops a sticker into a tray
   that rides in the corner of the stage; the last page shows the full collection (with
   outlined placeholders for any game the reader skipped). Persisted in sessionStorage so a
   fresh visit starts a fresh collection. All storage is guarded — private mode never crashes. */
(function () {
  "use strict";
  var GB = (window.GB = window.GB || {});
  var el = function (t, c, h) { return GB.el(t, c, h); };
  var esc = function (s) { return GB.esc(s); };

  var mem = {}; // in-memory fallback when storage is unavailable

  function keyFor(story) { return "gb:rewards:" + ((story && (story.slug || story.title)) || "book"); }
  function load(story) {
    var k = keyFor(story);
    try { var raw = sessionStorage.getItem(k); if (raw) return JSON.parse(raw); } catch (e) {}
    return mem[k] || { earned: {} };
  }
  function save(story, state) {
    var k = keyFor(story);
    mem[k] = state;
    try { sessionStorage.setItem(k, JSON.stringify(state)); } catch (e) {}
  }

  // Default sticker emoji by mechanic family, used when the author sets no reward.emoji.
  var FAMILY_ICON = {
    "hidden-object": "🔎", "find-in-scene": "🔎", "tap-on-art": "👆", "hotspot-reveal": "✨", "place-on-scene": "📍",
    "drag-sort": "🧺", "drag-match": "🔗", "jigsaw": "🧩", "dress-up": "👒", "feed-the-thing": "🍪",
    "connect-dots": "🐾", "scratch-reveal": "🪙", "sliding-puzzle": "🖼️", "balance-scale": "⚖️",
    "word-build": "🔤", "anagram": "🔡", "fill-the-blank": "✏️", "rhythm-tap": "🥁", "song-builder": "🎶",
    "sequence-recall": "🧠", "melody": "🎵", "maze": "🌀", "seek-and-find": "🔍", "spot-the-difference": "🔬",
    "coloring": "🎨", "memory": "🃏", "custom": "⭐"
  };
  function iconFor(it) {
    if (it.reward && it.reward.emoji) return it.reward.emoji;
    return FAMILY_ICON[it.type] || "⭐";
  }

  function pagesWithGames(story) {
    return ((story && story.pages) || []).filter(function (p) { return p.interaction; });
  }

  // Called by the controller's win() — records a sticker for this page (idempotent).
  function earnFor(story, it, page) {
    var state = load(story);
    var id = (it.reward && it.reward.id) || ("p" + (page && page.number));
    if (state.earned[id]) { updateTray(story); return; }
    state.earned[id] = { icon: iconFor(it), label: (it.reward && it.reward.label) || it.prompt || "Sticker", page: page && page.number };
    save(story, state);
    updateTray(story, true);
  }

  // Called by render() on each page — mounts/refreshes the corner tray.
  function onPage(story, page, idx, total, extrasBox) {
    if (!pagesWithGames(story).length) return;
    updateTray(story);
  }

  function trayHost() {
    var stage = document.getElementById("stage");
    return stage || document.body;
  }
  function updateTray(story, pop) {
    var host = trayHost();
    var state = load(story);
    var count = Object.keys(state.earned).length;
    var total = pagesWithGames(story).length;
    var tray = host.querySelector(".reward-tray");
    if (!tray) {
      tray = el("div", "reward-tray");
      tray.setAttribute("aria-live", "polite");
      tray.setAttribute("aria-label", "Sticker collection");
      host.appendChild(tray);
    }
    tray.innerHTML = "";
    tray.appendChild(el("span", "reward-star", "⭐"));
    tray.appendChild(el("span", "reward-count", count + "/" + total));
    if (pop && !GB.reduceMotion) { tray.classList.remove("pop"); void tray.offsetWidth; tray.classList.add("pop"); }
  }

  // The end-of-book collection grid.
  function renderCollection(container, story) {
    if (!container) return;
    var existing = container.querySelector(".reward-collection");
    if (existing) existing.remove();
    var state = load(story);
    var games = pagesWithGames(story);
    var wrap = el("div", "reward-collection");
    wrap.appendChild(el("h3", "reward-title", "Look what you found! 🌟"));
    var grid = el("div", "reward-grid");
    games.forEach(function (p) {
      var it = p.interaction;
      var id = (it.reward && it.reward.id) || ("p" + p.number);
      var got = state.earned[id];
      var badge = el("div", "reward-badge" + (got ? "" : " empty"));
      badge.appendChild(el("span", "reward-emoji", got ? esc(got.icon) : "·"));
      badge.appendChild(el("span", "reward-label", esc(got ? got.label : "Keep playing!")));
      grid.appendChild(badge);
    });
    wrap.appendChild(grid);
    container.appendChild(wrap);
    if (!GB.reduceMotion) { wrap.classList.add("pop"); }
  }

  GB.reward = { earnFor: earnFor, onPage: onPage, renderCollection: renderCollection, iconFor: iconFor };
})();
