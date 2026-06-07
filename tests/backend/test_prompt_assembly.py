"""Tests for ``scripts/lib/prompt_assembly.py`` — THE consistency lever.

The whole illustration-consistency story rides on this module: every page prompt
is *assembled* from the world's locked style, each present character's
appearance_token, the world palette, the negative prompt, the per-character seed,
and the reference images. We test that ALL of those pieces flow through, in the
right order, with the right precedence rules.
"""
from __future__ import annotations

import pytest

from lib.model import World
from lib.prompt_assembly import (
    AssembledPrompt, assemble_character_sheet_prompt, assemble_page_prompt,
)


def _world(factories, character_slug="hero"):
    """Build a World object in memory (no disk) — used by every test in this module."""
    wdata = factories.world(slug="ww")
    char = factories.character(slug=character_slug, world="ww")
    return World(slug="ww", data=wdata, path=None, characters={character_slug: char})


def _page(prompt="hero stands in the meadow", characters_present=None, **extras):
    p = {
        "number": 1,
        "text": "Hero stood in the meadow.",
        "image": {
            "prompt": prompt,
            "characters_present": characters_present or [],
            **extras,
        },
    }
    return p


# =============================================================================== assemble_page_prompt
def test_page_prompt_includes_scene(factories):
    w = _world(factories)
    p = _page("hero stands by the lake")
    ap = assemble_page_prompt(w, factories.story(), p)
    assert "hero stands by the lake" in ap.prompt


def test_page_prompt_injects_world_style_block(factories):
    """The single most important consistency lever — every prompt re-states the
    locked art style. Without it images drift visually book-to-book."""
    w = _world(factories)
    p = _page()
    ap = assemble_page_prompt(w, factories.story(), p)
    assert w.data["art_style"]["prompt_style_block"] in ap.prompt


def test_page_prompt_injects_each_present_characters_appearance_token(factories):
    """Visual consistency invariant: every character in frame contributes their
    dense appearance_token to the prompt. Multi-character pages stack them with
    a separator so the model can distinguish each identity."""
    wdata = factories.world(slug="ww")
    char_a = factories.character(slug="alice", world="ww")
    char_b = factories.character(slug="bob", world="ww")
    char_b["appearance_token"] = "BOB: a short fox in a green vest"
    w = World(slug="ww", data=wdata, path=None,
              characters={"alice": char_a, "bob": char_b})
    p = _page(characters_present=["alice", "bob"])
    ap = assemble_page_prompt(w, factories.story(), p)
    assert char_a["appearance_token"] in ap.prompt
    assert char_b["appearance_token"] in ap.prompt
    # Multi-character pages stack tokens with the pipe separator.
    assert "|" in ap.prompt
    assert sorted(ap.characters) == ["alice", "bob"]


def test_page_prompt_carries_negative_prompt(factories):
    w = _world(factories)
    ap = assemble_page_prompt(w, factories.story(), _page())
    assert ap.negative == w.data["art_style"]["negative_prompt"]
    assert "photorealism" in ap.negative


def test_page_prompt_lists_palette_with_hash_prefixed_hexes(factories):
    w = _world(factories)
    ap = assemble_page_prompt(w, factories.story(), _page())
    for swatch in w.data["art_style"]["palette"]:
        # The palette goes into the prompt as 'name #hex' regardless of whether
        # the source had the # prefix or not.
        assert "#" + swatch["hex"].lstrip("#") in ap.prompt


def test_page_prompt_reserves_a_text_zone_for_caption(factories):
    w = _world(factories)
    ap = assemble_page_prompt(w, factories.story(), _page())
    assert "text" in ap.prompt.lower()
    assert "low-detail" in ap.prompt.lower() or "negative space" in ap.prompt.lower()


def test_page_prompt_respects_per_page_text_zone_override(factories):
    """A page can override the world default — e.g. a centred title splash."""
    w = _world(factories)
    p = _page(text_zone="upper third")
    ap = assemble_page_prompt(w, factories.story(), p)
    assert "upper third" in ap.prompt


def test_page_prompt_falls_back_to_world_text_treatment_zone(factories):
    """No per-page override → use the world's text_treatment placement."""
    w = _world(factories)
    w.data["art_style"]["text_treatment"]["placement"] = "left margin"
    ap = assemble_page_prompt(w, factories.story(), _page())
    assert "left margin" in ap.prompt


def test_page_prompt_uses_world_aspect_ratio(factories):
    w = _world(factories)
    w.data["art_style"]["aspect_ratio"] = "16:9"
    ap = assemble_page_prompt(w, factories.story(), _page())
    assert ap.aspect_ratio == "16:9"


def test_page_prompt_defaults_aspect_ratio_when_missing(factories):
    w = _world(factories)
    del w.data["art_style"]["aspect_ratio"]
    ap = assemble_page_prompt(w, factories.story(), _page())
    assert ap.aspect_ratio == "4:3"


# =============================================================================== seed handling
def test_page_seed_prefers_explicit_page_seed(factories):
    w = _world(factories)
    p = _page(characters_present=["hero"], seed=99999)
    ap = assemble_page_prompt(w, factories.story(), p)
    assert ap.seed == 99999


def test_page_seed_uses_solo_character_seed_when_unset_and_single_character(factories):
    """Single-character pages inherit the character's preferred seed (a
    stabilisation lever). Multi-character pages skip this — no character is
    privileged over the others."""
    w = _world(factories)
    p = _page(characters_present=["hero"])
    ap = assemble_page_prompt(w, factories.story(), p)
    assert ap.seed == w.characters["hero"]["seed"]


