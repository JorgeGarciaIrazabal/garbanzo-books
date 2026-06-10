/* gx.arcade — REAL games. Six arcade mechanics (catch, flap, run, pop, toss, steer) built on
   the vendored Kaplay engine (vendor/kaplay.js, MIT — sprites, game loop, input, particles),
   wrapped in a story-skinning adapter so each game is ~60 lines of pure mechanic.

   The contract every arcade game shares:
     * lazy: the ~190KB engine loads only when the kid taps ▶ Play on an arcade page;
     * fullscreen: the game plays in an overlay ON TOP of the reader, backdropped by the
       page's own illustration, so it visibly belongs to THIS page of THIS book;
     * skinnable: every noun (player, things to catch, things to dodge) is an emoji or
       {emoji,label} straight from interaction.data — the story is the skin;
     * always winnable: no fail states (a bonk is a giggle, never a game-over), progress
       only goes up, and a rubber-band assist ladder ("🪄 Easier!" after a stall, then
       "✨ Finish it!") is the final backstop — mirroring the board games' hint ladder;
     * graceful: no WebGL / engine-load failure / prefers-reduced-motion → a calm DOM
       fallback of the same beat renders in the normal game sheet. Nothing blocks the book.

   Payload shapes are documented in methodology/interactivity.md (arcade section). */
