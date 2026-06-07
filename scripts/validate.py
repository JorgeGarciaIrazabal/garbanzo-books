#!/usr/bin/env python3
"""QA gate: validate worlds/characters/stories against the JSON schemas AND the workspace
invariants (consistency, reading level, interactivity, accessibility, illustration).

Usage:
    uv run python scripts/validate.py                       # everything
    uv run python scripts/validate.py worlds/<world>        # one world + its content
    uv run python scripts/validate.py worlds/<world>/stories/<story>

Exit code 0 = all PASS, 1 = failures, 2 = setup error.

The individual invariants live as focused, independently-testable checkers under
``scripts/lib/checks/``. This file is the thin runner that composes them and prints
one report. ``Report``, ``INTERACTION_DATA_KEYS`` and ``PILLARS`` are re-exported here
for backwards compatibility with existing imports/tests.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.checks import (INTERACTION_DATA_KEYS, PILLARS, Report,  # noqa: E402,F401
                        check_accessibility, check_appearance_token,
                        check_character_tokens, check_color_consistency,
                        check_illustration, check_interactivity, check_publish_gate,
                        check_reading, check_relationships, check_render_readiness,
                        check_story_roster, check_voice, check_world_rules,
                        check_world_style, load_schema, schema_check)
from lib.model import (SCHEMAS, WORLDS, ContentError, Story,  # noqa: E402,F401
                       load_all_worlds, load_world)


def check_world(rep: Report, world) -> None:
    """Schema + identity/consistency invariants for a world and its characters."""
    schema_check(rep, world.data, "world.schema.json", f"world {world.slug}")
    for cslug, c in world.characters.items():
        schema_check(rep, c, "character.schema.json", f"character {world.slug}/{cslug}")
    check_world_style(rep, world)
    check_character_tokens(rep, world)
    check_relationships(rep, world)
    check_color_consistency(rep, world)
    check_appearance_token(rep, world)


def check_story(rep: Report, world, story) -> None:
    """All story-level invariants. Order matters: the publish gate runs LAST because it
    reads the failures accumulated by every checker above it."""
    schema_check(rep, story.data, "story.schema.json", f"story {world.slug}/{story.slug}")
    check_story_roster(rep, world, story)
    check_reading(rep, world, story)
    check_interactivity(rep, world, story)
    check_world_rules(rep, world, story)
    check_voice(rep, world, story)
    check_accessibility(rep, world, story)
    check_illustration(rep, world, story)
    check_render_readiness(rep, world, story)
    check_publish_gate(rep, world, story)


def discover(target: str | None, errors: list[str]):
    """Yield (world, story_or_None) to validate. Malformed files are recorded in `errors` (and
    reported as failures by main) rather than aborting the whole run."""
    if not target:
        for w in load_all_worlds(with_stories=True, errors=errors):
            yield w, None
            for st in w.stories:
                yield w, st
        return
    p = Path(target)
    parts = p.parts
    try:
        if "stories" in parts:
            world_slug = parts[parts.index("worlds") + 1] if "worlds" in parts else parts[0]
            story_slug = parts[parts.index("stories") + 1]
            w = load_world(world_slug)
            errors.extend(w.errors)
            story_obj: Story | None = next((s for s in w.stories if s.slug == story_slug), None)
            yield w, None
            if story_obj:
                yield w, story_obj
        else:
            world_slug = parts[parts.index("worlds") + 1] if "worlds" in parts else p.name
            w = load_world(world_slug)
            errors.extend(w.errors)
            yield w, None
            for st in w.stories:
                yield w, st
    except ContentError as e:
        errors.append(str(e))


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate worlds/stories.")
    ap.add_argument("target", nargs="?", help="path to a world or story (default: all)")
    args = ap.parse_args()

    if not WORLDS.is_dir() or not any(WORLDS.iterdir()):
        print("No worlds yet. Create one with: python scripts/new_world.py \"My World\"")
        return 0

    rep = Report()
    seen_worlds = set()
    content_errors: list[str] = []
    try:
        targets = list(discover(args.target, content_errors))
    except FileNotFoundError as e:
        print(f"! {e}", file=sys.stderr)
        return 2
    for em in content_errors:
        rep.fail(f"[content] malformed file skipped — {em}")
    for world, story in targets:
        if world.slug not in seen_worlds:
            check_world(rep, world)
            seen_worlds.add(world.slug)
        if story is not None:
            check_story(rep, world, story)

    print(f"\n{'='*60}\nVALIDATION REPORT\n{'='*60}")
    print(f"  checks passed: {rep.passes}")
    if rep.warns:
        print(f"\n  WARNINGS ({len(rep.warns)}):")
        for w in rep.warns:
            print(f"    ⚠  {w}")
    if rep.fails:
        print(f"\n  FAILURES ({len(rep.fails)}):")
        for f in rep.fails:
            print(f"    ✗  {f}")
        print("\n  => FAIL")
        return 1
    print("\n  => PASS ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
