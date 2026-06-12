#!/usr/bin/env python3
"""Edit a character yaml by sending a JSON patch — never edit the YAML text by hand.

The agent-safe write path: emit JSON, this tool does load → deep-merge →
schema-validate → atomic YAML write. A bad patch changes NOTHING on disk and
prints every schema error at once.

Usage (patch is JSON on stdin — a heredoc — or via --file):

    uv run python scripts/edit_character.py <world>/<char> <<'JSON'
    {"appearance_token": "...",
     "personality": {"traits": ["brave", "curious"], "motivation": "..."}}
    JSON

Merge rules: nested objects merge key-by-key; lists replace wholesale (send the
FULL new list for traits/evolution/etc.); JSON null DELETES a key.
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


def _character_path(target: str) -> Path:
    """Accept "<world>/<char>" and "worlds/<world>/characters/<char>.yaml" alike."""
    parts = [p.removesuffix(".yaml")
             for p in Path(target).parts if p not in ("worlds", "characters")]
    if len(parts) < 2:
        raise ContentError(f"cannot resolve a <world>/<character> from '{target}'")
    return model.WORLDS / parts[0] / "characters" / f"{parts[1]}.yaml"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Patch a character yaml with JSON (merge + schema-validate + atomic write).")
    ap.add_argument("target", help="<world>/<character-slug> or a character yaml path")
    ap.add_argument("-f", "--file", help="read the JSON patch from a file instead of stdin")
    args = ap.parse_args()

    try:
        cpath = _character_path(args.target)
        char = load_for_patch("character", cpath)
        patch = read_patch(args.file)
        if not isinstance(patch, dict):
            raise ContentError("character patch must be a JSON object of fields to merge")
        deep_merge(char, patch)
        errors = save_patched("character", cpath, char)
    except ContentError as e:
        print(f"! {e}", file=sys.stderr)
        return 2 if "cannot resolve" in str(e) or "no character file" in str(e) else 1

    if errors:
        print(f"! patch rejected — merged character would violate the schema; {cpath} unchanged:",
              file=sys.stderr)
        for line in errors:
            print(f"    {line}", file=sys.stderr)
        return 1
    print(f"+ updated {cpath} — fields: {', '.join(patch)} (schema-valid)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
