"""Accessibility / layout invariants per page: alt text on every image and a
declared text-placement layout so words stay legible over art.

See ``methodology/accessibility.md``. These are warnings (a draft can still build),
but they should all be cleared before a book is reviewed.
"""
from __future__ import annotations

from typing import Any

from .report import Report


def check_accessibility(rep: Report, world: Any, story: Any) -> None:
    s = story.data
    where = f"{world.slug}/{story.slug}"
    positions: dict[str, int] = {}
    for p in s.get("pages", []) or []:
        n = p.get("number")
        img = p.get("image", {}) or {}
        if not img.get("alt"):
            rep.warn(f"{where} p{n}: image has no alt text")
        if p.get("kind") not in ("title",) and not p.get("layout"):
            rep.warn(f"{where} p{n}: no layout (text placement) set")
        lay = p.get("layout") or {}
        pos = lay.get("text_position")
        if pos and p.get("kind") not in ("title",):
            positions[pos] = positions.get(pos, 0) + 1
    # Nudge authors to vary text placement for visual rhythm — a book where every
    # page's text sits in the same spot reads as a flat wall. The page-layout skill
    # calls for varying placement; this surfaces it as a review-time warning.
    story_pages = sum(1 for p in s.get("pages", []) or [] if p.get("kind") not in ("title",))
    if story_pages >= 6 and len(positions) == 1:
        only = next(iter(positions))
        rep.warn(f"{where}: every story page uses text_position '{only}' — "
                 f"vary placement (top/center/lower-third/left/right) for rhythm")
