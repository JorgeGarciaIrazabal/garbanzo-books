#!/usr/bin/env python3
"""Build the static site (world -> story -> tags) into site/, ready for GitHub Pages.

Usage:
    uv run python scripts/build_site.py                 # published stories only → ./site
    uv run python scripts/build_site.py --include-drafts
    uv run python scripts/build_site.py --base /garbanzo-books   # project-pages subpath (optional)
    uv run python scripts/build_site.py --out site_publish       # build to a different dir
                                                         (used by the studio for the
                                                         "what GitHub Pages will see" preview)
    uv run python scripts/build_site.py --deploy        # print manual gh-pages deploy commands

Emits: index, world hubs (+ character galleries), interactive readers, tag pages, assets,
search-index.json, sitemap.xml, .nojekyll.

The two-build pattern: GitHub Pages gets a published-only build of ./site (this is what the
`deploy-pages` workflow runs and what end users see). The studio can additionally build a
"with-drafts" preview into the SAME ./site for its in-app preview, or a published-only
preview into ./site_publish for the "this is what will go live" tab. Both end up identical to
the GH Pages output when --include-drafts is off; --out only changes WHERE the build lands.
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.colors import norm_hex  # noqa: E402
from lib.model import ROOT, load_all_worlds, normalize_rules  # noqa: E402

SITE = ROOT / "site"  # default output dir; `build(out=...)` may override per call
ASSET_SRC = Path(__file__).resolve().parent / "site_assets"

# Reader base font size (px) per age band (accessibility.md).
READER_BASE = {"0-3": 28, "3-5": 24, "5-7": 22, "7-9": 18, "9-12": 16}

# The reader runtime, split into a toolkit + game registry. Order matters: the core defines
# window.GB and the controller; the toolkit + game files populate it; reader.boot.js (last)
# calls GB.boot() once everything is registered. (tests/frontend/harness.js mirrors this list.)
READER_SCRIPTS = [
    "reader.core.js",
    "toolkit.audio.js",
    "toolkit.juice.js",
    "toolkit.scene.js",
    "toolkit.dnd.js",
    "toolkit.steps.js",
    "toolkit.reward.js",
    "toolkit.shared.js",
    "games.builtin.js",
    "games.rich.js",
    "games.custom.js",
    "reader.boot.js",
]

# Image file types copied into the published site (everything else in images/, e.g. the
# page-NN.prompt.txt audit sidecars, stays internal).
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".avif"}


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def shell(title: str, body: str, root: str, *, extra_head: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="{root}assets/styles.css">
{extra_head}
</head>
<body>
<header class="topbar">
  <a class="brand" href="{root}index.html">Garbanzo<span>Books</span></a>
  <nav>
    <a href="{root}index.html">Worlds</a>
    <a href="{root}tags/index.html">Tags</a>
    <button class="btn secondary" id="dyslexia-toggle" type="button">Aa Easy-read</button>
  </nav>
</header>
<main>
{body}
</main>
<footer class="site">Made with the Garbanzo Books AI storybook studio · stories for growing readers</footer>
<script>
  document.getElementById('dyslexia-toggle').onclick = () => document.body.classList.toggle('dyslexia');
</script>
</body>
</html>"""


def thumb_for_story(story) -> str | None:
    cover = (story.data.get("cover") or {}).get("image")
    if cover:
        return cover
    for p in story.data.get("pages", []) or []:
        f = (p.get("image") or {}).get("file")
        if f:
            return f
    return None


def palette_swatches(world) -> str:
    out = ""
    for s in (world.data.get("art_style", {}) or {}).get("palette", []) or []:
        hexc = norm_hex(s.get("hex"))
        if not hexc:
            continue
        out += f'<div class="swatch" title="{esc(s.get("name",""))} {esc(hexc)}" style="background:{esc(hexc)}"></div>'
    return out


def chips(items, cls="chip") -> str:
    return "".join(f'<span class="{cls}">{esc(i)}</span>' for i in (items or []))


# ---------------- page builders ----------------

