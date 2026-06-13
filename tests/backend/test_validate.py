"""Tests for ``scripts/validate.py`` — the QA gate.

These cover the *invariants* the validator enforces before a book may be marked
``published``. Each test isolates ONE failure mode at a time and asserts that
the right kind of failure (consistency / reading / interaction / illustration /
publish) is reported, and that *correct* data passes.
"""
from __future__ import annotations

import pytest

import validate as v
from validate import (
    INTERACTION_DATA_KEYS, PILLARS, Report, check_story, check_world,
)


def _ok_report():
    return Report()


def _world_obj(write_world, factories, **overrides):
    """Create a world on disk, then load it back as a World object (so checks see
    real characters / stories)."""
    from lib.model import load_world
    slug, _ = write_world(
        slug="ww",
        characters=[factories.character(slug="hero", world="ww")],
        stories=[factories.story(slug="s1", world="ww", **overrides)],
        image_files=["images/page-01.png", "images/page-02.png"],
    )
    return load_world(slug)


# ================================================================================== check_world
def test_check_world_passes_on_clean_world(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    check_world(rep, w)
    assert rep.fails == []


def test_check_world_fails_when_prompt_style_block_missing(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.data["art_style"]["prompt_style_block"] = ""
    check_world(rep, w)
    assert any("prompt_style_block" in f for f in rep.fails)


def test_check_world_fails_when_palette_empty(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.data["art_style"]["palette"] = []
    check_world(rep, w)
    assert any("palette" in f.lower() for f in rep.fails)


def test_check_world_fails_when_character_appearance_token_missing(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.characters["hero"]["appearance_token"] = ""
    check_world(rep, w)
    assert any("appearance_token" in f for f in rep.fails)


def test_check_world_warns_when_appearance_token_has_TODO(write_world, factories):
    """A TODO marker in the locked descriptor isn't a hard failure but the
    validator must surface it as a warning (you forgot to finish the bible)."""
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.characters["hero"]["appearance_token"] = "HERO: TODO fill in"
    check_world(rep, w)
    assert any("TODO" in warn for warn in rep.warns)


# ================================================================================== consistency
def test_check_story_fails_when_story_references_unknown_character(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    # Pin a roster character that doesn't exist in the world
    w.stories[0].data["characters"].append({"slug": "ghost", "stage": "base"})
    check_story(rep, w, w.stories[0])
    assert any("ghost" in f and "consistency" in f for f in rep.fails)


def test_check_story_fails_when_image_names_character_not_in_world(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.stories[0].data["pages"][1]["image"]["characters_present"] = ["mystery-character"]
    check_story(rep, w, w.stories[0])
    assert any("mystery-character" in f for f in rep.fails)


def test_check_story_fails_when_pinned_to_unknown_evolution_stage(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.stories[0].data["characters"][0]["stage"] = "never-existed"
    check_story(rep, w, w.stories[0])
    assert any("never-existed" in f for f in rep.fails)


def test_check_story_accepts_base_stage_even_if_not_in_evolution_list(write_world, factories):
    """`base` is the universal default — even a character without an explicit
    `base` stage in their evolution list must accept stage=base."""
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.characters["hero"]["evolution"] = []
    w.stories[0].data["characters"][0]["stage"] = "base"
    check_story(rep, w, w.stories[0])
    assert not any("base" in f and "unknown stage" in f for f in rep.fails)


# ================================================================================== reading-level
def test_check_story_fails_when_page_exceeds_word_cap(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    long_text = " ".join(["word"] * 100)
    w.stories[0].data["pages"][1]["text"] = long_text
    w.stories[0].data["reading_level"]["max_words_per_page"] = 20
    check_story(rep, w, w.stories[0])
    assert any("word cap" in f for f in rep.fails)


def test_check_story_passes_when_words_within_cap(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    check_story(rep, w, w.stories[0])
    over = [f for f in rep.fails if "word cap" in f]
    assert over == []


def test_check_story_skips_word_cap_for_title_and_interaction_pages(write_world, factories):
    """Title pages and pure-interaction pages must NOT trip the word cap — they
    aren't reading text."""
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    # Title page has 200 words — must not fail.
    w.stories[0].data["pages"][0]["text"] = " ".join(["t"] * 200)
    w.stories[0].data["reading_level"]["max_words_per_page"] = 30
    check_story(rep, w, w.stories[0])
    assert not any("word cap" in f for f in rep.fails)


def test_check_story_fails_when_fk_grade_far_above_target(write_world, factories):
    """Very long, polysyllabic sentences push FK grade up; with a tiny target +
    tolerance, that must trigger the failure."""
    rep = _ok_report()
    text = (
        "Subsequently, the interconnectedness of philosophical postulates "
        "necessitated comprehensive reevaluation of foundational epistemological "
        "assumptions."
    )
    w = _world_obj(write_world, factories)
    w.stories[0].data["age_band"] = "5-7"
    w.stories[0].data["reading_level"]["target_fk_grade"] = 1.0
    w.stories[0].data["reading_level"]["fk_grade_tolerance"] = 0.5
    w.stories[0].data["pages"][1]["text"] = text
    check_story(rep, w, w.stories[0])
    assert any("FK grade" in f for f in rep.fails)


def test_check_story_does_not_check_fk_for_read_aloud_bands(write_world, factories):
    """FKGL is unreliable below ~Grade 1. Bands 0-3 and 3-5 opt out — even very
    complex text in a toddler book must not trigger the FK grade failure."""
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.stories[0].data["age_band"] = "0-3"
    w.stories[0].data["pages"][1]["text"] = (
        "Subsequently the interconnectedness of philosophical postulates "
        "necessitated comprehensive reevaluation."
    )
    # We'd still expect a word-cap failure, but NOT an FK-grade failure.
    check_story(rep, w, w.stories[0])
    assert not any("FK grade" in f for f in rep.fails)


# ================================================================================== interactions
def test_check_story_fails_on_unknown_interaction_type(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.stories[0].data["pages"][1]["interaction"] = {
        "type": "totally-made-up-game",
        "prompt": "play it",
        "data": {},
    }
    check_story(rep, w, w.stories[0])
    assert any("unknown type" in f for f in rep.fails)


@pytest.mark.parametrize("itype,required", list(INTERACTION_DATA_KEYS.items()))
def test_each_interaction_type_validates_its_required_data_keys(write_world, factories,
                                                                  itype, required):
    """The required-keys table doubles as a contract. For every type with required
    keys: dropping one of them must produce a clear `data missing` failure.
    For types with no required keys: the validator must NOT complain."""
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    if required:
        # populate all required keys with dummy values, then drop the first one
        good_data = {k: ["dummy"] if k in ("items", "pairs", "options", "notes") else "dummy"
                     for k in required}
        bad_data = {k: v for k, v in good_data.items() if k != required[0]}
        w.stories[0].data["pages"][1]["interaction"] = {
            "type": itype, "prompt": "play", "data": bad_data,
        }
        check_story(rep, w, w.stories[0])
        assert any(f"data missing [{required[0]!r}]" in f or required[0] in f for f in rep.fails)
    else:
        # No required keys — supplying an empty data dict must not fail.
        w.stories[0].data["pages"][1]["interaction"] = {
            "type": itype, "prompt": "play", "data": {},
        }
        check_story(rep, w, w.stories[0])
        type_fails = [f for f in rep.fails if "interaction" in f and itype in f]
        assert type_fails == []


def test_check_story_fails_when_choice_goto_targets_nonexistent_page(write_world, factories):
    """Branching is checked at validation time so the reader never hits a dead
    end. A goto must point to a real page number."""
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.stories[0].data["pages"][1]["interaction"] = {
        "type": "choice",
        "prompt": "pick",
        "data": {"options": [
            {"label": "A", "goto": 2},     # exists
            {"label": "B", "goto": 999},   # does NOT exist
        ]},
    }
    check_story(rep, w, w.stories[0])
    assert any("999" in f for f in rep.fails)


def test_check_story_accepts_choice_with_valid_gotos(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.stories[0].data["pages"][1]["interaction"] = {
        "type": "choice",
        "prompt": "pick",
        "data": {"options": [{"label": "A", "goto": 2}]},
    }
    check_story(rep, w, w.stories[0])
    goto_fails = [f for f in rep.fails if "goto" in f]
    assert goto_fails == []


def test_check_story_warns_when_no_interactions_at_all(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    # default story has no interactions
    check_story(rep, w, w.stories[0])
    assert any("no interactions" in warn for warn in rep.warns)


def test_check_story_warns_when_every_game_is_a_quiz(write_world, factories):
    """Fun-first: if every game is a pick-an-answer quiz (legacy), nudge the author to add a REAL
    arcade game a kid actually DOES."""
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    for n in (1, 2):
        w.stories[0].data["pages"][n]["interaction"] = {
            "type": "comprehension-question", "prompt": "?",
            "data": {"question": "?"},
        }
    check_story(rep, w, w.stories[0])
    assert any("REAL game" in warn for warn in rep.warns)


def test_check_story_no_variety_warning_when_games_vary_and_include_rich(write_world, factories):
    """Varied kinds of fun including a rich (non-quiz) game → no variety/richness nudge."""
    rep = _ok_report()
    pages = [
        {"number": 1, "kind": "story", "text": "go", "image": {"prompt": "x"},
         "interaction": {"type": "drag-sort", "prompt": "go",
                         "data": {"bins": [{"label": "In", "key": "in"}],
                                  "items": [{"label": "sock", "bin": "in"}]}}},
        {"number": 2, "kind": "story", "text": "go", "image": {"prompt": "x"},
         "interaction": {"type": "riddle", "prompt": "go", "data": {"answer": "x"}}},
        {"number": 3, "kind": "story", "text": "go", "image": {"prompt": "x"},
         "interaction": {"type": "rhyme-complete", "prompt": "go", "data": {"answer": "x"}}},
    ]
    from lib.model import load_world
    write_world(
        slug="ww",
        characters=[factories.character(slug="hero", world="ww")],
        stories=[factories.story(slug="s1", world="ww", pages=pages,
                                  reading_level={"target_fk_grade": 1.0,
                                                 "max_words_per_page": 60,
                                                 "max_sentence_words": 8})],
    )
    w = load_world("ww")
    check_story(rep, w, w.stories[0])
    assert not any("vary the fun" in warn.lower() or "rich game" in warn.lower() for warn in rep.warns)


# ================================================================================== accessibility / illustration
def test_check_story_warns_when_image_alt_missing(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.stories[0].data["pages"][1]["image"]["alt"] = ""
    check_story(rep, w, w.stories[0])
    assert any("alt text" in warn for warn in rep.warns)


def test_check_story_warns_when_layout_missing(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    del w.stories[0].data["pages"][1]["layout"]
    check_story(rep, w, w.stories[0])
    assert any("layout" in warn for warn in rep.warns)


def test_check_story_warns_when_image_file_missing(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    # default story has no `image.file` set on page 1 — exactly the case we want to warn about
    assert "file" not in w.stories[0].data["pages"][1]["image"]
    check_story(rep, w, w.stories[0])
    assert any("/illustrate" in warn or "no image file" in warn for warn in rep.warns)


def test_check_story_fails_when_declared_image_file_does_not_exist(write_world, factories):
    """Says it has an image, but the file isn't on disk → that's a real publish
    blocker, not a soft warning."""
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.stories[0].data["pages"][1]["image"]["file"] = "images/never-rendered.png"
    check_story(rep, w, w.stories[0])
    assert any("never-rendered.png" in f and "illustration" in f for f in rep.fails)


# ================================================================================== publish gate
def test_check_story_blocks_publish_status_when_other_failures_present(write_world, factories):
    """The publish gate: even if a book was *marked* published, any failure in
    the report turns into an extra '[publish] marked published but has failures'
    fail. This stops a half-broken book from going live."""
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.stories[0].data["status"] = "published"
    # introduce one consistency failure
    w.stories[0].data["characters"][0]["stage"] = "never-existed"
    check_story(rep, w, w.stories[0])
    assert any("[publish]" in f and "published" in f for f in rep.fails)


def test_check_story_no_publish_block_when_status_is_draft(write_world, factories):
    rep = _ok_report()
    w = _world_obj(write_world, factories)
    w.stories[0].data["status"] = "draft"
    w.stories[0].data["characters"][0]["stage"] = "never-existed"  # other failures
    check_story(rep, w, w.stories[0])
    # other failures exist, but specifically no '[publish]' failure
    assert not any("[publish]" in f for f in rep.fails)


# ================================================================================== Report
def test_report_accumulates_counts_correctly():
    r = Report()
    r.ok("good 1"); r.ok("good 2")
    r.fail("bad 1")
    r.warn("warn 1")
    assert r.passes == 2
    assert r.fails == ["bad 1"]
    assert r.warns == ["warn 1"]


# ================================================================================== INTERACTION_DATA_KEYS contract
def test_interaction_data_keys_covers_every_schema_type():
    """Validator-side allow-list MUST stay in sync with the schema enum. If a
    new interaction type lands in the schema and not here, those games will
    silently 'fail' validation as unknown types."""
    import json, pathlib
    schemas = pathlib.Path(__file__).resolve().parents[2] / "schemas"
    story_schema = json.loads((schemas / "story.schema.json").read_text())
    enum = story_schema["$defs"]["interaction"]["properties"]["type"]["enum"]
    missing = set(enum) - set(INTERACTION_DATA_KEYS)
    assert missing == set(), f"INTERACTION_DATA_KEYS missing schema types: {missing}"
