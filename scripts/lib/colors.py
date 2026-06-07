"""Hex-colour helpers shared across prompt assembly, the site build, image
placeholders, and the consistency checks.

Before this module the same "pull #rrggbb out of a palette" logic was copy-pasted
in generate_images.py and build_site.py with subtly different fallbacks; centralising
it keeps the world palette rendered identically everywhere.
"""
from __future__ import annotations

import re
from typing import Any

_HEX6 = re.compile(r"#?([0-9a-fA-F]{6})\b")

# Used only when a world somehow has no palette (keeps placeholders/site from going blank).
DEFAULT_PALETTE = ["#f4e1c1", "#6b8f71", "#d98a5b", "#3d5a73"]


def norm_hex(value: Any) -> str | None:
    """Return a normalised ``#rrggbb`` (lower-case) for a 6-digit hex, else None."""
    if not value:
        return None
    h = str(value).strip().lstrip("#")
    if len(h) == 6 and all(c in "0123456789abcdefABCDEF" for c in h):
        return "#" + h.lower()
    return None


def palette_hexes(art_style: dict[str, Any] | None, *, fallback: bool = False) -> list[str]:
    """The world master palette as a list of ``#rrggbb`` strings (order preserved).

    ``fallback=True`` returns DEFAULT_PALETTE when the world has none, for renderers
    (placeholders, swatches) that must always draw *something*.
    """
    out: list[str] = []
    for swatch in (art_style or {}).get("palette", []) or []:
        h = norm_hex(swatch.get("hex"))
        if h:
            out.append(h)
    if not out and fallback:
        return list(DEFAULT_PALETTE)
    return out


def hexes_in_text(text: str | None) -> set[str]:
    """Every ``#rrggbb`` mentioned in a free-text string (e.g. an appearance_token),
    normalised to lower-case ``#rrggbb``."""
    return {"#" + m.lower() for m in _HEX6.findall(text or "")}


def character_hexes(character: dict[str, Any]) -> set[str]:
    """All locked per-part hexes declared in a character's ``appearance.color_palette``."""
    out: set[str] = set()
    for cp in (character.get("appearance", {}) or {}).get("color_palette", []) or []:
        h = norm_hex(cp.get("hex"))
        if h:
            out.add(h)
    return out