def build_index(worlds, root="") -> str:
    cards = ""
    for w in worlds:
        pub = [s for s in w.stories if s.included]
        if not pub:
            continue
        thumb = next((thumb_for_story(s) for s in pub if thumb_for_story(s)), None)
        # story thumbs live under the story dir; reference via the story path
        thumb_html = ""
        if thumb:
            ts = pub[0]
            thumb_html = f'<img src="{root}story/{w.slug}/{ts.slug}/{esc(thumb)}" alt="" loading="lazy">'
        else:
            thumb_html = f'<div style="display:flex;height:100%">{palette_swatches(w)}</div>'
        cards += f"""<a class="card" href="{root}world/{w.slug}/index.html">
  <div class="thumb">{thumb_html}</div>
  <div class="body">
    <h3>{esc(w.data.get('title'))}</h3>
    <p>{esc(w.data.get('tagline') or w.data.get('premise',''))}</p>
    <div class="chips">{chips(w.data.get('target_age_bands'), 'chip age')}{chips(w.data.get('themes'))}</div>
  </div>
</a>"""
    body = f"""<section class="hero">
  <h1>A library of little worlds</h1>
  <p>Interactive storybooks that make children <em>want</em> to read — with puzzles, games, and
  characters who grow up alongside their readers.</p>
</section>
<div class="wrap"><div class="grid">{cards or '<p>No published stories yet. Build one with the studio, then <code>/publish</code>.</p>'}</div></div>"""
    return shell("Garbanzo Books — interactive storybooks", body, root)


def build_world(world, root="../../") -> str:
    pub = [s for s in world.stories if s.included]
    chars = ""
    for cslug, c in world.characters.items():
        ref = (c.get("reference_images") or [None])[0]
        # reference images are copied into world/<slug>/refs/<cslug>-<name> in build()
        ref_html = (f'<img src="refs/{esc(cslug)}-{esc(Path(ref).name)}" alt="{esc(c.get("name"))} reference">'
                    if ref else f'<div style="display:flex;height:100%">{palette_swatches(world)}</div>')
        chars += f"""<div class="card">
  <div class="thumb">{ref_html}</div>
  <div class="body"><h3>{esc(c.get('name'))}</h3>
  <p>{esc(c.get('one_liner') or c.get('role',''))}</p>
  <div class="chips">{chips(c.get('personality',{}).get('traits'))}</div></div>
</div>"""
    # The laws of the world — surfaced so a reader (and the author) can see what every
    # story here must honour (Core Principle #2; ties to story.affirms_rules).
    rules = normalize_rules(world.data)
    rules_html = ""
    if rules:
        items = "".join(f"<li>{esc(r['text'])}</li>" for r in rules if r["text"])
        if items:
            rules_html = (f'\n  <h2 class="section-title">The rules of this world</h2>'
                          f'\n  <ul class="world-rules">{items}</ul>')
    story_cards = ""
    for s in pub:
        thumb = thumb_for_story(s)
        th = (f'<img src="{root}story/{world.slug}/{s.slug}/{esc(thumb)}" alt="" loading="lazy">'
              if thumb else f'<div style="display:flex;height:100%">{palette_swatches(world)}</div>')
        story_cards += f"""<a class="card" href="{root}story/{world.slug}/{s.slug}/index.html">
  <div class="thumb">{th}</div>
  <div class="body"><h3>{esc(s.data.get('title'))}</h3>
  <p>{esc(s.data.get('logline',''))}</p>
  <div class="chips"><span class="chip age">{esc(s.data.get('age_band'))}</span>{chips(s.data.get('tags'))}</div></div>
</a>"""
    body = f"""<div class="wrap">
  <div class="breadcrumb"><a href="{root}index.html">Worlds</a> › {esc(world.data.get('title'))}</div>
  <section class="hero" style="text-align:left;padding:16px 0">
    <h1>{esc(world.data.get('title'))}</h1>
    <p style="margin:0">{esc(world.data.get('premise',''))}</p>
    <div class="swatches">{palette_swatches(world)}</div>
    <div class="chips">{chips(world.data.get('target_age_bands'),'chip age')}{chips(world.data.get('themes'))}{chips(world.data.get('genres'))}</div>
  </section>
  <h2 class="section-title">Stories</h2>
  <div class="grid">{story_cards or '<p>No stories yet.</p>'}</div>
  <h2 class="section-title">Characters</h2>
  <div class="grid">{chars or '<p>No characters yet.</p>'}</div>{rules_html}
</div>"""
    return shell(world.data.get("title", "World"), body, root)


