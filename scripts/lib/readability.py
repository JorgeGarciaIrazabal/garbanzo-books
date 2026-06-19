"""Readability metrics (Flesch Reading Ease + Flesch-Kincaid Grade Level) and the
per-YEAR reading targets from methodology/reading-pedagogy.md. Pure-Python, no dependencies.

Both formulas reward short words/sentences but ignore decodability and picture support,
and FKGL is unreliable below ~Grade 1 (few sentences -> volatile ratios). For bands 0-3 and
3-5 we therefore lean on words/page + sentence-length checks, not FKGL.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Age band -> targets. fk_grade is None where the formula is unreliable (read-aloud bands).
# max_sentence_words caps the LONGEST sentence in the book — the average should sit well
# below it, with varied sentence shapes. min_avg_sentence_words is the anti-telegraphic
# floor: prose chopped into fragments to game the caps ("Seoul at night. Bright lights.")
# reads like a robot and fails the read-aloud test. The floor is set for EVERY band now —
# the read-aloud bands (0-3, 3-5) had no floor, which is exactly why the worst telegram
# prose slipped through there (e.g. "Midnight-blue robe. Star-gold embroidery. Crumbs on
# her chin."). For those bands the floor surfaces as a WARN, not a hard fail (legitimate
# rhythmic/refrain lines are genuinely short — the read-aloud pass makes the human call);
# for graded bands (5-7+) it is a fail. See reading_level.py.
BANDS: dict[str, dict] = {
    "0-3":      {"fk_grade": None, "max_words_per_page": 10,  "max_sentence_words": 8,  "min_avg_sentence_words": 3.0,  "label": "Board book"},
    "3-5":      {"fk_grade": None, "max_words_per_page": 40,  "max_sentence_words": 12, "min_avg_sentence_words": 4.5,  "label": "Pre-reader"},
    "5-7":      {"fk_grade": 1.5,  "max_words_per_page": 60,  "max_sentence_words": 14, "min_avg_sentence_words": 5.0,  "label": "Early reader (K-1)"},
    "7-9":      {"fk_grade": 3.0,  "max_words_per_page": 150, "max_sentence_words": 18, "min_avg_sentence_words": 7.0,  "label": "Grade 2-3"},
    "9-12":     {"fk_grade": 5.5,  "max_words_per_page": 400, "max_sentence_words": 26, "min_avg_sentence_words": 9.0,  "label": "Middle grade"},
    "grown-up": {"fk_grade": 10.0, "max_words_per_page": 800, "max_sentence_words": 40, "min_avg_sentence_words": 12.0, "label": "Adult reader"},
}

# --- Per-YEAR reading targets (the source of truth) -------------------------------
# Reading level is selected by a SINGLE age in years, not the coarse band. Each year gets
# an FK *window* (fk_lo..fk_hi) plus its own caps, so the targets rise smoothly year on year
# instead of in band-sized steps. The FK curve is developmentally accurate: FK grade ~= age-5
# (a 5-year-old is in kindergarten ~= grade 0; FK = US school grade). fk_lo/fk_hi are None for
# the youngest read-aloud years where FKGL is meaningless on tiny text. fk_enforced says whether
# exceeding the window is a hard FAIL (only where the formula is reliable, ~age 7+) or a WARN.
# The bands above survive for display chips, world target_age_bands, and 'grown-up'.
#
# READ MODE — the same age is two very different readers (see methodology/reading-pedagogy.md,
# "Read-aloud or reading it alone?"). The page caps below are the READ-ALOUD baseline: a grown-up
# voices the words, so a young page can carry more text. `solo_max_words_per_page` /
# `solo_max_sentence_words` are the TIGHTER caps for a child decoding every word alone — a brand-
# new reader needs short lines and lots of white space (decodable / early-reader practice). They
# only differ in the early years (~4-8) where mode matters; from ~age 9 the two modes converge
# (almost everyone reads solo by then and the cap is already generous), so the solo fields are
# omitted and fall back to the read-aloud cap. All caps are ADVISORY anchors, never hard gates.
MIN_YEAR, MAX_YEAR = 2, 13
READING_BY_YEAR: dict[int, dict] = {
    2:  {"fk_lo": None, "fk_hi": None, "fk_enforced": False, "max_words_per_page": 8,   "max_sentence_words": 6,  "min_avg_sentence_words": 2.5,  "label": "Toddler / lap book"},
    3:  {"fk_lo": None, "fk_hi": None, "fk_enforced": False, "max_words_per_page": 18,  "max_sentence_words": 8,  "min_avg_sentence_words": 3.0,  "label": "Board book"},
    4:  {"fk_lo": 0.0,  "fk_hi": 0.4,  "fk_enforced": False, "max_words_per_page": 35,  "max_sentence_words": 10, "min_avg_sentence_words": 4.0,  "solo_max_words_per_page": 12, "solo_max_sentence_words": 7,  "label": "Pre-reader"},
    5:  {"fk_lo": 0.0,  "fk_hi": 0.6,  "fk_enforced": False, "max_words_per_page": 55,  "max_sentence_words": 13, "min_avg_sentence_words": 4.5,  "solo_max_words_per_page": 25, "solo_max_sentence_words": 8,  "solo_avg_words_per_page": 15, "label": "Kindergarten"},
    6:  {"fk_lo": 0.6,  "fk_hi": 1.3,  "fk_enforced": False, "max_words_per_page": 70,  "max_sentence_words": 15, "min_avg_sentence_words": 5.0,  "solo_max_words_per_page": 40, "solo_max_sentence_words": 11, "label": "Kindergarten / Grade 1"},
    7:  {"fk_lo": 1.5,  "fk_hi": 2.3,  "fk_enforced": True,  "max_words_per_page": 100, "max_sentence_words": 16, "min_avg_sentence_words": 6.0,  "solo_max_words_per_page": 65, "solo_max_sentence_words": 14, "label": "Grade 1-2"},
    8:  {"fk_lo": 2.5,  "fk_hi": 3.3,  "fk_enforced": True,  "max_words_per_page": 130, "max_sentence_words": 18, "min_avg_sentence_words": 6.5,  "solo_max_words_per_page": 100, "solo_max_sentence_words": 16, "label": "Grade 2-3"},
    9:  {"fk_lo": 3.5,  "fk_hi": 4.3,  "fk_enforced": True,  "max_words_per_page": 180, "max_sentence_words": 20, "min_avg_sentence_words": 7.5,  "label": "Grade 3-4"},
    10: {"fk_lo": 4.5,  "fk_hi": 5.3,  "fk_enforced": True,  "max_words_per_page": 260, "max_sentence_words": 23, "min_avg_sentence_words": 8.0,  "label": "Grade 4-5"},
    11: {"fk_lo": 5.5,  "fk_hi": 6.3,  "fk_enforced": True,  "max_words_per_page": 340, "max_sentence_words": 25, "min_avg_sentence_words": 8.5,  "label": "Grade 5-6"},
    12: {"fk_lo": 6.3,  "fk_hi": 7.0,  "fk_enforced": True,  "max_words_per_page": 420, "max_sentence_words": 27, "min_avg_sentence_words": 9.0,  "label": "Grade 6-7"},
    13: {"fk_lo": 7.0,  "fk_hi": 8.0,  "fk_enforced": True,  "max_words_per_page": 550, "max_sentence_words": 30, "min_avg_sentence_words": 10.0, "label": "Grade 7-8"},
}

# Read modes — WHO is turning the words into sound. Explicit on a story via
# `reading_level.read_mode`; when absent it defaults by age (a grown-up usually reads for the
# youngest, the child reads alone once they can). This is the single biggest lever on how hard
# the individual WORDS may be — orthogonal to sentence length / words-per-page.
READ_MODES = ("read_aloud", "solo")
# Age at/under which a book defaults to read-aloud when read_mode is not set. A 5-year-old is
# the hinge: plenty are read to, plenty are sounding out their first solo books — so the author
# should set read_mode explicitly for ages ~4-8. The default keeps old stories behaving as before.
DEFAULT_READ_ALOUD_MAX_YEAR = 5
# Age at/under which short, non-flowing lines are a LEGITIMATE style in either mode — rhythmic
# read-aloud refrains AND a brand-new solo decoder's short decodable sentences — so the
# telegraphic-prose guard backs off (WARN at most, never FAIL). From age 6 (Grade 1) flowing
# sentences chained with and/but/so are expected whoever reads them. Mode-independent on purpose:
# the win here is that a SOLO 5-year-old's short decodable sentences are no longer flagged either
# (previously only read-aloud got the pass, but read_mode didn't exist as a concept yet).
TELEGRAPHIC_RELAXED_MAX_YEAR = 5


def default_read_mode(year: int | None) -> str:
    """The read mode a story falls back to when it doesn't set one explicitly: read-aloud for
    the youngest (a grown-up voices the words), solo from ~age 6 (the child reads alone)."""
    if not isinstance(year, int):
        return "read_aloud"
    return "read_aloud" if year <= DEFAULT_READ_ALOUD_MAX_YEAR else "solo"


def normalize_read_mode(value, year: int | None) -> str:
    """Coerce an explicit read_mode to a known value, falling back to the age default."""
    v = (value or "").strip().lower().replace("-", "_") if isinstance(value, str) else ""
    if v in ("read_aloud", "readaloud", "aloud"):
        return "read_aloud"
    if v in ("solo", "independent", "solo_reader", "solo_decoder"):
        return "solo"
    return default_read_mode(year)

# Year -> coarse band (display label + the 'reader ability' enum). Boundaries overlap between
# bands by design, so each year is assigned to exactly one. Years outside 2..13 clamp.
_YEAR_TO_BAND = {2: "0-3", 3: "0-3", 4: "3-5", 5: "3-5", 6: "5-7", 7: "5-7",
                 8: "7-9", 9: "7-9", 10: "9-12", 11: "9-12", 12: "9-12", 13: "9-12"}
# Band -> representative year, for the legacy path where a story has only age_band (no year).
_BAND_TO_YEAR = {"0-3": 2, "3-5": 4, "5-7": 6, "7-9": 8, "9-12": 11}


def band_for_year(year: int) -> str:
    """The coarse age_band that owns this reader year (legacy/display only). Years 2..13 map
    to a child band; ~14+ is an adult reader -> 'grown-up'."""
    y = int(year)
    if y >= 14:
        return "grown-up"
    return _YEAR_TO_BAND[max(MIN_YEAR, min(MAX_YEAR, y))]


def targets_for_year(year: int, read_mode: str | None = None) -> dict:
    """Effective reading targets for a single age year + read mode: the FK window collapsed to a
    target+tolerance the existing checkers understand, plus the per-year caps. A solo reader
    (the child decodes every word) gets the tighter `solo_*` page caps where they exist; a
    read-aloud book keeps the generous baseline caps. read_mode defaults by age when omitted."""
    y = max(MIN_YEAR, min(MAX_YEAR, int(year)))
    row = READING_BY_YEAR[y]
    mode = normalize_read_mode(read_mode, y) if read_mode is not None else default_read_mode(y)
    lo, hi = row["fk_lo"], row["fk_hi"]
    if lo is None:
        fk_target = fk_tol = None
    else:
        fk_target = round((lo + hi) / 2, 2)
        fk_tol = round((hi - lo) / 2, 2)
    solo = mode == "solo"
    max_wpp = row["solo_max_words_per_page"] if solo and "solo_max_words_per_page" in row else row["max_words_per_page"]
    max_sent = row["solo_max_sentence_words"] if solo and "solo_max_sentence_words" in row else row["max_sentence_words"]
    # Advisory AVERAGE words/page for the youngest solo decoders — the ceiling (max_wpp) is the
    # most a page may carry, but a brand-new reader's TYPICAL page should sit well under it. Only
    # set for the early solo years where the gap matters (e.g. age 5 solo: aim ~15, max 25).
    avg_wpp = row.get("solo_avg_words_per_page") if solo else None
    return {
        "fk_target": fk_target, "fk_tol": fk_tol, "fk_lo": lo, "fk_hi": hi,
        "fk_enforced": row["fk_enforced"],
        "read_mode": mode,
        # read_aloud convenience flag: a grown-up voices the words, so juicy low-frequency words
        # are a gift; solo means the child sounds out every word, so lean decodable/high-frequency.
        "read_aloud": mode == "read_aloud",
        # telegraphic_relaxed: at the youngest ages short non-flowing lines are a legitimate style
        # in BOTH modes (rhythmic refrains / brand-new decodable sentences), so the anti-telegram
        # guard backs off. Age-driven, not mode-driven — fragments read badly aloud at any older age.
        "telegraphic_relaxed": y <= TELEGRAPHIC_RELAXED_MAX_YEAR,
        "max_words_per_page": max_wpp,
        "max_sentence_words": max_sent,
        "min_avg_sentence_words": row["min_avg_sentence_words"],
        "avg_words_per_page": avg_wpp,
        "label": row["label"],
    }


def story_age_label(story: dict) -> str:
    """Human display of a story's reader age: 'age 6' / 'adult'. Prefers target_year; falls
    back to the legacy band so old stories still read sensibly. No bands shown to users."""
    y = story.get("target_year")
    if not isinstance(y, int):
        ab = story.get("age_band")
        if ab == "grown-up":
            return "adult"
        y = _BAND_TO_YEAR.get(ab or "")
    if not isinstance(y, int):
        return ""
    return "adult" if y >= 14 else f"age {y}"


def world_age_label(world: dict) -> str:
    """Human display of a world's audience: 'age 6' or 'ages 5–7'. Prefers target_years;
    falls back to deriving years from the legacy target_age_bands."""
    years = list(world.get("target_years") or [])
    if not years:
        bands = world.get("target_age_bands") or []
        years = sorted({_BAND_TO_YEAR[b] for b in bands if b in _BAND_TO_YEAR})
        if any(b == "grown-up" for b in bands):
            years.append(14)
    years = sorted(set(years))
    if not years:
        return ""
    if len(years) == 1:
        return "adult" if years[0] >= 14 else f"age {years[0]}"
    lo, hi = years[0], years[-1]
    return f"ages {lo}–{hi}" + ("+" if hi >= 14 else "")


def _grownup_targets() -> dict:
    b = BANDS["grown-up"]
    return {"fk_target": b["fk_grade"], "fk_tol": 1.5, "fk_lo": None, "fk_hi": None,
            "fk_enforced": True, "read_mode": "solo", "read_aloud": False,
            "telegraphic_relaxed": False,
            "max_words_per_page": b["max_words_per_page"],
            "max_sentence_words": b["max_sentence_words"],
            "min_avg_sentence_words": b["min_avg_sentence_words"], "label": b["label"]}


def story_targets(story: dict) -> dict:
    """The single source every reading checker shares. Targets come from the per-year curve
    keyed on `target_year` + the story's `reading_level.read_mode` (read-aloud vs solo decoder);
    `age_band` is the fallback (and the authority for 'grown-up'). Explicit numbers in the
    story's `reading_level` override the curve (an author bump)."""
    band_id = story.get("age_band") or "5-7"
    rl = story.get("reading_level") or {}
    year = story.get("target_year")
    year_for_mode = year if isinstance(year, int) else _BAND_TO_YEAR.get(band_id, 6)
    read_mode = normalize_read_mode(rl.get("read_mode"), year_for_mode)

    if band_id == "grown-up":
        base = _grownup_targets()
    elif isinstance(year, int):
        base = targets_for_year(year, read_mode)
    else:
        base = targets_for_year(_BAND_TO_YEAR.get(band_id, 6), read_mode)

    fk_target = rl.get("target_fk_grade", base["fk_target"])
    fk_tol = rl.get("fk_grade_tolerance", base["fk_tol"])
    return {
        "fk_target": fk_target,
        "fk_tol": fk_tol if fk_tol is not None else 1.0,
        "fk_lo": base["fk_lo"], "fk_hi": base["fk_hi"],
        "fk_enforced": base["fk_enforced"],
        "read_mode": base["read_mode"],
        "read_aloud": base["read_aloud"],
        "telegraphic_relaxed": base["telegraphic_relaxed"],
        "max_words_per_page": rl.get("max_words_per_page", base["max_words_per_page"]),
        "max_sentence_words": rl.get("max_sentence_words", base["max_sentence_words"]),
        "min_avg_sentence_words": base["min_avg_sentence_words"],
        "label": base["label"],
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
