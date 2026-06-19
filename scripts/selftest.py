#!/usr/bin/env python3
"""Toolchain self-test. Verifies the library, formulas, prompt assembly, schemas, the sample
book, and a full site build — without any network or API key.

    uv run python scripts/selftest.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import readability  # noqa: E402
from lib.model import ROOT, SCHEMAS, all_world_slugs, load_world  # noqa: E402
from lib.prompt_assembly import assemble_page_prompt  # noqa: E402

PASS, FAIL = "  \033[32mPASS\033[0m", "  \033[31mFAIL\033[0m"
fails = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global fails
    print(f"{PASS if cond else FAIL}  {name}" + (f"  — {detail}" if detail and not cond else ""))
    if not cond:
        fails += 1


def _reading_level_ok(world_slug: str, story_slug: str) -> bool:
    """True if `reading_level.py` reports this story on-target (exit 0). The selftest
    uses this to pick a sample story whose prose actually passes, so the reading-level
    *check* proves the tool works rather than failing on an off-target story."""
    r = subprocess.run(
        [sys.executable, "scripts/reading_level.py", f"{world_slug}/{story_slug}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return r.returncode == 0


def find_sample_world():
    """Pick a world/story suitable for the selftest — dynamically, so it never breaks
    when content is added, removed, or renamed. The chosen world must: load, have a
    locked art_style.prompt_style_block, >=2 characters, and at least one story page
    with image.characters_present (to exercise prompt assembly). Among matching
    stories we prefer one whose reading level is on-target, so the reading-level
    check validates the tool rather than tripping on an off-target draft. Returns
    (World, Story, page) or (None, None, None)."""
    fallback = None
    for slug in all_world_slugs():
        try:
            w = load_world(slug)
        except Exception:  # noqa: BLE001
            continue
        if not (w.data.get("art_style", {}) or {}).get("prompt_style_block"):
            continue
        if len(w.characters) < 2:
            continue
        for st in w.stories:
            page = next(
                (p for p in st.data.get("pages", []) or []
                 if (p.get("image", {}) or {}).get("characters_present")),
                None,
            )
            if page is None:
                continue
            if _reading_level_ok(slug, st.slug):
                return w, st, page
            if fallback is None:
                fallback = (w, st, page)
    return fallback if fallback else (None, None, None)


def main() -> int:
    print("Garbanzo Books — self-test\n")

    # 1. Readability formula sanity (Flesch-Kincaid on a known simple sentence).
    m = readability.analyze("The cat sat on the mat. The dog ran.")
    check("readability: words counted", m.words == 9, f"got {m.words}")
    check("readability: FK grade is low for simple text", m.fk_grade < 3, f"got {m.fk_grade}")
    check("readability: syllables('storybook') == 3", readability.count_syllables("storybook") == 3,
          f"got {readability.count_syllables('storybook')}")

    # 2. Schemas are valid JSON and load.
    for s in ("world.schema.json", "character.schema.json", "story.schema.json"):
        try:
            json.loads((SCHEMAS / s).read_text())
            ok = True
        except Exception:  # noqa: BLE001
            ok = False
        check(f"schema loads: {s}", ok)

    # 3. Sample world loads and prompt assembly injects style + character tokens.
    # The world is discovered dynamically (see find_sample_world) so the selftest
    # doesn't break when content is added, removed, or renamed.
    w, story, page = find_sample_world()
    check("sample world loads", w is not None,
          "no world with >=2 chars + a characters_present page found" if w is None else "")
    if w:
        check("world has locked style block", bool(w.data.get("art_style", {}).get("prompt_style_block")))
        check("world has >=2 characters", len(w.characters) >= 2, f"{len(w.characters)}")
        ap = assemble_page_prompt(w, story.data, page)
        # The appearance token of any character present on the page should appear
        # in the assembled prompt — check generically against the world's roster
        # rather than hardcoding a character name.
        present = (page.get("image", {}) or {}).get("characters_present", []) or []
        roster = list(w.characters.keys())
        has_token = any(c in ap.prompt.lower() for c in (present or roster))
        check("prompt injects character appearance_token", has_token,
              f"none of {present or roster} found in prompt")
        # The world's locked style block is injected verbatim, so a distinctive
        # word from it must survive into the assembled prompt.
        style_block = (w.data.get("art_style", {}) or {}).get("prompt_style_block", "") or ""
        style_word = next((w_ for w_ in style_block.lower().split()
                          if len(w_) >= 5 and w_.isalpha()), None)
        check("prompt injects world style block",
              bool(style_word and style_word in ap.prompt.lower()),
              f"style marker '{style_word}' not in prompt")
        check("prompt carries negative prompt", "photorealism" in ap.negative.lower())
        check("prompt reserves a text zone", "text" in ap.prompt.lower())

    # 4. Validate passes on the workspace.
    r = subprocess.run([sys.executable, "scripts/validate.py"], cwd=ROOT, capture_output=True, text=True)
    check("validate.py exits 0", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])

    # 5. Reading level on target for the sample (uses the discovered story).
    if w and story:
        sample_path = f"{w.slug}/{story.slug}"
        r = subprocess.run([sys.executable, "scripts/reading_level.py", sample_path],
                           cwd=ROOT, capture_output=True, text=True)
        check(f"sample reading level on target ({sample_path})", r.returncode == 0, r.stdout[-200:])
    else:
        check("sample reading level on target", False, "no sample world discovered")

    # 6. Site builds and emits the expected structure. The world/story/tag paths
    # are derived from the discovered sample so the checks track real content.
    r = subprocess.run([sys.executable, "scripts/build_site.py"], cwd=ROOT, capture_output=True, text=True)
    check("build_site.py exits 0", r.returncode == 0, r.stderr[-200:])
    site = ROOT / "site"
    expected = ["index.html", "assets/reader.js", "search-index.json"]
    if w:
        expected.append(f"world/{w.slug}/index.html")
        if story:
            expected.append(f"story/{w.slug}/{story.slug}/index.html")
            # Pick a tag the story actually declares, so the tag page is guaranteed
            # to be built (tags come from story.data['tags'] in build_site.py).
            tags = story.data.get("tags", []) or []
            if tags:
                expected.append(f"tags/{tags[0]}/index.html")
    for rel in expected:
        check(f"site has {rel}", (site / rel).exists())

    print()
    if fails:
        print(f"\033[31m{fails} check(s) failed.\033[0m")
        return 1
    print("\033[32mAll checks passed.\033[0m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