def build_reader(world, story, root="../../../") -> str:
    # Inline a slim story payload for the reader runtime (only what the client needs).
    payload = {
        "title": story.data.get("title"),
        "pages": [
            {
                "number": p.get("number"),
                "kind": p.get("kind"),
                "text": p.get("text"),
                "image": {"file": (p.get("image") or {}).get("file"),
                          "alt": (p.get("image") or {}).get("alt")},
                "layout": p.get("layout"),
                "interaction": p.get("interaction"),
                "vocabulary": p.get("vocabulary"),
                "reading_notes": p.get("reading_notes"),
            }
            for p in story.data.get("pages", []) or []
        ],
    }
    base = READER_BASE.get(story.data.get("age_band", "5-7"), 20)
    data_json = json.dumps(payload, ensure_ascii=False)
    tags_html = "".join(
        f'<a class="chip" href="{root}tags/{esc(t)}/index.html">{esc(t)}</a>'
        for t in story.data.get("tags", []) or []
    )
    # The back-cover blurb (summary) sits under the logline on the landing, when present.
    summary = (story.data.get("summary") or "").strip()
    summary_html = f'\n  <p class="story-summary">{esc(summary)}</p>' if summary else ""
    body = f"""<div class="reader" style="--reader-base:{base}px">
  <div class="breadcrumb"><a href="{root}index.html">Worlds</a> ›
    <a href="{root}world/{world.slug}/index.html">{esc(world.data.get('title'))}</a> ›
    {esc(story.data.get('title'))}</div>
  <h1 style="margin:.2em 0">{esc(story.data.get('title'))}</h1>
  <p style="color:var(--muted);margin:.2em 0 1em">{esc(story.data.get('logline',''))}</p>{summary_html}
  <div id="stage"></div>
  <div id="interaction"></div>
  <div class="reader-controls">
    <button class="btn secondary" id="prev" type="button">‹ Back</button>
    <span class="progress pageno" id="pageno"></span>
    <button class="btn" id="next" type="button">Next ›</button>
  </div>
  <div class="chips" style="margin-top:18px">{tags_html}</div>
</div>
<script id="story-data" type="application/json">{data_json}</script>
""" + "".join(f'<script src="{root}assets/{s}"></script>\n' for s in READER_SCRIPTS)
    return shell(f"{story.data.get('title')} — read", body, root)


def build_tag_index(tag_map, root="../../") -> str:
    rows = ""
    for tag, entries in sorted(tag_map.items()):
        rows += f'<a class="chip" href="{root}tags/{esc(tag)}/index.html">{esc(tag)} ({len(entries)})</a> '
    body = f"""<div class="wrap"><div class="breadcrumb"><a href="{root}index.html">Worlds</a> › Tags</div>
    <h1>Browse by tag</h1><div class="chips">{rows or 'No tags yet.'}</div></div>"""
    return shell("Tags", body, root)


def build_tag_page(tag, entries, root="../../") -> str:
    cards = ""
    for world, s in entries:
        thumb = thumb_for_story(s)
        th = (f'<img src="{root}story/{world.slug}/{s.slug}/{esc(thumb)}" alt="" loading="lazy">'
              if thumb else "")
        cards += f"""<a class="card" href="{root}story/{world.slug}/{s.slug}/index.html">
  <div class="thumb">{th}</div>
  <div class="body"><h3>{esc(s.data.get('title'))}</h3>
  <p>{esc(world.data.get('title'))} · {esc(s.data.get('logline',''))}</p>
  <div class="chips"><span class="chip age">{esc(s.data.get('age_band'))}</span></div></div></a>"""
    body = f"""<div class="wrap"><div class="breadcrumb"><a href="{root}index.html">Worlds</a> ›
    <a href="{root}tags/index.html">Tags</a> › {esc(tag)}</div>
    <h1>#{esc(tag)}</h1><div class="grid">{cards}</div></div>"""
    return shell(f"#{tag}", body, root)


# ---------------- driver ----------------

