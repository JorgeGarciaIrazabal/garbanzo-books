// ================================================================================= library
async function loadLibrary() {
  try {
    const res = await fetch("/api/library");
    const data = await res.json();
    libraryWorlds = data.worlds || [];
    renderLibrary(libraryWorlds, data.errors || []);
  } catch (e) {
    const lib = $("#library");
    if (lib) lib.innerHTML = '<div class="empty">Could not load library: ' + escapeHtml(e.message) + "</div>";
  }
}

function pill(text, cls) { return `<span class="pill ${cls || ""}">${escapeHtml(text)}</span>`; }

// Which worlds the author has collapsed on the shelf — persisted so the view survives reloads
// and rebuilds (loadLibrary re-renders constantly as stories publish/delete).
function collapsedWorlds() {
  try { return new Set(JSON.parse(localStorage.getItem("gb_lib_collapsed") || "[]")); }
  catch (e) { return new Set(); }
}
function saveCollapsedWorlds(set) {
  try { localStorage.setItem("gb_lib_collapsed", JSON.stringify([...set])); } catch (e) { /* non-fatal */ }
}
function toggleWorldCollapsed(slug, force) {
  const set = collapsedWorlds();
  const on = force === undefined ? !set.has(slug) : force;
  if (on) set.add(slug); else set.delete(slug);
  saveCollapsedWorlds(set);
  const art = document.querySelector(`.world[data-w="${CSS.escape(slug)}"]`);
  if (art) {
    art.classList.toggle("collapsed", on);
    const head = art.querySelector(".world-head");
    if (head) head.setAttribute("aria-expanded", on ? "false" : "true");
  }
}
// Collapse / expand every world at once (the bar button).
function setAllWorldsCollapsed(on) {
  saveCollapsedWorlds(on ? new Set(libraryWorlds.map(w => w.slug)) : new Set());
  document.querySelectorAll("#library .world").forEach(art => {
    art.classList.toggle("collapsed", on);
    const head = art.querySelector(".world-head");
    if (head) head.setAttribute("aria-expanded", on ? "false" : "true");
  });
}

