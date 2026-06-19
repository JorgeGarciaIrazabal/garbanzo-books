#!/usr/bin/env python3
"""Scaffold a new character bible: worlds/<world>/characters/<slug>.yaml

Usage:
    uv run python scripts/new_character.py magical-forest "Pip the Fairy"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.model import WORLDS, dump_yaml, slugify  # noqa: E402


def starter(slug: str, world: str, name: str) -> dict:
    return {
        "slug": slug,
        "world": world,
        "name": name,
        "role": "protagonist",
        "species": "TODO",
        "pronouns": "she/her",
        "one_liner": "TODO: who they are in a sentence.",
        "personality": {
            "traits": ["curious", "kind"],
            "motivation": "TODO: what they want most.",
            "fears": ["TODO"],
            "flaws": ["TODO: the growth edge that drives arcs"],
            "strengths": ["TODO"],
            "quirks": ["TODO"],
            "values": ["friendship"],
        },
        "voice": {
            "speech_style": "warm, simple, lots of questions",
            "catchphrases": [],
            "vocabulary_level": "age-appropriate, concrete",
        },
        "appearance": {
            "age_appearance": "TODO",
            "build": "TODO",
            "height": "TODO (relative scale matters)",
            "skin": "TODO",
            "hair": "TODO",
            "eyes": "TODO",
            "outfit": "TODO: signature outfit",
            "distinguishing_features": [
                "TODO: unmistakable feature 1",
                "TODO: unmistakable feature 2",
            ],
            "color_palette": [
                {"part": "TODO", "hex": "#000000"},
            ],
            "silhouette_notes": "TODO: recognisable in pure outline; distinct from castmates.",
        },
        "appearance_token": (
            f"{name.split()[0].upper()}: TODO dense descriptor — species/age/build, hair+hex, "
            "eyes+hex, signature outfit+hexes, 2-4 distinguishing features, default expression"
        ),
        "reference_images": [],
        "seed": 1234,
        "relationships": [],
        "evolution": [
            {
                "stage": "base",
                "order": 0,
                "summary": "Starting state.",
                "personality_delta": "",
                "appearance_delta": "",
                "unlocked_by": "",
            }
        ],
        "tags": [],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Scaffold a new character.")
    ap.add_argument("world", help="world slug")
    ap.add_argument("name", help="character name")
    ap.add_argument("--slug", help="override the slug")
    args = ap.parse_args()

    wdir = WORLDS / args.world
    if not (wdir / "world.yaml").exists():
        print(f"! no world '{args.world}'. Run new_world.py first.", file=sys.stderr)
        return 1

    slug = args.slug or slugify(args.name)
    cpath = wdir / "characters" / f"{slug}.yaml"
    if cpath.exists():
        print(f"! character '{slug}' already exists at {cpath}", file=sys.stderr)
        return 1

    dump_yaml(starter(slug, args.world, args.name), cpath)
    print(f"+ created character '{slug}' at {cpath}")
    print("  next: fill personality + appearance_token, then /illustrate --character "
          f"{args.world}/{slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
