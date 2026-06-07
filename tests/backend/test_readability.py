"""Tests for ``scripts/lib/readability.py`` — the readability scoring engine.

These guard the formulas + the per-age-band targets that the validator uses to
gate publication. We test the *contracts* (FK grade goes up with longer/longer-word
sentences, syllable heuristic gets the common words right, BANDS table has the
right shape) rather than memorising exact float values that future tweaks may
move slightly.
"""
from __future__ import annotations

import pytest

from lib.readability import BANDS, Metrics, analyze, count_syllables, sentences, words


# =============================================================================== syllable heuristic
@pytest.mark.parametrize("word,expected", [
    ("cat", 1),
    ("dog", 1),
    ("happy", 2),
    ("storybook", 3),
    ("photography", 4),
    ("a", 1),
    ("the", 1),       # silent-e rule must keep this at 1, not collapse to 0
    ("sky", 1),       # 'y' counted as vowel
    ("ye", 1),        # silent-e exception
    ("eye", 1),
    ("hippopotamus", 5),
])
def test_count_syllables_handles_common_words(word, expected):
    assert count_syllables(word) == expected


@pytest.mark.parametrize("word", ["table", "little", "apple", "bottle"])
def test_count_syllables_treats_le_after_consonant_as_extra_syllable(word):
    """The heuristic counts the `-le` ending after a consonant as an extra
    syllable on top of the vowel-group count. Documenting this so we notice
    if the rule ever changes."""
    assert count_syllables(word) >= 2  # at minimum: it's polysyllabic
    # And specifically: the rule adds the +1 for the consonant+le ending.
    # 'apple': groups = (a, e) = 2; silent-e doesn't drop it (ends 'le'); +1 for le rule = 3
    assert count_syllables(word) == 3


def test_count_syllables_empty_returns_zero():
    assert count_syllables("") == 0
    assert count_syllables("   ") == 0


def test_count_syllables_minimum_one_for_any_real_word():
    assert count_syllables("xyz") >= 1


def test_count_syllables_is_case_insensitive():
    assert count_syllables("Storybook") == count_syllables("storybook")


# =============================================================================== words / sentences
def test_words_extracts_alpha_runs_with_apostrophes():
    assert words("It's a sunny day, isn't it?") == ["It's", "a", "sunny", "day", "isn't", "it"]


def test_words_handles_empty_input():
    assert words("") == []
    assert words(None) == []  # type: ignore[arg-type]


def test_words_strips_punctuation_and_digits():
    # Pure digits are not "words" for readability — they aren't English text.
    assert "123" not in words("the answer is 123")


def test_sentences_counts_terminators_minimum_one():
    assert sentences("Hello. There. Friend.") == 3
    assert sentences("Just one") == 1   # minimum 1 even without a period
    assert sentences("") == 1            # empty still considered 1 sentence


def test_sentences_treats_excitement_and_questions_as_terminators():
    assert sentences("Wow! Really? Yes.") == 3


# =============================================================================== Metrics formula
def test_metrics_short_simple_text_has_low_fk_grade():
    m = analyze("The cat sat. The dog ran.")
    assert m.fk_grade < 2.0, f"Expected low FK grade for very simple text, got {m.fk_grade}"
    assert m.flesch_reading_ease > 80   # high reading-ease = easy text


def test_metrics_complex_long_text_has_higher_fk_grade():
    simple = analyze("The cat sat. The dog ran.")
    complex_ = analyze(
        "The interconnectedness of philosophical postulates necessitates a "
        "comprehensive reevaluation of foundational epistemological assumptions."
    )
    assert complex_.fk_grade > simple.fk_grade


def test_metrics_words_per_sentence_uses_sentence_count():
    m = analyze("One two. Three four five.")
    # 5 words, 2 sentences = 2.5 wps
    assert m.words_per_sentence == pytest.approx(2.5)


def test_metrics_longest_sentence_words_finds_the_longest():
    m = analyze("Short. A much longer sentence with quite a few more words.")
    # "A much longer sentence with quite a few more words" = 10 words
    assert m.longest_sentence_words == 10


def test_metrics_empty_text_returns_zero_grade():
    m = analyze("")
    assert m.words == 0
    assert m.fk_grade == 0.0
    assert m.flesch_reading_ease == 0.0


def test_metrics_syllables_per_word_zero_when_empty():
    m = analyze("")
    assert m.syllables_per_word == 0.0


def test_metrics_sentence_minimum_one_avoids_divide_by_zero():
    m = analyze("no terminator")
    assert m.sentences >= 1
    assert m.words_per_sentence > 0


# =============================================================================== BANDS table
def test_bands_table_includes_every_supported_age_band():
    assert set(BANDS) == {"0-3", "3-5", "5-7", "7-9", "9-12"}


def test_bands_word_caps_increase_with_age():
    """Pedagogy invariant: older readers handle more words per page."""
    caps = [BANDS[b]["max_words_per_page"] for b in ("0-3", "3-5", "5-7", "7-9", "9-12")]
    assert caps == sorted(caps), f"Word caps should be monotone increasing, got {caps}"


def test_bands_read_aloud_bands_have_no_fk_target():
    """FKGL is unreliable below ~Grade 1 — bands 0-3 and 3-5 must opt out so the
    validator doesn't falsely fail toddler books."""
    assert BANDS["0-3"]["fk_grade"] is None
    assert BANDS["3-5"]["fk_grade"] is None
    # The early-reader bands do have FK targets.
    assert BANDS["5-7"]["fk_grade"] is not None
    assert BANDS["7-9"]["fk_grade"] is not None


def test_bands_have_label_and_sentence_cap():
    for band, cfg in BANDS.items():
        assert isinstance(cfg["label"], str) and cfg["label"]
        assert isinstance(cfg["max_sentence_words"], int) and cfg["max_sentence_words"] > 0


def test_bands_fk_targets_increase_with_age():
    """Older bands should target a higher grade level."""
    g = [BANDS[b]["fk_grade"] for b in ("5-7", "7-9", "9-12")]
    assert g == sorted(g)


# =============================================================================== integration sanity
def test_analyze_matches_pieces_for_known_input():
    text = "The cat sat on the mat. The dog ran."
    m = analyze(text)
    assert m.words == 9
    assert m.sentences == 2
    # 'mat' is the 6th word of the 6-word first sentence
    assert m.longest_sentence_words == 6


def test_analyze_returns_metrics_instance():
    assert isinstance(analyze("Hello world."), Metrics)
