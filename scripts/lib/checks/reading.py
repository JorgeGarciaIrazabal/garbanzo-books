"""Reading-level signals — ADVISORY ONLY.

Reading level is a creative judgement, not a contract. This checker NEVER blocks a
publish: it surfaces gentle, per-year signals (a page running denser than typical for
the age, FK drifting well past the age window) as WARNINGS the author weighs against
the one test that actually matters — reading it aloud. The concrete per-year anchors
live in ``scripts/lib/readability.py``; the craft guidance lives in
``methodology/reading-pedagogy.md``. Nothing here is a hard rule. See also the deeper,
human-run report in ``scripts/reading_level.py``.
"""
from __future__ import annotations

from typing import Any

from ..readability import analyze, story_targets, words
from .report import Report


def check_reading(rep: Report, world: Any, story: Any) -> None:
    s = story.data
    where = f"{world.slug}/{story.slug}"
    t = story_targets(s)
    rl = s.get("reading_level", {}) or {}
    pages = s.get("pages", []) or []

    text = " ".join((p.get("text") or "") for p in pages)
    m = analyze(text)
    target = t["fk_target"]
    tol = t["fk_tol"]
    max_wpp = t["max_words_per_page"]

    # FK drift is only worth a nudge well past the age window, and only where the formula
    # carries any signal (~age 7+). Even then it's advisory — FKGL is blind to fun, voice,
    # and read-aloud rhythm. Never a blocker.
    if target is not None and t["fk_enforced"] and m.fk_grade > target + tol:
        rep.warn(f"{where}: FK grade {m.fk_grade} reads older than ~age target ({target}±{tol}). "
                 "Only act if it also reads dense aloud — never sand a joke to move the number.")

    # A page running well over the typical words-per-page for the age is a layout/pacing
    # nudge (will it fit on the page with the art?), not a violation.
    over = [p.get("number") for p in pages
            if p.get("kind") not in ("title", "interaction")
            and len(words(p.get("text") or "")) > max_wpp]
    if over:
        rep.warn(f"{where}: pages denser than typical (~{max_wpp} words) for the age: {over}. "
                 "Fine if the read-aloud sings — just check it fits the page with the picture.")

    if rl.get("decodable") and not (rl.get("decoding_focus") or "").strip():
        rep.warn(f"{where}: reading_level.decodable is true but decoding_focus is empty — "
                 "name the phonics patterns + sight words so decodability can be checked")
