"""Colour consistency: every hex named inside a character's ``appearance_token``
(the string injected into every image prompt) should also be a locked colour in
that character's ``appearance.color_palette``.

This catches the most common silent drift — the token says the coat is ``#c0392b``
but the palette (and therefore the model sheet / reviewer's eye) says ``#b03a2e``.
The two are independent sources of truth; if they disagree, renders go off-model.
Advisory (warn), because a token may legitimately mention a world/background colour
that isn't a character part — but it's exactly the thing a human should eyeball.
"""
from __future__ import annotations

from typing import Any

from ..colors import character_hexes, hexes_in_text
from .report import Report


def check_color_consistency(rep: Report, world: Any) -> None:
    for cslug, c in world.characters.items():
        token = c.get("appearance_token") or ""
        token_hexes = hexes_in_text(token)
        if not token_hexes:
            continue
        palette = character_hexes(c)
        orphan = sorted(token_hexes - palette)
        if orphan:
            rep.warn(f"{world.slug}/{cslug}: appearance_token hex {', '.join(orphan)} "
                     "not in appearance.color_palette (possible colour drift)")
        else:
            rep.ok(f"colour consistency {cslug}")
