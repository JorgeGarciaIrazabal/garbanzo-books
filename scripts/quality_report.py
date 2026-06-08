#!/usr/bin/env python3
"""Grade a book against the professional 7-gate pipeline — not pass/fail, but *how good*.

``scripts/validate.py`` answers "is this book broken?". This answers "is this book
*good*?" by scoring each story against measurable proxies for the gates in
``methodology/storybook-pipeline.md`` (premise, spine, manuscript length, page-turn
pacing, character art, fun & games, accessibility/finish). Every gate returns PASS or
WARN with a specific reason, plus an overall score — so an author can see, at a glance,
the difference between a book that merely validates and a book that's ready to delight.
(Note: these are structural proxies — whether a book is actually *fun* is a human call;
see ``methodology/fun-first.md``, the north star the whole pipeline serves.)

Usage:
    uv run python scripts/quality_report.py                          # every book
    uv run python scripts/quality_report.py <world>/<story>          # one book
    uv run python scripts/quality_report.py worlds/<world>/stories/<story>

Advisory by design: exit code is always 0 (it never blocks). It reads the same data
model as the validator and reuses the readability + interactivity machinery.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from math import ceil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.checks.interactivity import RICH_TYPES, SKILL_PRACTICE_TYPES  # noqa: E402
from lib.model import load_all_worlds, load_world  # noqa: E402
from lib.readability import BANDS, words  # noqa: E402

# Generous upper bounds on total word count per band (sprawl guard, from the
# storybook-pipeline manuscript table). Short is fine for kids' books; bloat isn't.
MAX_TOTAL_WORDS = {"0-3": 150, "3-5": 600, "5-7": 1500, "7-9": 3500, "9-12": 9000}
SPINE_BEATS = ["once_upon_a_time", "every_day", "until_one_day", "until_finally", "ever_since_then"]


@dataclass
class Gate:
    name: str
    ok: bool          # True = PASS, False = WARN
    detail: str


def _content_pages(pages: list[dict]) -> list[dict]:
    return [p for p in pages if p.get("kind") not in ("title", "end")]


def _gate_premise(story: dict) -> Gate:
    logline = (story.get("logline") or "").strip()
    if len(words(logline)) >= 5:
        return Gate("Premise & hook", True, "logline names protagonist + goal + obstacle")
    return Gate("Premise & hook", False, "logline is missing or too thin (want protagonist + goal + obstacle)")


def _gate_spine(story: dict) -> Gate:
    spine = story.get("spine", {}) or {}
    missing = [b for b in SPINE_BEATS if not (spine.get(b) or "").strip()]
    causes = spine.get("because_of_that", []) or []
    if not missing and len(causes) >= 2:
        return Gate("Story spine", True, "all beats present; each step causes the next")
    problems = []
    if missing:
        problems.append("missing " + ", ".join(missing))
    if len(causes) < 2:
        problems.append("needs ≥2 'because of that' causal links")
    return Gate("Story spine", False, "; ".join(problems))


def _gate_manuscript(story: dict, band_id: str) -> Gate:
    band = BANDS.get(band_id, BANDS["5-7"])
    pages = story.get("pages", []) or []
    total = sum(len(words(p.get("text") or "")) for p in pages)
    cap = band["max_words_per_page"]
    over = [p.get("number") for p in pages
            if p.get("kind") not in ("title", "interaction")
            and len(words(p.get("text") or "")) > cap]
    max_total = MAX_TOTAL_WORDS.get(band_id, 1500)
    if not over and total <= max_total:
        return Gate("Manuscript length", True, f"{total} words; all pages within the {cap}-word cap")
    problems = []
    if over:
        problems.append(f"pages over {cap}-word cap: {over}")
    if total > max_total:
        problems.append(f"{total} words exceeds ~{max_total} for {band_id} (risk of sprawl)")
    return Gate("Manuscript length", False, "; ".join(problems))


def _gate_pacing(story: dict) -> Gate:
    pages = story.get("pages", []) or []
    content = _content_pages(pages)
    n = len(content)
    interactions = [p for p in pages if p.get("interaction")]
    # Expect at least one engagement beat per ~6 content pages (interactivity.md cadence).
    expected = max(1, ceil(n / 6))
    problems = []
    if n < 6:
        problems.append(f"only {n} content pages (thin for a picture book)")
    elif n > 40:
        problems.append(f"{n} content pages (long — consider tightening)")
    if len(interactions) < expected:
        problems.append(f"{len(interactions)} interaction(s) over {n} pages "
                        f"(want ≥{expected} for a lively page-turn rhythm)")
    if not problems:
        return Gate("Pacing & page-turns", True,
                    f"{n} content pages, {len(interactions)} engagement beats")
    return Gate("Pacing & page-turns", False, "; ".join(problems))


def _gate_character_art(world, story: dict) -> Gate:
    roster = [c.get("slug") for c in story.get("characters", []) or []]
    missing_sheet = []
    missing_seed = []
    for slug in roster:
        ch = world.characters.get(slug)
        if not ch:
            continue
        if not ch.get("reference_images"):
            missing_sheet.append(slug)
        if ch.get("seed") is None:
            missing_seed.append(slug)
    if not missing_sheet and not missing_seed:
        return Gate("Character art", True, "every character has a model sheet + locked seed")
    problems = []
    if missing_sheet:
        problems.append("no reference art: " + ", ".join(missing_sheet))
    if missing_seed:
        problems.append("no locked seed: " + ", ".join(missing_seed))
    return Gate("Character art", False, "; ".join(problems))


def _gate_engagement(story: dict) -> Gate:
    """Fun & games: the interactions should be VARIED kinds of fun (not the same mechanic),
    at least one should be RICH (a kid DOES something — plays on the art, drags, solves a
    puzzle, makes music — not just picks an answer), and every game that can be 'gotten
    wrong' should respond warmly. We do NOT grade reading-skill coverage — fun is the point,
    not pedagogy."""
    pages = story.get("pages", []) or []
    interactions = [p["interaction"] for p in pages if p.get("interaction")]
    types = {it.get("type") for it in interactions if it.get("type")}
    rich = types & RICH_TYPES
    no_feedback = [p.get("number") for p in pages
                   if p.get("interaction")
                   and p["interaction"].get("type") in SKILL_PRACTICE_TYPES
                   and not (p["interaction"].get("feedback") or {})]
    problems = []
    if len(types) < 3 and len(types) < len(interactions):
        problems.append(f"games use only {len(types)} kind(s) of fun (<3) — vary them")
    if len(interactions) >= 2 and not rich:
        problems.append("every game is a quiz/tap — add at least one rich game "
                        "(in-scene, drag-and-drop, a puzzle, music, or a custom game)")
    if no_feedback:
        problems.append(f"games lacking warm feedback on pages {no_feedback}")
    if not problems:
        return Gate("Fun & games", True,
                    f"{len(types)} kinds of game ({len(rich)} rich), each gives warm feedback")
    return Gate("Fun & games", False, "; ".join(problems))


def _gate_finish(world, story: dict) -> Gate:
    pages = story.get("pages", []) or []
    no_alt = [p.get("number") for p in pages if not (p.get("image", {}) or {}).get("alt")]
    no_file = [p.get("number") for p in pages if not (p.get("image", {}) or {}).get("file")]
    has_cover = bool((story.get("cover", {}) or {}).get("image"))
    problems = []
    if no_alt:
        problems.append(f"pages without alt text: {no_alt}")
    if no_file:
        problems.append(f"pages not yet illustrated: {no_file}")
    if not has_cover:
        problems.append("no cover image")
    if not problems:
        return Gate("Accessibility & finish", True, "alt text + illustration on every page; cover set")
    return Gate("Accessibility & finish", False, "; ".join(problems))


def score_story(world, story) -> list[Gate]:
    """The full 7-gate scorecard for one story. Pure: takes a loaded World + Story,
    returns gate results (no I/O), so it's easy to unit-test and reuse in the UI."""
    s = story.data
    band_id = s.get("age_band", "5-7")
    return [
        _gate_premise(s),
        _gate_spine(s),
        _gate_manuscript(s, band_id),
        _gate_pacing(s),
        _gate_character_art(world, s),
        _gate_engagement(s),
        _gate_finish(world, s),
    ]


