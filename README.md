# 🌱 Garbanzo Books — an AI studio for interactive children's storybooks

Garbanzo Books is a complete **AI workspace** for producing interactive children's storybooks
that **kids beg to re-read** — funny, surprising, a little mischievous, with real stakes and a
relentless page-turn pull. Full-page illustrations with embedded text, games that are a fun
break (not a drill), language lightly age-fit so the words never block the fun, and obsessive
**character / world / art-style consistency** across a whole series. We make irresistible
romps, **not lessons.** Finished books publish to **GitHub Pages**, organised as
`world → story → tags`. A **dynamic UI** — driven by **OpenCode + a local Ollama model (no API
key)** — lets you make a book just by asking.

---

## Why it's good (the craft is built in)
- **Fun first** — the [north star](methodology/fun-first.md): bold, funny, a little mischievous,
  with real stakes and a page-turn pull. No moral-of-the-story endings; no plot that's secretly
  a lesson. Every other rule below serves the romp.
- **Professional pipeline** — premise → [story spine](methodology/storybook-pipeline.md) →
  ~14-spread pacing → deliberate page-turns → model sheets, style guide & color script.
  Distilled from how top studios/publishers actually work — structure that powers the fun.
- **Lightly age-fit language** — words tuned to a chosen [age band](methodology/reading-pedagogy.md)
  so a kid can read them, never at the cost of a joke or the pace. A light touch, not a curriculum.
- **Consistency, assembled not hoped-for** — image prompts are *built* from a locked world
  style block + each character's `appearance_token` + palette + seed + reference art, so the
  whole series looks like one artist drew it. ([how](methodology/consistency.md))
- **Games, not drills** — seek-and-find, mazes, riddles, music challenges, branching choices —
  a fun break that's part of the story, [matched to the age band](methodology/interactivity.md).
- **Accessible** — dyslexia-friendly type, contrast, legible [text-on-image](methodology/accessibility.md).

## What's in the box
```
schemas/        data contract: world / character / story (JSON Schema)
methodology/    the craft: pipeline · pedagogy · consistency · interactivity · accessibility
.claude/
  skills/       9 craft skills (storybook-studio orchestrator + 8 specialists)
  agents/       7 specialist subagents (world architect, illustration director, validator…)
  commands/     /new-world /new-character /new-story /illustrate /validate /publish /new-book
scripts/        Python tools: scaffold · generate_images · reading_level · validate · build_site
worlds/         your content (the sample "Whispering Woods" world ships included)
site/           generated static site → GitHub Pages
ui/             the dynamic studio UI (Node + OpenCode + local Ollama, no API key)
```

## Quick start
The Python env is managed with [uv](https://docs.astral.sh/uv):
```bash
make setup            # uv sync — creates .venv from pyproject.toml/uv.lock
make test             # self-test the whole toolchain (no API key needed)
make serve            # build + preview the site at http://localhost:8008
```
Every tool runs through the locked env, e.g. `uv run python scripts/validate.py`. No uv? A
generated `requirements.txt` lets you `pip install -r requirements.txt` and run with `python3`
(`make test RUN=python3`).
Make a book with Claude Code (the skills/commands load automatically in this repo):
```
/new-book a shy dragon who learns to share, for ages 5-7
```
…or run the **dynamic UI** and just ask (no API key — uses OpenCode + local Ollama):
```bash
ollama pull minimax-m3:cloud      # one-time; needs ollama + opencode installed
cd ui && npm install && npm start # → http://localhost:4317
```

## The workflow
```
/new-world  →  /new-character  →  /new-story  →  /illustrate  →  /validate  →  /publish
```
Each step is owned by a skill (and an optional agent); `scripts/validate.py` gates publishing
on schema validity, character/world consistency, reading level, interactivity, and
accessibility. See [CLAUDE.md](CLAUDE.md) for the conventions and invariants.

## Publishing to GitHub Pages
`scripts/build_site.py` renders `site/` (worlds index, world hubs + character galleries, the
interactive reader per story, and `tags/` pages). Push to `main` and the included
[GitHub Actions workflow](.github/workflows/deploy-pages.yml) validates, builds, and deploys —
enable **Settings → Pages → Source: GitHub Actions** once.

## The included example
`worlds/whispering-woods/` ships a full, validated world (locked watercolor art style; two
characters with appearance tokens, palettes & an evolution track) and a 16-page illustrated,
interactive early-reader, *Pip and the Lost Star* — proof the whole pipeline runs end-to-end.
Illustrations use Google's **"Nano Banana"** (Gemini `gemini-2.5-flash-image`) by default —
set a free `GEMINI_API_KEY` from [Google AI Studio](https://aistudio.google.com/apikey) and
it anchors each page to the character's reference sheet for consistency. With no key set it
falls back to dependency-free SVG placeholders so everything still runs offline. Every
render is also QC'd by a local Ollama vision model (best-of-3: regenerate with a varied
seed if the first frame doesn't meet the bar) so bad spreads don't ship. Pull a vision
model (`ollama pull gemma3:4b`) and the loop is automatic; pass `--qc-off` to skip.

---
*Numbers in the methodology are targets, not laws — break them deliberately, and for the
right reader.*
