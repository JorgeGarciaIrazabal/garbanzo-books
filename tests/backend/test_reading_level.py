"""Tests for ``scripts/reading_level.py`` — the per-story FK / word-cap checker.

We use the ``report()`` function directly so we don't have to fight argv parsing,
and we use ``capsys`` to read the human-readable PASS/FAIL output. The exit-code
contract (returns True == on target, False == needs work) is what publishers use
to gate releases, so we test that explicitly.
"""
from __future__ import annotations

import pytest

import reading_level
from reading_level import (DEFAULT_SIGHT, decodable_focus_letters, page_text,
                            report, resolve_story_yaml)
from lib.model import dump_yaml


def _write_story(workspace, factories, **overrides):
    """Write a story into the isolated workspace and return its yaml path."""
    s = factories.story(slug="s1", world="ww", **overrides)
    sdir = workspace.worlds / "ww" / "stories" / "s1"
    dump_yaml(s, sdir / "story.yaml")
    return sdir / "story.yaml"


# ============================================================================ resolve_story_yaml
def test_resolve_story_yaml_accepts_world_slash_story_shorthand(workspace, factories):
    sy = _write_story(workspace, factories)
    # Use the in-workspace relative form; the helper looks under ROOT/worlds
    # but ROOT is monkey-patched in the workspace fixture, so this resolves.
    out = resolve_story_yaml("ww/s1")
    assert out == sy


def test_resolve_story_yaml_accepts_directory_path(workspace, factories):
    sy = _write_story(workspace, factories)
    out = resolve_story_yaml(str(sy.parent))
    assert out == sy


def test_resolve_story_yaml_accepts_yaml_path_directly(workspace, factories):
    sy = _write_story(workspace, factories)
    out = resolve_story_yaml(str(sy))
    assert out == sy


def test_resolve_story_yaml_raises_for_unresolved_input(workspace):
    with pytest.raises(FileNotFoundError):
        resolve_story_yaml("definitely-not-here/nope")


# ============================================================================ page_text
def test_page_text_concats_only_text_fields(factories):
    pages = [
        {"text": "Hello.", "image": {}},
        {"text": "World!", "image": {}},
        {"image": {}},  # no text
    ]
    out = page_text(pages)
    assert "Hello" in out and "World" in out
    assert out.count(" ") >= 1  # joined with spaces


# ============================================================================ report (the meat)
def test_report_passes_for_simple_story_at_target_grade(workspace, factories, capsys):
    """Easy text + on-target FK + within word cap → returns True and prints PASS."""
    sy = _write_story(workspace, factories,
                       age_band="5-7",
                       reading_level={"target_fk_grade": 1.0, "fk_grade_tolerance": 1.5,
                                      "max_words_per_page": 60, "max_sentence_words": 8})
    ok = report(sy)
    out = capsys.readouterr().out
    assert ok is True
    assert "ON TARGET" in out


def test_report_fails_when_pages_exceed_word_cap(workspace, factories, capsys):
    """Per-page word cap is one of the validator's hard gates."""
    long_text = " ".join(["foo"] * 100)
    story = factories.story(slug="s1", world="ww")
    story["pages"][1]["text"] = long_text
    story["reading_level"]["max_words_per_page"] = 10
    dump_yaml(story, workspace.worlds / "ww" / "stories" / "s1" / "story.yaml")
    sy = workspace.worlds / "ww" / "stories" / "s1" / "story.yaml"
    ok = report(sy)
    out = capsys.readouterr().out
    assert ok is False
    assert "FAIL" in out
    assert "word cap" in out.lower()


