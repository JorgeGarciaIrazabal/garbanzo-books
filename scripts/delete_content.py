#!/usr/bin/env python3
"""Delete a whole story, or a whole world (with everything in it), from the workspace.

Usage:
    uv run python scripts/delete_content.py <world>/<story>   # delete ONE story
    uv run python scripts/delete_content.py <world>           # delete the WHOLE world

This is DESTRUCTIVE and irreversible — it removes the content directory from disk:
    - a story  → worlds/<world>/stories/<story>/   (text, images, everything)
    - a world  → worlds/<world>/                    (world bible, every character AND story)

The generated site/ and site_publish/ builds still hold a stale copy until rebuilt; the
studio rebuilds both previews after a delete. To rid the public site of a deleted book,
rebuild + redeploy (the publish build only includes what's still on disk).

Safety: the resolved path must live inside worlds/ — anything else is refused, so a bad
slug can never delete outside the content tree. Pass --yes to skip the interactive
confirmation (the studio UI confirms in its own popup before calling this).

Exit code 0 = deleted, 1 = aborted at the prompt, 2 = bad / unresolvable target.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.model import WORLDS  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Delete a story or a whole world (destructive).")
    ap.add_argument("target", help="<world> (whole world) or <world>/<story> (one story)")
    ap.add_argument("--yes", "-y", action="store_true", help="skip the confirmation prompt")
    args = ap.parse_args()

    # Accept "<world>", "<world>/<story>", and the long "worlds/<world>/stories/<story>" forms.
    parts = [p for p in Path(args.target).parts if p not in ("worlds", "stories", "story.yaml")]
    if not parts:
        print(f"! cannot resolve a target from '{args.target}'", file=sys.stderr)
        return 2
    wslug = parts[0]
    sslug = parts[1] if len(parts) >= 2 else None

    if sslug:
        target = WORLDS / wslug / "stories" / sslug
        kind, label = "story", f"{wslug}/{sslug}"
        check = target / "story.yaml"
    else:
        target = WORLDS / wslug
        kind, label = "world", wslug
        check = target / "world.yaml"

    target = target.resolve()
    # Refuse anything that isn't a real content dir inside worlds/ — never delete outside the tree.
    if not check.exists() or not target.is_dir():
        print(f"! no {kind} '{label}' to delete (looked for {check})", file=sys.stderr)
        return 2
    if WORLDS.resolve() not in target.parents:
        print(f"! refusing to delete '{target}' — outside the worlds/ tree", file=sys.stderr)
        return 2

    if not args.yes:
        extra = " AND every character and story inside it" if kind == "world" else ""
        reply = input(f"Delete {kind} '{label}'{extra}? This cannot be undone. [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("aborted — nothing deleted")
            return 1

    shutil.rmtree(target)
    print(f"- deleted {kind} '{label}' ({target})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