function renderLibrary(worlds, errors) {
  const lib = $("#library");
  if (!lib) return;
  // Shelf totals in the bar above the list.
  const counts = $("#lib-counts");
  if (counts) {
    const ns = worlds.reduce((a, w) => a + w.stories.length, 0);
    const np = worlds.reduce((a, w) => a + w.stories.filter(s => s.status === "published").length, 0);
    counts.textContent = worlds.length
      ? `${worlds.length} world${worlds.length === 1 ? "" : "s"} · ${ns} ${ns === 1 ? "story" : "stories"} · ${np} published`
      : "Everything on your shelves — drafts & published.";
  }
  // A malformed file no longer blanks the library — show the good worlds and warn about bad files.
  const banner = (errors && errors.length)
    ? `<div class="libwarn">⚠ ${errors.length} file(s) couldn't be read and were skipped:<ul>` +
        errors.map(e => `<li>${escapeHtml(e)}</li>`).join("") + `</ul></div>`
    : "";
  if (!worlds.length) {
    lib.innerHTML = banner + '<div class="empty">No worlds yet. Pick a guided form on the left to make your first book ✨</div>';
    return;
  }
  const collapsed = collapsedWorlds();
  lib.innerHTML = banner + worlds.map(w => `
    <article class="world${collapsed.has(w.slug) ? " collapsed" : ""}" data-w="${escapeHtml(w.slug)}">
      ${(w.palette||[]).length ? `<div class="swatches">${w.palette.map(p=>`<span class="sw" title="${escapeHtml(p.name)}" style="background:${escapeHtml(p.hex)}"></span>`).join("")}</div>` : ""}
      <div class="world-head" data-w="${escapeHtml(w.slug)}" role="button" tabindex="0"
        aria-expanded="${collapsed.has(w.slug) ? "false" : "true"}" title="Click to collapse / expand this world">
        <span class="world-chev" aria-hidden="true">▾</span>
        <h3>${escapeHtml(w.title)}</h3>
        <span class="world-count">${w.stories.length} ${w.stories.length === 1 ? "story" : "stories"} · ${w.characters.length} cast</span>
        <button type="button" class="delbtn delworld" data-w="${escapeHtml(w.slug)}" data-title="${escapeHtml(w.title || w.slug)}"
          title="Delete this whole world — every character and story in it">🗑 Delete world</button>
      </div>
      <div class="world-body">
      <p class="tagline">${escapeHtml(w.tagline || w.premise || "")}</p>
      <div class="row">${(w.age_bands||[]).map(a=>pill(a,"age")).join("")}${(w.themes||[]).slice(0,4).map(t=>pill(t)).join("")}</div>
      <div class="subhead">Bookshelf</div>
      <div class="shelf">
      ${w.stories.map(s=>{
        const pub = s.status === "published";
        // A draft only lives in the studio preview build; a published story lives in BOTH the
        // studio preview and the public preview. Linking straight to the right build avoids
        // the user landing on a 404 (drafts are not in /publish-preview/).
        const readHref = pub
          ? `/publish-preview/story/${w.slug}/${s.slug}/index.html`
          : `/preview/story/${w.slug}/${s.slug}/index.html`;
        // Cover: page-00 art from the studio preview build; falls back to a paper cover.
        const coverSrc = `/preview/story/${encodeURIComponent(w.slug)}/${encodeURIComponent(s.slug)}/images/page-00.png`;
        return `
        <a class="bookcard ${pub ? "is-pub" : "is-draft"}" href="${readHref}" target="_blank"
           title="${escapeHtml(s.logline || s.title || "")}${pub ? "" : " (draft — opens the studio preview)"}">
          <span class="bookcover">
            <img src="${coverSrc}" alt="" loading="lazy" onerror="this.parentElement.classList.add('noimg')">
            <span class="ribbon ${pub ? "pub" : "draft"}">${pub ? "published" : "draft"}</span>
            ${s.logline ? `<span class="caption">${escapeHtml(s.logline)}</span>` : ""}
            <span class="readhint">Read ↗</span>
          </span>
          <span class="booktitle">${escapeHtml(s.title)}</span>
          <span class="bookmeta">${escapeHtml(s.age_band || "")} · ${s.pages} pages · ${s.interactions} ${s.interactions === 1 ? "game" : "games"}</span>
          <button type="button" class="pubbtn ${pub ? "to-draft" : "to-pub"}"
            data-w="${escapeHtml(w.slug)}" data-s="${escapeHtml(s.slug)}" data-next="${pub ? "draft" : "published"}"
            title="${pub ? "Take this story off the public site (back to draft)" : "Run the publish gate and put this story on the public site"}">
            ${pub ? "⏏ Unpublish" : "🚀 Publish"}</button>
          <button type="button" class="delbtn delstory"
            data-w="${escapeHtml(w.slug)}" data-s="${escapeHtml(s.slug)}" data-title="${escapeHtml(s.title || s.slug)}"
            title="Delete this story permanently (text + images)">🗑</button>
        </a>`;
      }).join("") || '<p class="tagline">No stories yet.</p>'}
      </div>
      <div class="subhead">Cast</div>
      <div class="cast">
      ${w.characters.map(c=>{
        // Reference art is copied into the preview build as refs/<slug>-model-sheet.png;
        // the onerror chain retries .svg, then falls back to a friendly bean.
        const av = (c.has_reference && c.slug)
          ? `<img src="/preview/world/${encodeURIComponent(w.slug)}/refs/${encodeURIComponent(c.slug)}-model-sheet.png" alt="" loading="lazy"
               onerror="if(this.dataset.f){this.closest('.castchip').classList.add('noimg');}else{this.dataset.f=1;this.src=this.src.replace('.png','.svg');}">`
          : "";
        return `<button type="button" class="castchip ${av ? "" : "noimg"}" data-w="${escapeHtml(w.slug)}" data-c="${escapeHtml(c.slug || c.name || "")}"
          title="${escapeHtml(c.one_liner || c.role || "")} — click for the character card">
          <span class="cast-avatar">${av}</span>
          <span class="cast-name">${escapeHtml(c.name)}${c.stages && c.stages.length > 1 ? ` <em>· ${c.stages.length} stages</em>` : ""}</span>
        </button>`;
      }).join("") || '<p class="tagline">No characters yet.</p>'}
      </div>
      </div>
    </article>`).join("");
}