def build(include_drafts: bool, out: Path | None = None) -> dict:
    """Render the site tree into `out` (defaults to the module-level SITE = ./site).

    Passing a custom `out` lets the studio build a second, "published-only, what GH Pages
    will see" copy into e.g. ./site_publish — without clobbering the in-app preview build
    sitting at ./site (which is --include-drafts so the author can browse their WIP)."""
    site = Path(out) if out is not None else SITE
    if site.exists():
        shutil.rmtree(site)
    site.mkdir(parents=True)
    (site / ".nojekyll").write_text("", encoding="utf-8")
    shutil.copytree(ASSET_SRC, site / "assets")

    worlds = load_all_worlds(with_stories=True)
    tag_map: dict[str, list] = defaultdict(list)
    search: list[dict] = []
    urls: list[str] = ["index.html", "tags/index.html"]

    # Mark which stories are included.
    for w in worlds:
        for s in w.stories:
            s.included = include_drafts or s.data.get("status") == "published"

    # Index
    (site / "index.html").write_text(build_index(worlds), encoding="utf-8")

    for w in worlds:
        wdir = site / "world" / w.slug
        wdir.mkdir(parents=True, exist_ok=True)
        # Copy character reference images into world/<slug>/refs/
        refs_out = wdir / "refs"
        for cslug, c in w.characters.items():
            for ref in c.get("reference_images", []) or []:
                src = (ROOT / "worlds" / w.slug / ref)
                if src.exists():
                    refs_out.mkdir(exist_ok=True)
                    shutil.copy2(src, refs_out / f"{cslug}-{Path(ref).name}")
        (wdir / "index.html").write_text(build_world(w), encoding="utf-8")
        urls.append(f"world/{w.slug}/index.html")

        for s in w.stories:
            if not s.included:
                continue
            sdir = site / "story" / w.slug / s.slug
            (sdir / "images").mkdir(parents=True, exist_ok=True)
            # copy page images (only image files — never the page-NN.prompt.txt audit
            # sidecars, which are internal and may quote the full assembled prompt)
            src_images = s.dir / "images"
            if src_images.is_dir():
                for img in src_images.iterdir():
                    if img.is_file() and img.suffix.lower() in IMAGE_EXTS:
                        shutil.copy2(img, sdir / "images" / img.name)
            # copy cover if outside images
            cover = (s.data.get("cover") or {}).get("image")
            if cover and not cover.startswith("images/"):
                csrc = s.dir / cover
                if csrc.exists():
                    shutil.copy2(csrc, sdir / Path(cover).name)
            (sdir / "index.html").write_text(build_reader(w, s), encoding="utf-8")
            urls.append(f"story/{w.slug}/{s.slug}/index.html")

            for t in s.data.get("tags", []) or []:
                tag_map[t].append((w, s))
            search.append({
                "title": s.data.get("title"),
                "world": w.data.get("title"),
                "world_slug": w.slug,
                "slug": s.slug,
                "age_band": s.data.get("age_band"),
                "logline": s.data.get("logline", ""),
                "tags": s.data.get("tags", []),
                "url": f"story/{w.slug}/{s.slug}/index.html",
            })

    # Tags
    (site / "tags").mkdir(exist_ok=True)
    (site / "tags" / "index.html").write_text(build_tag_index(tag_map), encoding="utf-8")
    for tag, entries in tag_map.items():
        tdir = site / "tags" / tag
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "index.html").write_text(build_tag_page(tag, entries), encoding="utf-8")
        urls.append(f"tags/{tag}/index.html")

    (site / "search-index.json").write_text(json.dumps(search, ensure_ascii=False, indent=2), encoding="utf-8")
    sitemap = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
    (site / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{sitemap}\n</urlset>',
        encoding="utf-8")

    return {"worlds": len(worlds), "stories": len(search), "tags": len(tag_map),
            "drafts_included": include_drafts,
            "out": str(site.relative_to(ROOT)) if site.is_absolute() and ROOT in site.parents else str(site)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the static site.")
    ap.add_argument("--include-drafts", action="store_true",
                    help="include stories with status=draft (default: only published). "
                         "The studio uses this for the in-app preview build.")
    ap.add_argument("--base", default="", help="(reserved) base path for project pages")
    ap.add_argument("--out", default=None,
                    help="output directory (default: ./site). The studio's 'publish preview' "
                         "build uses --out site_publish so it doesn't clobber the studio's "
                         "drafts-included preview at ./site.")
    ap.add_argument("--deploy", action="store_true", help="print manual gh-pages deploy steps")
    args = ap.parse_args()

    out = Path(args.out).resolve() if args.out else None
    stats = build(args.include_drafts, out=out)
    out_label = stats.get("out", "site")
    print(f"+ built {out_label}/ — {stats['worlds']} world(s), {stats['stories']} story page(s), "
          f"{stats['tags']} tag(s)"
          + ("  [drafts included]" if stats['drafts_included'] else "  [published only]"))
    if out_label == "site":
        print("  preview: uv run python -m http.server -d site 8008  →  http://localhost:8008")
    if args.deploy:
        print("\n  Manual gh-pages deploy:")
        print("    cd site && git init -q && git add -A && git commit -qm 'site'")
        print("    git branch -M gh-pages")
        print("    git remote add origin <your-repo-url> && git push -f origin gh-pages")
        print("    (or just push main and let .github/workflows/deploy-pages.yml deploy)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
