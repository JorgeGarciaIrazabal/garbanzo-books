#!/usr/bin/env python3
"""One-shot context pack for writing a story in a world — everything the author-agent
needs in a SINGLE tool call instead of five-plus serial file reads.

Usage:
    uv run python scripts/story_context.py <world-slug>

Prints, compactly: the world's premise/tone/rules/motifs + locked art notes, every
character's personality/voice/catchphrases/evolution stages, the existing story slugs
(avoid collisions, honour the timeline), the age-band language table, and the exact
scaffold command. Each LLM round trip on a local model costs 10-60s of context
re-processing — collapsing the pre-flight reads into one call is the single biggest
time win in the story workflow short of the writing itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.model import ContentError, load_world  # noqa: E402
from lib.readability import BANDS  # noqa: E402


def _line(label: str, value) -> None:
    if isinstance(value, (list, tuple)):
        value = "; ".join(str(v) for v in value if v)
    if value:
        print(f"  {label}: {value}")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: story_context.py <world-slug>", file=sys.stderr)
        return 2
    try:
        world = load_world(sys.argv[1], with_stories=True)
    except (ContentError, FileNotFoundError) as e:
        print(f"! {e}", file=sys.stderr)
        return 2

    w = world.data
    print(f"=== WORLD: {w.get('title')} ({world.slug}) ===")
    _line("premise", w.get("premise"))
    _line("tagline", w.get("tagline"))
    _line("tone", w.get("tone"))
    _line("age bands", w.get("target_age_bands"))
    _line("themes", w.get("themes"))
    _line("motifs", w.get("motifs"))
    print("  rules (INVIOLABLE):")
    for r in w.get("rules", []) or []:
        print(f"    - {r}")
    locs = ((w.get("geography") or {}).get("locations")) or []
    if locs:
        _line("locations", [loc.get("name") for loc in locs])
    art = w.get("art_style", {}) or {}
    _line("art (locked, injected automatically)", art.get("medium"))
    print("  NOTE: image prompts are SCENE-ONLY — style & appearance tokens are injected.")

    print(f"\n=== CAST ({len(world.characters)}) ===")
    for slug, c in world.characters.items():
        p = c.get("personality", {}) or {}
        v = c.get("voice", {}) or {}
        print(f"--- {c.get('name')} ({slug}) — {c.get('role')} ---")
        _line("one-liner", c.get("one_liner"))
        _line("traits", p.get("traits"))
        _line("motivation", p.get("motivation"))
        _line("flaws", p.get("flaws"))
        _line("speech", v.get("speech_style"))
        for cp in (v.get("catchphrases") or [])[:3]:
            print(f"  catchphrase: {cp}")
        _line("stages", [st.get("stage") for st in c.get("evolution", []) or []])

    print(f"\n=== EXISTING STORIES ({len(world.stories)}) — don't reuse slugs ===")
    for s in world.stories:
        print(f"  {s.slug} [{s.data.get('status','draft')}] — {s.data.get('title')}")

    print("\n=== AGE-BAND LANGUAGE (light touch — see methodology/reading-pedagogy.md) ===")
    for band_id, b in BANDS.items():
        avg = b.get("min_avg_sentence_words")
        print(f"  {band_id}: ≤{b['max_words_per_page']} words/page, longest sentence "
              f"≤{b['max_sentence_words']}"
              + (f", avg ≥{avg:g} (no telegraphic fragments!)" if avg else " (read-aloud band)"))

    print("\n=== NEXT STEPS ===")
    print(f"  scaffold: uv run python scripts/new_story.py {world.slug} \"<Title>\" --age 5-7"
          " [--slug s]   (world+title are POSITIONAL)")
    print("  then: write spine + pages in STAGES (small writes), validate, illustrate.")
    print("  north star: methodology/fun-first.md — funny, mischievous, real stakes, "
          "flowing read-aloud prose (never chopped fragments), no moral-of-the-story.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
