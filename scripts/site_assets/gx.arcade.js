/* gx.arcade — REAL games. Twelve arcade mechanics (catch, flap, run, pop, toss, steer,
   snake, shoot, maze, build, whack, bounce) built on the vendored Kaplay engine
   (vendor/kaplay.js, MIT — sprites, game loop, input, particles), wrapped in a
   story-skinning adapter so each game is ~60–100 lines of pure mechanic.

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

  /* ====================================================================
     SHARED INPUT: swipe + arrow keys → a 4-way direction (snake, maze)
     ==================================================================== */
  const DIRS = { left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1] };
  function dirPad(k, onDir) {
    ["left", "right", "up", "down"].forEach((key) => k.onKeyPress(key, () => onDir(key)));
    let start = null;
    k.onMousePress(() => { start = k.mousePos(); });
    k.onMouseDown(() => {
      if (!start) return;
      const m = k.mousePos();
      const dx = m.x - start.x, dy = m.y - start.y;
      if (Math.hypot(dx, dy) < 26) return;
      onDir(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "right" : "left") : (dy > 0 ? "down" : "up"));
      start = m; // re-arm, so one long curving swipe can steer again and again
    });
    k.onMouseRelease(() => { start = null; });
  }

  // ---------------- arcade-snake: classic snake — slither, gobble, GROW ----------------
  // data: { player, body, food:[...], avoid:[...], goal, speed }
  def("arcade-snake", { icon: "🐍", arcade: true, render(ctx) {
    const data = ctx.data;
    const player = skin(data.player, "🐍");
    const body = data.body ? skin(data.body) : null;
    const foodPool = (data.food || ["🍎"]).map((s) => skin(s));
    const avoidPool = (data.avoid || []).map((s) => skin(s));
    const goal = data.goal || 8;
    intro(ctx, {
      sprites: [player.emoji, ...foodPool.map((f) => f.emoji)],
      how: data.how || "Swipe (or use the arrows) to slither — gobble them all and GROW!",
      fallback: (c) => calmTap(c, { how: "Tap to gobble them all!", targets: foodPool, decoys: avoidPool, goal }),
      async run(stage) {
        const k = stage.k, u = stage.u, sf = speedFactor(ctx.it, data);
        stage.backdrop(ctx.page);
        stage.goal(goal);
        const names = await stage.sprites([player.emoji, ...(body ? [body.emoji] : []),
          ...foodPool.map((f) => f.emoji), ...avoidPool.map((a) => a.emoji)]);
        if (stage.isClosed()) return;

        const cell = Math.max(40, 52 * u);
        const cols = Math.max(9, Math.floor((stage.W - 16 * u) / cell));
        const rows = Math.max(6, Math.floor((stage.H - 100 * u) / cell));
        const ox = (stage.W - cols * cell) / 2, oy = (stage.H - rows * cell) / 2 + 16 * u;
        const at = (c, r) => k.vec2(ox + (c + 0.5) * cell, oy + (r + 0.5) * cell);

        const segs = [{ c: 3, r: (rows >> 1) }, { c: 2, r: (rows >> 1) }, { c: 1, r: (rows >> 1) }];
        let dir = "right", nextDir = "right", grow = 0;
        dirPad(k, (d) => {
          const [dx, dy] = DIRS[d], [cx, cy] = DIRS[dir];
          if (dx === -cx && dy === -cy) return; // no instant U-turn into your own neck
          nextDir = d;
        });

        const head = k.add([k.sprite(names[player.emoji]), k.pos(at(segs[0].c, segs[0].r)),
          k.anchor("center"), k.scale((cell / 96) * 1.25), k.rotate(0), k.z(10)]);
        const tailObjs = [];
        function addTail() {
          const o = body
            ? k.add([k.sprite(names[body.emoji]), k.pos(head.pos.x, head.pos.y), k.anchor("center"),
                k.scale((cell / 96) * 0.9), k.z(9)])
            : k.add([k.circle(cell * 0.32), k.pos(head.pos.x, head.pos.y), k.anchor("center"),
                k.color(255, 204, 92), k.opacity(0.95), k.z(9)]);
          tailObjs.push(o);
        }
        for (let i = 1; i < segs.length; i++) addTail();

        const taken = (c, r) => segs.some((s) => s.c === c && s.r === r);
        function freeCell() {
          for (let i = 0; i < 200; i++) {
            const c = Math.floor(rand(0, cols)), r = Math.floor(rand(0, rows));
            if (!taken(c, r) && !(food && food.cell.c === c && food.cell.r === r) &&
                !decoys.some((d) => d.cell.c === c && d.cell.r === r)) return { c, r };
          }
          return { c: 0, r: 0 };
        }
        let food = null;
        const decoys = [];
        function spawnFood() {
          const s = pick(foodPool), cl = freeCell();
          const o = k.add([k.sprite(names[s.emoji]), k.pos(at(cl.c, cl.r)), k.anchor("center"),
            k.scale(cell / 96), k.z(5), { t: Math.random() * 6 }]);
          o.onUpdate(() => {
            o.t += k.dt();
            const sc = (cell / 96) * (1 + Math.sin(o.t * 4) * 0.1) * stage.tune.size;
            o.scale = k.vec2(sc, sc);
          });
          food = { cell: cl, obj: o, s };
        }
        spawnFood();
        avoidPool.slice(0, 2).forEach((s) => {
          const cl = freeCell();
          decoys.push({ cell: cl, s,
            obj: k.add([k.sprite(names[s.emoji]), k.pos(at(cl.c, cl.r)), k.anchor("center"),
              k.scale(cell / 96), k.z(5)]) });
        });

        stage.every(() => 0.26 / (sf * stage.tune.speed), () => {
          dir = nextDir;
          const [dx, dy] = DIRS[dir];
          const nc = (segs[0].c + dx + cols) % cols, nr = (segs[0].r + dy + rows) % rows;
          if (taken(nc, nr)) {
            // you ate your own tail — a comic knot, never a game over
            GB.audio.sfx("bonk");
            stage.toast("Oops — you tied yourself in a knot! 🪢");
            while (segs.length > 3) { segs.pop(); const o = tailObjs.pop(); if (o) k.destroy(o); }
          }
          segs.unshift({ c: nc, r: nr });
          if (grow > 0) { grow--; addTail(); } else segs.pop();
          if (food && food.cell.c === nc && food.cell.r === nr) {
            stage.burst(at(nc, nr), names[food.s.emoji]);
            k.destroy(food.obj);
            food = null;
            grow++;
            GB.juice.haptic(10);
            stage.progress();
            if (stage.score() < goal) spawnFood();
          }
          const hitDecoy = decoys.find((d) => d.cell.c === nc && d.cell.r === nr);
          if (hitDecoy) {
            GB.audio.sfx("bonk");
            stage.toast(data.avoid_line || "Blech — not THAT! 🤢");
            const cl = freeCell();
            hitDecoy.cell = cl;
            hitDecoy.obj.pos = at(cl.c, cl.r); // it scurries somewhere else
          }
        });

        k.onUpdate(() => {
          const ease = Math.min(1, 14 * k.dt());
          const glide = (o, p) => {
            // wrapping across an edge snaps (gliding the whole board looks like teleporting)
            if (Math.hypot(p.x - o.pos.x, p.y - o.pos.y) > cell * 2.2) { o.pos.x = p.x; o.pos.y = p.y; }
            else { o.pos.x += (p.x - o.pos.x) * ease; o.pos.y += (p.y - o.pos.y) * ease; }
          };
          glide(head, at(segs[0].c, segs[0].r));
          head.angle = Math.sin(k.time() * 6) * 8;
          tailObjs.forEach((o, i) => {
            const s = segs[i + 1] || segs[segs.length - 1];
            glide(o, at(s.c, s.r));
          });
        });
      },
    });
  } });

  // ---------------- arcade-shoot: a gentle space shooter — steer & zap ----------------
  // data: { player, shot, targets:[...], avoid:[...], goal, speed }
  def("arcade-shoot", { icon: "🛸", arcade: true, render(ctx) {
    const data = ctx.data;
    const player = skin(data.player, "🚀");
    const shot = skin(data.shot, "✨");
    const targetPool = (data.targets || ["🛸"]).map((s) => skin(s));
    const avoidPool = (data.avoid || []).map((s) => skin(s));
    const goal = data.goal || 8;
    intro(ctx, {
      sprites: [player.emoji, shot.emoji, ...targetPool.map((t) => t.emoji)],
      how: data.how || "Drag to steer — you fire all by yourself. Zap them all!",
      fallback: (c) => calmTap(c, { how: "Tap to zap them all!", targets: targetPool, decoys: avoidPool, goal }),
      async run(stage) {
        const k = stage.k, u = stage.u, sf = speedFactor(ctx.it, data);
        stage.backdrop(ctx.page);
        stage.goal(goal);
        const names = await stage.sprites([player.emoji, shot.emoji,
          ...targetPool.map((t) => t.emoji), ...avoidPool.map((a) => a.emoji)]);
        if (stage.isClosed()) return;
        const py = stage.H - 78 * u;
        const pl = k.add([k.sprite(names[player.emoji]), k.pos(stage.W / 2, py), k.anchor("center"),
          k.scale(1.15 * u), k.rotate(0), k.z(10)]);
        const move = stage.steer(pl, { axis: "x", lockY: py });
        k.onUpdate(() => { move(); pl.angle = Math.sin(k.time() * 3) * 4; });

        const targets = [];
        function spawnTarget() {
          if (targets.filter((t) => !t.dead).length >= 7) return;
          const good = avoidPool.length ? Math.random() < 0.78 : true;
          const s = good ? pick(targetPool) : pick(avoidPool);
          const o = k.add([k.sprite(names[s.emoji]), k.pos(rand(60 * u, stage.W - 60 * u), -40 * u),
            k.anchor("center"), k.scale(0.95 * u), k.rotate(0), k.z(5),
            { vy: rand(26, 58) * u * sf, sway: rand(30, 90) * u, t: Math.random() * 6 }]);
          const rec = { obj: o, good, dead: false, sname: names[s.emoji], bonked: 0 };
          targets.push(rec);
          o.onUpdate(() => {
            const dt = k.dt();
            o.t += dt;
            o.pos.y += o.vy * stage.tune.speed * dt;
            o.pos.x += Math.sin(o.t * 1.8) * o.sway * dt;
            o.angle = Math.sin(o.t * 2.2) * 12;
            const sc = 0.95 * u * stage.tune.size;
            o.scale = k.vec2(sc, sc);
            if (rec.bonked > 0) rec.bonked -= dt;
            // drifting low just loops back up — never a threat, never a fail
            if (o.pos.y > stage.H * 0.62) { o.pos.y = -40 * u; o.pos.x = rand(60 * u, stage.W - 60 * u); }
          });
        }
        stage.every(() => rand(0.7, 1.2) / (sf * stage.tune.speed), spawnTarget);

        function fire() {
          if (stage.isClosed()) return;
          const b = k.add([k.sprite(names[shot.emoji]), k.pos(pl.pos.x, pl.pos.y - 44 * u),
            k.anchor("center"), k.scale(0.55 * u), k.rotate(0), k.z(8)]);
          GB.audio.sfx("whoosh");
          b.onUpdate(() => {
            b.pos.y -= 560 * u * k.dt();
            b.angle += 420 * k.dt();
            if (b.pos.y < -40 * u) return k.destroy(b);
            for (const t of targets) {
              if (t.dead || t.obj.pos.dist(b.pos) > 50 * u * stage.tune.size) continue;
              k.destroy(b);
              if (t.good) {
                t.dead = true;
                stage.burst(t.obj.pos, t.sname, 8);
                GB.juice.haptic(10);
                k.destroy(t.obj);
                stage.progress();
              } else if (t.bonked <= 0) {
                t.bonked = 1;          // it just wobbles indignantly — no penalty
                GB.audio.sfx("bonk");
                stage.toast(data.avoid_line || "Hey! Not that one! 🙈");
                t.obj.angle += 40;
              }
              return;
            }
          });
        }
        stage.every(() => 0.5, fire);          // auto-fire keeps little hands free to steer
        k.onMousePress(fire);                  // …and every tap adds an extra pew
        k.onKeyPress("space", fire);
      },
    });
  } });

  // ---------------- arcade-maze: a REAL-TIME maze — swipe to scoot through ----------------
  // data: { player, exit, collect, size: cozy|normal|big, speed }
  def("arcade-maze", { icon: "🌀", arcade: true, render(ctx) {
    const data = ctx.data;
    const player = skin(data.player, "🐭");
    const exitS = skin(data.exit, "🏁");
    const collectS = data.collect ? skin(data.collect) : null;
    intro(ctx, {
      sprites: [player.emoji, exitS.emoji],
      how: data.how || "Swipe to scoot through the maze — find the way out!",
      fallback: (c) => calmTap(c, {
        how: "Tap to clear a path to the exit!",
        targets: collectS ? [collectS, exitS] : [exitS], decoys: [], goal: 5,
      }),
      async run(stage) {
        const k = stage.k, u = stage.u, sf = speedFactor(ctx.it, data);
        stage.backdrop(ctx.page);
        const sizes = { cozy: [7, 5], easy: [7, 5], normal: [9, 6], medium: [9, 6], big: [11, 7], hard: [11, 7] };
        const [cols, rows] = sizes[data.size] || sizes[(ctx.it && ctx.it.difficulty) || ""] || sizes.normal;

        // carve a perfect maze (recursive backtracker)
        const walls = Array.from({ length: rows }, () =>
          Array.from({ length: cols }, () => ({ n: 1, e: 1, s: 1, w: 1 })));
        const seen = Array.from({ length: rows }, () => Array(cols).fill(false));
        const CARVE = [["n", 0, -1, "s"], ["s", 0, 1, "n"], ["e", 1, 0, "w"], ["w", -1, 0, "e"]];
        const stack = [[0, 0]];
        seen[0][0] = true;
        while (stack.length) {
          const [c, r] = stack[stack.length - 1];
          const opts = CARVE.filter(([, dx, dy]) => {
            const nc = c + dx, nr = r + dy;
            return nc >= 0 && nc < cols && nr >= 0 && nr < rows && !seen[nr][nc];
          });
          if (!opts.length) { stack.pop(); continue; }
          const [w, dx, dy, ow] = pick(opts);
          const nc = c + dx, nr = r + dy;
          walls[r][c][w] = 0;
          walls[nr][nc][ow] = 0;
          seen[nr][nc] = true;
          stack.push([nc, nr]);
        }
        // solve it (BFS) so the assist ladder can reveal the trail
        const key = (c, r) => c + "," + r;
        const prev = {};
        const q = [[0, 0]];
        const vis = { "0,0": true };
        while (q.length) {
          const [c, r] = q.shift();
          if (c === cols - 1 && r === rows - 1) break;
          for (const [w, dx, dy] of CARVE) {
            const nc = c + dx, nr = r + dy;
            if (walls[r][c][w] || vis[key(nc, nr)]) continue;
            vis[key(nc, nr)] = true;
            prev[key(nc, nr)] = [c, r];
            q.push([nc, nr]);
          }
        }
        const path = [];
        for (let cur = [cols - 1, rows - 1]; cur; cur = prev[key(cur[0], cur[1])]) path.unshift(cur);

        const names = await stage.sprites([player.emoji, exitS.emoji,
          ...(collectS ? [collectS.emoji] : [])]);
        if (stage.isClosed()) return;

        const cell = Math.min((stage.W - 36 * u) / cols, (stage.H - 120 * u) / rows);
        const ox = (stage.W - cols * cell) / 2, oy = (stage.H - rows * cell) / 2 + 12 * u;
        const center = (c, r) => k.vec2(ox + (c + 0.5) * cell, oy + (r + 0.5) * cell);
        k.add([k.rect(cols * cell + 24 * u, rows * cell + 24 * u), k.pos(ox - 12 * u, oy - 12 * u),
          k.color(10, 13, 30), k.opacity(0.6), k.z(0)]);
        const T = Math.max(3, cell * 0.08);
        const wallBit = (x, y, w2, h2) =>
          k.add([k.rect(w2, h2), k.pos(x, y), k.color(132, 160, 226), k.opacity(0.95), k.z(1)]);
        for (let r = 0; r < rows; r++)
          for (let c = 0; c < cols; c++) {
            const x = ox + c * cell, y = oy + r * cell;
            if (walls[r][c].n) wallBit(x - T / 2, y - T / 2, cell + T, T);
            if (walls[r][c].w) wallBit(x - T / 2, y - T / 2, T, cell + T);
            if (r === rows - 1 && walls[r][c].s) wallBit(x - T / 2, y + cell - T / 2, cell + T, T);
            if (c === cols - 1 && walls[r][c].e) wallBit(x + cell - T / 2, y - T / 2, T, cell + T);
          }

        // the exit + a few collectibles sprinkled deep in the maze
        const exit = k.add([k.sprite(names[exitS.emoji]), k.pos(center(cols - 1, rows - 1)),
          k.anchor("center"), k.scale((cell / 96) * 0.8), k.z(5), { t: 0 }]);
        exit.onUpdate(() => {
          exit.t += k.dt();
          const sc = (cell / 96) * 0.8 * (1 + Math.sin(exit.t * 3) * 0.1);
          exit.scale = k.vec2(sc, sc);
        });
        const pickups = [];
        if (collectS) {
          for (let i = 0; i < 200 && pickups.length < 3; i++) {
            const c = Math.floor(rand(0, cols)), r = Math.floor(rand(0, rows));
            if ((c < 2 && r < 2) || (c === cols - 1 && r === rows - 1)) continue;
            if (pickups.some((p) => p.c === c && p.r === r)) continue;
            pickups.push({ c, r, obj: k.add([k.sprite(names[collectS.emoji]), k.pos(center(c, r)),
              k.anchor("center"), k.scale((cell / 96) * 0.6), k.z(4)]) });
          }
        }
        stage.goal(pickups.length + 1, { auto: false }); // win = reaching the exit

        const pl = k.add([k.sprite(names[player.emoji]), k.pos(center(0, 0)), k.anchor("center"),
          k.scale((cell / 96) * 0.78), k.rotate(0), k.z(10)]);
        let pc = 0, pr = 0, tc = 0, tr = 0, want = null;
        dirPad(k, (d) => { want = d; });
        const open = (c, r, d) => !walls[r][c][{ left: "w", right: "e", up: "n", down: "s" }[d]];

        let hinted = false;
        k.onUpdate(() => {
          pl.angle = Math.sin(k.time() * 8) * 6;
          // the assist ladder ("Easier!") reveals the secret trail to the exit
          if (!hinted && stage.tune.speed < 1) {
            hinted = true;
            path.forEach(([c, r], i) => {
              if (i % 2) return;
              k.add([k.circle(cell * 0.08), k.pos(center(c, r)), k.anchor("center"),
                k.color(255, 235, 170), k.opacity(0.55), k.z(2)]);
            });
          }
          const tgt = center(tc, tr);
          const dx = tgt.x - pl.pos.x, dy = tgt.y - pl.pos.y;
          const dist = Math.hypot(dx, dy);
          if (dist < 2) {
            if (pc !== tc || pr !== tr) {
              pc = tc; pr = tr;
              const got = pickups.find((p) => p.c === pc && p.r === pr && p.obj);
              if (got) {
                stage.burst(got.obj.pos, names[collectS.emoji]);
                k.destroy(got.obj);
                got.obj = null;
                stage.progress();
              }
              if (pc === cols - 1 && pr === rows - 1) return stage.win();
            }
            // keep scooting in the swiped direction until a wall says no
            if (want && open(pc, pr, want)) {
              const [mx, my] = DIRS[want];
              tc = pc + mx;
              tr = pr + my;
              GB.audio.sfx("tick");
            }
          } else {
            const step = Math.min(dist, cell * 5.2 * sf * k.dt());
            pl.pos.x += (dx / dist) * step;
            pl.pos.y += (dy / dist) * step;
          }
        });
      },
    });
  } });

  // ---------------- arcade-build: stack the swinging pieces into a tower ----------------
  // data: { blocks:[...], goal, speed }
  def("arcade-build", { icon: "🏗️", arcade: true, render(ctx) {
    const data = ctx.data;
    const blockPool = (data.blocks || ["📦"]).map((s) => skin(s));
    const goal = data.goal || 6;
    intro(ctx, {
      sprites: blockPool.map((b) => b.emoji),
      how: data.how || "Tap to drop each piece — stack the tower all the way up!",
      fallback: (c) => calmTap(c, { how: "Tap the pieces to stack them all!", targets: blockPool, goal }),
      async run(stage) {
        const k = stage.k, u = stage.u, sf = speedFactor(ctx.it, data);
        stage.backdrop(ctx.page);
        stage.goal(goal);
        const names = await stage.sprites(blockPool.map((b) => b.emoji));
        if (stage.isClosed()) return;
        const B = 74 * u;
        const groundY = stage.H - 46 * u;
        k.add([k.rect(stage.W, 46 * u), k.pos(0, groundY), k.color(34, 40, 64), k.opacity(0.85), k.z(2)]);

        const placed = [];
        let towerX = stage.W / 2, topY = groundY, swing = null, falling = null, t = 0;

        function newSwing() {
          if (stage.isClosed()) return;
          const s = pick(blockPool);
          swing = k.add([k.sprite(names[s.emoji]), k.pos(stage.W / 2, 64 * u), k.anchor("center"),
            k.scale(B / 96), k.rotate(0), k.z(8), { sname: names[s.emoji], vy: 0, vx: 0 }]);
        }
        newSwing();
        const drop = () => {
          if (!swing || falling) return;
          falling = swing;
          swing = null;
          GB.audio.sfx("whoosh");
        };
        k.onMousePress(drop);
        k.onKeyPress("space", drop);

        k.onUpdate(() => {
          const dt = k.dt();
          t += dt;
          if (swing) swing.pos.x = stage.W / 2 + Math.sin(t * 1.7 * sf * stage.tune.speed) * (stage.W / 2 - 90 * u);
          placed.forEach((o, i) => { o.angle = Math.sin(k.time() * 1.6 + i * 0.7) * 1.6; }); // a living wobble
          if (!falling) return;
          falling.vy += 2100 * u * dt;
          falling.pos.y += falling.vy * dt;
          falling.pos.x += falling.vx * dt;
          if (falling.vx) falling.angle += 320 * dt; // a missed piece tumbles off comically
          if (falling.vx && falling.pos.y > stage.H + 80 * u) { k.destroy(falling); falling = null; newSwing(); return; }
          if (!falling.vx && falling.pos.y + B / 2 >= topY) {
            const dx = falling.pos.x - towerX;
            const wiggleRoom = B * 0.55 * stage.tune.size; // generous, and the assist grows it
            if (placed.length === 0 || Math.abs(dx) <= wiggleRoom) {
              falling.pos.y = topY - B / 2;
              falling.pos.x = placed.length === 0 ? falling.pos.x : towerX + dx * 0.35; // kid-friendly auto-snug
              falling.vy = 0;
              towerX = falling.pos.x;
              topY -= B * 0.92;
              placed.push(falling);
              stage.burst(falling.pos, falling.sname, 5);
              GB.juice.haptic(12);
              falling = null;
              stage.progress();
              // the tower outgrows the screen → everything rides down one storey
              if (topY < stage.H * 0.4) {
                placed.forEach((o) => (o.pos.y += B));
                topY += B;
              }
              if (stage.score() < goal) newSwing();
            } else {
              GB.audio.sfx("bonk");
              stage.toast(pick(["Wide! Try the next one! 😅", "Boing — off it goes!", "So close! Again!"]));
              falling.vx = (dx > 0 ? 1 : -1) * 260 * u;
              falling.vy = -380 * u;
            }
          }
        });
      },
    });
  } });

  // ---------------- arcade-whack: they pop up — bop them before they duck! ----------------
  // data: { whack:[...], avoid:[...], goal, speed }
  def("arcade-whack", { icon: "🔨", arcade: true, render(ctx) {
    const data = ctx.data;
    const whackPool = (data.whack || ["🐹"]).map((s) => skin(s));
    const avoidPool = (data.avoid || []).map((s) => skin(s));
    const goal = data.goal || 8;
    intro(ctx, {
      sprites: whackPool.map((w) => w.emoji),
      how: data.how || "They pop up and duck back down — tap them before they hide!",
      fallback: (c) => calmTap(c, { how: "Tap to bop them all!", targets: whackPool, decoys: avoidPool, goal }),
      async run(stage) {
        const k = stage.k, u = stage.u, sf = speedFactor(ctx.it, data);
        stage.backdrop(ctx.page);
        stage.goal(goal);
        const names = await stage.sprites([...whackPool.map((w) => w.emoji), ...avoidPool.map((a) => a.emoji)]);
        if (stage.isClosed()) return;
        // a 3×3 field of burrows
        const cols2 = 3, rows2 = 3;
        const gx = stage.W / (cols2 + 1), gy = (stage.H - 90 * u) / (rows2 + 1);
        const holes = [];
        for (let r = 0; r < rows2; r++)
          for (let c = 0; c < cols2; c++) {
            const x = gx * (c + 1), y = 70 * u + gy * (r + 1);
            const lip = k.add([k.circle(34 * u), k.pos(x, y + 26 * u), k.anchor("center"),
              k.color(8, 10, 24), k.opacity(0.55), k.z(3)]);
            lip.scale = k.vec2(1.25, 0.45);
            holes.push({ x, y, busy: false });
          }
        function popUp() {
          const free = holes.filter((hh) => !hh.busy);
          if (!free.length) return;
          const hole = pick(free);
          hole.busy = true;
          const good = avoidPool.length ? Math.random() < 0.74 : true;
          const s = good ? pick(whackPool) : pick(avoidPool);
          const upFor = rand(1.1, 1.7) / (sf * stage.tune.speed);
          const o = k.add([k.sprite(names[s.emoji]), k.pos(hole.x, hole.y + 30 * u), k.anchor("center"),
            k.scale(0.01), k.rotate(0), k.area(), k.z(5), good ? "bop" : "nobop",
            { t: 0, upFor, done: false, sname: names[s.emoji], hole }]);
          o.onUpdate(() => {
            o.t += k.dt();
            const full = 1.0 * u * stage.tune.size;
            // rise … linger … duck (shrinks back into the burrow)
            const ph = o.t < 0.18 ? o.t / 0.18 : o.t > o.upFor - 0.22 ? Math.max(0, (o.upFor - o.t) / 0.22) : 1;
            const sc = Math.max(0.01, full * ph);
            o.scale = k.vec2(sc, sc);
            o.pos.y = hole.y + 30 * u - 36 * u * ph;
            if (o.t >= o.upFor && !o.done) { o.done = true; hole.busy = false; k.destroy(o); }
          });
        }
        stage.every(() => rand(0.45, 0.8) / (sf * stage.tune.speed), popUp);
        k.onClick("bop", (o) => {
          if (o.done) return;
          o.done = true;
          o.hole.busy = false;
          stage.burst(o.pos, o.sname, 7);
          GB.juice.haptic(12);
          k.destroy(o);
          stage.progress();
        });
        k.onClick("nobop", (o) => {
          GB.audio.sfx("bonk");
          stage.toast(data.avoid_line || "Not that one — it's friendly! 🙊");
          o.angle += 30;
        });
      },
    });
  } });

  // ---------------- arcade-bounce: breakout — bounce the ball, smash the wall ----------------
  // data: { player (paddle), ball, bricks:[...], rows, speed }
  def("arcade-bounce", { icon: "🧱", arcade: true, render(ctx) {
    const data = ctx.data;
    const player = skin(data.player, "🏓");
    const ballS = skin(data.ball, "⭐");
    const brickPool = (data.bricks || ["🧱"]).map((s) => skin(s));
    const rows3 = Math.min(3, Math.max(1, data.rows || 2));
    intro(ctx, {
      sprites: [player.emoji, ballS.emoji, ...brickPool.map((b) => b.emoji)],
      how: data.how || "Drag to slide — bounce it up and smash every piece of the wall!",
      fallback: (c) => calmTap(c, { how: "Tap to smash the wall!", targets: brickPool, decoys: [], goal: 8 }),
      async run(stage) {
        const k = stage.k, u = stage.u, sf = speedFactor(ctx.it, data);
        stage.backdrop(ctx.page);
        const names = await stage.sprites([player.emoji, ballS.emoji, ...brickPool.map((b) => b.emoji)]);
        if (stage.isClosed()) return;
        const cols3 = 6;
        const bw = (stage.W - 70 * u) / cols3, bh = 56 * u;
        const bricks = [];
        for (let r = 0; r < rows3; r++)
          for (let c = 0; c < cols3; c++) {
            const s = pick(brickPool);
            const o = k.add([k.sprite(names[s.emoji]),
              k.pos(35 * u + (c + 0.5) * bw, 64 * u + (r + 0.5) * bh),
              k.anchor("center"), k.scale(Math.min(bw, bh) / 96 * 0.92), k.rotate(0), k.z(5)]);
            bricks.push({ obj: o, alive: true, sname: names[s.emoji] });
          }
        stage.goal(bricks.length);

        const py = stage.H - 64 * u;
        const pl = k.add([k.sprite(names[player.emoji]), k.pos(stage.W / 2, py), k.anchor("center"),
          k.scale(1.5 * u), k.rotate(0), k.z(10)]);
        const move = stage.steer(pl, { axis: "x", lockY: py, pad: 60 });

        const ball = k.add([k.sprite(names[ballS.emoji]), k.pos(stage.W / 2, py - 60 * u),
          k.anchor("center"), k.scale(0.6 * u), k.rotate(0), k.z(9)]);
        let dx = 0.45, dy = -1; // unit-ish direction; speed is computed live (assist slows it)
        let lastSave = 0;
        const renorm = () => {
          const m = Math.hypot(dx, dy) || 1;
          dx /= m; dy /= m;
          if (Math.abs(dy) < 0.4) { dy = (dy < 0 ? -0.4 : 0.4); dx = Math.sign(dx || 1) * Math.sqrt(1 - dy * dy); }
        };
        renorm();

        k.onUpdate(() => {
          const dt = k.dt();
          move();
          const ps = 1.5 * u * stage.tune.size; // the assist grows the paddle
          pl.scale = k.vec2(ps * 1.4, ps);      // a paddle is wider than tall
          const sp = 380 * u * sf * stage.tune.speed;
          ball.pos.x += dx * sp * dt;
          ball.pos.y += dy * sp * dt;
          ball.angle += 240 * dt;
          // walls
          if (ball.pos.x < 26 * u) { ball.pos.x = 26 * u; dx = Math.abs(dx); }
          if (ball.pos.x > stage.W - 26 * u) { ball.pos.x = stage.W - 26 * u; dx = -Math.abs(dx); }
          if (ball.pos.y < 26 * u) { ball.pos.y = 26 * u; dy = Math.abs(dy); }
          // the floor is bouncy too — a miss is a giggle, never a lost ball
          if (ball.pos.y > stage.H - 22 * u) {
            ball.pos.y = stage.H - 22 * u;
            dy = -Math.abs(dy);
            if (k.time() - lastSave > 3) {
              lastSave = k.time();
              GB.audio.sfx("bonk");
              stage.toast(data.avoid_line || "Boing! The floor bounced it back! 🛟");
            }
          }
          // paddle
          if (dy > 0 && Math.abs(ball.pos.y - py) < 34 * u && Math.abs(ball.pos.x - pl.pos.x) < 80 * u * stage.tune.size) {
            dy = -Math.abs(dy);
            dx += (ball.pos.x - pl.pos.x) / (110 * u); // steer the rebound off the paddle edge
            renorm();
            GB.audio.sfx("jump");
          }
          // bricks
          for (const br of bricks) {
            if (!br.alive) continue;
            const ddx = ball.pos.x - br.obj.pos.x, ddy = ball.pos.y - br.obj.pos.y;
            if (Math.abs(ddx) < bw / 2 + 14 * u && Math.abs(ddy) < bh / 2 + 14 * u) {
              br.alive = false;
              stage.burst(br.obj.pos, br.sname, 7);
              GB.juice.haptic(10);
              k.destroy(br.obj);
              if (Math.abs(ddx) / (bw / 2) > Math.abs(ddy) / (bh / 2)) dx = ddx > 0 ? Math.abs(dx) : -Math.abs(dx);
              else dy = ddy > 0 ? Math.abs(dy) : -Math.abs(dy);
              stage.progress();
              break;
            }
          }
        });
      },
    });
  } });
})();
