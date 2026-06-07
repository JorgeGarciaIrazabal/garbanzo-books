"""Behavioural / voice consistency (Core Principle #2: personality is a contract).

Visual consistency is *assembled* by the prompt pipeline; a character's voice has,
until now, only been human-reviewed. This checker gives that contract a machine
hook. It is deliberately **advisory (warn-only)** and conservative about
attribution — language is subtle, and a false *failure* would be worse than a
missed nudge. Three signals:

1. **Catchphrase silence** — a character declares catchphrases but the whole book
   never uses one. (Whole-book, cleanly attributable: catchphrases are unique text.)
2. **Gentle voice, shouting text** — a character whose ``speech_style`` reads soft/
   gentle/quiet is the *only* character in a spread, yet that spread SHOUTS.
3. **Simple voice, advanced words** — a character whose ``vocabulary_level`` reads
   simple/early is alone in a spread that uses 4+ syllable words.

Signals 2–3 only fire when the character is the sole one ``present`` on the page,
so the contradiction is confidently theirs.
"""
from __future__ import annotations

import re
from typing import Any

from ..readability import count_syllables, words
from .report import Report

_GENTLE = ("soft", "gentle", "quiet", "shy", "timid", "calm", "soothing",
           "whisper", "meek", "tender", "sweet", "mild")
_SIMPLE = ("simple", "basic", "easy", "early", "limited", "young", "minimal", "beginner")
_SHOUT_RE = re.compile(r"\b[A-Z]{3,}\b")
_SHOUT_ALLOW = {"NO", "YES", "OK", "BFF", "TV"}  # 3+ only, but keep a tiny allow-list anyway


def _norm(text: str) -> str:
    """Lower-case and collapse runs of non-alphanumerics to single spaces, for lenient
    phrase matching."""
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _present(page: dict[str, Any]) -> list[str]:
    return (page.get("image", {}) or {}).get("characters_present", []) or []


def _has_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    low = (text or "").lower()
    return any(k in low for k in keywords)


def _shout_tokens(text: str) -> list[str]:
    toks = [t for t in _SHOUT_RE.findall(text or "") if t not in _SHOUT_ALLOW]
    if (text or "").count("!!!"):
        toks.append("!!!")
    return toks


def check_voice(rep: Report, world: Any, story: Any) -> None:
    s = story.data
    where = f"{world.slug}/{story.slug}"
    pages = s.get("pages", []) or []
    roster = [c.get("slug") for c in s.get("characters", []) or []]

    book_norm = _norm(" ".join((p.get("text") or "") for p in pages))

    # 1) catchphrase silence (whole-book, per roster character). Matching is punctuation- and
    # case-insensitive so "BEAUTIFUL AND MINE!" matches "beautiful and mine".
    for slug in roster:
        ch = world.characters.get(slug)
        if not ch:
            continue
        phrases = [p for p in (ch.get("voice", {}) or {}).get("catchphrases", []) or [] if p.strip()]
        if phrases and not any(_norm(p) in book_norm for p in phrases if _norm(p)):
            rep.warn(f"{where}: '{slug}' declares a catchphrase ({phrases[0]!r}) but never says it "
                     "in this book")

    # 2 & 3) per-spread signals, only when the character is alone in frame
    for p in pages:
        if p.get("kind") in ("title",):
            continue
        present = _present(p)
        if len(present) != 1:
            continue
        slug = present[0]
        ch = world.characters.get(slug)
        if not ch:
            continue
        voice = ch.get("voice", {}) or {}
        text = p.get("text") or ""
        n = p.get("number")

        if _has_keyword(voice.get("speech_style", ""), _GENTLE):
            shouts = _shout_tokens(text)
            if shouts:
                rep.warn(f"{where} p{n}: '{slug}' has a gentle voice "
                         f"({voice.get('speech_style')!r}) but the text shouts ({shouts[0]})")

        if _has_keyword(voice.get("vocabulary_level", ""), _SIMPLE):
            advanced = sorted({w.lower() for w in words(text) if count_syllables(w) >= 4})
            if advanced:
                rep.warn(f"{where} p{n}: '{slug}' has a simple vocabulary "
                         f"({voice.get('vocabulary_level')!r}) but the text uses "
                         f"{', '.join(advanced[:3])}")