// ------------------------------------------------------------ character card (library popup)
// Clicking a cast chip opens the character's bible as a pop-up card: reference art, who they
// are, personality, voice, and their evolution track. Pure read-only — closes on ✕, backdrop
// click, or Escape.
function closeCharacterCard() {
  const ov = $("#char-overlay");
  if (ov) {
    if (ov._esc) document.removeEventListener("keydown", ov._esc);
    ov.remove();
  }
}
function openCharacterCard(w, c) {
  closeCharacterCard();
  const pillRow = (items, cls) => (items && items.length)
    ? `<div class="row">${items.map(t => pill(t, cls)).join("")}</div>` : "";
  const listRows = (items) => (items && items.length)
    ? `<ul class="cc-list">${items.map(t => `<li>${escapeHtml(t)}</li>`).join("")}</ul>` : "";
  const section = (label, body) => body ? `<div class="cc-section"><div class="subhead">${label}</div>${body}</div>` : "";

  // Reference art from the studio preview build (refs/<slug>-<filename>); the onerror chain
  // retries .svg before giving up (some characters only have an svg sheet).
  const refName = c.reference || "model-sheet.png";
  const refSrc = `/preview/world/${encodeURIComponent(w.slug)}/refs/${encodeURIComponent((c.slug || "") + "-" + refName)}`;
  const art = c.has_reference
    ? `<div class="cc-art"><img src="${refSrc}" alt="${escapeHtml(c.name || "")} reference sheet"
         onerror="if(this.dataset.f){this.closest('.cc-art').classList.add('noimg');}else{this.dataset.f=1;this.src=this.src.replace(/\\.[a-z]+$/,'.svg');}"></div>`
    : `<div class="cc-art noimg"></div>`;

  const who = [c.species, c.pronouns, c.role].filter(Boolean).map(escapeHtml).join(" · ");
  const evo = (c.evolution && c.evolution.length)
    ? `<ol class="cc-evo">${c.evolution.map(st =>
        `<li><strong>${escapeHtml(st.stage || "")}</strong>${st.summary ? ` — ${escapeHtml(st.summary)}` : ""}</li>`).join("")}</ol>`
    : "";
  const phrases = (c.catchphrases && c.catchphrases.length)
    ? `<div class="cc-phrases">${c.catchphrases.map(p => `<span class="cc-phrase">“${escapeHtml(p)}”</span>`).join("")}</div>` : "";

  const ov = document.createElement("div");
  ov.className = "char-overlay";
  ov.id = "char-overlay";
  ov.innerHTML = `<div class="char-card" role="dialog" aria-label="${escapeHtml(c.name || "character")}">
    <button class="kids-x cc-x" title="Close">✕</button>
    ${art}
    <div class="cc-body">
      <div class="cc-head">
        <h3>${escapeHtml(c.name || "")}</h3>
        ${who ? `<span class="cc-who">${who}</span>` : ""}
      </div>
      ${c.one_liner ? `<p class="cc-oneliner">${escapeHtml(c.one_liner)}</p>` : ""}
      ${section("Personality", pillRow(c.traits))}
      ${section("Wants", c.motivation ? `<p class="cc-text">${escapeHtml(c.motivation)}</p>` : "")}
      ${section("Flaws &amp; quirks", listRows([].concat(c.flaws || [], c.quirks || [])))}
      ${section("How they talk", (c.speech_style ? `<p class="cc-text">${escapeHtml(c.speech_style)}</p>` : "") + phrases)}
      ${section("Evolution", evo)}
      <p class="cc-foot">from <strong>${escapeHtml(w.title || w.slug)}</strong> · <code>characters/${escapeHtml(c.slug || "")}.yaml</code></p>
    </div>
  </div>`;
  document.body.appendChild(ov);
  ov.addEventListener("click", (e) => { if (e.target === ov) closeCharacterCard(); });
  const x = ov.querySelector(".cc-x");
  if (x) x.onclick = closeCharacterCard;
  ov._esc = (e) => { if (e.key === "Escape") closeCharacterCard(); };
  document.addEventListener("keydown", ov._esc);
}

