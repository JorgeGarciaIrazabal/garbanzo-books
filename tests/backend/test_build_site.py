"""Tests for ``scripts/build_site.py`` — the static-site generator that powers
the GitHub Pages output.

We test the *behavioural* contracts:
  * The world/story/tag URL structure shows up under site/
  * Draft stories are EXCLUDED by default, INCLUDED only with --include-drafts
  * search-index.json carries the keys the on-site search relies on
  * sitemap.xml lists every emitted URL
  * Character reference images get copied into the per-world refs/ dir
  * Each story page that has an image gets the image copied into site/story/.../images/
  * Page reader payload contains only the keys the runtime needs
  * thumb selection prefers cover.image, falls back to first page image
"""
from __future__ import annotations

import json

import pytest

from build_site import build


# ============================================================================ basics
def test_build_emits_top_level_files(workspace):
    stats = build(include_drafts=False)
    site = workspace.site
    assert (site / "index.html").exists()
    assert (site / ".nojekyll").exists()             # blocks Jekyll on GH Pages
    assert (site / "assets").is_dir()
    assert (site / "search-index.json").exists()
    assert (site / "sitemap.xml").exists()
    assert stats == {"worlds": 0, "stories": 0, "tags": 0, "drafts_included": False, "out": "site"}


def test_build_returns_counts_in_stats(workspace, write_world, factories):
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published",
                                          tags=["friendship", "courage"])])
    stats = build(include_drafts=False)
    assert stats["worlds"] == 1
    assert stats["stories"] == 1
    assert stats["tags"] == 2
    assert stats["drafts_included"] is False


# ============================================================================ draft filtering
def test_build_excludes_draft_stories_by_default(workspace, write_world, factories):
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="published", world="ww", status="published"),
                         factories.story(slug="my-draft", world="ww", status="draft")])
    build(include_drafts=False)
    site = workspace.site
    assert (site / "story" / "ww" / "published" / "index.html").exists()
    assert not (site / "story" / "ww" / "my-draft" / "index.html").exists()


def test_build_includes_drafts_when_flag_set(workspace, write_world, factories):
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="my-draft", world="ww", status="draft")])
    stats = build(include_drafts=True)
    assert stats["drafts_included"] is True
    assert (workspace.site / "story" / "ww" / "my-draft" / "index.html").exists()


# ============================================================================ url structure
def test_build_creates_world_story_tag_layout(workspace, write_world, factories):
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published",
                                          tags=["bedtime", "courage"])])
    build(include_drafts=False)
    site = workspace.site
    # world/<slug>/index.html — the world hub
    assert (site / "world" / "ww" / "index.html").exists()
    # story/<world>/<story>/index.html — the interactive reader
    assert (site / "story" / "ww" / "s1" / "index.html").exists()
    # tags/index.html — the tag browser
    assert (site / "tags" / "index.html").exists()
    # tags/<tag>/index.html — every tag gets its own page
    assert (site / "tags" / "bedtime" / "index.html").exists()
    assert (site / "tags" / "courage" / "index.html").exists()


# ============================================================================ search index
def test_search_index_lists_published_stories_with_required_keys(workspace, write_world, factories):
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published",
                                          tags=["friendship"])])
    build(include_drafts=False)
    index = json.loads((workspace.site / "search-index.json").read_text())
    assert len(index) == 1
    entry = index[0]
    for k in ("title", "world", "world_slug", "slug", "age", "logline", "tags", "url"):
        assert k in entry, f"search-index missing {k}"
    assert entry["url"].endswith("/index.html")
    assert "story/ww/s1" in entry["url"]


def test_search_index_excludes_drafts(workspace, write_world, factories):
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="draftie", world="ww", status="draft"),
                         factories.story(slug="liveone", world="ww", status="published")])
    build(include_drafts=False)
    index = json.loads((workspace.site / "search-index.json").read_text())
    slugs = [e["slug"] for e in index]
    assert "liveone" in slugs
    assert "draftie" not in slugs


# ============================================================================ sitemap
def test_sitemap_lists_every_emitted_url(workspace, write_world, factories):
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published",
                                          tags=["t1"])])
    build(include_drafts=False)
    sitemap = (workspace.site / "sitemap.xml").read_text()
    for url in ("index.html", "tags/index.html", "world/ww/index.html",
                "story/ww/s1/index.html", "tags/t1/index.html"):
        assert f"<loc>{url}</loc>" in sitemap