def grade(gates: list[Gate]) -> tuple[int, int, str]:
    passed = sum(1 for g in gates if g.ok)
    total = len(gates)
    ratio = passed / total if total else 0
    label = "excellent" if ratio == 1 else "strong" if ratio >= 0.8 else \
        "developing" if ratio >= 0.5 else "early draft"
    return passed, total, label


def _print_card(world, story) -> None:
    gates = score_story(world, story)
    passed, total, label = grade(gates)
    print(f"\n=== {story.data.get('title', story.slug)}  [{world.slug}/{story.slug}] ===")
    for g in gates:
        mark = "✓" if g.ok else "⚠"
        print(f"  {mark}  {g.name}: {g.detail}")
    print(f"  → {passed}/{total} gates — {label}")


def _resolve(target: str):
    p = Path(target)
    if "stories" in p.parts:
        parts = p.parts
        wslug = parts[parts.index("worlds") + 1] if "worlds" in parts else parts[0]
        sslug = parts[parts.index("stories") + 1]
    elif "/" in target and not p.exists():
        wslug, sslug = target.split("/", 1)
    elif p.is_dir() and (p / "story.yaml").exists():
        wslug, sslug = p.parent.parent.name, p.name
    else:
        raise FileNotFoundError(f"Could not resolve a story from '{target}'")
    world = load_world(wslug)
    story = next((s for s in world.stories if s.slug == sslug), None)
    if not story:
        raise FileNotFoundError(f"No story '{sslug}' in world '{wslug}'")
    return world, story


def main() -> int:
    ap = argparse.ArgumentParser(description="Grade books against the 7-gate quality checklist.")
    ap.add_argument("target", nargs="?", help="<world>/<story> or a story path (default: all)")
    args = ap.parse_args()

    if args.target:
        try:
            world, story = _resolve(args.target)
        except FileNotFoundError as e:
            print(f"! {e}", file=sys.stderr)
            return 2
        _print_card(world, story)
        return 0

    worlds = load_all_worlds(with_stories=True)
    if not worlds:
        print("No worlds yet.")
        return 0
    for w in worlds:
        for st in w.stories:
            _print_card(w, st)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
