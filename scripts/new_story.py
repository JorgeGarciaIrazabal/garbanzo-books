#!/usr/bin/env python3
"""Scaffold a new story: worlds/<world>/stories/<slug>/story.yaml + images/ dir.

Usage:
    uv run python scripts/new_story.py whispering-woods "Pip and the Lost Star" --age 5-7
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.model import WORLDS, dump_yaml, slugify  # noqa: E402
from lib.readability import BANDS  # noqa: E402

# Sensible default FK targets per band (None bands use a soft early-reader target).
# Deliberately NOT aggressive: FK rewards short sentences, and an over-tight target
# trains writers to chop prose into telegraphic fragments. The band caps + the
# anti-telegraphic floor in lib/readability.py do the real guarding.
DEFAULT_FK = {"0-3": 0.5, "3-5": 0.8, "5-7": 1.5, "7-9": 3.0, "9-12": 5.5}


def starter(slug: str, world: str, title: str, age: str) -> dict:
    band = BANDS.get(age, BANDS["5-7"])
    return {
        "slug": slug,
        "world": world,
        "title": title,
        "logline": "TODO: protagonist + goal + obstacle, in one sentence.",
        "summary": "TODO",
        "age_band": age,
        "reading_level": {
            "target_fk_grade": DEFAULT_FK.get(age, 1.5),
            # Wide on purpose: FKGL is noisy on picture-book-sized text, and a tight
            # tolerance pressures writers into chopping prose to make the number move.
            "fk_grade_tolerance": 1.5,
            "lexile_range": "",
            "fountas_pinnell": "",
            "max_words_per_page": band["max_words_per_page"],
            "max_sentence_words": band["max_sentence_words"],
            "decoding_focus": "",
            "decodable": False,
        },
        "themes": ["friendship"],
        "moral": "TODO: shown, not told.",
        "characters": [
            {"slug": "TODO-character-slug", "stage": "base", "role_in_story": "protagonist"}
        ],
        "spine": {
            "once_upon_a_time": "TODO",
            "every_day": "TODO",
            "until_one_day": "TODO",
            "because_of_that": ["TODO", "TODO"],
            "until_finally": "TODO",
            "ever_since_then": "TODO",
        },
        "pages": [
            {
                "number": 0,
                "kind": "title",
                "text": title,
                "image": {
                    "prompt": "TODO: a warm establishing scene for the cover/title.",
                    "characters_present": [],
                    "alt": "TODO",
                    "text_zone": "center",
                },
                "layout": {"text_position": "center", "text_align": "center", "scrim": True},
            },
            {
                "number": 1,
                "kind": "story",
                "text": "TODO: page text within the word cap.",
                "image": {
                    "prompt": "TODO: scene only — who/where/action/emotion.",
                    "characters_present": [],
                    "alt": "TODO",
                    "text_zone": "lower third",
                },
                "layout": {"text_position": "lower-third", "text_align": "center", "scrim": True},
                "vocabulary": [],
            },
        ],
        "interactions_summary": [],
        "status": "draft",
        "tags": [],
        "cover": {"image": "", "image_prompt": "", "alt": ""},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Scaffold a new story.")
    ap.add_argument("world", help="world slug")
    ap.add_argument("title", help="story title")
    ap.add_argument("--age", default="5-7", choices=list(BANDS), help="target age band")
    ap.add_argument("--slug", help="override the slug")
    args = ap.parse_args()

    wdir = WORLDS / args.world
    if not (wdir / "world.yaml").exists():
        print(f"! no world '{args.world}'. Run new_world.py first.", file=sys.stderr)
        return 1

    slug = args.slug or slugify(args.title)
    sdir = wdir / "stories" / slug
    if (sdir / "story.yaml").exists():
        print(f"! story '{slug}' already exists at {sdir}", file=sys.stderr)
        return 1

    dump_yaml(starter(slug, args.world, args.title, args.age), sdir / "story.yaml")
    (sdir / "images").mkdir(parents=True, exist_ok=True)
    print(f"+ created story '{slug}' ({args.age}) at {sdir}")
    print("  next: write the spine + pages (story-craft), then reading-level-adaptation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
