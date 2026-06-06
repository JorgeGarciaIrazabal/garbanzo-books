"""Readability metrics (Flesch Reading Ease + Flesch-Kincaid Grade Level) and the
per-age-band targets from methodology/reading-pedagogy.md. Pure-Python, no dependencies.

Both formulas reward short words/sentences but ignore decodability and picture support,
and FKGL is unreliable below ~Grade 1 (few sentences -> volatile ratios). For bands 0-3 and
3-5 we therefore lean on words/page + sentence-length checks, not FKGL.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Age band -> targets. fk_grade is None where the formula is unreliable (read-aloud bands).
BANDS: dict[str, dict] = {
    "0-3":  {"fk_grade": None, "max_words_per_page": 10,  "max_sentence_words": 6,  "label": "Board book"},
    "3-5":  {"fk_grade": None, "max_words_per_page": 40,  "max_sentence_words": 10, "label": "Pre-reader"},
    "5-7":  {"fk_grade": 1.0,  "max_words_per_page": 60,  "max_sentence_words": 8,  "label": "Early reader (K-1)"},
    "7-9":  {"fk_grade": 2.5,  "max_words_per_page": 150, "max_sentence_words": 14, "label": "Grade 2-3"},
    "9-12": {"fk_grade": 5.0,  "max_words_per_page": 400, "max_sentence_words": 20, "label": "Middle grade"},
}

_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_SENT_RE = re.compile(r"[.!?]+")
_VOWEL_GROUPS = re.compile(r"[aeiouy]+")


def count_syllables(word: str) -> int:
    """Heuristic English syllable counter. Good enough for grade estimation."""
    word = word.lower().strip()
    if not word:
        return 0
    groups = _VOWEL_GROUPS.findall(word)
    count = len(groups)
    # Silent trailing 'e' (but keep words like 'the' at >=1).
    if word.endswith("e") and not word.endswith(("le", "ye")) and count > 1:
        count -= 1
    # 'le' at the end after a consonant adds a syllable (table, little).
    if word.endswith("le") and len(word) > 2 and word[-3] not in "aeiouy":
        count += 1
    return max(1, count)


def words(text: str) -> list[str]:
    return _WORD_RE.findall(text or "")


def sentences(text: str) -> int:
    parts = [p for p in _SENT_RE.split(text or "") if p.strip()]
    return max(1, len(parts))


@dataclass
class Metrics:
    words: int
    sentences: int
    syllables: int
    longest_sentence_words: int

    @property
    def words_per_sentence(self) -> float:
        return self.words / self.sentences if self.sentences else 0.0

    @property
    def syllables_per_word(self) -> float:
        return self.syllables / self.words if self.words else 0.0

    @property
    def flesch_reading_ease(self) -> float:
        if not self.words:
            return 0.0
        return round(
            206.835 - 1.015 * self.words_per_sentence - 84.6 * self.syllables_per_word, 1
        )

    @property
    def fk_grade(self) -> float:
        if not self.words:
            return 0.0
        return round(
            0.39 * self.words_per_sentence + 11.8 * self.syllables_per_word - 15.59, 2
        )


def analyze(text: str) -> Metrics:
    wlist = words(text)
    nsent = sentences(text)
    syll = sum(count_syllables(w) for w in wlist)
    # Longest sentence in words.
    longest = 0
    for chunk in _SENT_RE.split(text or ""):
        longest = max(longest, len(words(chunk)))
    return Metrics(words=len(wlist), sentences=nsent, syllables=syll, longest_sentence_words=longest)
