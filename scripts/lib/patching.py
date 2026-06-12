"""JSON-patch editing for world/character/story YAML — the agent-safe write path.

Agents (especially small local models) are bad at editing YAML text: indentation
slips, exact-match Edit calls fail, and a format error only surfaces at validate
time. So content edits flow through here instead: the model emits a small JSON
payload, we load the YAML, deep-merge the patch, validate the MERGED document
against the JSON schema, and only then write — via dump_yaml's atomic,
re-parse-checked path. A file on disk is therefore always complete, well-formed
YAML; a bad patch changes nothing and reports every schema error at once.

Merge semantics (deliberately simple, documented in each CLI's --help):
  * dict into dict   → recursive merge, key by key
  * JSON null        → DELETE that key from the target
  * anything else    → replace wholesale (lists included — no element merging,
                        EXCEPT story pages, which merge_pages() keys by number)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from .model import ContentError, SCHEMAS, dump_yaml, load_yaml

_FENCE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n|\n\s*```\s*$")


def parse_patch(text: str) -> Any:
    """Parse a JSON patch payload. Tolerates a markdown code fence around the
    JSON (local models love to add one); everything else is strict JSON so a
    malformed payload fails loudly here, not as mystery YAML later."""
    cleaned = _FENCE.sub("", text.strip()).strip()
    if not cleaned:
        raise ContentError("empty patch — pass JSON on stdin or via --file")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ContentError(f"patch is not valid JSON: {e.msg} (line {e.lineno} column {e.colno})")


def read_patch(file: str | None) -> Any:
    """Read the patch from --file if given, else stdin."""
    if file:
        text = Path(file).read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            raise ContentError("no patch given — pipe JSON on stdin (heredoc) or use --file")
        text = sys.stdin.read()
    return parse_patch(text)


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> None:
    """Merge `patch` into `base` in place. null deletes; nested dicts recurse;
    scalars and lists replace."""
    for key, val in patch.items():
        if val is None:
            base.pop(key, None)
        elif isinstance(val, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], val)
        else:
            base[key] = val


def merge_pages(pages: list[dict[str, Any]], patch_pages: list[dict[str, Any]]) -> list[int]:
    """Merge partial page objects into `pages` keyed by their `number`.

    An existing page is deep-merged (so {"number": 3, "text": "..."} updates just
    the text); an unknown number is appended as a new page and the list re-sorted.
    Returns the touched page numbers. Raises ContentError on a page without a
    usable integer `number` — that's the join key, never guessable."""
    by_number = {p.get("number"): p for p in pages if isinstance(p, dict)}
    touched: list[int] = []
    for pp in patch_pages:
        if not isinstance(pp, dict) or not isinstance(pp.get("number"), int):
            raise ContentError(
                'every page patch needs an integer "number" — e.g. {"number": 3, "text": "..."}'
            )
        n = pp["number"]
        if n in by_number:
            deep_merge(by_number[n], pp)
        else:
            pages.append(pp)
            by_number[n] = pp
        touched.append(n)
    pages.sort(key=lambda p: p.get("number", 0) if isinstance(p, dict) else 0)
    return touched


def schema_error_lines(kind: str, data: dict[str, Any], limit: int = 10) -> list[str]:
    """All schema violations for `data` as friendly `path: message` lines (capped at
    `limit`), so the agent can fix everything in ONE follow-up patch instead of
    discovering errors one at a time. Empty list = valid (or jsonschema/schema file
    unavailable — same graceful degradation as model.validate_content)."""
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return []
    sp = SCHEMAS / f"{kind}.schema.json"
    if not sp.exists():
        return []
    schema = json.loads(sp.read_text(encoding="utf-8"))
    errs = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
    lines = []
    for e in errs[:limit]:
        loc = "/".join(str(x) for x in e.path) or "(root)"
        lines.append(f"{loc}: {e.message}")
    if len(errs) > limit:
        lines.append(f"... and {len(errs) - limit} more")
    return lines


def save_patched(kind: str, path: Path, data: dict[str, Any]) -> list[str]:
    """Validate the merged document and write it atomically. Returns the list of
    schema errors; the file is written ONLY when that list is empty."""
    errors = schema_error_lines(kind, data)
    if errors:
        return errors
    dump_yaml(data, path)
    return []


def load_for_patch(kind: str, path: Path) -> dict[str, Any]:
    """Load the YAML to be patched, normalizing errors to ContentError."""
    if not Path(path).exists():
        raise ContentError(f"no {kind} file at {path}")
    return load_yaml(path)
