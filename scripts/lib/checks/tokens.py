"""The ``appearance_token`` contract — beyond "is a non-empty string".

The token is the #1 visual-consistency lever (it's injected verbatim into every
image prompt featuring the character), so a weak one quietly degrades every render.
A strong token is concrete: it names colours (hexes) and is long enough to pin
build/outfit/features. Failures here are advisory (warn): they don't block a draft,
but they tell the author the lever isn't pulling its weight.
"""
from __future__ import annotations

from typing import Any

from ..colors import hexes_in_text
from .report import Report

# A serviceable token ("NAME: a small fox, red coat (#c0392b), yellow boots (#f1c40f)…")
# is comfortably longer than this; much shorter means it can't be carrying enough detail.
MIN_TOKEN_CHARS = 40
PLACEHOLDER_MARKERS = ("todo", "tbd", "lorem ipsum", "fixme", "xxx", "placeholder")


def check_appearance_token(rep: Report, world: Any) -> None:
    for cslug, c in world.characters.items():
        token = (c.get("appearance_token") or "").strip()
        if not token:
            continue  # absence is a hard fail handled by the consistency check
        low = token.lower()
        marker = next((m for m in PLACEHOLDER_MARKERS if m in low), None)
        if marker:
            rep.warn(f"{world.slug}/{cslug}: appearance_token contains placeholder text '{marker}'")
        if len(token) < MIN_TOKEN_CHARS:
            rep.warn(f"{world.slug}/{cslug}: appearance_token is very short "
                     f"({len(token)} chars) — add build/outfit/feature detail so it locks the look")
        if not hexes_in_text(token):
            rep.warn(f"{world.slug}/{cslug}: appearance_token names no hex colours — "
                     "add the locked colours so renders stay on-palette")
