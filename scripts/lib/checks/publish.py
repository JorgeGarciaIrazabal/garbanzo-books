"""The publish gate — the last thing run for a story.

A book marked ``published`` must be whole: no outstanding failures *of its own*, and
(ideally) a cover image to represent it. This is what stops a half-broken book from
going live.

Two subtleties:

* It scopes "has failures above" to *this* story's findings (messages carry a
  ``world/story`` or ``world <slug>`` tag), so one broken book can't make a sibling
  published book look broken — the runner shares a single Report across the library.
* A missing cover is a **warning**, not a blocker: it's a presentation nicety, not a
  correctness/consistency invariant, so it shouldn't hard-block an otherwise-whole book.
"""
from __future__ import annotations

from typing import Any

from .report import Report


def _belongs_to(msg: str, world_slug: str, story_slug: str) -> bool:
    return f"{world_slug}/{story_slug}" in msg or f"world {world_slug}" in msg


def check_publish_gate(rep: Report, world: Any, story: Any) -> None:
    s = story.data
    where = f"{world.slug}/{story.slug}"
    if s.get("status") != "published":
        return
    if not (s.get("cover", {}) or {}).get("image"):
        rep.warn(f"{where}: published but has no cover image — add cover.image for the library")
    own_failures = [f for f in rep.fails if _belongs_to(f, world.slug, story.slug)]
    if own_failures:
        rep.fail(f"[publish] {where}: marked published but has failures above")
