"""Interactivity invariants: each beat is a known type with the right ``data``
payload, branching ``choice`` targets resolve to real pages, the book spreads its
beats across reading pillars, and skill-practice beats give the child feedback.

See ``methodology/interactivity.md`` for the type catalogue and age-band fit.
"""
from __future__ import annotations

from typing import Any

from .report import Report

# Allowed interaction types and the keys their `data` payload should carry.
INTERACTION_DATA_KEYS: dict[str, list[str]] = {
    "seek-and-find": ["items"],
    "spot-the-difference": ["count"],
    "counting": ["answer"],
    "rhyme-complete": ["answer"],
    "word-match": ["pairs"],
    "sound-hunt": ["sound", "words"],
    "riddle": ["answer"],
    "comprehension-question": ["question"],
    "choice": ["options"],
    "maze": [],
    "trace-letter": ["letter"],
    "memory": [],
    "drag-order": ["sequence"],
    "tap-to-reveal": [],
    "coloring": [],
    "sorting": ["bins", "items"],
    "pattern": ["answer"],
    "odd-one-out": ["answer", "items"],
    "melody": ["notes"],
}
PILLARS = {"phonemic-awareness", "phonics", "fluency", "vocabulary", "comprehension"}

# Beats that practise a discrete skill (vs. pure discovery like seek-and-find) read as
# flat without an encouraging response — feedback.correct / feedback.try_again.
SKILL_PRACTICE_TYPES = {
    "rhyme-complete", "comprehension-question", "maze", "choice", "sorting", "pattern",
    "word-match", "riddle", "odd-one-out", "counting",
}


def check_interactivity(rep: Report, world: Any, story: Any) -> None:
    s = story.data
    where = f"{world.slug}/{story.slug}"
    pages = s.get("pages", []) or []
    page_nums = {p.get("number") for p in pages}

    pillars_seen: set[str] = set()
    has_interaction = False
    for p in pages:
        it = p.get("interaction")
        if not it:
            continue
        has_interaction = True
        t = it.get("type")
        need = INTERACTION_DATA_KEYS.get(t)
        if need is None:
            rep.fail(f"[interaction] {where} p{p.get('number')}: unknown type '{t}'")
            continue
        data = it.get("data", {}) or {}
        missing = [k for k in need if k not in data]
        if missing:
            rep.fail(f"[interaction] {where} p{p.get('number')} ({t}): data missing {missing}")
        if it.get("skill") in PILLARS:
            pillars_seen.add(it.get("skill"))
        if t in SKILL_PRACTICE_TYPES and not (it.get("feedback") or {}):
            rep.warn(f"{where} p{p.get('number')}: {t} has no feedback (correct/try_again) — "
                     "add encouragement so the beat lands")
        if t == "choice":
            for opt in data.get("options", []) or []:
                if opt.get("goto") not in page_nums:
                    rep.fail(f"[interaction] {where} p{p.get('number')}: choice goto "
                             f"{opt.get('goto')} is not a real page")
    if has_interaction:
        rep.ok(f"interactions {where}")
        if len(pillars_seen) < 3:
            rep.warn(f"{where}: interactions cover only {len(pillars_seen)} reading pillar(s) (<3)")
    else:
        rep.warn(f"{where}: no interactions yet")
