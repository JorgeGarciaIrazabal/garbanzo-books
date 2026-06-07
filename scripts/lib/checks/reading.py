"""Reading-level invariants: whole-book Flesch-Kincaid grade against the target
(only where the formula is reliable, i.e. 5-7 and up) and per-page word caps.

Mirrors the deeper analysis in ``scripts/reading_level.py`` but as a pass/fail gate
for the validator. See ``methodology/reading-pedagogy.md`` for why FKGL is skipped
on the read-aloud bands.
"""
from __future__ import annotations

from typing import Any

from ..readability import BANDS, analyze, words
from .report import Report


def check_reading(rep: Report, world: Any, story: Any) -> None:
    s = story.data
    where = f"{world.slug}/{story.slug}"
    band_id = s.get("age_band", "5-7")
    band = BANDS.get(band_id, BANDS["5-7"])
    rl = s.get("reading_level", {}) or {}
    pages = s.get("pages", []) or []

    text = " ".join((p.get("text") or "") for p in pages)
    m = analyze(text)
    target = rl.get("target_fk_grade", band.get("fk_grade"))
    tol = rl.get("fk_grade_tolerance", 1.0)
    max_wpp = rl.get("max_words_per_page", band["max_words_per_page"])

    if band.get("fk_grade") is not None and target is not None:
        if m.fk_grade > target + tol:
            rep.fail(f"[reading] {where}: FK grade {m.fk_grade} > target {target}+{tol}")
        else:
            rep.ok(f"reading level {where}")

    over = [p.get("number") for p in pages
            if p.get("kind") not in ("title", "interaction")
            and len(words(p.get("text") or "")) > max_wpp]
    if over:
        rep.fail(f"[reading] {where}: pages over {max_wpp}-word cap: {over}")

    if rl.get("decodable") and not (rl.get("decoding_focus") or "").strip():
        rep.warn(f"{where}: reading_level.decodable is true but decoding_focus is empty — "
                 "name the phonics patterns + sight words so decodability can be checked")
