"""Illustration invariants: declared image files exist on disk, and recurring
characters are *ready* to render on-model (a stable seed + at least one reference
image) before illustration — so visual consistency is provable, not hoped-for (A4).

The hard gate is file existence (a published book with a dangling image path is
broken). Render-readiness is advisory: the placeholder pipeline works without it,
but a recurring character with no seed/reference will drift between spreads.
"""
from __future__ import annotations

from typing import Any

from .report import Report


def check_illustration(rep: Report, world: Any, story: Any) -> None:
    s = story.data
    where = f"{world.slug}/{story.slug}"
    pages = s.get("pages", []) or []

    for p in pages:
        n = p.get("number")
        img = p.get("image", {}) or {}
        if not img.get("file"):
            rep.warn(f"{where} p{n}: no image file yet (run /illustrate)")
        elif not (story.dir / img["file"]).exists():
            rep.fail(f"[illustration] {where} p{n}: image file '{img['file']}' not found")


def check_render_readiness(rep: Report, world: Any, story: Any) -> None:
    """Advisory: every character that appears in 2+ spreads should have a locked seed
    and a reference image so renders stay on-model (A4)."""
    s = story.data
    where = f"{world.slug}/{story.slug}"
    appear: dict[str, int] = {}
    for p in s.get("pages", []) or []:
        for slug in (p.get("image", {}) or {}).get("characters_present", []) or []:
            appear[slug] = appear.get(slug, 0) + 1

    for slug, count in appear.items():
        if count < 2:
            continue  # one-off cameo: drift between spreads isn't a concern
        ch = world.characters.get(slug)
        if not ch:
            continue  # missing-character is a hard fail elsewhere
        if not ch.get("reference_images"):
            rep.warn(f"{where}: recurring character '{slug}' has no reference_images — "
                     "illustrate a model sheet first (/illustrate --character) to anchor renders")
        if ch.get("seed") is None:
            rep.warn(f"{where}: recurring character '{slug}' has no locked seed — "
                     "set one so renders are reproducible")
