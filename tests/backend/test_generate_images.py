"""Tests for ``scripts/generate_images.py`` — the prompt-assembling image runner.

These tests focus on the *business logic* (provider selection + fallback,
placeholder SVG generation, story.yaml mutation contract, evolution stage
flowing through, character sheet path) and avoid hitting any external API.
"""
from __future__ import annotations

import json
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
                 seed_override=None, print_only=False,
                 qc_retries=0, qc_threshold=7.0, qc_model=None, qc_off=True)
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
                 seed_override=None, print_only=False,
                 qc_retries=0, qc_threshold=7.0, qc_model=None, qc_off=True)
    sdir = workspace.worlds / "ww" / "stories" / "s1"
    # Only image files (not sidecars) — see comments on the .prompt.txt and .qc.json files
    # written alongside each render for the audit trail.
    images = sorted(p.name for p in (sdir / "images").iterdir()
                    if p.suffix not in (".txt", ".json"))
    # only page-01 was rendered
    assert images == ["page-01.svg"]
    # and its audit sidecar sits beside it (A4)
    assert (sdir / "images" / "page-01.prompt.txt").exists()
    # and the per-page QC log sidecar records that QC was disabled (regression test for
    # the new best-of-N loop's persistence step)
    qc_log = json.loads((sdir / "images" / "page-01.qc.json").read_text())
    assert qc_log["page"] == 1
    assert qc_log["attempts"][0]["flags"] == ["qc_disabled"]
    assert qc_log["winner"] == "page-01.svg"


def test_gen_story_print_prompts_does_not_write_files(workspace, write_world, factories, capsys):
    """Dry-run mode: prints prompts but does NOT touch disk."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    gi.gen_story("ww/s1", provider="placeholder", only_page=None,
                 seed_override=None, print_only=True,
                 qc_retries=0, qc_threshold=7.0, qc_model=None, qc_off=True)
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
                 seed_override=99999, print_only=True,
                 qc_retries=0, qc_threshold=7.0, qc_model=None, qc_off=True)
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
                 seed_override=None, print_only=True,
                 qc_retries=0, qc_threshold=7.0, qc_model=None, qc_off=True)
    out = capsys.readouterr().out
    assert "[brave: a brave-medal pinned to the coat]" in out


# ============================================================================ prompt sidecar (A4)
def test_gen_story_writes_prompt_sidecar_with_assembled_prompt(workspace, write_world, factories):
    """Every rendered page gets a page-NN.prompt.txt recording the exact assembled
    prompt + seed + characters, so renders are auditable and reproducible."""
    char = factories.character(slug="hero", world="ww")
    char["seed"] = 4242
    write_world(slug="ww", characters=[char],
                stories=[factories.story(slug="s1", world="ww")])
    gi.gen_story("ww/s1", provider="placeholder", only_page=1,
                 seed_override=None, print_only=False,
                 qc_retries=0, qc_threshold=7.0, qc_model=None, qc_off=True)
    side = workspace.worlds / "ww" / "stories" / "s1" / "images" / "page-01.prompt.txt"
    assert side.exists()
    body = side.read_text()
    assert "PROMPT:" in body and "SEED:" in body and "CHARACTERS: hero" in body


# ============================================================================ verify mode (A4)
def test_verify_story_ready_returns_zero(workspace, write_world, factories):
    char = factories.character(slug="hero", world="ww")
    char["seed"] = 4242
    char["reference_images"] = ["hero.refs/model-sheet.png"]
    write_world(slug="ww", characters=[char],
                stories=[factories.story(slug="s1", world="ww")])
    assert gi.verify_story("ww/s1") == 0


def test_verify_story_blocks_when_present_character_missing_token(workspace, write_world,
                                                                   factories, capsys):
    char = factories.character(slug="hero", world="ww")
    char["appearance_token"] = ""  # can't be injected → not render-ready
    write_world(slug="ww", characters=[char],
                stories=[factories.story(slug="s1", world="ww")])
    rc = gi.verify_story("ww/s1")
    out = capsys.readouterr().out
    assert rc == 1
    assert "NOT READY" in out


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


# ============================================================================ best-of-N vision QC
def test_run_best_of_n_stops_at_first_good_candidate(monkeypatch, workspace, write_world, factories):
    """If the first candidate passes the threshold the loop MUST short-circuit — no
    extra renders, no extra API calls. This is the "if the first one is good, go with
    that" rule the user asked for."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    from lib.model import load_world
    from lib.prompt_assembly import assemble_page_prompt
    w = load_world("ww")
    story = w.stories[0].data
    page = story["pages"][1]
    ap = assemble_page_prompt(w, story, page)

    # Stub: generator copies page-01 placeholder; QC always returns a high score.
    calls = {"n": 0}
    def fake_gen(ap_, images_dir, world, ref_base, provider, num, title):
        calls["n"] += 1
        out = images_dir / f"page-{num:02d}-{ap_.seed}.svg"
        out.write_text("<svg/>", encoding="utf-8")
        return out
    monkeypatch.setattr(gi, "_generate_one_candidate", fake_gen)
    monkeypatch.setattr(gi, "_qc_candidate",
                        lambda *a, **kw: {"ok": True, "score": 9.5, "reason": "great",
                                          "flags": ["good"]})

    img_dir = workspace.worlds / "ww" / "stories" / "s1" / "images"
    winner, qc_log = gi._run_best_of_n(
        ap, img_dir, w, w.dir, story, page, provider="nano-banana",
        num=1, title="t", qc_retries=2, qc_threshold=7.0, qc_model=None,
        qc_off=False, verbose=False,
    )
    assert calls["n"] == 1, f"expected short-circuit on first good candidate, got {calls['n']} attempts"
    assert qc_log[0]["score"] == 9.5