def test_report_fails_when_longest_sentence_exceeds_cap(workspace, factories, capsys):
    """Sentence length is a separate gate — even within the word cap, ONE very
    long sentence trips it (kids' attention spans fail at long sentences)."""
    long_sentence = " ".join(["w"] * 30) + "."
    story = factories.story(slug="s1", world="ww")
    story["pages"][1]["text"] = long_sentence
    story["reading_level"]["max_sentence_words"] = 8
    story["reading_level"]["max_words_per_page"] = 200  # plenty of room word-wise
    dump_yaml(story, workspace.worlds / "ww" / "stories" / "s1" / "story.yaml")
    sy = workspace.worlds / "ww" / "stories" / "s1" / "story.yaml"
    ok = report(sy)
    out = capsys.readouterr().out
    assert ok is False
    assert "longest sentence" in out


def test_report_fails_when_fk_above_target_plus_tolerance(workspace, factories, capsys):
    text = ("Subsequently the interconnectedness of philosophical postulates "
            "necessitated comprehensive reevaluation of epistemological assumptions.")
    story = factories.story(slug="s1", world="ww")
    story["pages"][1]["text"] = text
    story["age_band"] = "5-7"
    story["reading_level"]["target_fk_grade"] = 1.0
    story["reading_level"]["fk_grade_tolerance"] = 0.5
    dump_yaml(story, workspace.worlds / "ww" / "stories" / "s1" / "story.yaml")
    sy = workspace.worlds / "ww" / "stories" / "s1" / "story.yaml"
    ok = report(sy)
    assert ok is False
    assert "FK grade" in capsys.readouterr().out


def test_report_does_not_check_fk_for_read_aloud_bands(workspace, factories, capsys):
    """For 0-3 / 3-5 the FKGL line should explicitly say it's not used."""
    sy = _write_story(workspace, factories, age_band="3-5",
                       reading_level={"target_fk_grade": 0.5, "fk_grade_tolerance": 1.0,
                                      "max_words_per_page": 40, "max_sentence_words": 10})
    report(sy)
    out = capsys.readouterr().out
    assert "FKGL not used" in out or "read-aloud band" in out


def test_report_passes_FKGL_a_bit_below_target_is_just_a_note(workspace, factories, capsys):
    """Easier-than-target text is fine — confidence is good — so it gets a note,
    not a fail."""
    sy = _write_story(workspace, factories, age_band="7-9",
                       reading_level={"target_fk_grade": 4.0, "fk_grade_tolerance": 1.0,
                                      "max_words_per_page": 150, "max_sentence_words": 14})
    ok = report(sy)
    out = capsys.readouterr().out
    # Default factory text is very simple; FK will be well below 4.0
    # Still should pass overall (it's not above target).
    assert ok is True
    assert "FAIL" not in out or "below target" in out


# ============================================================================ telegraphic guard
def _pages_with_text(texts: list[str]) -> list[dict]:
    pages = [{"number": 0, "kind": "title", "text": "T",
              "image": {"prompt": "x", "characters_present": [], "alt": "t", "text_zone": "center"}}]
    for i, t in enumerate(texts, start=1):
        pages.append({"number": i, "kind": "story", "text": t,
                      "image": {"prompt": "x", "characters_present": [], "alt": "a",
                                "text_zone": "lower third"}})
    return pages


def test_report_fails_telegraphic_fragment_prose(workspace, factories, capsys):
    """Prose chopped into fragment-chains to game the sentence cap must FAIL —
    this is the 'Seoul at night. Bright lights.' failure mode."""
    choppy = "Seoul at night. Bright lights. Palaces glow. Best snack spot. A lady watches."
    story = factories.story(slug="s1", world="ww", age_band="5-7")
    story["pages"] = _pages_with_text([choppy] * 4)  # 20 sentences, avg ~3 words
    dump_yaml(story, workspace.worlds / "ww" / "stories" / "s1" / "story.yaml")
    ok = report(workspace.worlds / "ww" / "stories" / "s1" / "story.yaml")
    out = capsys.readouterr().out
    assert ok is False
    assert "telegraphic" in out.lower()


