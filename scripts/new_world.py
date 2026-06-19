#!/usr/bin/env python3
"""Scaffold a new world: worlds/<slug>/world.yaml + style-guide.md + dirs.

Usage:
    uv run python scripts/new_world.py "The Whispering Woods" [--year 5 --year 6 --year 7]

Creates a schema-valid starter you then flesh out (see the world-building skill).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.model import WORLDS, dump_yaml, slugify  # noqa: E402
from lib.readability import band_for_year  # noqa: E402


def starter(slug: str, title: str, years: list[int]) -> dict:
    return {
        "slug": slug,
        "title": title,
        "tagline": "TODO: one memorable sentence that sells this world.",
        "premise": "TODO: 2-4 sentences — the central idea and the kind of stories it produces.",
        "tone": ["cozy", "whimsical"],
        "genres": ["adventure"],
        # Reader AGES are the audience knob; the coarse bands are derived for back-compat/display.
        "target_years": years,
        "target_age_bands": sorted({band_for_year(y) for y in years}),
        "languages": ["en"],
        "geography": {
            "overview": "TODO: the shape of the world.",
            "locations": [
                {"name": "TODO Place", "description": "TODO", "mood": "warm", "recurring": True}
            ],
        },
        "rules": ["TODO: an inviolable law of this world (and its limits)."],
        "factions": [],
        "timeline": [],
        "motifs": ["TODO: a recurring symbol/refrain"],
        "themes": ["friendship", "courage"],
        "art_style": {
            "medium": "soft watercolor with colored-pencil texture",
            "line_quality": "gentle, rounded, hand-drawn",
            "shading": "soft, low-contrast",
            "lighting": "warm, gentle rim light",
            "perspective": "eye-level, character-centered",
            "palette": [
                {"name": "cream", "hex": "#f4e1c1", "role": "background"},
                {"name": "sage", "hex": "#6b8f71", "role": "primary"},
                {"name": "terracotta", "hex": "#d98a5b", "role": "accent"},
                {"name": "dusk-blue", "hex": "#3d5a73", "role": "shadow"},
            ],
            "influences": [],
            "prompt_style_block": (
                "soft watercolor children's book illustration, warm muted palette, rounded "
                "friendly shapes, gentle rim lighting, hand-painted paper texture, cozy "
                "storybook mood, no text"
            ),
            "negative_prompt": (
                "photorealism, harsh shadows, scary or distorted faces, extra fingers, "
                "text artifacts, watermark, cluttered composition"
            ),
            "aspect_ratio": "4:3",
            "text_treatment": {
                "placement": "lower-third",
                "scrim": "soft cream rounded panel at 85% opacity",
                "font_family": "Andika",
                "dyslexia_friendly": True,
            },
        },
        "tags": [],
    }


STYLE_GUIDE = """# {title} — Style Guide

> The locked visual identity for this world. Every illustration is assembled from the
> `art_style` block in `world.yaml`; this doc is the human-readable art direction.

## Palette
| Swatch | Hex | Role |
|---|---|---|
{palette_rows}

## Look & feel
- **Medium:** soft watercolor with colored-pencil texture
- **Line:** gentle, rounded, hand-drawn
- **Lighting:** warm, gentle rim light
- **Mood:** cozy, reassuring, wonder-filled

## Do
- Keep characters on-model (use the appearance tokens + reference sheets).
- Reserve the lower third of each page as calm negative space for text.
- Stay within the palette above.

## Don't
- No photorealism, harsh shadows, or scary faces.
- No text baked into the art (text is overlaid by the reader).
- Don't break the world's `rules` (see world.yaml).
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Scaffold a new world.")
    ap.add_argument("title")
    ap.add_argument("--year", action="append", dest="years", type=int, default=[],
                    metavar="N", help="target reader AGE in years (repeatable), e.g. --year 5 "
                                      "--year 6 --year 7. Default 6.")
    ap.add_argument("--slug", help="override the slug")
    args = ap.parse_args()

    if any(not (1 <= y <= 18) for y in args.years):
        print("! each --year must be 1-18", file=sys.stderr)
        return 1

    slug = args.slug or slugify(args.title)
    wdir = WORLDS / slug
    if (wdir / "world.yaml").exists():
        print(f"! world '{slug}' already exists at {wdir}", file=sys.stderr)
        return 1

    years = sorted(set(args.years)) or [6]
    data = starter(slug, args.title, years)
    dump_yaml(data, wdir / "world.yaml")
    (wdir / "characters").mkdir(parents=True, exist_ok=True)
    (wdir / "stories").mkdir(parents=True, exist_ok=True)
    (wdir / "assets").mkdir(parents=True, exist_ok=True)

    rows = "\n".join(
        f"| {s['name']} | `{s['hex']}` | {s['role']} |" for s in data["art_style"]["palette"]
    )
    (wdir / "style-guide.md").write_text(
        STYLE_GUIDE.format(title=args.title, palette_rows=rows), encoding="utf-8"
    )

    print(f"+ created world '{slug}' at {wdir}")
    print("  next: edit world.yaml (premise, rules, palette, prompt_style_block), then /new-character")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
