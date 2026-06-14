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
from lib.readability import story_targets, words  # noqa: E402

# Generous upper bounds on total word count per band (sprawl guard, from the
# storybook-pipeline manuscript table). Short is fine for kids' books; bloat isn't.
MAX_TOTAL_WORDS = {"0-3": 150, "3-5": 600, "5-7": 1500, "7-9": 3500, "9-12": 9000, "grown-up": 20000}
SPINE_BEATS = ["once_upon_a_time", "every_day", "until_one_day", "until_finally", "ever_since_then"]

# Cause-and-effect / temporal connectors. A book whose pages mostly DON'T pick up a thread
# from the page before reads as a string of disconnected vignettes — the "things aren't
# connected page to page" complaint. This is a soft proxy: real flow is a human call (the
# read-aloud pass), but a book with almost no connective tissue is worth flagging.
CONNECTORS = {
    "and", "but", "so", "then", "because", "when", "while", "after", "before", "until",
    "since", "soon", "suddenly", "now", "later", "meanwhile", "still", "yet", "though",
    "if", "as", "once", "finally", "next", "first", "too", "also",
}


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
    pages = story.get("pages", []) or []
    total = sum(len(words(p.get("text") or "")) for p in pages)
    cap = story_targets(story)["max_words_per_page"]
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
    """Page-count sanity only. We deliberately do NOT enforce a games-per-page quota any
    more — games are OPTIONAL add-ons matched to a beat, never a cadence to hit (a quota
    pushes authors to drop blank-text game pages into the story, which fragments the read).
    See _gate_flow for the cost of those interruptions, and methodology/fun-first.md."""
    pages = story.get("pages", []) or []
    content = _content_pages(pages)
    n = len(content)
    interactions = [p for p in pages if p.get("interaction")]
    problems = []
    if n < 6:
        problems.append(f"only {n} content pages (thin for a picture book)")
    elif n > 40:
        problems.append(f"{n} content pages (long — consider tightening)")
    if not problems:
        return Gate("Pacing & page-turns", True,
                    f"{n} content pages, {len(interactions)} optional game(s)")
    return Gate("Pacing & page-turns", False, "; ".join(problems))


def _gate_flow(story: dict) -> Gate:
    """Flow & continuity — a soft proxy for 'does it read as one connected story?'. Two
    concrete signals: (1) pure-interaction pages with no story text dropped mid-book punch
    literal holes in the narrative; (2) story pages that almost never pick up a thread from
    the page before (no cause/effect/temporal connectors) read as disconnected vignettes.
    Real flow is a human call — this just flags the books most likely to feel choppy."""
    pages = story.get("pages", []) or []
    story_pages = [p for p in pages if p.get("kind") == "story"]
    n = len(story_pages)

    # (1) Blank-text pages that interrupt the story (a game page with no narrative text,
    # sitting between story pages). The game belongs ON a story page, not in a gap.
    seen_story = trailing = False
    holes = []
    for p in pages:
        kind = p.get("kind")
        has_text = bool((p.get("text") or "").strip())
        if kind == "story" and has_text:
            seen_story = True
            trailing = False
        elif kind in ("title", "end"):
            continue
        elif not has_text and seen_story:
            # an empty-text page (typically a standalone interaction) after the story began
            holes.append(p.get("number"))
            trailing = True
    # A trailing empty page at the very end isn't a mid-story hole; drop the last if trailing.
    if holes and trailing:
        holes = holes[:-1]

    # (2) Connective tissue across story pages.
    connected = 0
    for p in story_pages:
        toks = {w.lower() for w in words(p.get("text") or "")}
        if toks & CONNECTORS:
            connected += 1
    ratio = connected / n if n else 1.0

    problems = []
    if holes:
        problems.append(f"blank-text page(s) interrupt the story: {holes} "
                        "(put the game on a story page, don't break the read)")
    if n >= 6 and ratio < 0.5:
        problems.append(f"only {connected}/{n} story pages connect to the flow "
                        "(few cause/effect/temporal links — risks reading as separate vignettes)")
    if not problems:
        return Gate("Flow & continuity", True,
                    f"no narrative gaps; {connected}/{n} story pages carry connective tissue")
    return Gate("Flow & continuity", False, "; ".join(problems))


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
    """Fun & games: every game beat should be a REAL game (the arcade-* family — a game
    loop, movement, physics), the kinds of fun should be VARIED (not the same mechanic
    twice in a row), and every game should respond warmly on the win. Legacy minigames
    (drag-and-drop, find-in-picture, tap boards, quizzes) keep playing in published books
    but count against new ones. We do NOT grade reading-skill coverage — fun is the point,
    not pedagogy."""
    pages = story.get("pages", []) or []
    interactions = [p["interaction"] for p in pages if p.get("interaction")]
    types = {it.get("type") for it in interactions if it.get("type")}
    real = types & RICH_TYPES  # = the arcade family
    legacy = types - RICH_TYPES - {"choice"}
    no_feedback = [p.get("number") for p in pages
                   if p.get("interaction")
                   and p["interaction"].get("type") in SKILL_PRACTICE_TYPES
                   and not (p["interaction"].get("feedback") or {})]
    problems = []
    if len(types) < 3 and len(types) < len(interactions):
        problems.append(f"games use only {len(types)} kind(s) of fun (<3) — vary the arcade mechanics")
    if interactions and not real:
        problems.append("no REAL game — every game beat should be an arcade-* mechanic "
                        "(snake, shoot, maze, build, whack, bounce, catch, flap, run, pop, toss, steer)")
    if legacy:
        problems.append("legacy minigames present (" + ", ".join(sorted(legacy)) +
                        ") — fine in already-published books, not in new ones")
    if no_feedback:
        problems.append(f"games lacking warm feedback on pages {no_feedback}")
    if not problems:
        return Gate("Fun & games", True,
                    f"{len(types)} kinds of game ({len(real)} real arcade), each gives warm feedback")
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
        _gate_flow(s),
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
    print(f"  → {passed}/{total} STRUCTURAL gates — {label}")
    print("  NOTE: these are structural proxies only. The gate that actually decides if a "
          "book is good — is it FUN, and does it flow aloud? — is a human call (the "
          "read-aloud / debate pass). A green card here is necessary, never sufficient.")


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