def test_run_best_of_n_retries_until_threshold_is_met(monkeypatch, workspace, write_world, factories):
    """The whole point of best-of-N: if the first candidate fails QC, retry with a
    different seed and pick the best."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    from lib.model import load_world
    from lib.prompt_assembly import assemble_page_prompt
    w = load_world("ww")
    story = w.stories[0].data
    page = story["pages"][1]
    ap = assemble_page_prompt(w, story, page)

    calls = {"n": 0}
    def fake_gen(ap_, images_dir, world, ref_base, provider, num, title):
        calls["n"] += 1
        out = images_dir / f"page-{num:02d}-{ap_.seed}.svg"
        out.write_text("<svg/>", encoding="utf-8")
        return out
    monkeypatch.setattr(gi, "_generate_one_candidate", fake_gen)
    # First two attempts are bad (score 3.0), third is good (score 9.0).
    scores = [3.0, 3.0, 9.0]
    def fake_qc(cand, **kw):
        s = scores.pop(0) if scores else 9.0
        return {"ok": s >= 7.0, "score": s, "reason": "ok" if s >= 7.0 else "bad",
                "flags": [] if s >= 7.0 else ["scene_mismatch"]}
    monkeypatch.setattr(gi, "_qc_candidate", fake_qc)

    img_dir = workspace.worlds / "ww" / "stories" / "s1" / "images"
    winner, qc_log = gi._run_best_of_n(
        ap, img_dir, w, w.dir, story, page, provider="nano-banana",
        num=1, title="t", qc_retries=2, qc_threshold=7.0, qc_model=None,
        qc_off=False, verbose=False,
    )
    assert calls["n"] == 3, f"expected 3 attempts (2 bad + 1 good), got {calls['n']}"
    # Winner path is the THIRD attempt (highest score).
    assert "page-01" in winner.name
    # qc_log has all three attempts recorded.
    assert len(qc_log) == 3
    assert [e["score"] for e in qc_log] == [3.0, 3.0, 9.0]


def test_run_best_of_n_caps_at_max_attempts(monkeypatch, workspace, write_world, factories):
    """If every candidate fails, the loop still exits (caller gets the best of the bad
    ones, not an infinite loop)."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    from lib.model import load_world
    from lib.prompt_assembly import assemble_page_prompt
    w = load_world("ww")
    story = w.stories[0].data
    page = story["pages"][1]
    ap = assemble_page_prompt(w, story, page)

    calls = {"n": 0}
    def fake_gen(ap_, images_dir, world, ref_base, provider, num, title):
        calls["n"] += 1
        out = images_dir / f"page-{num:02d}-{ap_.seed}.svg"
        out.write_text("<svg/>", encoding="utf-8")
        return out
    monkeypatch.setattr(gi, "_generate_one_candidate", fake_gen)
    monkeypatch.setattr(gi, "_qc_candidate",
                        lambda *a, **kw: {"ok": False, "score": 2.0, "reason": "terrible",
                                          "flags": ["scene_mismatch"]})

    img_dir = workspace.worlds / "ww" / "stories" / "s1" / "images"
    winner, qc_log = gi._run_best_of_n(
        ap, img_dir, w, w.dir, story, page, provider="nano-banana",
        num=1, title="t", qc_retries=2, qc_threshold=7.0, qc_model=None,
        qc_off=False, verbose=False,
    )
    # 3 attempts = 1 initial + 2 retries; all bad, but a winner is still returned.
    assert calls["n"] == 3
    assert winner is not None
    assert all(e["score"] < 7.0 for e in qc_log)


