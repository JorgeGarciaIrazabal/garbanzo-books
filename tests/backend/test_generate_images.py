"""Tests for ``scripts/generate_images.py`` — the prompt-assembling image runner.

These tests focus on the *business logic* (provider selection + fallback,
placeholder SVG generation, story.yaml mutation contract, evolution stage
flowing through, character sheet path) and avoid hitting any external API.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import generate_images as gi
from lib.model import dump_yaml, load_yaml


# ============================================================================ resolve / split
def test_split_ref_splits_world_and_name():
    assert gi.split_ref("ww/char") == ("ww", "char")


def test_split_ref_handles_multipath_names():
    """If the second segment has slashes (it shouldn't really) we still grab
    just the first '/'."""
    out = gi.split_ref("ww/inner/name")
    assert out[0] == "ww"


def test_split_ref_raises_systemexit_for_missing_slash():
    with pytest.raises(SystemExit):
        gi.split_ref("no-slash")


def test_resolve_story_via_short_form_returns_world_and_story():
    assert gi._resolve_story("ww/s1") == ("ww", "s1")


def test_resolve_story_via_directory_path(workspace, write_world, factories):
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    sdir = workspace.worlds / "ww" / "stories" / "s1"
    assert gi._resolve_story(str(sdir)) == ("ww", "s1")


def test_resolve_story_raises_systemexit_for_unparseable(workspace):
    with pytest.raises(SystemExit):
        gi._resolve_story("totally-bogus-input")


# ============================================================================ palette helper
def test_palette_hexes_extracts_six_char_hex_with_hash(workspace, write_world, factories):
    from lib.model import load_world
    write_world(slug="ww")
    w = load_world("ww", with_stories=False)
    hexes = gi._palette_hexes(w)
    assert all(h.startswith("#") and len(h) == 7 for h in hexes)


def test_palette_hexes_falls_back_to_defaults_on_empty(workspace, write_world, factories):
    from lib.model import load_world
    world = factories.world()
    world["art_style"]["palette"] = []
    # write_world treats world_overrides as a partial; just write directly
    wdir = workspace.worlds / "ww"
    dump_yaml(world, wdir / "world.yaml")
    (wdir / "characters").mkdir(parents=True, exist_ok=True)
    w = load_world("ww", with_stories=False)
    hexes = gi._palette_hexes(w)
    assert hexes  # never empty — there's a hardcoded fallback so SVGs always render


# ============================================================================ placeholder SVG
def test_placeholder_svg_writes_self_describing_file(workspace, write_world, factories, tmp_path):
    from lib.model import load_world
    from lib.prompt_assembly import assemble_page_prompt
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    w = load_world("ww")
    story = w.stories[0].data
    page = story["pages"][1]
    ap = assemble_page_prompt(w, story, page)
    out = tmp_path / "placeholder.svg"
    gi.write_placeholder_svg(out, "Test page", ap, w)
    text = out.read_text()
    # SVG header
    assert text.startswith("<svg")
    # The visible label includes characters + seed for at-a-glance QA
    assert "PLACEHOLDER" in text
    # The text-zone reservation note is visible so the user sees it's reserved
    assert "text zone" in text.lower()


def test_placeholder_svg_escapes_html_in_prompt(workspace, write_world, factories, tmp_path):
    """A scene prompt containing `<` or `&` should NOT break the SVG."""
    from lib.model import load_world
    from lib.prompt_assembly import assemble_page_prompt
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    w = load_world("ww")
    story = w.stories[0].data
    page = story["pages"][1]
    page["image"]["prompt"] = "<scary> wolf & friends"
    ap = assemble_page_prompt(w, story, page)
    out = tmp_path / "p.svg"
    gi.write_placeholder_svg(out, "<title>", ap, w)
    text = out.read_text()
    assert "<scary>" not in text  # the raw bracket must have been escaped
    assert "&lt;scary&gt;" in text or "&lt;scary&gt" in text


# ============================================================================ try_real_provider fallback
def test_try_real_provider_returns_false_when_gemini_key_missing(monkeypatch, tmp_path,
                                                                  workspace, write_world,
                                                                  factories):
    from lib.model import load_world
    from lib.prompt_assembly import assemble_page_prompt
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    w = load_world("ww")
    story = w.stories[0].data
    ap = assemble_page_prompt(w, story, story["pages"][1])
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    ok = gi.try_real_provider("nano-banana", ap, tmp_path / "x.png", ref_base=w.dir)
    assert ok is False


def test_try_real_provider_returns_false_when_openai_key_missing(monkeypatch, tmp_path,
                                                                   workspace, write_world,
                                                                   factories):
    from lib.model import load_world
    from lib.prompt_assembly import assemble_page_prompt
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    w = load_world("ww")
    story = w.stories[0].data
    ap = assemble_page_prompt(w, story, story["pages"][1])
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    ok = gi.try_real_provider("openai", ap, tmp_path / "x.png")
    assert ok is False


def test_try_real_provider_swallows_provider_exceptions(monkeypatch, tmp_path):
    """The toolchain promise: image-gen failures NEVER crash the pipeline. If
    the network/provider misbehaves we fall back to placeholders silently."""

    def raises(*a, **kw):
        raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(gi, "_gen_nano_banana", raises)
    from lib.prompt_assembly import AssembledPrompt
    ap = AssembledPrompt(prompt="x", negative="", seed=None, aspect_ratio="4:3")
    ok = gi.try_real_provider("nano-banana", ap, tmp_path / "x.png", ref_base=tmp_path)
    assert ok is False


# ============================================================================ end-to-end: story → placeholders
def test_gen_story_with_placeholder_provider_writes_files_and_updates_yaml(
        workspace, write_world, factories):
    """Placeholder provider is the offline path. After running it the story.yaml
    must be updated with `image.file` paths AND `image.alt` for each rendered
    page."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    gi.gen_story("ww/s1", provider="placeholder", only_page=None,
                 seed_override=None, print_only=False)
    sdir = workspace.worlds / "ww" / "stories" / "s1"
    story = load_yaml(sdir / "story.yaml")
    # Every page that wasn't skipped should now have a file + alt
    for p in story["pages"]:
        assert p["image"].get("file"), f"page {p['number']} has no image.file"
        assert p["image"].get("alt"), f"page {p['number']} has no image.alt"
    # SVG placeholders landed in images/
    svgs = list((sdir / "images").glob("*.svg"))
    assert len(svgs) >= len(story["pages"])


