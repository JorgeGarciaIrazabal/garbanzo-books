#!/usr/bin/env python3
"""QA gate: validate worlds/characters/stories against the JSON schemas AND the workspace
invariants (consistency, reading level, interactivity, accessibility, illustration).

Usage:
    uv run python scripts/validate.py                       # everything
    uv run python scripts/validate.py worlds/<world>        # one world + its content
    uv run python scripts/validate.py worlds/<world>/stories/<story>

Exit code 0 = all PASS, 1 = failures, 2 = setup error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.model import (SCHEMAS, WORLDS, ContentError, load_all_worlds, load_world)  # noqa: E402
from lib.readability import BANDS, analyze, words  # noqa: E402

try:
    from jsonschema import Draft202012Validator
    HAVE_JSONSCHEMA = True
except Exception:  # noqa: BLE001
    HAVE_JSONSCHEMA = False

# Allowed interaction types and the keys their `data` payload should carry.
INTERACTION_DATA_KEYS = {
    "seek-and-find": ["items"],
    "spot-the-difference": ["count"],
    "counting": ["answer"],
    "rhyme-complete": ["answer"],
    "word-match": ["pairs"],
    "sound-hunt": ["sound", "words"],
    "riddle": ["answer"],
    "comprehension-question": ["question"],
    "choice": ["options"],
    "maze": [],
    "trace-letter": ["letter"],
    "memory": [],
    "drag-order": [],
    "tap-to-reveal": [],
    "coloring": [],
}
PILLARS = {"phonemic-awareness", "phonics", "fluency", "vocabulary", "comprehension"}


class Report:
    def __init__(self) -> None:
        self.passes = 0
        self.fails: list[str] = []
        self.warns: list[str] = []

    def ok(self, msg: str) -> None:
        self.passes += 1

    def fail(self, msg: str) -> None:
        self.fails.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)


def load_schema(name: str) -> dict | None:
    p = SCHEMAS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def schema_check(rep: Report, data: dict, schema_name: str, where: str) -> None:
    if not HAVE_JSONSCHEMA:
        rep.warn(f"jsonschema not installed — skipped schema check for {where} (pip install jsonschema)")
        return
    schema = load_schema(schema_name)
    if not schema:
        rep.warn(f"schema {schema_name} missing")
        return
    errs = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
    if errs:
        for e in errs[:10]:
            loc = "/".join(str(p) for p in e.path) or "(root)"
            rep.fail(f"[schema] {where}: {loc}: {e.message}")
    else:
        rep.ok(f"schema {where}")


def check_world(rep: Report, world) -> None:
    schema_check(rep, world.data, "world.schema.json", f"world {world.slug}")
    art = world.data.get("art_style", {}) or {}
    if not art.get("prompt_style_block"):
        rep.fail(f"[consistency] world {world.slug}: art_style.prompt_style_block missing (style won't lock)")
    else:
        rep.ok("style block")
    if not art.get("palette"):
        rep.fail(f"[consistency] world {world.slug}: art_style.palette empty")
    for cslug, c in world.characters.items():
        schema_check(rep, c, "character.schema.json", f"character {world.slug}/{cslug}")
        if not c.get("appearance_token"):
            rep.fail(f"[consistency] character {cslug}: appearance_token missing (visual consistency lever)")
        elif "TODO" in c.get("appearance_token", ""):
            rep.warn(f"character {cslug}: appearance_token still has TODO")
        else:
            rep.ok(f"appearance_token {cslug}")


def check_story(rep: Report, world, story) -> None:
    s = story.data
    where = f"{world.slug}/{story.slug}"
    schema_check(rep, s, "story.schema.json", f"story {where}")

    band_id = s.get("age_band", "5-7")
    band = BANDS.get(band_id, BANDS["5-7"])
    rl = s.get("reading_level", {}) or {}
    pages = s.get("pages", []) or []

    # --- Consistency: characters referenced exist + have tokens + valid stage ---
    roster = {c.get("slug"): c for c in s.get("characters", []) or []}
    for slug, entry in roster.items():
        ch = world.characters.get(slug)
        if not ch:
            rep.fail(f"[consistency] {where}: references missing character '{slug}'")
            continue
        if not ch.get("appearance_token"):
            rep.fail(f"[consistency] {where}: character '{slug}' has no appearance_token")
        stage = entry.get("stage")
        if stage:
            stages = {st.get("stage") for st in ch.get("evolution", []) or []}
            if stage not in stages and stage != "base":
                rep.fail(f"[consistency] {where}: character '{slug}' pinned to unknown stage '{stage}'")
    # Pages referencing characters not in the roster
    page_nums = {p.get("number") for p in pages}
    for p in pages:
        for cp in (p.get("image", {}) or {}).get("characters_present", []) or []:
            if cp not in world.characters:
                rep.fail(f"[consistency] {where} p{p.get('number')}: image character '{cp}' not in world")
    if roster:
        rep.ok(f"character roster {where}")

    # --- Reading level ---
    text = " ".join((p.get("text") or "") for p in pages)
    m = analyze(text)
    target = rl.get("target_fk_grade", band.get("fk_grade"))
    tol = rl.get("fk_grade_tolerance", 1.0)
    max_wpp = rl.get("max_words_per_page", band["max_words_per_page"])
    if band.get("fk_grade") is not None and target is not None:
        if m.fk_grade > target + tol:
            rep.fail(f"[reading] {where}: FK grade {m.fk_grade} > target {target}+{tol}")
        else:
            rep.ok(f"reading level {where}")
    over = [p.get("number") for p in pages
            if p.get("kind") not in ("title", "interaction")
            and len(words(p.get("text") or "")) > max_wpp]
    if over:
        rep.fail(f"[reading] {where}: pages over {max_wpp}-word cap: {over}")

    # --- Interactivity ---
    pillars_seen = set()
    has_interaction = False
    for p in pages:
        it = p.get("interaction")
        if not it:
            continue
        has_interaction = True
        t = it.get("type")
        need = INTERACTION_DATA_KEYS.get(t)
        if need is None:
            rep.fail(f"[interaction] {where} p{p.get('number')}: unknown type '{t}'")
            continue
        data = it.get("data", {}) or {}
        missing = [k for k in need if k not in data]
        if missing:
            rep.fail(f"[interaction] {where} p{p.get('number')} ({t}): data missing {missing}")
        if it.get("skill") in PILLARS:
            pillars_seen.add(it.get("skill"))
        # branching targets resolve
        if t == "choice":
            for opt in data.get("options", []) or []:
                if opt.get("goto") not in page_nums:
                    rep.fail(f"[interaction] {where} p{p.get('number')}: choice goto "
                             f"{opt.get('goto')} is not a real page")
    if has_interaction:
        rep.ok(f"interactions {where}")
        if len(pillars_seen) < 3:
            rep.warn(f"{where}: interactions cover only {len(pillars_seen)} reading pillar(s) (<3)")
    else:
        rep.warn(f"{where}: no interactions yet")

    # --- Accessibility / layout / illustration ---
    for p in pages:
        n = p.get("number")
        img = p.get("image", {}) or {}
        if not img.get("alt"):
            rep.warn(f"{where} p{n}: image has no alt text")
        if p.get("kind") not in ("title",) and not p.get("layout"):
            rep.warn(f"{where} p{n}: no layout (text placement) set")
        if not img.get("file"):
            rep.warn(f"{where} p{n}: no image file yet (run /illustrate)")
        elif not (story.dir / img["file"]).exists():
            rep.fail(f"[illustration] {where} p{n}: image file '{img['file']}' not found")

    if s.get("status") == "published" and rep.fails:
        rep.fail(f"[publish] {where}: marked published but has failures above")


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
            st = next((s for s in w.stories if s.slug == story_slug), None)
            yield w, None
            if st:
                yield w, st
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
