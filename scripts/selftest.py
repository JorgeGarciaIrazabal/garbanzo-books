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
from lib.model import ROOT, SCHEMAS, load_world  # noqa: E402
from lib.prompt_assembly import assemble_page_prompt  # noqa: E402

PASS, FAIL = "  \033[32mPASS\033[0m", "  \033[31mFAIL\033[0m"
fails = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global fails
    print(f"{PASS if cond else FAIL}  {name}" + (f"  — {detail}" if detail and not cond else ""))
    if not cond:
        fails += 1


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
    try:
        w = load_world("whispering-woods")
        loaded = True
    except Exception as e:  # noqa: BLE001
        loaded = False
        print("   ", e)
    check("sample world loads", loaded)
    if loaded:
        check("world has locked style block", bool(w.data.get("art_style", {}).get("prompt_style_block")))
        check("world has >=2 characters", len(w.characters) >= 2, f"{len(w.characters)}")
        story = w.stories[0]
        page = next(p for p in story.data["pages"] if (p.get("image", {}) or {}).get("characters_present"))
        ap = assemble_page_prompt(w, story.data, page)
        check("prompt injects character appearance_token", "PIP" in ap.prompt or "OLO" in ap.prompt)
        check("prompt injects world style block",
              "watercolor" in ap.prompt.lower())
        check("prompt carries negative prompt", "photorealism" in ap.negative.lower())
        check("prompt reserves a text zone", "text" in ap.prompt.lower())

    # 4. Validate passes on the workspace.
    r = subprocess.run([sys.executable, "scripts/validate.py"], cwd=ROOT, capture_output=True, text=True)
    check("validate.py exits 0", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])

    # 5. Reading level on target for the sample.
    r = subprocess.run([sys.executable, "scripts/reading_level.py", "whispering-woods/pip-and-the-lost-star"],
                       cwd=ROOT, capture_output=True, text=True)
    check("sample reading level on target", r.returncode == 0, r.stdout[-200:])

    # 6. Site builds and emits the expected structure.
    r = subprocess.run([sys.executable, "scripts/build_site.py"], cwd=ROOT, capture_output=True, text=True)
    check("build_site.py exits 0", r.returncode == 0, r.stderr[-200:])
    site = ROOT / "site"
    for rel in ("index.html", "world/whispering-woods/index.html",
                "story/whispering-woods/pip-and-the-lost-star/index.html",
                "tags/courage/index.html", "assets/reader.js", "search-index.json"):
        check(f"site has {rel}", (site / rel).exists())

    print()
    if fails:
        print(f"\033[31m{fails} check(s) failed.\033[0m")
        return 1
    print("\033[32mAll checks passed.\033[0m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
