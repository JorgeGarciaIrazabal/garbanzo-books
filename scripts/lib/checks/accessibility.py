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
    for p in s.get("pages", []) or []:
        n = p.get("number")
        img = p.get("image", {}) or {}
        if not img.get("alt"):
            rep.warn(f"{where} p{n}: image has no alt text")
        if p.get("kind") not in ("title",) and not p.get("layout"):
            rep.warn(f"{where} p{n}: no layout (text placement) set")