def test_page_seed_is_none_when_unset_and_multiple_characters(factories):
    """Multi-character page with no explicit page seed → seed stays None (no
    character should bias the whole frame)."""
    wdata = factories.world(slug="ww")
    a = factories.character(slug="a", world="ww")
    b = factories.character(slug="b", world="ww")
    a["seed"], b["seed"] = 100, 200
    w = World(slug="ww", data=wdata, path=None, characters={"a": a, "b": b})
    ap = assemble_page_prompt(w, factories.story(), _page(characters_present=["a", "b"]))
    assert ap.seed is None


# =============================================================================== reference images
def test_page_prompt_gathers_reference_images_from_each_present_character(factories):
    wdata = factories.world(slug="ww")
    a = factories.character(slug="a", world="ww")
    a["reference_images"] = ["characters/a.refs/sheet.png"]
    b = factories.character(slug="b", world="ww")
    b["reference_images"] = ["characters/b.refs/sheet.png", "characters/b.refs/turn.png"]
    w = World(slug="ww", data=wdata, path=None, characters={"a": a, "b": b})
    ap = assemble_page_prompt(w, factories.story(), _page(characters_present=["a", "b"]))
    assert set(ap.reference_images) == {
        "characters/a.refs/sheet.png",
        "characters/b.refs/sheet.png",
        "characters/b.refs/turn.png",
    }


def test_page_prompt_emits_character_color_locks(factories):
    """Per-character color_palette parts are re-stated in the prompt to keep
    coat/eye/boot colors locked across pages."""
    w = _world(factories)
    ap = assemble_page_prompt(w, factories.story(), _page(characters_present=["hero"]))
    assert "hero coat" in ap.prompt.lower()
    assert "c0392b" in ap.prompt.lower()


def test_page_prompt_silently_drops_unknown_character_slugs(factories):
    """An image that names a character not in the world is reported by the
    validator separately — assemble_page_prompt itself must NOT crash and must
    simply leave them out of the prompt."""
    w = _world(factories)
    ap = assemble_page_prompt(w, factories.story(),
                              _page(characters_present=["hero", "ghost-not-in-world"]))
    assert "hero" in [c.lower() for c in ap.characters]
    assert all(c != "ghost-not-in-world" for c in ap.characters)


# =============================================================================== story-stage application
def test_page_prompt_applies_story_stage_to_character_token(factories):
    """The story's `characters` array pins each character to a specific
    evolution stage; that stage's appearance_delta must extend the token in the
    final prompt (and ONLY for the stages picked by THIS story)."""
    w = _world(factories)
    story = factories.story()
    story["characters"] = [{"slug": "hero", "stage": "brave"}]
    ap = assemble_page_prompt(w, story, _page(characters_present=["hero"]))
    assert "[brave: a brave-medal pinned to the coat]" in ap.prompt


def test_page_prompt_base_stage_leaves_token_unchanged(factories):
    w = _world(factories)
    story = factories.story()
    story["characters"] = [{"slug": "hero", "stage": "base"}]
    ap = assemble_page_prompt(w, story, _page(characters_present=["hero"]))
    assert "[base:" not in ap.prompt
    assert w.characters["hero"]["appearance_token"] in ap.prompt


# =============================================================================== character sheet
def test_character_sheet_prompt_includes_turnaround_request(factories):
    w = _world(factories)
    ap = assemble_character_sheet_prompt(w, w.characters["hero"])
    text = ap.prompt.lower()
    # The sheet must request the canonical turnaround so it works as an anchor.
    assert "front" in text
    assert "side" in text
    assert "back" in text or "rear" in text
    assert "neutral" in text or "plain background" in text


def test_character_sheet_prompt_uses_3_2_aspect(factories):
    w = _world(factories)
    ap = assemble_character_sheet_prompt(w, w.characters["hero"])
    assert ap.aspect_ratio == "3:2"


def test_character_sheet_prompt_carries_character_seed(factories):
    w = _world(factories)
    w.characters["hero"]["seed"] = 7777
    ap = assemble_character_sheet_prompt(w, w.characters["hero"])
    assert ap.seed == 7777


def test_character_sheet_returns_only_that_character(factories):
    w = _world(factories)
    ap = assemble_character_sheet_prompt(w, w.characters["hero"])
    assert ap.characters == ["hero"]


def test_character_sheet_injects_world_style_block(factories):
    w = _world(factories)
    ap = assemble_character_sheet_prompt(w, w.characters["hero"])
    assert w.data["art_style"]["prompt_style_block"] in ap.prompt


# =============================================================================== output structure
def test_assembled_prompt_dataclass_shape(factories):
    w = _world(factories)
    ap = assemble_page_prompt(w, factories.story(), _page())
    assert isinstance(ap, AssembledPrompt)
    assert isinstance(ap.prompt, str)
    assert ap.prompt.endswith(".")
    assert isinstance(ap.negative, str)
    assert ap.aspect_ratio in {"4:3", "16:9", "3:2", "1:1"} or ":" in ap.aspect_ratio
    assert isinstance(ap.reference_images, list)
    assert isinstance(ap.characters, list)


def test_page_prompt_no_double_periods_between_segments(factories):
    """Segments are joined with ". " — assert we don't end up with ".." which
    would make the rendered prompt look broken to the user."""
    w = _world(factories)
    ap = assemble_page_prompt(w, factories.story(), _page())
    assert ".." not in ap.prompt
