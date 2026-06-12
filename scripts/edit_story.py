#!/usr/bin/env python3
"""Edit a story.yaml by sending small JSON patches — never edit the YAML text by hand.

This is the agent-safe write path: emit JSON (the format models are reliable at),
and this tool does load → merge → schema-validate → atomic YAML write. A bad patch
changes NOTHING on disk and prints every schema error at once.

Usage (patch is JSON on stdin — a heredoc — or via --file):

    # top-level fields: logline, summary, themes, spine, characters, reading_level, ...
    uv run python scripts/edit_story.py <world>/<story> meta <<'JSON'
    {"logline": "...", "spine": {"until_one_day": "..."}}
    JSON

    # pages, merged by "number" — send partial objects, a few pages per call
    uv run python scripts/edit_story.py <world>/<story> pages <<'JSON'
    [{"number": 3, "text": "...", "image": {"prompt": "...", "alt": "..."}},
     {"number": 4, "text": "..."}]
    JSON

    # set (replace) one page's interaction — or remove it
    uv run python scripts/edit_story.py <world>/<story> interaction 8 <<'JSON'
    {"type": "seek-and-find", "prompt": "...", "data": {...}}
    JSON
    uv run python scripts/edit_story.py <world>/<story> interaction 8 --remove

Merge rules: nested objects merge key-by-key; lists replace wholesale (except
`pages`, keyed by number); JSON null DELETES a key. Exit 0 = written, 1 = patch
rejected (file unchanged), 2 = bad target/usage.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import model  # noqa: E402
from lib.model import ContentError  # noqa: E402
from lib.patching import deep_merge, load_for_patch, merge_pages, read_patch, save_patched  # noqa: E402


def _story_path(target: str) -> Path:
    """Accept "<world>/<story>", "worlds/<world>/stories/<story>" and story.yaml paths."""
    parts = [p for p in Path(target).parts if p not in ("worlds", "stories", "story.yaml")]
    if len(parts) < 2:
        raise ContentError(f"cannot resolve a <world>/<story> from '{target}'")
    return model.WORLDS / parts[0] / "stories" / parts[1] / "story.yaml"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Patch a story.yaml with JSON (merge + schema-validate + atomic write).")
    ap.add_argument("target", help="<world>/<story> or a story.yaml path")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_meta = sub.add_parser("meta", help="merge top-level fields (anything except pages)")
    p_pages = sub.add_parser("pages", help="merge page objects by number (list or one object)")
    p_inter = sub.add_parser("interaction", help="set or remove one page's interaction")
    p_inter.add_argument("page", type=int, help="page number")
    p_inter.add_argument("--remove", action="store_true", help="delete the interaction instead")
    for p in (p_meta, p_pages, p_inter):
        p.add_argument("-f", "--file", help="read the JSON patch from a file instead of stdin")
    args = ap.parse_args()

    try:
        spath = _story_path(args.target)
        story = load_for_patch("story", spath)

        if args.cmd == "meta":
            patch = read_patch(args.file)
            if not isinstance(patch, dict):
                raise ContentError("meta patch must be a JSON object of top-level fields")
            if "pages" in patch:
                raise ContentError('meta must not contain "pages" — use the pages subcommand '
                                   "(small batches merge by page number)")
            deep_merge(story, patch)
            what = f"meta fields: {', '.join(patch)}"

        elif args.cmd == "pages":
            patch = read_patch(args.file)
            if isinstance(patch, dict):
                patch = [patch]
            if not isinstance(patch, list):
                raise ContentError("pages patch must be a JSON list of page objects (or one object)")
            touched = merge_pages(story.setdefault("pages", []), patch)
            what = f"pages: {', '.join(str(n) for n in touched)}"

        else:  # interaction
            pages = story.get("pages", [])
            page = next((p for p in pages if isinstance(p, dict) and p.get("number") == args.page),
                        None)
            if page is None:
                raise ContentError(f"no page {args.page} in {args.target} "
                                   f"(it has pages {[p.get('number') for p in pages]})")
            if args.remove:
                page.pop("interaction", None)
                what = f"removed interaction on page {args.page}"
            else:
                patch = read_patch(args.file)
                if not isinstance(patch, dict):
                    raise ContentError("interaction patch must be a JSON object (type, prompt, ...)")
                page["interaction"] = patch
                what = f"interaction on page {args.page} ({patch.get('type', '?')})"

        errors = save_patched("story", spath, story)
    except ContentError as e:
        print(f"! {e}", file=sys.stderr)
        return 2 if "cannot resolve" in str(e) or "no story file" in str(e) else 1

    if errors:
        print(f"! patch rejected — merged story would violate the schema; {spath} unchanged:",
              file=sys.stderr)
        for line in errors:
            print(f"    {line}", file=sys.stderr)
        return 1
    print(f"+ updated {spath} — {what} (schema-valid)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