def test_gen_story_only_page_skips_other_pages(workspace, write_world, factories):
    """Targeted re-render — only the requested page changes."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    gi.gen_story("ww/s1", provider="placeholder", only_page=1,
                 seed_override=None, print_only=False)
    sdir = workspace.worlds / "ww" / "stories" / "s1"
    files = sorted(p.name for p in (sdir / "images").iterdir())
    # only page-01 was rendered
    assert files == ["page-01.svg"]


def test_gen_story_print_prompts_does_not_write_files(workspace, write_world, factories, capsys):
    """Dry-run mode: prints prompts but does NOT touch disk."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    gi.gen_story("ww/s1", provider="placeholder", only_page=None,
                 seed_override=None, print_only=True)
    sdir = workspace.worlds / "ww" / "stories" / "s1"
    out = capsys.readouterr().out
    assert "page" in out.lower()
    # Nothing was written
    assert not list((sdir / "images").iterdir())


def test_gen_story_seed_override_takes_priority_over_page_seed(workspace, write_world,
                                                                  factories, capsys):
    """`--seed 99` from the CLI must overwrite the page's stored seed in the
    assembled prompt, so the user can force a regeneration variant."""
    story = factories.story(slug="s1", world="ww")
    story["pages"][1]["image"]["seed"] = 1
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[story])
    gi.gen_story("ww/s1", provider="placeholder", only_page=1,
                 seed_override=99999, print_only=True)
    out = capsys.readouterr().out
    assert "SEED: 99999" in out
    assert "SEED: 1" not in out


def test_gen_story_evolution_stage_flows_through_to_prompt(workspace, write_world, factories,
                                                            capsys):
    """The whole point of evolution stages: pinning a stage in story.characters
    must make the corresponding appearance_delta show up in the prompt."""
    char = factories.character(slug="hero", world="ww")
    story = factories.story(slug="s1", world="ww")
    story["characters"] = [{"slug": "hero", "stage": "brave"}]
    write_world(slug="ww", characters=[char], stories=[story])
    gi.gen_story("ww/s1", provider="placeholder", only_page=1,
                 seed_override=None, print_only=True)
    out = capsys.readouterr().out
    assert "[brave: a brave-medal pinned to the coat]" in out