# ============================================================================ image copying
def test_build_copies_page_images_into_per_story_images_dir(workspace, write_world, factories):
    story = factories.story(slug="s1", world="ww", status="published")
    story["pages"][1]["image"]["file"] = "images/page-01.png"
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[story],
                image_files=["images/page-01.png"])
    build(include_drafts=False)
    out = workspace.site / "story" / "ww" / "s1" / "images" / "page-01.png"
    assert out.exists()


def test_build_copies_character_reference_images_into_world_refs_dir(workspace, write_world,
                                                                        factories):
    # Set up a real character reference image on disk
    char = factories.character(slug="hero", world="ww",
                                reference_images=["characters/hero.refs/sheet.png"])
    slug, wdir = write_world(slug="ww", characters=[char])
    refpath = wdir / "characters" / "hero.refs"
    refpath.mkdir(parents=True)
    (refpath / "sheet.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    build(include_drafts=True)
    # Reference images land at site/world/<slug>/refs/<charslug>-<filename>
    out = workspace.site / "world" / "ww" / "refs" / "hero-sheet.png"
    assert out.exists()


# ============================================================================ reader payload
def test_reader_html_embeds_story_data_json(workspace, write_world, factories):
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published")])
    build(include_drafts=False)
    reader = (workspace.site / "story" / "ww" / "s1" / "index.html").read_text()
    assert '<script id="story-data" type="application/json">' in reader
    # the runtime depends on the split reader bundle (controller + framework + game
    # libraries + last-loaded boot)
    assert "reader.js" in reader
    assert "gx.core.js" in reader
    assert "gx.board.js" in reader
    assert "gx.arcade.js" in reader
    assert "reader.boot.js" in reader


def test_reader_html_payload_only_contains_runtime_keys(workspace, write_world, factories):
    """The reader payload is a slim subset of story.yaml. Story fields like
    `spine`, `summary`, `moral` must NOT leak into the runtime JSON (smaller
    bundle, no spoilers in view-source for end pages)."""
    import re
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published",
                                          moral="hidden moral text 99999")])
    build(include_drafts=False)
    reader = (workspace.site / "story" / "ww" / "s1" / "index.html").read_text()
    # Extract the JSON payload from the <script id="story-data"> block
    m = re.search(r'<script id="story-data"[^>]*>([\s\S]*?)</script>', reader)
    assert m
    payload = json.loads(m.group(1))
    assert set(payload.keys()) == {"title", "pages"}
    # And the hidden moral string didn't sneak into the bundle
    assert "hidden moral text 99999" not in reader


def test_reader_per_page_keys_match_runtime_contract(workspace, write_world, factories):
    """Each page in the runtime payload must have exactly these keys — the
    reader.js code reads them directly without defensive null-checks for
    structural keys."""
    import re
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published")])
    build(include_drafts=False)
    reader = (workspace.site / "story" / "ww" / "s1" / "index.html").read_text()
    m = re.search(r'<script id="story-data"[^>]*>([\s\S]*?)</script>', reader)
    payload = json.loads(m.group(1))
    expected = {"number", "kind", "text", "image", "layout", "interaction",
                "vocabulary", "reading_notes"}
    for page in payload["pages"]:
        assert set(page.keys()) == expected, f"reader page schema drift: {page.keys()}"


def test_reader_payload_preserves_rich_vocabulary_objects(workspace, write_world, factories):
    """Rich vocabulary hints {word, clue, icon, read_aloud} must survive the
    build and reach the runtime so the reader can show clickable in-text clues."""
    import re
    story = factories.story(slug="s1", world="ww", status="published")
    story["pages"][1]["vocabulary"] = [
        {"word": "glimmer", "clue": "shine with a soft light.", "icon": "✨",
         "read_aloud": "glimmer"},
    ]
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[story])
    build(include_drafts=False)
    reader = (workspace.site / "story" / "ww" / "s1" / "index.html").read_text()
    m = re.search(r'<script id="story-data"[^>]*>([\s\S]*?)</script>', reader)
    payload = json.loads(m.group(1))
    vocab = payload["pages"][1]["vocabulary"]
    assert len(vocab) == 1
    assert vocab[0] == {
        "word": "glimmer",
        "clue": "shine with a soft light.",
        "icon": "✨",
        "read_aloud": "glimmer",
    }


# ============================================================================ accessibility hooks
def test_reader_includes_dyslexia_toggle_in_chrome(workspace, write_world, factories):
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published")])
    build(include_drafts=False)
    reader = (workspace.site / "story" / "ww" / "s1" / "index.html").read_text()
    assert "dyslexia-toggle" in reader


