#!/usr/bin/env python3
"""Edit a world.yaml by sending a JSON patch — never edit the YAML text by hand.

The agent-safe write path: emit JSON, this tool does load → deep-merge →
schema-validate → atomic YAML write. A bad patch changes NOTHING on disk and
prints every schema error at once.

Usage (patch is JSON on stdin — a heredoc — or via --file):

    uv run python scripts/edit_world.py <world> <<'JSON'
    {"tagline": "...", "art_style": {"prompt_style_block": "...", "negative_prompt": "..."}}
    JSON

Merge rules: nested objects merge key-by-key; lists replace wholesale (send the
FULL new list for rules/palette/locations/etc.); JSON null DELETES a key.
Exit 0 = written, 1 = patch rejected (file unchanged), 2 = bad target.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import model  # noqa: E402
from lib.model import ContentError  # noqa: E402
from lib.patching import deep_merge, load_for_patch, read_patch, save_patched  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Patch a world.yaml with JSON (merge + schema-validate + atomic write).")
    ap.add_argument("world", help="world slug")
    ap.add_argument("-f", "--file", help="read the JSON patch from a file instead of stdin")
    args = ap.parse_args()

    wpath = model.WORLDS / args.world / "world.yaml"
    try:
        world = load_for_patch("world", wpath)
        patch = read_patch(args.file)
        if not isinstance(patch, dict):
            raise ContentError("world patch must be a JSON object of fields to merge")
        deep_merge(world, patch)
        errors = save_patched("world", wpath, world)
    except ContentError as e:
        print(f"! {e}", file=sys.stderr)
        return 2 if "no world file" in str(e) else 1

    if errors:
        print(f"! patch rejected — merged world would violate the schema; {wpath} unchanged:",
              file=sys.stderr)
        for line in errors:
            print(f"    {line}", file=sys.stderr)
        return 1
    print(f"+ updated {wpath} — fields: {', '.join(patch)} (schema-valid)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