# ============================================================================ character sheet
def test_gen_character_sheet_writes_placeholder_and_records_reference(workspace, write_world,
                                                                       factories):
    """The character sheet IS the canonical reference. After running, the
    character's `reference_images` list must include the new sheet path."""
    char = factories.character(slug="hero", world="ww")
    char["reference_images"] = []  # start empty
    write_world(slug="ww", characters=[char])
    gi.gen_character_sheet("ww/hero", provider="placeholder", print_only=False)
    cpath = workspace.worlds / "ww" / "characters" / "hero.yaml"
    cdata = load_yaml(cpath)
    assert cdata["reference_images"], "character sheet not recorded as reference"
    sheet_path = cdata["reference_images"][0]
    # SVG fallback lands at characters/<slug>.refs/model-sheet.svg
    assert sheet_path.endswith("model-sheet.svg")
    # Actual file exists on disk
    on_disk = workspace.worlds / "ww" / sheet_path
    assert on_disk.exists()


def test_gen_character_sheet_does_not_duplicate_reference_on_re_run(workspace, write_world,
                                                                      factories):
    char = factories.character(slug="hero", world="ww")
    char["reference_images"] = []
    write_world(slug="ww", characters=[char])
    gi.gen_character_sheet("ww/hero", provider="placeholder", print_only=False)
    gi.gen_character_sheet("ww/hero", provider="placeholder", print_only=False)
    cdata = load_yaml(workspace.worlds / "ww" / "characters" / "hero.yaml")
    assert cdata["reference_images"].count(cdata["reference_images"][0]) == 1


def test_gen_character_sheet_unknown_character_exits(workspace, write_world, factories):
    write_world(slug="ww", characters=[factories.character(slug="hero", world="ww")])
    with pytest.raises(SystemExit):
        gi.gen_character_sheet("ww/nobody", provider="placeholder", print_only=False)


def test_gen_character_sheet_unknown_world_exits(workspace):
    with pytest.raises(FileNotFoundError):
        gi.gen_character_sheet("nope/x", provider="placeholder", print_only=False)


# ============================================================================ auto alt
def test_auto_alt_uses_prompt_and_who(workspace, factories):
    from lib.prompt_assembly import AssembledPrompt
    page = {"image": {"prompt": "a sunny meadow"}}
    ap = AssembledPrompt(prompt="...", negative="", seed=None, aspect_ratio="4:3",
                          characters=["alice", "bob"])
    alt = gi._auto_alt(page, ap)
    assert "a sunny meadow" in alt
    assert "alice" in alt and "bob" in alt
    assert "featuring" in alt.lower()


def test_auto_alt_handles_empty_prompt():
    from lib.prompt_assembly import AssembledPrompt
    page = {"image": {"prompt": ""}}
    ap = AssembledPrompt(prompt="...", negative="", seed=None, aspect_ratio="4:3",
                          characters=[])
    alt = gi._auto_alt(page, ap)
    assert alt == "Illustration"


def test_auto_alt_no_characters_just_returns_scene(workspace, factories):
    from lib.prompt_assembly import AssembledPrompt
    page = {"image": {"prompt": "an empty room"}}
    ap = AssembledPrompt(prompt="...", negative="", seed=None, aspect_ratio="4:3",
                          characters=[])
    assert gi._auto_alt(page, ap).startswith("an empty room")


# ============================================================================ raster refs filter
def test_raster_refs_only_includes_supported_image_types(workspace, tmp_path):
    from lib.prompt_assembly import AssembledPrompt
    # Make a mix of supported (png/jpg) and unsupported (svg/txt) reference files
    for name in ("ref.png", "ref.jpg", "ref.svg", "ref.txt"):
        (tmp_path / name).write_bytes(b"x")
    ap = AssembledPrompt(prompt="x", negative="", seed=None, aspect_ratio="4:3",
                          reference_images=["ref.png", "ref.jpg", "ref.svg", "ref.txt"])
    out = gi._raster_refs(ap, tmp_path)
    names = sorted(p.name for p in out)
    # png + jpg are usable as image-to-image anchors; svg/txt are not.
    assert names == ["ref.jpg", "ref.png"]


def test_raster_refs_skips_missing_files(tmp_path):
    from lib.prompt_assembly import AssembledPrompt
    ap = AssembledPrompt(prompt="x", negative="", seed=None, aspect_ratio="4:3",
                          reference_images=["does-not-exist.png"])
    assert gi._raster_refs(ap, tmp_path) == []


def test_raster_refs_empty_when_ref_base_is_none():
    from lib.prompt_assembly import AssembledPrompt
    ap = AssembledPrompt(prompt="x", negative="", seed=None, aspect_ratio="4:3",
                          reference_images=["ref.png"])
    assert gi._raster_refs(ap, None) == []