def test_run_best_of_n_hard_flags_short_circuit(monkeypatch, workspace, write_world, factories):
    """A 'duplicate_characters' or 'anatomy_issue' flag is not salvageable by re-rolling
    the seed — it reflects a prompt problem. The loop should stop early."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    from lib.model import load_world
    from lib.prompt_assembly import assemble_page_prompt
    w = load_world("ww")
    story = w.stories[0].data
    page = story["pages"][1]
    ap = assemble_page_prompt(w, story, page)

    calls = {"n": 0}
    def fake_gen(ap_, images_dir, world, ref_base, provider, num, title):
        calls["n"] += 1
        out = images_dir / f"page-{num:02d}-{ap_.seed}.svg"
        out.write_text("<svg/>", encoding="utf-8")
        return out
    monkeypatch.setattr(gi, "_generate_one_candidate", fake_gen)
    monkeypatch.setattr(gi, "_qc_candidate",
                        lambda *a, **kw: {"ok": False, "score": 4.0, "reason": "dupes",
                                          "flags": ["duplicate_characters"]})

    img_dir = workspace.worlds / "ww" / "stories" / "s1" / "images"
    winner, qc_log = gi._run_best_of_n(
        ap, img_dir, w, w.dir, story, page, provider="nano-banana",
        num=1, title="t", qc_retries=2, qc_threshold=7.0, qc_model=None,
        qc_off=False, verbose=False,
    )
    # 1 attempt, not 3 — the hard flag short-circuits the loop.
    assert calls["n"] == 1
    assert "duplicate_characters" in qc_log[0]["flags"]


def test_qc_off_writes_disabled_marker(monkeypatch, workspace, write_world, factories):
    """--qc-off (or no vision model available) writes a transparent 'qc disabled' /
    'qc_unavailable' marker into the per-page QC log so the audit trail is honest."""
    write_world(slug="ww",
                characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    gi.gen_story("ww/s1", provider="placeholder", only_page=1,
                 seed_override=None, print_only=False,
                 qc_retries=0, qc_threshold=7.0, qc_model=None, qc_off=True)
    sdir = workspace.worlds / "ww" / "stories" / "s1"
    qc_log = json.loads((sdir / "images" / "page-01.qc.json").read_text())
    assert qc_log["attempts"][0]["flags"] == ["qc_disabled"]


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
