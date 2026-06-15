"""Self-describing SVG placeholder art — the offline fallback for image generation.

When no provider key is set (or the user explicitly picks ``placeholder``), we still emit a
frame so the whole pipeline runs/validates/builds: palette bands + the assembled prompt text
+ characters + seed, with the text zone marked. Never a network call.
"""
from __future__ import annotations

import html
import textwrap
from pathlib import Path

from .colors import palette_hexes
from .model import World
from .prompt_assembly import AssembledPrompt

PLACEHOLDER_W, PLACEHOLDER_H = 1024, 768


def _palette_hexes(world: World) -> list[str]:
    """The world palette as ``#rrggbb`` strings, with a sensible fallback so a
    placeholder still draws colour bands. Thin wrapper over the shared helper."""
    return palette_hexes(world.data.get("art_style"), fallback=True)


def write_placeholder_svg(path: Path, title: str, ap: AssembledPrompt, world: World) -> None:
    """A self-describing placeholder: palette bands + the assembled prompt text + seed."""
    pal = _palette_hexes(world)
    bands = ""
    bw = PLACEHOLDER_W / max(1, len(pal))
    for i, c in enumerate(pal):
        bands += f'<rect x="{i*bw:.0f}" y="0" width="{bw:.0f}" height="{PLACEHOLDER_H}" fill="{c}"/>'
    wrapped = textwrap.wrap(ap.prompt, width=64)[:14]
    lines = ""
    for i, ln in enumerate(wrapped):
        lines += f'<tspan x="48" dy="{0 if i==0 else 26}">{html.escape(ln)}</tspan>'
    chars = ", ".join(ap.characters) or "—"
    path.parent.mkdir(parents=True, exist_ok=True)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{PLACEHOLDER_W}" height="{PLACEHOLDER_H}" viewBox="0 0 {PLACEHOLDER_W} {PLACEHOLDER_H}">
  {bands}
  <rect x="32" y="120" width="{PLACEHOLDER_W-64}" height="{PLACEHOLDER_H-220}" rx="24" fill="#fffdf7" opacity="0.92"/>
  <text x="48" y="80" font-family="Georgia, serif" font-size="40" fill="#2d2a26">{html.escape(title)}</text>
  <text x="48" y="108" font-family="monospace" font-size="18" fill="#5b554d">PLACEHOLDER · characters: {html.escape(chars)} · seed: {ap.seed}</text>
  <text x="48" y="170" font-family="monospace" font-size="18" fill="#3a352f">{lines}</text>
  <rect x="0" y="{PLACEHOLDER_H-70}" width="{PLACEHOLDER_W}" height="70" fill="#2d2a26" opacity="0.08"/>
  <text x="48" y="{PLACEHOLDER_H-28}" font-family="sans-serif" font-size="20" fill="#2d2a26" opacity="0.6">text zone reserved here</text>
</svg>"""
    path.write_text(svg, encoding="utf-8")