def test_reader_font_size_scales_with_age_band(workspace, write_world, factories):
    from build_site import READER_BASE
    # Build two stories at different age bands and check their --reader-base
    write_world(slug="ww",
                 characters=[factories.character(slug="hero", world="ww")],
                 stories=[
                     factories.story(slug="tots", world="ww", status="published",
                                     age_band="0-3"),
                     factories.story(slug="big-kids", world="ww", status="published",
                                     age_band="9-12"),
                 ])
    build(include_drafts=False)
    tot_reader = (workspace.site / "story" / "ww" / "tots" / "index.html").read_text()
    big_reader = (workspace.site / "story" / "ww" / "big-kids" / "index.html").read_text()
    assert f"--reader-base:{READER_BASE['0-3']}px" in tot_reader
    assert f"--reader-base:{READER_BASE['9-12']}px" in big_reader
    # Pedagogy invariant: smaller readers get bigger text.
    assert READER_BASE["0-3"] > READER_BASE["9-12"]


# ============================================================================ thumb logic
def test_thumb_for_story_uses_cover_image_when_set(workspace, write_world, factories):
    from build_site import thumb_for_story
    story = factories.story(slug="s1", world="ww")
    story["cover"] = {"image": "images/cover.png"}
    story["pages"][1]["image"]["file"] = "images/page-01.png"
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[story])
    from lib.model import load_world
    w = load_world("ww")
    assert thumb_for_story(w.stories[0]) == "images/cover.png"


def test_thumb_for_story_falls_back_to_first_page_image(workspace, write_world, factories):
    from build_site import thumb_for_story
    story = factories.story(slug="s1", world="ww")
    story["pages"][0]["image"]["file"] = "images/page-00.png"
    story["pages"][1]["image"]["file"] = "images/page-01.png"
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[story])
    from lib.model import load_world
    w = load_world("ww")
    assert thumb_for_story(w.stories[0]) == "images/page-00.png"


def test_thumb_for_story_returns_none_when_nothing_rendered(workspace, write_world, factories):
    from build_site import thumb_for_story
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    from lib.model import load_world
    w = load_world("ww")
    assert thumb_for_story(w.stories[0]) is None


# ============================================================================ tags pages
def test_tag_page_lists_only_stories_with_that_tag(workspace, write_world, factories):
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="a", world="ww", status="published",
                                          tags=["bedtime"]),
                         factories.story(slug="b", world="ww", status="published",
                                          tags=["adventure"])])
    build(include_drafts=False)
    bedtime_page = (workspace.site / "tags" / "bedtime" / "index.html").read_text()
    assert "story/ww/a/index.html" in bedtime_page
    assert "story/ww/b/index.html" not in bedtime_page


# ============================================================================ html safety
def test_build_html_escapes_user_strings_in_chrome(workspace, write_world, factories):
    """Any text injected into the static-site CHROME (titles, breadcrumbs,
    captions, headings) must be HTML-escaped — otherwise a user could put
    `<script>` in a story title and have it execute in the browser.

    Strings inside `<script type=application/json>` blocks are deliberately
    raw JSON; the runtime parses them with JSON.parse so they cannot execute
    in that context."""
    import re
    story = factories.story(slug="s1", world="ww", status="published",
                             title="<script>alert(1)</script>",
                             logline="A & B's tale")
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[story])
    build(include_drafts=False)
    reader = (workspace.site / "story" / "ww" / "s1" / "index.html").read_text()
    # Strip the JSON payload block, then assert the rest contains no raw <script>.
    chrome = re.sub(r'<script id="story-data"[^>]*>[\s\S]*?</script>', "", reader)
    assert "<script>alert(1)</script>" not in chrome, "title was not escaped in chrome"
    # And the escaped version IS in the chrome (e.g. in <h1>, <title>, breadcrumbs)
    assert "&lt;script&gt;" in chrome
    # And the ampersand in the logline gets escaped to &amp;
    assert "A &amp; B" in chrome