(function () {
  "use strict";
  const GB = window.GB;
  const h = GB.h, esc = GB.esc, skin = GB.skin;
  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

  /* ====================================================================
     THE ADAPTER (GB.arcade)
     ==================================================================== */

  // Where the reader assets live — derived from this script's own URL so the vendored
  // engine resolves from any page depth. Falls back to "assets/" for inline harnesses.
  let ASSET_ROOT = "assets/";
  try {
    const me = document.currentScript && document.currentScript.src;
    if (me) ASSET_ROOT = me.replace(/[?#].*$/, "").replace(/[^/]+$/, "");
  } catch (e) {}

  let _webgl = null;
  function hasWebGL() {
    if (_webgl != null) return _webgl;
    try {
      const c = document.createElement("canvas");
      _webgl = !!(c.getContext("webgl2") || c.getContext("webgl") || c.getContext("experimental-webgl"));
    } catch (e) { _webgl = false; }
    return _webgl;
  }
  // Arcade games are motion games; reduced-motion readers get the calm fallback by design.
  const available = () => !GB.reduceMotion && hasWebGL();

  let _loading = null;
  function loadEngine() {
    if (window.kaplay) return Promise.resolve(window.kaplay);
    if (_loading) return _loading;
    _loading = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = ASSET_ROOT + "vendor/kaplay.js";
      s.onload = () => (window.kaplay ? resolve(window.kaplay) : reject(new Error("kaplay missing")));
      s.onerror = () => { _loading = null; reject(new Error("kaplay failed to load")); };
      document.head.appendChild(s);
    });
    return _loading;
  }

  // Emoji → sprite data-URL (the engine's bitmap font has no emoji).
  const _emojiCache = {};
  function emojiDataUrl(ch, px = 96) {
    const key = ch + "@" + px;
    if (_emojiCache[key]) return _emojiCache[key];
    const c = document.createElement("canvas");
    c.width = c.height = px;
    const g = c.getContext("2d");
    g.font = `${Math.round(px * 0.82)}px "Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",serif`;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText(ch, px / 2, px / 2 + px * 0.04);
    return (_emojiCache[key] = c.toDataURL());
  }

  // difficulty / speed words → a single pace multiplier
  function speedFactor(it, data) {
    const map = { gentle: 0.72, easy: 0.72, normal: 1, medium: 1, wild: 1.3, hard: 1.3 };
    return map[data.speed] || map[(it && it.difficulty) || ""] || 1;
  }

  // The intro card, rendered in the normal game sheet: icons, a how-to line, ▶ Play.
  // When the engine can't run, Play renders the calm fallback in the same sheet instead.
  function intro(ctx, spec) {
    const card = h("div", "arcade-intro");
    const icons = (spec.sprites || []).slice(0, 4).map((s) => esc(skin(s).emoji)).join(" ");
    if (icons) card.appendChild(h("div", "arcade-intro-icons", icons));
    if (spec.how) card.appendChild(h("p", "game-line", esc(spec.how)));
    const play = h("button", "btn arcade-play", "▶ Play!");
    play.onclick = () => {
      if (!available()) { card.remove(); spec.fallback(ctx); return; }
      play.disabled = true;
      play.textContent = "Loading…";
      loadEngine()
        .then(() => { play.disabled = false; play.textContent = "▶ Play!"; open(ctx, spec); })
        .catch(() => { card.remove(); spec.fallback(ctx); }); // engine unreachable → never a dead end
    };
    card.appendChild(play);
    ctx.body.appendChild(card);
  }

  // The fullscreen stage: overlay + engine + HUD + assist ladder + win/teardown plumbing.
  function open(ctx, spec) {
    const overlay = h("div", "arcade-overlay");
    const top = h("div", "arcade-top");
    top.appendChild(h("span", "arcade-prompt", esc((ctx.it && ctx.it.prompt) || "Let's play!")));
    const closeBtn = h("button", "arcade-close", "✕");
    closeBtn.setAttribute("aria-label", "Back to the story");
    top.appendChild(closeBtn);
    overlay.appendChild(top);
    const host = h("div", "arcade-host");
    overlay.appendChild(host);
    const hud = h("div", "arcade-hud");
    const score = h("div", "arcade-score", "");
    const assistBtn = h("button", "btn ghost arcade-assist", "🪄 Easier!");
    assistBtn.hidden = true;
    hud.appendChild(score);
    hud.appendChild(assistBtn);
    overlay.appendChild(hud);
    document.body.appendChild(overlay);
    document.body.classList.add("arcade-open");

    const W = host.clientWidth || 800, H = host.clientHeight || 520;
    let k = null, closed = false, won = false;

    function cleanup() {
      if (closed) return;
      closed = true;
      clearInterval(stallTimer);
      try { if (k) k.quit(); } catch (e) {}
      overlay.remove();
      document.body.classList.remove("arcade-open");
      document.removeEventListener("visibilitychange", onVis);
    }
    GB.onTeardown(cleanup); // the reader closes us on page change / sheet close
    closeBtn.onclick = cleanup;
    const onVis = () => { try { k.debug.paused = document.hidden; } catch (e) {} };
    document.addEventListener("visibilitychange", onVis);

    try {
      k = window.kaplay({
        root: host, width: W, height: H, global: false,
        background: spec.background || "#10142b",
        touchToMouse: true,
        pixelDensity: Math.min(window.devicePixelRatio || 1, 2),
        texFilter: "linear",
      });
    } catch (e) {
      cleanup();
      return spec.fallback(ctx);
    }

    // ---- HUD: progress pips + counter ----
    let goalTotal = 0, got = 0, autoWin = true;
    function paintScore() {
      if (!goalTotal) { score.textContent = ""; return; }
      const max = Math.min(goalTotal, 12);
      let pips = "";
      for (let i = 0; i < max; i++)
        pips += `<span class="arcade-pip${i < Math.round((got * max) / goalTotal) ? " on" : ""}"></span>`;
      score.innerHTML = `${pips} <span class="arcade-count">${got} / ${goalTotal}</span>`;
    }

    // ---- always-winnable assist ladder: stall ⇒ "Easier!" ⇒ … ⇒ "Finish it!" ----
    let assists = 0, lastProgress = Date.now();
    const stallTimer = setInterval(() => {
      if (closed || won) return;
      if (Date.now() - lastProgress > 22000) {
        assistBtn.hidden = false;
        if (assists >= 2) assistBtn.textContent = "✨ Finish it!";
      }
    }, 4000);

    const stage = {
      k, W, H, overlay, host,
      u: Math.min(W, H) / 600,        // scale unit: speeds/sizes feel the same on any screen
      tune: { speed: 1, size: 1 },    // games read these live; the assist ladder nudges them

      // Preload emoji sprites; resolves to {emoji → spriteName} once the engine has them.
      sprites(emojis, px) {
        const names = {};
        (emojis || []).forEach((ch) => {
          if (!ch || names[ch]) return;
          const name = "em_" + Array.from(ch).map((c) => c.codePointAt(0).toString(16)).join("_");
          k.loadSprite(name, emojiDataUrl(ch, px || 96));
          names[ch] = name;
        });
        return new Promise((resolve) => k.onLoad(() => resolve(names)));
      },

      // Dimmed page-art backdrop so the game visibly belongs to THIS page.
      backdrop(page) {
        const file = page && page.image && page.image.file;
        if (!file) return;
        k.loadSprite("gb_backdrop", file);
        k.onLoad(() => {
          try {
            const bg = k.add([k.sprite("gb_backdrop"), k.pos(W / 2, H / 2), k.anchor("center"),
              k.scale(1), k.opacity(0.45), k.z(-20)]);
            const sc = Math.max(W / bg.width, H / bg.height);
            bg.scale = k.vec2(sc, sc);
            k.add([k.rect(W, H), k.color(10, 12, 28), k.opacity(0.35), k.z(-19)]);
          } catch (e) {}
        });
      },

      goal(n, o) {
        goalTotal = Math.max(1, Math.round(n || 1));
        got = 0;
        autoWin = !(o && o.auto === false);
        paintScore();
      },
      progress() {
        if (won) return;
        got++;
        lastProgress = Date.now();
        paintScore();
        GB.audio.sfx(autoWin && got >= goalTotal ? "win" : "pop");
        if (autoWin && got >= goalTotal) stage.win();
      },
      score: () => got,

      // Floating encouragement that never interrupts play.
      toast(text) {
        const t = h("div", "arcade-toast", esc(text));
        overlay.appendChild(t);
        setTimeout(() => t.remove(), 1600);
      },

      // Pointer-follow steering (drag anywhere; the object eases toward the finger) plus
      // arrow keys. axis "x" (catch) or "xy" (steer). Call the returned fn each frame.
      steer(obj, o = {}) {
        const axis = o.axis || "x";
        const ease = o.ease || 8;
        const keys = {};
        ["left", "right", "up", "down"].forEach((key) => {
          k.onKeyDown(key, () => (keys[key] = true));
          k.onKeyRelease(key, () => (keys[key] = false));
        });
        let pointerActive = false;
        k.onMouseDown(() => (pointerActive = true));
        k.onMouseRelease(() => (pointerActive = false));
        return () => {
          const dt = k.dt();
          const kbSpeed = (o.kbSpeed || 380) * stage.u;
          if (keys.left) obj.pos.x -= kbSpeed * dt;
          if (keys.right) obj.pos.x += kbSpeed * dt;
          if (axis === "xy" && keys.up) obj.pos.y -= kbSpeed * dt;
          if (axis === "xy" && keys.down) obj.pos.y += kbSpeed * dt;
          if (pointerActive) {
            const m = k.mousePos();
            obj.pos.x += (m.x - obj.pos.x) * Math.min(1, ease * dt);
            if (axis === "xy") obj.pos.y += (m.y - obj.pos.y) * Math.min(1, ease * dt);
          }
          const pad = (o.pad || 40) * stage.u;
          obj.pos.x = Math.max(pad, Math.min(W - pad, obj.pos.x));
          if (axis === "xy") obj.pos.y = Math.max(pad, Math.min(H - pad, obj.pos.y));
          if (o.lockY != null) obj.pos.y = o.lockY;
        };
      },

      // A juicy in-canvas burst (sprite shards flying out) — on every catch/pop/hit.
      burst(pos, spriteName, n = 6) {
        try {
          for (let i = 0; i < n; i++) {
            const ang = Math.random() * Math.PI * 2, sp = rand(120, 280) * stage.u;
            const p = k.add([
              k.sprite(spriteName), k.pos(pos.x, pos.y), k.anchor("center"),
              k.scale(rand(0.25, 0.45)), k.opacity(1), k.z(50),
              { vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp - 60 * stage.u },
            ]);
            p.onUpdate(() => {
              p.pos.x += p.vx * k.dt();
              p.pos.y += p.vy * k.dt();
              p.vy += 500 * stage.u * k.dt();
              p.opacity -= 1.8 * k.dt();
              if (p.opacity <= 0) k.destroy(p);
            });
          }
        } catch (e) {}
      },

      // Repeating spawner whose interval is re-read each round (so assist slows it live).
      every(intervalFn, fn) {
        (function next() {
          if (closed || won) return;
          k.wait(intervalFn(), () => {
            if (closed || won) return;
            fn();
            next();
          });
        })();
      },

      win() {
        if (won || closed) return;
        won = true;
        got = Math.max(got, goalTotal);
        paintScore();
        try { k.add([k.rect(W, H), k.color(255, 255, 255), k.opacity(0.18), k.z(90)]); } catch (e) {}
        GB.juice.confetti();
        GB.audio.chime(true);
        stage.toast((ctx.it && ctx.it.feedback && ctx.it.feedback.correct) || "You did it! 🎉");
        setTimeout(() => {
          cleanup();
          ctx.win(); // the standard sheet celebration: sticker + "Keep reading ›"
        }, 1300);
      },
      close: cleanup,
      isClosed: () => closed,
    };

    assistBtn.onclick = () => {
      assists++;
      lastProgress = Date.now();
      assistBtn.hidden = true;
      if (assists >= 3) return stage.win(); // the final backstop — never a dead end
      stage.tune.speed *= 0.68;
      stage.tune.size *= 1.25;
      stage.toast("There you go — nice and easy! 🪄");
    };

    Promise.resolve()
      .then(() => spec.run(stage, ctx))
      .catch(() => {
        // A buggy payload must never strand the reader mid-overlay.
        cleanup();
        spec.fallback(ctx);
      });
  }

  GB.arcade = { available, loadEngine, intro, open, speedFactor, emojiDataUrl, assetRoot: () => ASSET_ROOT };

  /* ====================================================================
     CALM FALLBACK (shared)
     A gently animated tap board with the same skin and beat as the arcade
     game — used when the engine can't run. Always winnable.
     ==================================================================== */
  function calmTap(ctx, { how, targets, decoys = [], goal, missLine }) {
    targets = targets.map((t) => skin(t));
    decoys = decoys.map((d) => skin(d));
    goal = Math.min(goal || targets.length, 12);
    ctx.body.appendChild(h("p", "game-line", esc(how)));
    const grid = h("div", "calm-grid");
    let got = 0;
    const cells = [];
    for (let i = 0; i < goal; i++) cells.push({ s: targets[i % targets.length], ok: true });
    decoys.slice(0, Math.max(2, Math.round(goal / 3))).forEach((d) => cells.push({ s: d, ok: false }));
    GB.shuffle(cells).forEach(({ s, ok }, i) => {
      const b = h("button", "calm-cell", esc(s.emoji));
      b.style.animationDelay = (i % 7) * 0.35 + "s";
      if (s.label) b.setAttribute("aria-label", s.label);
      b.onclick = () => {
        if (b.disabled) return;
        if (ok) {
          b.disabled = true;
          b.classList.add("popped");
          GB.juice.burstAt(b, { emoji: s.emoji, count: 6 });
          GB.audio.sfx("pop");
          if (++got >= goal) ctx.win();
        } else {
          GB.juice.nudge(b);
          ctx.nope(missLine || "Whoops — not that one!");
        }
      };
      grid.appendChild(b);
    });
    ctx.body.appendChild(grid);
  }

  /* ====================================================================
     THE SIX ARCADE GAMES
     ==================================================================== */
  const def = GB.define;

  // ---------------- arcade-catch: steer the catcher, catch what falls ----------------
  // data: { player, catch:[...], avoid:[...], goal, speed }
  def("arcade-catch", { icon: "🧺", arcade: true, render(ctx) {
    const data = ctx.data;
    const player = skin(data.player, "🧺");
    const goodPool = (data.catch || ["⭐"]).map((s) => skin(s));
    const badPool = (data.avoid || []).map((s) => skin(s));
    intro(ctx, {
      sprites: [player.emoji, ...goodPool.map((g) => g.emoji)],
      how: data.how || "Drag left and right — catch them before they fall!",
      fallback: (c) => calmTap(c, {
        how: "Tap to catch them all!",
        targets: goodPool, decoys: badPool, goal: data.goal || 8,
      }),
      async run(stage) {
        const k = stage.k, u = stage.u, sf = speedFactor(ctx.it, data);
        stage.backdrop(ctx.page);
        stage.goal(data.goal || 8);
        const names = await stage.sprites([player.emoji, ...goodPool.map((g) => g.emoji), ...badPool.map((b) => b.emoji)]);
        if (stage.isClosed()) return;
        const py = stage.H - 80 * u;
        const pl = k.add([k.sprite(names[player.emoji]), k.pos(stage.W / 2, py), k.anchor("center"),
          k.scale(1.15 * u), k.rotate(0), k.z(10)]);
        const move = stage.steer(pl, { axis: "x", lockY: py });
        k.onUpdate(() => {
          move();
          const s = 1.15 * u * stage.tune.size;
          pl.scale = k.vec2(s, s);
        });
        stage.every(() => (rand(0.75, 1.2) / (sf * stage.tune.speed)), () => {
          const isGood = badPool.length ? Math.random() < 0.74 : true;
          const s = isGood ? pick(goodPool) : pick(badPool);
          const it = k.add([k.sprite(names[s.emoji]), k.pos(rand(50 * u, stage.W - 50 * u), -40 * u),
            k.anchor("center"), k.scale(0.8 * u), k.rotate(0), k.z(5),
            { vy: rand(150, 215) * u * sf, sway: rand(-45, 45) * u, t: Math.random() * 6, live: true }]);
          it.onUpdate(() => {
            const dt = k.dt();
            it.t += dt;
            it.pos.y += it.vy * stage.tune.speed * dt;
            it.pos.x += Math.sin(it.t * 3) * it.sway * dt;
            it.angle = Math.sin(it.t * 2) * 14;
            const sc = 0.8 * u * stage.tune.size;
            it.scale = k.vec2(sc, sc);
            if (it.live && it.pos.dist(pl.pos) < (62 * u * stage.tune.size + 28 * u)) {
              it.live = false;
              if (isGood) {
                stage.burst(it.pos, names[s.emoji]);
                k.destroy(it);
                stage.progress();
              } else {
                GB.audio.sfx("bonk");
                stage.toast(data.avoid_line || "Eek — not that one! 🙈");
                it.vy = -180 * u;          // it comically bounces off the catcher
                it.sway = rand(120, 220) * u * (Math.random() < 0.5 ? -1 : 1);
                k.wait(0.8, () => { try { k.destroy(it); } catch (e) {} });
              }
            } else if (it.pos.y > stage.H + 60 * u) {
              k.destroy(it);
            }
          });
        });
      },
    });
  } });

  // ---------------- arcade-pop: things drift by — pop the right ones ----------------
  // data: { pop:[...], avoid:[...], goal, speed }
  def("arcade-pop", { icon: "🎈", arcade: true, render(ctx) {
    const data = ctx.data;
    const popPool = (data.pop || ["🎈"]).map((s) => skin(s));
    const avoidPool = (data.avoid || []).map((s) => skin(s));
    intro(ctx, {
      sprites: popPool.map((p) => p.emoji),
      how: data.how || "Tap them to pop them — quick, before they float away!",
      fallback: (c) => calmTap(c, {
        how: "Tap to pop them all!",
        targets: popPool, decoys: avoidPool, goal: data.goal || 10,
      }),
      async run(stage) {
        const k = stage.k, u = stage.u, sf = speedFactor(ctx.it, data);
        stage.backdrop(ctx.page);
        stage.goal(data.goal || 10);
        const names = await stage.sprites([...popPool.map((p) => p.emoji), ...avoidPool.map((a) => a.emoji)]);
        if (stage.isClosed()) return;
        stage.every(() => (rand(0.5, 0.9) / (sf * stage.tune.speed)), () => {
          const isPop = avoidPool.length ? Math.random() < 0.72 : true;
          const s = isPop ? pick(popPool) : pick(avoidPool);
          const it = k.add([k.sprite(names[s.emoji]), k.pos(rand(60 * u, stage.W - 60 * u), stage.H + 50 * u),
            k.anchor("center"), k.scale(0.95 * u), k.area(), k.z(5), isPop ? "pop" : "nopop",
            { vy: rand(55, 110) * u * sf, sway: rand(-40, 40) * u, t: Math.random() * 6, popped: false, sname: names[s.emoji] }]);
          it.onUpdate(() => {
            const dt = k.dt();
            it.t += dt;
            it.pos.y -= it.vy * stage.tune.speed * dt;
            it.pos.x += Math.sin(it.t * 2.4) * it.sway * dt;
            const sc = 0.95 * u * stage.tune.size;
            it.scale = k.vec2(sc, sc);
            if (it.pos.y < -60 * u) k.destroy(it);
          });
        });
        k.onClick("pop", (it) => {
          if (it.popped) return;
          it.popped = true;
          stage.burst(it.pos, it.sname, 7);
          GB.juice.haptic(10);
          k.destroy(it);
          stage.progress();
        });
        k.onClick("nopop", (it) => {
          GB.audio.sfx("bonk");
          stage.toast(data.avoid_line || "Not that one — it's ticklish! 🙊");
          it.sway = rand(160, 260) * u * (Math.random() < 0.5 ? -1 : 1);
        });
      },
    });
  } });

  // ---------------- arcade-flap: tap to fly through the gaps ----------------
  // data: { player, obstacle, gates, goal, speed }
  def("arcade-flap", { icon: "🕊️", arcade: true, render(ctx) {
    const data = ctx.data;
    const player = skin(data.player, "🕊️");
    const obstacle = skin(data.obstacle, "☁️");
    const gates = data.gates || data.goal || 6;
    intro(ctx, {
      sprites: [player.emoji, obstacle.emoji],
      how: data.how || "Tap anywhere to flap — fly through the gaps!",
      fallback: (c) => calmTap(c, {
        how: "Tap the gaps to fly through!",
        targets: [player.emoji], decoys: [obstacle.emoji], goal: gates,
        missLine: "Bonk! Aim for the open sky!",
      }),
      async run(stage) {
        const k = stage.k, u = stage.u, sf = speedFactor(ctx.it, data);
        stage.backdrop(ctx.page);
        stage.goal(gates);
        const names = await stage.sprites([player.emoji, obstacle.emoji]);
        if (stage.isClosed()) return;
        const pl = k.add([k.sprite(names[player.emoji]), k.pos(stage.W * 0.28, stage.H * 0.45),
          k.anchor("center"), k.scale(1.0 * u), k.rotate(0), k.z(10), { vy: 0, invuln: 0 }]);
        const G = 1250 * u, FLAP = -440 * u;
        const flap = () => { pl.vy = FLAP; GB.audio.sfx("jump"); };
        k.onMousePress(flap);
        k.onKeyPress("space", flap);
        k.onKeyPress("up", flap);

        const speedX = () => 165 * u * sf * stage.tune.speed;
        k.onUpdate(() => {
          const dt = k.dt();
          pl.vy += G * dt;
          pl.pos.y += pl.vy * dt;
          pl.angle = Math.max(-28, Math.min(40, pl.vy * 0.05));
          if (pl.invuln > 0) pl.invuln -= dt;
          pl.opacity = pl.invuln > 0 ? 0.55 : 1;
          if (pl.pos.y < 30 * u) { pl.pos.y = 30 * u; pl.vy = 60 * u; }
          if (pl.pos.y > stage.H - 30 * u) { pl.pos.y = stage.H - 30 * u; pl.vy = FLAP * 0.6; }
        });

        stage.every(() => 2.5 / (sf * stage.tune.speed), () => {
          const gapH = Math.min(stage.H * 0.5, stage.H * 0.34 * stage.tune.size);
          const gapY = rand(stage.H * 0.28, stage.H * 0.72);
          const step = 58 * u;
          const gate = { passed: false, pieces: [] };
          const addPiece = (y) => {
            const o = k.add([k.sprite(names[obstacle.emoji]), k.pos(stage.W + 60 * u, y),
              k.anchor("center"), k.scale(0.9 * u), k.z(4)]);
            gate.pieces.push(o);
            o.onUpdate(() => {
              o.pos.x -= speedX() * k.dt();
              if (o.pos.x < -80 * u) k.destroy(o);
              else if (pl.invuln <= 0 && o.pos.dist(pl.pos) < 48 * u) {
                pl.invuln = 1.1;
                pl.vy = -260 * u;            // a bouncy bonk, never a death
                GB.audio.sfx("bonk");
                stage.toast("Bonk! Keep flying! 💨");
              }
            });
          };
          for (let y = gapY - gapH / 2 - step / 2; y > -step; y -= step) addPiece(y);
          for (let y = gapY + gapH / 2 + step / 2; y < stage.H + step; y += step) addPiece(y);
          // an invisible gate sensor: passing the gap scores
          const sensor = k.add([k.pos(stage.W + 60 * u, gapY), k.z(1)]);
          sensor.onUpdate(() => {
            sensor.pos.x -= speedX() * k.dt();
            if (!gate.passed && sensor.pos.x < pl.pos.x) {
              gate.passed = true;
              GB.audio.sfx("whoosh");
              stage.progress();
              k.destroy(sensor);
            } else if (sensor.pos.x < -80 * u) {
              k.destroy(sensor);
            }
          });
        });
      },
    });
  } });

  // ---------------- arcade-run: tap to jump, collect, reach the finish ----------------
  // data: { player, obstacles:[...], collect, goal, finish, speed }
  def("arcade-run", { icon: "🏃", arcade: true, render(ctx) {
    const data = ctx.data;
    const player = skin(data.player, "🏃");
    const obstaclePool = (data.obstacles || ["🪨"]).map((s) => skin(s));
    const collectS = skin(data.collect, "⭐");
    const finishS = skin(data.finish, "🏁");
    const goal = data.goal || 7;
    intro(ctx, {
      sprites: [player.emoji, collectS.emoji, finishS.emoji],
      how: data.how || "Tap to jump (tap twice for a BIG jump) — grab them all and reach the finish!",
      fallback: (c) => calmTap(c, {
        how: "Tap to scoop them up on the way!",
        targets: [collectS], decoys: obstaclePool, goal,
      }),
      async run(stage) {
        const k = stage.k, u = stage.u, sf = speedFactor(ctx.it, data);
        stage.backdrop(ctx.page);
        stage.goal(goal, { auto: false }); // win = crossing the finish flag, not the count
        const names = await stage.sprites([player.emoji, collectS.emoji, finishS.emoji,
          ...obstaclePool.map((o) => o.emoji)]);
        if (stage.isClosed()) return;
        const groundY = stage.H - 64 * u;
        k.add([k.rect(stage.W, 64 * u), k.pos(0, groundY + 32 * u), k.anchor("left"),
          k.color(34, 40, 64), k.opacity(0.85), k.z(2)]);
        const pl = k.add([k.sprite(names[player.emoji]), k.pos(stage.W * 0.22, groundY),
          k.anchor("center"), k.scale(1.1 * u), k.rotate(0), k.z(10),
          { vy: 0, jumps: 0, invuln: 0, stumble: 0 }]);
        const G = 1500 * u;
        const jump = () => {
          if (pl.jumps >= 2) return;
          pl.vy = -560 * u * (pl.jumps ? 0.85 : 1);
          pl.jumps++;
          GB.audio.sfx("jump");
        };
        k.onMousePress(jump);
        k.onKeyPress("space", jump);
        k.onKeyPress("up", jump);

        const speedX = () => 250 * u * sf * stage.tune.speed * (pl.stumble > 0 ? 0.45 : 1);
        let finished = false;
        k.onUpdate(() => {
          const dt = k.dt();
          pl.vy += G * dt;
          pl.pos.y += pl.vy * dt;
          if (pl.pos.y >= groundY) { pl.pos.y = groundY; pl.vy = 0; pl.jumps = 0; }
          pl.angle = pl.jumps ? Math.min(20, -pl.vy * 0.03) : Math.sin(k.time() * 14) * 5; // run wobble
          if (pl.invuln > 0) pl.invuln -= dt;
          if (pl.stumble > 0) pl.stumble -= dt;
          pl.opacity = pl.invuln > 0 ? 0.55 : 1;
        });

        const mover = (o, onMeet, meetR) => o.onUpdate(() => {
          o.pos.x -= speedX() * k.dt();
          if (o.pos.x < -80 * u) k.destroy(o);
          else if (o.pos.dist(pl.pos) < meetR) onMeet(o);
        });

        stage.every(() => rand(1.3, 2.1) / (sf * stage.tune.speed), () => {
          const s = pick(obstaclePool);
          const o = k.add([k.sprite(names[s.emoji]), k.pos(stage.W + 60 * u, groundY + 6 * u),
            k.anchor("center"), k.scale(0.85 * u), k.z(5), { hitOnce: false }]);
          mover(o, () => {
            if (pl.invuln > 0 || o.hitOnce) return;
            o.hitOnce = true;
            pl.invuln = 1.2;
            pl.stumble = 0.7;               // a comic stumble, never a stop
            GB.audio.sfx("bonk");
            stage.toast("Whoops! 😵‍💫 Keep running!");
          }, 44 * u);
        });
        stage.every(() => rand(1.0, 1.7) / (sf * stage.tune.speed), () => {
          if (finished) return;
          const c = k.add([k.sprite(names[collectS.emoji]),
            k.pos(stage.W + 60 * u, groundY - rand(10, 190) * u),
            k.anchor("center"), k.scale(0.8 * u * stage.tune.size), k.z(6), { got: false }]);
          mover(c, () => {
            if (c.got) return;
            c.got = true;
            stage.burst(c.pos, names[collectS.emoji]);
            k.destroy(c);
            stage.progress();
            if (stage.score() >= goal && !finished) {
              finished = true;
              stage.toast(`${finishS.emoji} The finish is coming up!`);
              const f = k.add([k.sprite(names[finishS.emoji]), k.pos(stage.W + 120 * u, groundY - 10 * u),
                k.anchor("center"), k.scale(1.5 * u), k.z(7)]);
              mover(f, () => stage.win(), 50 * u);
            }
          }, 52 * u * stage.tune.size);
        });
      },
    });
  } });

  // ---------------- arcade-toss: slingshot it into the target ----------------
  // data: { projectile, target, goal, speed }
  def("arcade-toss", { icon: "🎯", arcade: true, render(ctx) {
    const data = ctx.data;
    const proj = skin(data.projectile, "🍎");
    const target = skin(data.target, "🧺");
    const goal = data.goal || 4;
    intro(ctx, {
      sprites: [proj.emoji, target.emoji],
      how: data.how || "Drag back like a slingshot, let go to throw — land it in the target!",
      fallback: (c) => calmTap(c, {
        how: `Tap every ${target.label || "target"} you can!`,
        targets: [target], decoys: [], goal,
      }),
      async run(stage) {
        const k = stage.k, u = stage.u, sf = speedFactor(ctx.it, data);
        stage.backdrop(ctx.page);
        stage.goal(goal);
        const names = await stage.sprites([proj.emoji, target.emoji]);
        if (stage.isClosed()) return;
        const HOME = k.vec2(stage.W * 0.2, stage.H - 90 * u);
        const G = 900 * u;
        const tgt = k.add([k.sprite(names[target.emoji]), k.pos(stage.W * 0.78, stage.H * 0.45),
          k.anchor("center"), k.scale(1.5 * u), k.z(5), { t: 0 }]);
        tgt.onUpdate(() => {
          tgt.t += k.dt();
          tgt.pos.y = stage.H * 0.45 + Math.sin(tgt.t * 1.1 * sf * stage.tune.speed) * 60 * u;
          const sc = 1.5 * u * stage.tune.size;
          tgt.scale = k.vec2(sc, sc);
        });
        const ball = k.add([k.sprite(names[proj.emoji]), k.pos(HOME.x, HOME.y), k.anchor("center"),
          k.scale(1.0 * u), k.rotate(0), k.z(10), { vx: 0, vy: 0, flying: false }]);
        // aim preview dots
        const dots = Array.from({ length: 9 }, () =>
          k.add([k.circle(4 * u), k.pos(-99, -99), k.opacity(0), k.z(8), k.color(255, 235, 170)]));
        let aiming = false, aimStart = null;
        const aimVel = (m) => {
          const v = k.vec2((aimStart.x - m.x) * 5, (aimStart.y - m.y) * 5);
          const mag = Math.hypot(v.x, v.y), cap = 1300 * u;
          return mag > cap ? k.vec2((v.x * cap) / mag, (v.y * cap) / mag) : v;
        };
        k.onMousePress(() => { if (!ball.flying) { aiming = true; aimStart = k.mousePos(); } });
        k.onMouseRelease(() => {
          if (!aiming) return;
          aiming = false;
          dots.forEach((d) => (d.opacity = 0));
          const v = aimVel(k.mousePos());
          if (Math.hypot(v.x, v.y) < 60 * u) return; // a stray tap isn't a throw
          ball.vx = Math.max(v.x, 80 * u);           // always toss forward
          ball.vy = v.y;
          ball.flying = true;
          GB.audio.sfx("whoosh");
        });
        const reset = () => {
          ball.flying = false;
          ball.pos = k.vec2(HOME.x, HOME.y);
          ball.vx = ball.vy = 0;
          ball.angle = 0;
        };
        k.onUpdate(() => {
          const dt = k.dt();
          if (aiming && !ball.flying) {
            const v = aimVel(k.mousePos());
            for (let i = 0; i < dots.length; i++) {
              const t = 0.08 * (i + 1);
              dots[i].pos = k.vec2(ball.pos.x + Math.max(v.x, 80 * u) * t,
                ball.pos.y + v.y * t + 0.5 * G * t * t);
              dots[i].opacity = 0.85 - i * 0.08;
            }
          }
          if (!ball.flying) return;
          ball.vy += G * dt;
          ball.pos.x += ball.vx * dt;
          ball.pos.y += ball.vy * dt;
          ball.angle += 320 * dt;
          if (ball.pos.dist(tgt.pos) < 58 * u * stage.tune.size) {
            stage.burst(ball.pos, names[proj.emoji], 8);
            GB.juice.haptic(14);
            reset();
            stage.progress();
          } else if (ball.pos.y > stage.H + 60 * u || ball.pos.x > stage.W + 60 * u || ball.pos.x < -60 * u) {
            stage.toast(pick(["So close! 🎯", "Almost! Try again!", "Big swing! Once more!"]));
            reset();
          }
        });
      },
    });
  } });

  // ---------------- arcade-steer: fly around, collect, dodge ----------------
  // data: { player, collect, avoid:[...], goal, speed }
  def("arcade-steer", { icon: "🚀", arcade: true, render(ctx) {
    const data = ctx.data;
    const player = skin(data.player, "🚀");
    const collectS = skin(data.collect, "⭐");
    const avoidPool = (data.avoid || []).map((s) => skin(s));
    const goal = data.goal || 8;
    intro(ctx, {
      sprites: [player.emoji, collectS.emoji],
      how: data.how || "Drag your finger to steer — collect them all, dodge the rest!",
      fallback: (c) => calmTap(c, {
        how: "Tap to collect them all!",
        targets: [collectS], decoys: avoidPool, goal,
      }),
      async run(stage) {
        const k = stage.k, u = stage.u, sf = speedFactor(ctx.it, data);
        stage.backdrop(ctx.page);
        stage.goal(goal);
        const names = await stage.sprites([player.emoji, collectS.emoji,
          ...avoidPool.map((a) => a.emoji)]);
        if (stage.isClosed()) return;
        const pl = k.add([k.sprite(names[player.emoji]), k.pos(stage.W / 2, stage.H / 2),
          k.anchor("center"), k.scale(1.05 * u), k.rotate(0), k.z(10), { invuln: 0 }]);
        const move = stage.steer(pl, { axis: "xy", ease: 7 });
        k.onUpdate(() => {
          move();
          if (pl.invuln > 0) pl.invuln -= k.dt();
          pl.opacity = pl.invuln > 0 ? 0.55 : 1;
          pl.angle = Math.sin(k.time() * 3) * 6;
        });
        const spawnStar = () => {
          const c = k.add([k.sprite(names[collectS.emoji]),
            k.pos(rand(60 * u, stage.W - 60 * u), rand(60 * u, stage.H - 60 * u)),
            k.anchor("center"), k.scale(0.85 * u), k.z(5), { t: Math.random() * 6, got: false }]);
          c.onUpdate(() => {
            c.t += k.dt();
            const sc = (0.85 + Math.sin(c.t * 4) * 0.12) * u * stage.tune.size;
            c.scale = k.vec2(sc, sc);
            if (!c.got && c.pos.dist(pl.pos) < 56 * u * stage.tune.size) {
              c.got = true;
              stage.burst(c.pos, names[collectS.emoji]);
              k.destroy(c);
              stage.progress();
              spawnStar();
            }
          });
        };
        for (let i = 0; i < 3; i++) spawnStar();
        avoidPool.slice(0, 4).forEach((s, i) => {
          const a = k.add([k.sprite(names[s.emoji]),
            k.pos(rand(80 * u, stage.W - 80 * u), rand(80 * u, stage.H - 80 * u)),
            k.anchor("center"), k.scale(1.0 * u), k.rotate(0), k.z(6),
            { vx: rand(70, 130) * u * (i % 2 ? 1 : -1), vy: rand(60, 110) * u * (i % 3 ? 1 : -1) }]);
          a.onUpdate(() => {
            const dt = k.dt(), sp = sf * stage.tune.speed;
            a.pos.x += a.vx * sp * dt;
            a.pos.y += a.vy * sp * dt;
            if (a.pos.x < 50 * u || a.pos.x > stage.W - 50 * u) a.vx *= -1;
            if (a.pos.y < 50 * u || a.pos.y > stage.H - 50 * u) a.vy *= -1;
            a.angle += 40 * dt;
            if (pl.invuln <= 0 && a.pos.dist(pl.pos) < 52 * u) {
              pl.invuln = 1.1;
              // a bouncy knockback, never a penalty
              const dx = pl.pos.x - a.pos.x, dy = pl.pos.y - a.pos.y;
              const m = Math.hypot(dx, dy) || 1;
              pl.pos.x += (dx / m) * 60 * u;
              pl.pos.y += (dy / m) * 60 * u;
              GB.audio.sfx("bonk");
              stage.toast(data.avoid_line || "Wobble! 😵‍💫 Keep going!");
            }
          });
        });
      },
    });
  } });
})();