def test_report_passes_flowing_prose_of_same_difficulty(workspace, factories, capsys):
    """The same content written as short flowing sentences passes the guard."""
    flowing = ("Seoul glowed below them like a bowl of candy. "
               "A lady in the night market waved at them. "
               "She held out one hot bowl and smiled.")
    story = factories.story(slug="s1", world="ww", age_band="5-7",
                            reading_level={"target_fk_grade": 1.5, "fk_grade_tolerance": 1.5,
                                           "max_words_per_page": 60, "max_sentence_words": 14})
    story["pages"] = _pages_with_text([flowing] * 4)
    dump_yaml(story, workspace.worlds / "ww" / "stories" / "s1" / "story.yaml")
    ok = report(workspace.worlds / "ww" / "stories" / "s1" / "story.yaml")
    out = capsys.readouterr().out
    assert ok is True, out
    assert "prose flows" in out.lower()


def test_telegraphic_guard_skips_read_aloud_bands(workspace, factories, capsys):
    """Very short refrain lines are a legitimate style for 0-5 — no telegraphic FAIL."""
    refrain = "The bus goes beep. The bus goes beep. Beep beep beep."
    story = factories.story(slug="s1", world="ww", age_band="3-5")
    story["reading_level"]["max_words_per_page"] = 40
    story["reading_level"]["max_sentence_words"] = 12
    story["pages"] = _pages_with_text([refrain] * 5)
    dump_yaml(story, workspace.worlds / "ww" / "stories" / "s1" / "story.yaml")
    ok = report(workspace.worlds / "ww" / "stories" / "s1" / "story.yaml")
    out = capsys.readouterr().out
    assert ok is True, out
    assert "telegraphic" not in out.lower()


# ============================================================================ decodable mode
def test_decodable_focus_letters_extracts_phonics_focus():
    letters = decodable_focus_letters("s a t p i n; sight: the,is,a")
    # Each grapheme/digraph from before the 'sight:' marker is captured.
    assert "s" in letters
    assert "a" in letters
    assert "p" in letters
    # The sight-words list is ignored at the letter level.
    assert "the" not in letters


def test_decodable_focus_letters_ignores_text_after_sight_marker():
    letters = decodable_focus_letters("m k ; sight: was,said,the")
    assert "m" in letters
    assert "k" in letters
    assert "was" not in letters


def test_decodable_mode_flags_multisyllable_non_sight_words(workspace, factories, capsys):
    story = factories.story(slug="s1", world="ww")
    story["pages"][1]["text"] = "The hippopotamus loved his banana."
    story["reading_level"]["decodable"] = True
    story["reading_level"]["decoding_focus"] = "h b n; sight: the,his"
    dump_yaml(story, workspace.worlds / "ww" / "stories" / "s1" / "story.yaml")
    sy = workspace.worlds / "ww" / "stories" / "s1" / "story.yaml"
    ok = report(sy)
    out = capsys.readouterr().out
    assert ok is False
    assert "decodable" in out.lower()
    # The big polysyllabic words must show up in the flagged list
    assert "hippopotamus" in out
    assert "banana" in out


def test_decodable_mode_passes_when_only_sight_and_short_words(workspace, factories, capsys):
    story = factories.story(slug="s1", world="ww")
    # Replace ALL text so no smuggled-in multisyllable words trip the check.
    # All words here are either single-syllable or in DEFAULT_SIGHT.
    story["title"] = "Cat Sat"
    for p in story["pages"]:
        p["text"] = "The cat sat. The dog ran."
    story["reading_level"]["decodable"] = True
    story["reading_level"]["decoding_focus"] = "c d r s t; sight: the,a"
    story["reading_level"]["max_sentence_words"] = 8
    dump_yaml(story, workspace.worlds / "ww" / "stories" / "s1" / "story.yaml")
    sy = workspace.worlds / "ww" / "stories" / "s1" / "story.yaml"
    ok = report(sy)
    out = capsys.readouterr().out
    assert ok is True, out


def test_default_sight_list_contains_high_frequency_words():
    """High-frequency irregular sight words must be in the default list, otherwise
    decodable mode would falsely flag them in every book."""
    for w in ("the", "a", "is", "was", "said", "you", "he", "she", "of"):
        assert w in DEFAULT_SIGHT