function refreshPreview() {
  const f = $("#preview");
  if (f) f.src = f.src.split("?")[0] + "?t=" + Date.now();
}
function refreshPublicPreview() {
  const f = $("#public-preview");
  if (f) f.src = f.src.split("?")[0] + "?t=" + Date.now();
}
async function refreshPublishStatus() {
  // Surface "last built 2m ago" on the public-preview tab and disable its iframe until a
  // build exists (so the user doesn't see a 404 iframe with no explanation).
  const badge = $("#public-badge");
  const frame = $("#public-preview");
  try {
    const r = await fetch("/api/publish/status");
    const s = await r.json();
    if (badge) {
      if (s.built) {
        const m = s.last_built_mtime ? Math.max(1, Math.round((Date.now()/1000 - s.last_built_mtime) / 60)) : null;
        badge.textContent = m != null ? `built ${m}m ago` : "built";
        badge.className = "badge pub ok";
      } else {
        badge.textContent = "no build yet — click Publish";
        badge.className = "badge pub empty";
      }
    }
    if (frame) {
      // A 404 iframe renders as the studio's 404 page inside; the badge tells the user
      // to click Publish first. We still load the iframe so the tab is ready to show
      // the result the moment they rebuild.
      frame.dataset.built = s.built ? "1" : "0";
    }
    // The Pages workflow only deploys pushes to main — warn when Deploy would push
    // somewhere it won't auto-ship from.
    const bw = $("#branch-warn");
    if (bw) {
      const off = s.branch && s.branch !== "main" && s.branch !== "HEAD";
      bw.textContent = off ? `on '${s.branch}' — Pages auto-deploys from main` : "";
      bw.classList.toggle("hidden", !off);
      bw.classList.toggle("warnish", !!off);
    }
  } catch (e) { /* non-fatal — leave the badge as-is */ }
}

// Publish / unpublish ONE story from its library card. publish_story.py runs the full
// validator gate before allowing "published", so this button IS the publish gate — when it
// fails, the gate's output lands in the chat so the author sees exactly what to fix.
// On success the studio quietly rebuilds both previews so every link/ribbon stays true.
async function setStoryStatus(btn) {
  const wslug = btn.dataset.w, sslug = btn.dataset.s, next = btn.dataset.next;
  if (!wslug || !sslug || btn.disabled) return;
  const label = btn.textContent;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>' + (next === "published" ? "Checking gate…" : "Working…");
  let data = null;
  try {
    const res = await fetch("/api/story/status", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ world: wslug, story: sslug, status: next }),
    });
    data = await res.json();
  } catch (e) {
    data = { ok: false, output: String((e && e.message) || e) };
  }
  if (!data.ok) {
    btn.disabled = false;
    btn.textContent = label;
    addMsg("system", "🚧 **" + sslug + "** wasn't " + (next === "published" ? "published" : "set to draft") +
      ":\n\n```\n" + String(data.output || "").trim() + "\n```", "system");
    return;
  }
  btn.innerHTML = '<span class="spinner"></span>Rebuilding…';
  // Both builds: studio preview (ribbons/links) + public preview (the real shape).
  try { await fetch("/api/build", { method: "POST" }); } catch (e) { /* non-fatal */ }
  try { await fetch("/api/build/publish", { method: "POST" }); } catch (e) { /* non-fatal */ }
  loadLibrary();
  refreshPreview();
  refreshPublicPreview();
  refreshPublishStatus();
  if (next === "published") {
    addMsg("system", "🚀 **" + sslug + "** passed the gate and is published. " +
      "It's in the public build — hit **Deploy** on the Publish tab to ship it to GitHub Pages.", "system");
  }
}
