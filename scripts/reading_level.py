#!/usr/bin/env python3
"""Measure a story's reading level against its target.

Usage:
    uv run python scripts/reading_level.py worlds/<world>/stories/<story>
    uv run python scripts/reading_level.py <world-slug>/<story-slug>

Reports per-book FKGL + Flesch Reading Ease, per-page word counts vs the cap, the longest
sentence, and (if decodable) words outside the phonics focus. Exit code 0 if on target.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.model import ROOT, load_yaml  # noqa: E402
from lib.readability import analyze, count_syllables, story_targets, words  # noqa: E402

# Common irregular sight/heart words allowed even in decodable text.
DEFAULT_SIGHT = {
    "the", "a", "i", "is", "to", "and", "was", "said", "you", "he", "she", "it", "of",
    "are", "for", "they", "we", "me", "my", "be", "have", "has", "do", "go", "no", "so",
    "her", "his", "as", "on", "in", "at", "up", "but", "all", "one", "two",
}


def resolve_story_yaml(arg: str) -> Path:
    p = Path(arg)
    if p.is_dir() and (p / "story.yaml").exists():
        return p / "story.yaml"
    if p.name == "story.yaml" and p.exists():
        return p
    if "/" in arg and not p.exists():
        world, story = arg.split("/", 1)
        cand = ROOT / "worlds" / world / "stories" / story / "story.yaml"
        if cand.exists():
            return cand
    if p.exists():
        return p / "story.yaml" if p.is_dir() else p
    raise FileNotFoundError(f"Could not resolve a story.yaml from '{arg}'")


def page_text(pages: list[dict]) -> str:
    return " ".join((pg.get("text") or "") for pg in pages)


def decodable_focus_letters(focus: str) -> set[str]:
    # Pull single letters / digraphs out of a focus string like "s a t p i n; sight: the,is".
    focus_part = focus.split("sight", 1)[0]
    toks = re.findall(r"[a-z]{1,3}", focus_part.lower())
    return set(toks)


def report(story_yaml: Path) -> bool:
    data = load_yaml(story_yaml)
    band_id = data.get("age_band", "5-7")
    year = data.get("target_year")
    t = story_targets(data)
    rl = data.get("reading_level", {}) or {}
    pages = data.get("pages", []) or []

    target = t["fk_target"]
    tol = t["fk_tol"]
    max_wpp = t["max_words_per_page"]
    max_sent = t["max_sentence_words"]
    fk_enforced = t["fk_enforced"]
    read_aloud = t["read_aloud"]

    text = page_text(pages)
    m = analyze(text)

    # Longest sentence measured PER PAGE (joining pages would merge across page breaks).
    longest = 0
    longest_pg = None
    for pg in pages:
        if pg.get("kind") in ("interaction",):
            continue
        pm = analyze(pg.get("text") or "")
        if pm.longest_sentence_words > longest:
            longest = pm.longest_sentence_words
            longest_pg = pg.get("number")

    yr = f"age {year}" if isinstance(year, int) else band_id
    print(f"=== {data.get('title','(untitled)')}  [{yr} — {t['label']}] ===")
    print(f"  words: {m.words}   sentences: {m.sentences}   words/sentence: {m.words_per_sentence:.1f}")
    print(f"  Flesch Reading Ease: {m.flesch_reading_ease}   FK grade: {m.fk_grade}")
    print(f"  longest sentence: {longest} words (cap {max_sent}) on page {longest_pg}")

    ok = True

    # FKGL guardrail — only where the formula carries signal (fk_enforced, ~age 7+). Below that
    # FKGL is noisy on tiny text, so we don't gate on it at all; the words/page + sentence
    # length + read-aloud judgement carry the weight.
    if fk_enforced and target is not None:
        lo, hi = target - tol, target + tol
        if m.fk_grade > hi:
            ok = False
            print(f"  FAIL: FK grade {m.fk_grade} above target {target} (+/-{tol}). "
                  "Simplify word choice and untangle long sentences — never by chopping "
                  "prose into fragments.")
        elif m.fk_grade < lo - 0.5:
            print(f"  note: FK grade {m.fk_grade} a bit below target {target} (fine for confidence).")
        else:
            print(f"  PASS: FK grade within {target} +/-{tol}.")
    else:
        print("  (early/read-aloud age: FKGL not used — it's unreliable this young; judging by "
              "words/page, sentence length, rhyme/repetition.)")

    # Per-page word caps + longest sentence.
    over_pages = []
    for pg in pages:
        if pg.get("kind") in ("title", "interaction"):
            continue
        wc = len(words(pg.get("text") or ""))
        if wc > max_wpp:
            over_pages.append((pg.get("number"), wc))
    if over_pages:
        ok = False
        print(f"  FAIL: {len(over_pages)} page(s) over the {max_wpp}-word cap: " +
              ", ".join(f"p{n}={c}" for n, c in over_pages))
    else:
        print(f"  PASS: all pages within the {max_wpp}-word cap.")

    if longest > max_sent:
        ok = False
        print(f"  FAIL: longest sentence {longest} words (page {longest_pg}) > cap {max_sent}. "
              "Rewrite it as two natural sentences — do NOT chop it into fragments.")
    else:
        print(f"  PASS: longest sentence within the {max_sent}-word cap.")

    # Anti-telegraphic guard: prose amputated into fragments to duck the caps
    # ("Seoul at night. Bright lights. Palaces glow.") reads like a robot. Only
    # meaningful with enough sentences to average over, and ONLY for ages past the
    # read-aloud years — for ages <=5 short rhythmic refrain lines are a legitimate
    # style, so we don't flag them at all (the human read-aloud pass makes that call).
    min_avg = t["min_avg_sentence_words"]
    total_w = total_s = 0
    for pg in pages:
        if pg.get("kind") in ("title", "end", "interaction"):
            continue
        pm = analyze(pg.get("text") or "")
        if pm.words:
            total_w += pm.words
            total_s += pm.sentences
    avg = total_w / total_s if total_s else 0.0
    if not read_aloud and min_avg and total_s >= 6:
        # The kid is reading these words themselves now; telegram prose is amputated writing —
        # the one firm line (see methodology/reading-pedagogy.md "the telegraphic trap").
        if avg < min_avg:
            ok = False
            print(f"  FAIL: telegraphic prose — sentences average {avg:.1f} words "
                  f"(want >= {min_avg:g} for age {year if isinstance(year, int) else band_id}). "
                  "The fix is NEVER more chopping: join the fragments into flowing sentences "
                  "(and/but/so/then/because) that read aloud like a person telling a story.")
        else:
            print(f"  PASS: prose flows — sentences average {avg:.1f} words.")
    elif total_s:
        print(f"  avg sentence: {avg:.1f} words across {total_s} sentences.")

    # Decodable check.
    if rl.get("decodable"):
        focus = rl.get("decoding_focus", "")
        sight = set(DEFAULT_SIGHT)
        msight = re.search(r"sight[^:]*:\s*([a-z, ]+)", focus.lower())
        if msight:
            sight |= {w.strip() for w in msight.group(1).split(",") if w.strip()}
        flagged = []
        for w in words(text):
            lw = w.lower()
            if lw in sight:
                continue
            # crude: multisyllable words are unlikely to be early-decodable.
            if count_syllables(lw) > 1:
                flagged.append(lw)
        flagged = sorted(set(flagged))
        if flagged:
            ok = False
            print(f"  FAIL (decodable): {len(flagged)} multi-syllable / non-sight words: "
                  + ", ".join(flagged[:20]) + ("..." if len(flagged) > 20 else ""))
        else:
            print("  PASS: decodable text within focus + sight words.")

    print("  => ON TARGET" if ok else "  => NEEDS WORK")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="Measure story reading level.")
    ap.add_argument("story", help="story dir, story.yaml, or <world>/<story>")
    args = ap.parse_args()
    try:
        sy = resolve_story_yaml(args.story)
    except FileNotFoundError as e:
        print(f"! {e}", file=sys.stderr)
        return 2
    return 0 if report(sy) else 1


if __name__ == "__main__":
    raise SystemExit(main())
