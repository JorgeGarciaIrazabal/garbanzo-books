#!/usr/bin/env python3
"""Flip a story between draft and published — with the publish gate built in.

Usage:
    uv run python scripts/publish_story.py <world>/<story>            # publish
    uv run python scripts/publish_story.py <world>/<story> --draft    # back to draft

Publishing runs the FULL validator over the story's world with the new status applied
in memory first; if any failure touches this story (or its world/characters), nothing
is written and the command fails. That makes "mark it published" and "it passed the
publish gate" the same action — a broken book can't be flipped by accident.
Unpublishing (--draft) never needs a gate.

Exit code 0 = status changed (or already there), 1 = blocked by the gate, 2 = bad target.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.checks import Report  # noqa: E402
from lib.model import ContentError, dump_yaml, load_world  # noqa: E402
from validate import check_story, check_world  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish or unpublish one story (with the QA gate).")
    ap.add_argument("target", help="<world>/<story>, or a path to the story dir / story.yaml")
    ap.add_argument("--draft", action="store_true", help="set the story back to draft")
    args = ap.parse_args()

    # Accept "<world>/<story>", "worlds/<world>/stories/<story>" and story.yaml paths alike.
    parts = [p for p in Path(args.target).parts if p not in ("worlds", "stories", "story.yaml")]
    if len(parts) < 2:
        print(f"! cannot resolve a <world>/<story> from '{args.target}'", file=sys.stderr)
        return 2
    wslug, sslug = parts[0], parts[1]
    try:
        world = load_world(wslug)
    except (ContentError, FileNotFoundError) as e:
        print(f"! {e}", file=sys.stderr)
        return 2
    story = next((s for s in world.stories if s.slug == sslug), None)
    if not story:
        print(f"! no story '{sslug}' in world '{wslug}'", file=sys.stderr)
        return 2

    new_status = "draft" if args.draft else "published"
    old_status = story.data.get("status", "draft")
    if old_status == new_status:
        print(f"= {wslug}/{sslug} is already {new_status}")
        return 0

    story.data["status"] = new_status
    if new_status == "published":
        # The gate: validate the whole world with the flip applied in memory. Only failures
        # are blockers (warnings print but pass), matching scripts/validate.py.
        rep = Report()
        check_world(rep, world)
        for st in world.stories:
            check_story(rep, world, st)
        if rep.fails:
            print(f"✗ NOT published — {len(rep.fails)} validator failure(s) block the gate:")
            for f in rep.fails:
                print(f"    ✗ {f}")
            return 1
        for w in rep.warns:
            print(f"    ⚠ {w}")

    dump_yaml(story.data, story.path)
    print(f"+ {wslug}/{sslug}: {old_status} → {new_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
