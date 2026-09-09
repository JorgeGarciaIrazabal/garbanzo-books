/* gx.quest — COMPOSED arcade games: a game is DESIGNED for the page's beat, not picked
   from a list. One interaction type — `arcade-quest` — with a declarative scenario the
   author (or LLM) writes per book:

     * a STAGE  — side-view / sky / top-down, optional scroll, parallax bands skinned
                  from the story (cloud bands, seaweed bands, hills…), ground or floor
     * a HERO   — the thing the kid controls: steer / flap / hop / drive (control styles),
                  skinned from the page's protagonist
     * ACTORS   — named groups the author defines freely ("sparks", "crones", "gulls"),
                  each with a ROLE (collect / rescue / dodge / bonk / squash / decoy /
                  guard), a MOTION pattern (9 kinds), a spawn pattern, a count, and a
                  story-written line the kid hears when they meet one
     * WAVES    — escalation beats: each wave re-stocks the field with the author's mix
                  of actor groups, a story-written banner line, and a slightly bigger
                  field — the game RISES like the page it belongs to
     * a FINALE — reach / clear / bigOne / tower: the beat's payoff moment

   The engine turns that scenario into a real Kaplay game (fullscreen over the page art,
   same as the arcade family) with all the standing guarantees: always-winnable (funny
   bonks, never a fail state; rubber-band assist ladder), lazy engine load, calm DOM
   fallback when WebGL is missing, goal HUD, win celebration.

   Payload contract (schemas/story.schema.json $defs/questSpec; validated by
   scripts/lib/checks/interactivity.py):
     data.stage   { view, scroll, bands[], floor }
     data.hero    { skin, control, speed? }
     data.actors  [{ name, skin(s), role, motion, from, count, pace, line? }]
     data.waves   [{ line?, spawn:[ {name, count} ] }]
     data.finale  { kind, skin, line? }
     data.goal    total meets to win (default: summed wave spawns)
     data.speed / how / avoid_line — same as the arcade family.
*/
(function () {
  "use strict";
  const GB = window.GB;
  const h = GB.h, skin = GB.skin;
  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
  const norm = (v, lo, hi, dflt) => {
    v = Number(v);
    return Number.isFinite(v) ? Math.max(lo, Math.min(hi, v)) : dflt;
  };

  const ROLES = ["collect", "rescue", "dodge", "bonk", "squash", "decoy", "guard"];
  const MOTIONS = ["drift", "fall", "rise", "sine", "chase", "flee", "hover", "march", "still"];

  // ---- role semantics -----------------------------------------------------
  // meet    → the effect when the hero touches one
  // counts  → does touching it advance the goal?
  const ROLE = {
    collect: { counts: true, meet: "pop", how: "grab" },
    rescue:  { counts: true, meet: "carry", how: "carry" },
    dodge:   { counts: false, meet: "bonk" },
    bonk:    { counts: true, meet: "bonk", how: "bop" },
    squash:  { counts: true, meet: "squash", how: "squash" },
    decoy:   { counts: false, meet: "wiggle" },
    guard:   { counts: false, meet: "shove" },
  };

  // ---- motion integrators (per-frame displacement in stage units) ---------
  // Each returns {vx, vy} for this actor this frame, given its state. `t` is the
  // actor's own clock; scroll shifts the world for scroll stages.
  const MOTION = {
    still: () => ({ vx: 0, vy: 0 }),
    // drift: constant heading chosen at spawn (slight downward bias for sky feel)
    drift: (a) => ({ vx: a.dirx * a.sp * u(), vy: a.diry * a.sp * u() }),
    fall: (a) => ({ vx: Math.sin(a.t * 2) * a.sway * u(), vy: a.sp * u() }),
    rise: (a) => ({ vx: Math.sin(a.t * 2) * a.sway * u(), vy: -a.sp * u() }),
    // sine: forward drift with a sine bob (butterflies, jellyfish)
    sine: (a) => ({ vx: a.dirx * a.sp * u(), vy: Math.sin(a.t * a.freq) * a.sway * u() }),
    // chase: eases toward the hero (crones, gulls, goblins)
    chase: (a, hero) => {
      const dx = hero.pos.x - a.obj.pos.x, dy = hero.pos.y - a.obj.pos.y;
      const m = Math.hypot(dx, dy) || 1;
      return { vx: (dx / m) * a.sp * u(), vy: (dy / m) * a.sp * u() };
    },
    // flee: eases AWAY from the hero (butterflies that don't want to be caught)
    flee: (a, hero) => {
      const dx = a.obj.pos.x - hero.pos.x, dy = a.obj.pos.y - hero.pos.y;
      const m = Math.hypot(dx, dy) || 1;
      const want = { vx: (dx / m) * a.sp * u(), vy: (dy / m) * a.sp * u() };
      // keep them inside the field so the game stays playable
      if (a.obj.pos.x < 70 * u() || a.obj.pos.x > W - 70 * u() ||
          a.obj.pos.y < 70 * u() || a.obj.pos.y > H - 90 * u()) {
        return { vx: -want.vx * 0.55, vy: -want.vy * 0.55 };
      }
      return want;
    },
    // hover: stays at its anchor, gentle bob (guards, the big one before it wakes)
    hover: (a) => ({ vx: 0, vy: Math.sin(a.t * a.freq) * a.sway * u() }),
    // march: steady side-to-side patrol between edges
    march: (a) => {
      if (a.obj.pos.x < 80 * u()) a.dirx = 1;
      if (a.obj.pos.x > W - 80 * u()) a.dirx = -1;
      return { vx: a.dirx * a.sp * u(), vy: 0 };
    },
  };
  const u = () => _u; // scale unit, set at open()
  let W = 800, H = 520, _u = 1;

  /* =====================================================================
     CALM FALLBACK (no WebGL / reduced motion / engine failure)
     Same beat as the quest: waves of tappable actors, decoys wiggle,
     reach-the-finale as a final tap target. Always winnable.
     ===================================================================== */
  function questFallback(ctx, spec) {
    const how = spec.how || "Tap the right ones — wave by wave!";
    const targets = spec.flatActors.filter((a) => a.role !== "decoy" && a.role !== "dodge")
      .map((a) => a.skin);
    const decoys = spec.flatActors.filter((a) => a.role === "decoy" || a.role === "dodge")
      .map((a) => a.skin);
    // If a quest has no countable actors at all, the calm board taps the finale.
    const tapTargets = targets.length ? targets : [spec.finaleS];
    const firstWaveLine = spec.waves[0] && spec.waves[0].line;
    GB.arcade.calmTap(ctx, {
      how: firstWaveLine ? firstWaveLine + " — " + how : how,
      targets: tapTargets,
      decoys,
      goal: Math.min(spec.total || 3, 12),
      missLine: spec.avoidLine || "Whoops — not that one!",
    });
  }

  /* =====================================================================
     THE COMPOSER
     ===================================================================== */
  function buildQuest(ctx) {
    const data = ctx.data || {};
    const it = ctx.it;

    const stageSpec = data.stage || {};
    const heroSpec = data.hero || {};
    const actorsSpec = Array.isArray(data.actors) ? data.actors : [];
    const wavesSpec = Array.isArray(data.waves) ? data.waves : [];
    const finaleSpec = data.finale || {};

    const view = String(stageSpec.view || "side");
    const scrolling = stageSpec.scroll !== false && view !== "topdown";
    const bands = Array.isArray(stageSpec.bands) ? stageSpec.bands.map(skin) : [];
    const floorS = stageSpec.floor ? skin(stageSpec.floor) : null;

    const heroS = skin(heroSpec.skin, "🦊");
    const control = String(heroSpec.control || (view === "topdown" ? "steer" : "walk"));
    const heroSpeed = norm(heroSpec.speed, 0.4, 2.5, 1);

    const finaleS = skin(finaleSpec.skin, "🏆");
    const FINALES = ["reach", "clear", "bigOne", "tower"];
    const finaleKind = FINALES.includes(finaleSpec.kind) ? finaleSpec.kind : "reach";
    const finaleLine = finaleSpec.line ? String(finaleSpec.line) : "";

    const avoidLine = data.avoid_line;
    const sf = GB.arcade.speedFactor(it, data);

    // ---- normalize actors ------------------------------------------------
    const actors = actorsSpec.map((a, i) => {
      const role = ROLES.includes(a.role) ? a.role : "collect";
      const motion = MOTIONS.includes(a.motion) ? a.motion : "drift";
      const skins = (Array.isArray(a.skin) ? a.skin : [a.skin || "⭐"]).map((s) => skin(s, "⭐"));
      return {
        name: String(a.name || `actor${i}`),
        skins,
        role,
        motion,
        from: String(a.from || (view === "topdown" ? "anywhere" : "top")),
        count: norm(a.count, 1, 12, 3),
        pace: norm(a.pace, 0.25, 3, 1),
        line: a.line,
      };
    });
    const byName = {};
    actors.forEach((a) => (byName[a.name] = a));

    // ---- normalize waves -------------------------------------------------
    const waves = wavesSpec.length ? wavesSpec.map((w, i) => ({
      line: w && w.line ? String(w.line) : "",
      banner: w && w.banner !== false,
      spawn: (w && Array.isArray(w.spawn) ? w.spawn : []).map((s) => {
        const actor = byName[s.name] || actors[0];
        return { actor, count: norm(s.count, 1, 12, (actor && actor.count) || 3) };
      }).filter((s) => s.actor),
    })) : [{
      line: "",
      banner: false,
      spawn: actors.map((a) => ({ actor: a, count: a.count })),
    }];

    // total meets to win across all waves (rescue/collect/bonk/squash roles count)
    const countRoles = ({ role }) => ROLE[role].counts;
    const total = norm(data.goal, 3, 60,
      waves.reduce((sum, w) => sum + w.spawn.reduce((s, sp) =>
        s + (countRoles(sp.actor) ? sp.count : 0), 0), 0) || 6);

    // flat list for the intro card + calm fallback
    const flatActors = [];
    waves.forEach((w) => w.spawn.forEach((sp) => {
      for (let i = 0; i < sp.count; i++) flatActors.push({ role: sp.actor.role, skin: pick(sp.actor.skins) });
    }));
    if (!flatActors.length) flatActors.push({ role: "collect", skin: heroS });

    return {
      view, scrolling, bands, floorS, heroS, control, heroSpeed, actors, waves, total,
      finaleS, finaleKind, finaleLine, avoidLine, sf, flatActors,
      how: data.how, wavesRaw: wavesSpec, floorRaw: stageSpec.floor,
    };
  }

  /* =====================================================================
     THE RUNTIME — one composed Kaplay game
     ===================================================================== */
  function runQuest(stage, ctx, spec) {
    const k = stage.k;
    W = stage.W; H = stage.H; _u = stage.u;
    const u = () => _u;
    const { view, scrolling, bands, floorS, heroS, control, heroSpeed,
            actors, waves, total, finaleS, finaleKind, avoidLine, sf } = spec;

    stage.backdrop(ctx.page);
    stage.goal(total, { auto: false }); // win = the finale, not the pip count

    // collect every emoji once for sprite preloading
    const emojis = [heroS.emoji, finaleS.emoji, ...bands.map((b) => b.emoji)];
    if (floorS) emojis.push(floorS.emoji);
    actors.forEach((a) => a.skins.forEach((s) => emojis.push(s.emoji)));
    const uniq = [...new Set(emojis)];
    stage.sprites(uniq).then((names) => {
      if (stage.isClosed()) return;
      build(names);
    });

    function build(names) {
      /* ---- the stage: bands, floor, scroll ------------------------------- */
      const spx = () => (view === "topdown" ? 0 : (scrolling ? 120 * u() : 0) * sf * stage.tune.speed);
      const bandObjs = [];
      bands.forEach((b, i) => {
        const depth = (i + 1) / (bands.length + 1); // 0..1, near bands move faster
        const row = [];
        const n = Math.ceil(W / (110 * u())) + 2;
        for (let j = -1; j < n; j++) {
          const o = k.add([k.sprite(names[b.emoji]), k.pos(j * 110 * u() + rand(-14, 14) * u(),
            H * (0.08 + i * (0.72 / Math.max(1, bands.length))) + rand(-8, 8) * u()),
            k.anchor("center"), k.scale((0.55 + depth * 0.35) * u()), k.opacity(0.55), k.z(-10)]);
          row.push(o);
        }
        bandObjs.push({ row, depth });
      });
      if (floorS) {
        const fl = [];
        const n = Math.ceil(W / (110 * u())) + 2;
        for (let j = -1; j < n; j++)
          fl.push(k.add([k.sprite(names[floorS.emoji]), k.pos(j * 110 * u(), H - 34 * u()),
            k.anchor("center"), k.scale(0.9 * u()), k.opacity(0.9), k.z(-5)]));
        bandObjs.push({ row: fl, depth: 1.2 });
      }

      /* ---- the hero ------------------------------------------------------ */
      const groundY = H - 92 * u();
      const heroTop = view === "sky" ? H * 0.25 : groundY - 10 * u();
      const hero = k.add([k.sprite(names[heroS.emoji]), k.pos(W * 0.24, heroTop),
        k.anchor("center"), k.scale(1.15 * u()), k.rotate(0), k.z(10),
        { vy: 0, invuln: 0, carrying: 0 }]);

      let input = { x: 0, y: 0, jump: false, hold: false };
      const setJump = () => (input.jump = true);
      k.onMousePress(() => { input.hold = true; setJump(); });
      k.onMouseRelease(() => (input.hold = false));
      k.onKeyPress("space", setJump);
      k.onKeyPress("up", setJump);

      // control styles → per-frame hero update fn
      let heroTick = null;
      const steerAxis = (control === "steer" || control === "drive") &&
        (view === "topdown" || view === "sky") ? "xy" : "x";
      const lockY = view === "sky" ? null : groundY;
      if (control === "steer" || control === "drive") {
        heroTick = stage.steer(hero, { axis: steerAxis, lockY });
      } else if (control === "flap") {
        heroTick = () => {
          const dt = k.dt();
          if (input.jump) { input.jump = false; hero.vy = -430 * u() * sf * heroSpeed; GB.audio.sfx("jump"); }
          hero.vy += 1250 * u() * dt;
          hero.pos.y += hero.vy * dt;
          hero.pos.y = Math.max(30 * u(), Math.min(H - 60 * u(), hero.pos.y));
          hero.angle = Math.max(-30, Math.min(35, hero.vy * 0.05));
        };
      } else if (control === "hop") {
        let hops = 0;
        heroTick = () => {
          const dt = k.dt();
          if (input.jump && hops < 2) { input.jump = false; hero.vy = -540 * u() * sf * heroSpeed; hops++; GB.audio.sfx("jump"); }
          hero.vy += 1500 * u() * dt;
          hero.pos.y += hero.vy * dt;
          if (hero.pos.y >= groundY) { hero.pos.y = groundY; hero.vy = 0; hops = 0; }
          hero.angle = hops ? Math.min(20, -hero.vy * 0.03) : Math.sin(k.time() * 12) * 4;
        };
      } else { // walk
        heroTick = () => {
          const dt = k.dt();
          if (input.jump && Math.abs(hero.vy) < 1) { input.jump = false; hero.vy = -520 * u() * sf * heroSpeed; GB.audio.sfx("jump"); }
          hero.vy += 1500 * u() * dt;
          hero.pos.y += hero.vy * dt;
          if (hero.pos.y >= groundY) { hero.pos.y = groundY; hero.vy = 0; }
          hero.angle = Math.sin(k.time() * 12) * 4;
        };
      }

      /* ---- actor factory -------------------------------------------------- */
      const live = [];
      function spawnActor(actor) {
        const s = pick(actor.skins);
        const sp = (70 + rand(0, 90)) * u() * actor.pace * sf;
        const dirx = Math.random() < 0.5 ? -1 : 1;
        // spawn edges by `from` + view
        let x, y;
        const from = actor.from;
        if (view === "topdown") {
          x = from === "left" ? -40 * u() : from === "right" ? W + 40 * u() : rand(60 * u(), W - 60 * u());
          y = from === "top" ? -40 * u() : from === "bottom" ? H + 40 * u() : rand(60 * u(), H - 60 * u());
        } else {
          if (from === "left") { x = -40 * u(); y = rand(H * 0.15, H * 0.75); }
          else if (from === "right") { x = W + 40 * u(); y = rand(H * 0.15, H * 0.75); }
          else if (from === "bottom") { x = rand(60 * u(), W - 60 * u()); y = H + 40 * u(); }
          else { x = rand(60 * u(), W - 60 * u()); y = -40 * u(); } // top
        }
        const obj = k.add([k.sprite(names[s.emoji]), k.pos(x, y), k.anchor("center"),
          k.scale(0.95 * u()), k.rotate(0), k.z(6),
          { t: rand(0, 6), sp, dirx, sway: rand(20, 55) * u(), freq: rand(1.6, 3), dead: false }]);
        const rec = { actor, skin: s, obj, role: ROLE[actor.role], motion: MOTION[actor.motion], cool: 0 };
        live.push(rec);
        obj.onUpdate(() => {
          if (rec.dead) return;
          const dt = k.dt();
          obj.t += dt;
          if (rec.cool > 0) rec.cool -= dt;
          const d = rec.motion(rec, hero);
          obj.pos.x += d.vx * stage.tune.speed * dt;
          obj.pos.y += d.vy * stage.tune.speed * dt;
          obj.angle = Math.sin(obj.t * 2.2) * 10;
          // despawn + recycle: gone off any edge → respawn at the same wave's
          // spawn edge while waves are still running (so the field never empties
          // mid-wave); once the show moves on, let them drift away
          const off = obj.pos.x < -90 * u() || obj.pos.x > W + 90 * u() ||
                      obj.pos.y < -90 * u() || obj.pos.y > H + 90 * u();
          if (off) {
            if (!spawnedAll && !finaleOn) {
              const p = spawnPoint(actor);
              obj.pos.x = p.x; obj.pos.y = p.y;
              if (obj.t > 9e3) obj.t = 0;
            } else {
              k.destroy(obj);
              const ix = live.indexOf(rec);
              if (ix >= 0) live.splice(ix, 1);
            }
          }
        });
        return rec;
      }

      // spawn edges for a recycled actor
      function spawnPoint(actor) {
        const from = actor.from;
        if (view === "topdown") {
          if (from === "left") return { x: -40 * u(), y: rand(60 * u(), H - 60 * u()) };
          if (from === "right") return { x: W + 40 * u(), y: rand(60 * u(), H - 60 * u()) };
          if (from === "top") return { x: rand(60 * u(), W - 60 * u()), y: -40 * u() };
          if (from === "bottom") return { x: rand(60 * u(), W - 60 * u()), y: H + 40 * u() };
          return { x: rand(60 * u(), W - 60 * u()), y: rand(60 * u(), H - 60 * u()) };
        }
        if (from === "left") return { x: -40 * u(), y: rand(H * 0.15, H * 0.75) };
        if (from === "right") return { x: W + 40 * u(), y: rand(H * 0.15, H * 0.75) };
        if (from === "bottom") return { x: rand(60 * u(), W - 60 * u()), y: H + 40 * u() };
        return { x: rand(60 * u(), W - 60 * u()), y: -40 * u() };
      }

      /* ---- the wave sequencer --------------------------------------------- */
      const waveRef = {}; // (kept for potential per-wave accounting; recycle is time-based)
      let waveIdx = 0, waveT = 0, spawnedAll = false, finaleOn = false;
      function stockWave(i, banner) {
        const w = waves[i];
        w.spawn.forEach((sp) => {
          const actor = sp.actor;
          waveRef[actor.name] = { wave: i + 1 };
          for (let n = 0; n < sp.count; n++) spawnActor(actor);
        });
        if (banner && w.line) waveBanner(w.line);
      }
      function nextWave() {
        if (waveIdx >= waves.length) { spawnedAll = true; return; }
        stockWave(waveIdx, true);
        waveIdx++;
      }
      nextWave();

      // wave banner (DOM, over the canvas but under the HUD)
      const banner = h("div", "quest-banner");
      banner.setAttribute("aria-live", "polite");
      stage.overlay.appendChild(banner);
      let bannerTimer = null;
      function waveBanner(text) {
        banner.textContent = text;
        banner.classList.add("show");
        clearTimeout(bannerTimer);
        bannerTimer = setTimeout(() => banner.classList.remove("show"), 2600);
      }

      // wave pacing: each wave runs on a timer (14s — actors recycle so the field
      // never empties early); when the last wave's time is up (or every countable
      // has been met ahead of schedule), the show moves to the finale.
      const WAVE_TIME = 14;
      k.onUpdate(() => {
        heroTick();
        if (hero.invuln > 0) hero.invuln -= k.dt();
        hero.opacity = hero.invuln > 0 ? 0.55 : 1;
        const sc = 1.15 * u() * stage.tune.size;
        hero.scale = k.vec2(sc, sc);
        // scroll the parallax bands
        const dx = spx() * k.dt();
        bandObjs.forEach((b) => b.row.forEach((o) => {
          o.pos.x -= dx * b.depth;
          if (o.pos.x < -130 * u()) o.pos.x += b.row.length * 110 * u();
        }));
        // wave advance
        if (!spawnedAll) {
          waveT += k.dt();
          if (waveT > WAVE_TIME) {
            waveT = 0;
            if (waveIdx < waves.length) nextWave();
            else spawnedAll = true;
          }
        }
        if (spawnedAll && !finaleOn) {
          finaleOn = true;
          startFinale();
        }
      });

      /* ---- meets (hero × actor) ------------------------------------------- */
      k.onUpdate(() => {
        for (const rec of live) {
          if (rec.dead) continue;
          const meetR = (56 * u() * stage.tune.size + 30 * u());
          if (rec.obj.pos.dist(hero.pos) > meetR) continue;
          meet(rec);
        }
      });

      function meet(rec) {
        const { role, meet } = rec.role;
        // cooldown so a non-consuming meet (wiggle/shove) doesn't re-fire every frame
        if (rec.cool > 0) return;
        rec.cool = 0.6;
        const line = rec.actor.line || (role === "decoy" || role === "dodge" ? avoidLine : null);
        if (meet === "pop" || meet === "carry") {
          rec.dead = true;
          stage.burst(rec.obj.pos, names[rec.skin.emoji], 7);
          if (meet === "carry") { hero.carrying++; GB.audio.sfx("pickup"); }
          else GB.audio.sfx("pop");
          destroyActor(rec);
          stage.progress();
          afterMeet();
        } else if (meet === "bonk") {
          rec.dead = true;
          GB.audio.sfx("bonk");
          if (line) stage.toast(line);
          else if (role === "dodge") stage.toast(avoidLine || "Bonk! Keep going!");
          // dodge = bounce the hero a little; bonk role = the actor is bopped away
          if (role === "dodge") {
            hero.invuln = 1.1;
            hero.pos.x = Math.max(40 * u(), hero.pos.x - 70 * u());
            hero.vy = -260 * u();
          } else {
            stage.burst(rec.obj.pos, names[rec.skin.emoji], 6);
            stage.progress(); // bop-able things count toward the goal
            afterMeet();
          }
          destroyActor(rec);
        } else if (meet === "squash") {
          rec.dead = true;
          const sc0 = rec.obj.scale.x;
          rec.obj.scale = k.vec2(sc0 * 1.5, sc0 * 0.25); // flat as a pancake
          k.wait(0.5, () => destroyActor(rec));
          stage.burst(rec.obj.pos, names[rec.skin.emoji], 8);
          GB.juice.haptic(12);
          stage.progress();
          afterMeet();
        } else if (meet === "wiggle") {
          // decoy: comically refuses, wiggles, scoots aside
          GB.audio.sfx("bonk");
          if (line) stage.toast(line);
          rec.obj.angle += 40;
          rec.obj.pos.x += rand(-70, 70) * u();
          rec.obj.pos.y += rand(-40, 40) * u();
        } else if (meet === "shove") {
          // guard: blocks the way — bounces the hero back, never a penalty
          GB.audio.sfx("bonk");
          if (line) stage.toast(line);
          hero.invuln = 1.0;
          const dx = hero.pos.x - rec.obj.pos.x, dy = hero.pos.y - rec.obj.pos.y;
          const m = Math.hypot(dx, dy) || 1;
          hero.pos.x += (dx / m) * 80 * u();
          hero.pos.y += (dy / m) * 40 * u();
        }
      }

      function destroyActor(rec) {
        const ix = live.indexOf(rec);
        if (ix >= 0) live.splice(ix, 1);
        try { k.destroy(rec.obj); } catch (e) {}
      }

      function afterMeet() {
        // reached the goal early? cue the finale right away
        if (stage.score() >= total && !finaleOn) {
          spawnedAll = true;
          // clear remaining actors with a gentle poof
          live.slice().forEach((r) => {
            stage.burst(r.obj.pos, names[r.skin.emoji], 4);
            destroyActor(r);
          });
          startFinale();
        }
      }

      /* ---- finales -------------------------------------------------------- */
      function startFinale() {
        const line = (ctx.it.feedback && ctx.it.feedback.correct) || "You did it! 🎉";
        if (finaleKind === "tower") {
          // pieces swing in; tap to drop — stack `goal` (or 5) of them skyward
          const pieces = actors.flatMap((a) => a.skins);
          const pool = pieces.length ? pieces : [finaleS];
          towerFinale(pool, line);
        } else if (finaleKind === "bigOne") {
          bigOneFinale(line);
        } else if (finaleKind === "clear") {
          // the remaining stragglers become poppable confetti — pop N to close
          clearFinale(line);
        } else {
          reachFinale(line);
        }
      }

      function finaleBanner(text) {
        banner.textContent = text;
        banner.classList.add("show");
        clearTimeout(bannerTimer);
        bannerTimer = setTimeout(() => banner.classList.remove("show"), 2600);
      }

      function reachFinale(line) {
        finaleBanner(finaleLine || "Here it comes — reach it!");
        const f = k.add([k.sprite(names[finaleS.emoji]), k.pos(W + 120 * u(), groundY - 8 * u()),
          k.anchor("center"), k.scale(1.6 * u()), k.z(7)]);
        f.onUpdate(() => {
          f.pos.x -= 210 * u() * sf * stage.tune.speed * k.dt();
          if (f.pos.dist(hero.pos) < 64 * u()) stage.win();
        });
      }

      function bigOneFinale(line) {
        finaleBanner(line || "Here comes the BIG one!");
        // a giant guarding the goal: hover it, wait for the tell, then tap-tap-tap
        const big = k.add([k.sprite(names[finaleS.emoji]), k.pos(W * 0.72, H * 0.4),
          k.anchor("center"), k.scale(3.2 * u() * stage.tune.size), k.rotate(0), k.area(), k.z(7),
          { t: 0, taps: 0, need: 3, tell: false, tellT: 0 }]);
        big.onUpdate(() => {
          big.t += k.dt();
          big.angle = Math.sin(big.t * 2) * 6;
          if (!big.tell && big.t > 2.2 && Math.random() < 0.4 * k.dt()) { big.tell = true; big.tellT = 0; }
          if (big.tell) {
            big.tellT += k.dt();
            const sc = 3.2 * u() * stage.tune.size * (1 + Math.sin(big.tellT * 9) * 0.08);
            big.scale = k.vec2(sc, sc);
            if (big.tellT > 1.4) { big.tell = false; big.t = 0; }
          }
        });
        big.onClick(() => {
          if (!big.tell) { GB.audio.sfx("bonk"); big.angle += 25; return; } // too early — it wobbles
          big.taps++;
          stage.burst(big.pos, names[finaleS.emoji], 6);
          GB.juice.haptic(14);
          if (big.taps >= big.need) { stage.burst(big.pos, names[finaleS.emoji], 14); stage.win(); }
        });
      }

      function clearFinale(line) {
        finaleBanner(line || "Pop the rest — clear the field!");
        const need = Math.max(3, Math.min(8, Math.round(total / 2)));
        let popped = 0;
        stage.every(() => rand(0.6, 1.1) / (sf * stage.tune.speed), () => {
          if (popped >= need * 2) return;
          const s = pick(spec.flatActors).skin;
          const o = k.add([k.sprite(names[s.emoji]), k.pos(rand(60 * u(), W - 60 * u()), H + 40 * u()),
            k.anchor("center"), k.scale(0.95 * u() * stage.tune.size), k.area(), k.z(6), "qpop",
            { vy: rand(70, 130) * u() * sf, t: rand(0, 6) }]);
          o.onUpdate(() => {
            o.t += k.dt();
            o.pos.y -= o.vy * stage.tune.speed * k.dt();
            o.pos.x += Math.sin(o.t * 2.4) * 40 * u() * k.dt();
            if (o.pos.y < -60 * u()) k.destroy(o);
          });
          o.onClick(() => {
            stage.burst(o.pos, names[s.emoji], 6);
            GB.juice.haptic(10);
            k.destroy(o);
            if (++popped >= need) stage.win();
          });
        });
      }

      function towerFinale(pool, line) {
        finaleBanner(line || "Stack them HIGH!");
        const need = 5;
        let stacked = 0, topY = groundY, towerX = W / 2, swing = null, falling = null, t = 0;
        const placed = [];
        function newSwing() {
          const s = pick(pool);
          swing = k.add([k.sprite(names[s.emoji]), k.pos(W / 2, 64 * u()), k.anchor("center"),
            k.scale(0.8 * u()), k.rotate(0), k.z(8), { vy: 0, vx: 0, sname: names[s.emoji] }]);
        }
        newSwing();
        const drop = () => { if (swing && !falling) { falling = swing; swing = null; GB.audio.sfx("whoosh"); } };
        k.onMousePress(drop);
        k.onKeyPress("space", drop);
        k.onUpdate(() => {
          const dt = k.dt();
          t += dt;
          if (swing) swing.pos.x = W / 2 + Math.sin(t * 1.7 * sf * stage.tune.speed) * (W / 2 - 90 * u());
          if (!falling) return;
          falling.vy += 2100 * u() * dt;
          falling.pos.y += falling.vy * dt;
          falling.pos.x += falling.vx * dt;
          if (falling.vx) falling.angle += 320 * dt;
          if (falling.vx && falling.pos.y > H + 80 * u()) { k.destroy(falling); falling = null; newSwing(); return; }
          if (!falling.vx && falling.pos.y + 30 * u() >= topY) {
            const dx = falling.pos.x - towerX;
            const wiggle = 60 * u() * stage.tune.size;
            if (stacked === 0 || Math.abs(dx) <= wiggle) {
              falling.pos.y = topY - 30 * u();
              falling.pos.x = stacked === 0 ? falling.pos.x : towerX + dx * 0.35;
              falling.vy = 0;
              towerX = falling.pos.x;
              topY -= 56 * u();
              stacked++;
              placed.push(falling);
              stage.burst(falling.pos, falling.sname, 5);
              GB.juice.haptic(12);
              falling = null;
              // tower outgrows the screen → everything rides down one storey
              if (topY < H * 0.4) {
                placed.forEach((o) => (o.pos.y += 56 * u()));
                topY += 56 * u();
              }
              if (stacked >= need) { stage.win(); return; }
              newSwing();
            } else {
              GB.audio.sfx("bonk");
              stage.toast(pick(["Wide! Try again! 😅", "Boing — off it goes!"]));
              falling.vx = (dx > 0 ? 1 : -1) * 260 * u();
              falling.vy = -380 * u();
            }
          }
        });
      }
    }
  }

  /* =====================================================================
     REGISTRATION — one type, composed per book
     ===================================================================== */
  GB.define("arcade-quest", { icon: "🗺️", arcade: true, render(ctx) {
    const spec = buildQuest(ctx);
    const introIcons = [spec.heroS.emoji, ...spec.flatActors.slice(0, 3).map((a) => a.skin.emoji)];
    GB.arcade.intro(ctx, {
      sprites: introIcons,
      how: spec.how || defaultHow(spec),
      fallback: (c) => questFallback(c, spec),
      run: (stage) => runQuest(stage, ctx, spec),
    });
  } });

  function defaultHow(spec) {
    const c = spec.control;
    if (c === "flap") return "Tap to flap — gather them all!";
    if (c === "steer") return "Drag to steer — gather them all!";
    if (c === "drive") return "Hold and drag to drive — gather them all!";
    if (c === "hop") return "Tap to hop (twice for a BIG hop) — gather them all!";
    return "Tap to jump — gather them all!";
  }
})();