#!/usr/bin/env python3
"""Scaffold a new story: worlds/<world>/stories/<slug>/story.yaml + images/ dir.

Usage:
    uv run python scripts/new_story.py magical-forest "Pip and the Hidden Honey" --year 6
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.model import WORLDS, dump_yaml, slugify  # noqa: E402
from lib.readability import (  # noqa: E402
    band_for_year, default_read_mode, normalize_read_mode, story_targets,
    adult_threshold_label, read_mode_default_label, valid_cli_year, year_range_label,
)

DEFAULT_YEAR = 6  # a safe early-reader when no --year is given


def _story_page_stub(number: int) -> dict:
    return {
        "number": number,
        "kind": "story",
        "text": "TODO: page text within the word cap.",
        "image": {
            "prompt": "TODO: scene only — who/where/action/emotion.",
            "characters_present": [],
            "alt": "TODO",
        },
        "layout": {"text_position": "lower-third", "text_align": "center", "scrim": True},
        # NOTE: no `vocabulary` field on purpose. It used to seed an empty list per page,
        # which trained authors to pre-pick "target words" and then write fancy prose to
        # contain them — the opposite of fun-first. The field still exists in the schema as
        # an OPTIONAL, passive glossary byproduct, but it is never an authoring target.
        # NOTE: no `image.text_zone` — layout.text_position is the single source of truth
        # for where text sits; the image generator derives the calm zone from it.
    }


def starter(slug: str, world: str, title: str, band_id: str, year: int,
            read_mode: str, n_pages: int = 1) -> dict:
    # Reading targets are selected by AGE (the per-year curve) AND read mode (read-aloud vs solo
    # decoder), with the band as the 'grown-up' authority. These are ADVISORY anchors the author
    # writes toward — not gates; the validator only WARNs on drift. See methodology/reading-pedagogy.md.
    t = story_targets({"age_band": band_id, "target_year": year, "reading_level": {"read_mode": read_mode}})
    return {
        "slug": slug,
        "world": world,
        "title": title,
        "logline": "TODO: protagonist + goal + obstacle, in one sentence.",
        "summary": "TODO",
        "age_band": band_id,
        "target_year": year,
        "reading_level": {
            "read_mode": t["read_mode"],
            "target_fk_grade": t["fk_target"] if t["fk_target"] is not None else 0.5,
            "fk_grade_tolerance": t["fk_tol"],
            "lexile_range": "",
            "fountas_pinnell": "",
            "max_words_per_page": t["max_words_per_page"],
            "max_sentence_words": t["max_sentence_words"],
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
                },
                "layout": {"text_position": "center", "text_align": "center", "scrim": True},
            },
            *[_story_page_stub(n) for n in range(1, max(1, n_pages) + 1)],
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
    ap.add_argument("--year", type=int, default=DEFAULT_YEAR, metavar="N",
                    help="the reader's AGE in years (" + year_range_label() + ") — the single age knob for the book. "
                         "Sets target_year and derives the advisory reading anchors from the "
                         f"per-year curve. {adult_threshold_label()} = adult reader. Default {DEFAULT_YEAR}.")
    ap.add_argument("--read-mode", choices=["read_aloud", "solo"], default=None, dest="read_mode",
                    help="WHO reads the words: 'read_aloud' (a grown-up voices it — rich words "
                         "welcome) or 'solo' (the child decodes every word — lean decodable, "
                         "tighter word cap). Set it for ages ~4-8 where it's ambiguous (e.g. a "
                         "5-year-old solo reader). Default: " + read_mode_default_label() + ".")
    ap.add_argument("--slug", help="override the slug")
    ap.add_argument("--pages", type=int, default=1, metavar="N",
                    help="scaffold N story-page stubs (plus the title page) so the author "
                         "only fills in text + scene prompts instead of generating all the "
                         "page boilerplate — e.g. --pages 14 for a standard picture book")
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

    if not valid_cli_year(args.year):
        print(f"! --year must be {year_range_label()} (got {args.year})", file=sys.stderr)
        return 1
    # Year is the single knob; the legacy age_band is derived from it (display/back-compat).
    year = args.year
    band_id = band_for_year(year)
    # Read mode: explicit if given, else the age default (read-aloud for the youngest, solo later).
    read_mode = normalize_read_mode(args.read_mode, year) if args.read_mode else default_read_mode(year)

    data = starter(slug, args.world, args.title, band_id, year, read_mode, n_pages=args.pages)
    dump_yaml(data, sdir / "story.yaml")
    (sdir / "images").mkdir(parents=True, exist_ok=True)
    print(f"+ created story '{slug}' (age {year}, {read_mode.replace('_', '-')}) at {sdir}")
    print("  next: write the spine + pages (story-craft), then reading-level-adaptation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