def test_build_html_escapes_world_title_in_index(workspace, write_world, factories):
    write_world(slug="ww",
                world_overrides={"title": "<img onerror=x>", "premise": "p"},
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published")])
    build(include_drafts=False)
    index = (workspace.site / "index.html").read_text()
    assert "<img onerror=x>" not in index
    assert "&lt;img onerror=x&gt;" in index


# ============================================================================ rebuild idempotency
def test_build_clears_old_site_dir_on_each_run(workspace, write_world, factories):
    """site/ is rebuilt from scratch every run — stale files from a previous
    build must not survive."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published")])
    build(include_drafts=False)
    # Plant a stale file
    stale = workspace.site / "stale-leftover.txt"
    stale.write_text("from a previous build")
    assert stale.exists()
    build(include_drafts=False)
    assert not stale.exists(), "Stale files should not survive a rebuild"


# ============================================================================ surfaced authored fields (E2)
def test_reader_renders_story_summary(workspace, write_world, factories):
    """The back-cover blurb (story.summary) appears on the reader landing — but
    never inside the runtime JSON payload."""
    import re
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published",
                                          summary="A cozy tale about courage and acorns.")])
    build(include_drafts=False)
    reader = (workspace.site / "story" / "ww" / "s1" / "index.html").read_text()
    chrome = re.sub(r'<script id="story-data"[^>]*>[\s\S]*?</script>', "", reader)
    assert "A cozy tale about courage and acorns." in chrome
    assert "story-summary" in chrome


def test_world_hub_lists_world_rules(workspace, write_world, factories):
    """A world's laws are surfaced on its hub so every story's adherence is reviewable."""
    write_world(slug="ww",
                world_overrides={"rules": ["Magic is gentle and small.",
                                           {"id": "kindness", "text": "Kindness always wins."}]},
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published")])
    build(include_drafts=False)
    hub = (workspace.site / "world" / "ww" / "index.html").read_text()
    assert "The rules of this world" in hub
    assert "Magic is gentle and small." in hub
    assert "Kindness always wins." in hub


# ============================================================================ --out (two-build pattern)
def test_build_out_writes_to_a_custom_directory(workspace, write_world, factories):
    """The studio builds two flavours of the site side by side: the studio preview (with
    drafts) at ./site/ and the public preview (published only) at ./site_publish/. The
    second one MUST be possible without touching the first — verified by passing out=."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published")])
    alt = workspace.root / "alt_out"
    stats = build(include_drafts=False, out=alt)
    assert (alt / "index.html").exists()
    assert (alt / "story" / "ww" / "s1" / "index.html").exists()
    # The default ./site/ was NOT touched by this call.
    assert not (workspace.site / "index.html").exists()
    # The stats report reflects the actual output location (so the studio can label the tab).
    assert stats["out"].endswith("alt_out")


def test_build_out_does_not_touch_default_site_dir(workspace, write_world, factories):
    """Writing a public build to ./alt MUST leave the existing ./site preview intact. This
    is the property the studio relies on: the in-app preview and the public preview are
    independent builds that can be browsed side by side."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published")])
    # First build the default ./site/ — this is what the in-app iframe shows.
    build(include_drafts=True)
    assert (workspace.site / "index.html").exists()
    # Now build the public flavour elsewhere; the studio preview must still be there.
    alt = workspace.root / "alt_out"
    build(include_drafts=False, out=alt)
    assert (workspace.site / "index.html").exists(), "studio preview must survive public build"
    assert (alt / "index.html").exists()


def test_build_out_clears_the_target_dir_on_each_run(workspace, write_world, factories):
    """Just like the default build, --out must nuke the target dir first so stale files
    from a previous build don't leak through (otherwise a story that was renamed would
    leave a ghost behind in the public preview)."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", status="published")])
    alt = workspace.root / "alt_out"
    build(include_drafts=False, out=alt)
    (alt / "stale.txt").write_text("from previous build")
    build(include_drafts=False, out=alt)
    assert not (alt / "stale.txt").exists()


def test_build_out_published_only_excludes_drafts(workspace, write_world, factories):
    """The studio's 'Publish' build is published-only — even when --include-drafts is
    *not* set on the out= build, drafts must not appear in the output. This is the
    invariant that keeps GitHub Pages from ever seeing draft content."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[
                    factories.story(slug="draftie", world="ww", status="draft"),
                    factories.story(slug="liveone", world="ww", status="published"),
                ])
    alt = workspace.root / "public_out"
    build(include_drafts=False, out=alt)
    # The published story is present
    assert (alt / "story" / "ww" / "liveone" / "index.html").exists()
    # The draft is NOT present in the published-only build
    assert not (alt / "story" / "ww" / "draftie" / "index.html").exists()
    # And the search index has only the published one
    import json
    index = json.loads((alt / "search-index.json").read_text())
    assert [e["slug"] for e in index] == ["liveone"]


def test_build_includes_drafts_still_includes_drafts_when_out_set(workspace, write_world,
                                                                    factories):
    """Sanity: --include-drafts in combination with --out still emits drafts. The studio's
    'Preview' build (with drafts) might one day want a custom out — must not silently
    drop drafts."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[
                    factories.story(slug="draftie", world="ww", status="draft"),
                ])
    alt = workspace.root / "studio_alt"
    build(include_drafts=True, out=alt)
    assert (alt / "story" / "ww" / "draftie" / "index.html").exists()
