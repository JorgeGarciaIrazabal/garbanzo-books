# Garbanzo Books — AI Storybook Workspace

This repository is an **AI workspace for producing interactive children's storybooks** with
professional-grade craft: strong narrative structure, age/reading-level adaptation, deep
**character / world / style consistency**, full-page illustrations with embedded text, and
small puzzles & games that keep young readers engaged. Finished books are published to
**GitHub Pages**, organised as `world → story → tags`.

## How the system is organised

```
schemas/        JSON Schemas — the data contract (world, character, story)
methodology/    The craft: pro picture-book pipeline + reading pedagogy reference
.claude/
  skills/       Reusable craft procedures (the "how") — invoked by name
  agents/       Specialist subagents (world architect, illustrator, validator…)
  commands/     Slash commands that drive end-to-end workflows
templates/      How to start new content (scaffolders + schema pointers)
scripts/        Python tooling (scaffold, image gen, readability, validate, build site)
worlds/         CONTENT lives here:
  <world>/
    world.yaml              # the world bible + locked art style
    style-guide.md          # human-readable art direction
    characters/<char>.yaml  # character bibles (personality + appearance_token + evolution)
    assets/                 # world-level reference art (model sheets, palettes)
    stories/<story>/
      story.yaml            # the book: spine, pages, interactions, reading targets
      images/               # generated page illustrations
site/           Generated static site (build output → GitHub Pages)
ui/             Dynamic UI server (OpenCode + local Ollama, no API key) — the entrypoint
```

## The data model (read `schemas/` for the full contract)

- **World** (`world.yaml`) — a persistent universe. Holds geography, rules, factions,
  timeline, motifs, themes, and the **`art_style`** block whose `prompt_style_block` +
  `palette` + `negative_prompt` are injected into *every* image so the whole world looks
  like one artist drew it. This is the world-consistency lever.
- **Character** (`characters/*.yaml`) — personality (behaviour/voice consistency), a locked
  **`appearance_token`** (the dense descriptor injected into every image featuring them =
  visual consistency), `reference_images` + `seed` (image anchors), and an **`evolution`**
  track so a character can grow across a series without losing identity.
- **Story** (`stories/*/story.yaml`) — one book: the **`spine`** (story structure), the
  **`reading_level`** targets, the character roster (with each character's evolution
  `stage` for this book), and **`pages[]`**. Each page = embedded `text` + an `image`
  (scene-only prompt — style & character tokens are injected automatically) + an optional
  **`interaction`** (puzzle/game/comprehension beat) + target `vocabulary`.

## Core principles (always uphold these)

1. **Consistency is assembled, not hoped for.** Never write a full image prompt by hand.
   A prompt = `scene` (from the page) + `appearance_token` of each character present +
   the world `prompt_style_block` + `palette` + `negative_prompt`. Use
   `scripts/generate_images.py`, which assembles this for you. Reuse `seed`s and
   `reference_images`.
2. **Personality is a contract.** Characters act from their `personality` (traits,
   motivation, flaws). The world `rules` are inviolable. Continuity follows the `timeline`.
3. **Age-adapt the language, not the heart.** Every story declares an `age_band` and
   `reading_level`. Verify with `scripts/reading_level.py` before publishing. See
   `methodology/reading-pedagogy.md` for per-band targets.
4. **Full-page image, text on top.** Pages are full-bleed illustrations; text sits in a
   reserved zone with a scrim for legibility. Keep that zone clear in the image prompt.
5. **Engagement every few pages.** Interleave interactions (seek-and-find, rhyme-complete,
   choices, comprehension). Match the interaction type to the age band & target skill.
6. **Validate before publish.** `scripts/validate.py` checks schema validity, consistency
   (every character referenced exists; appearance_tokens present; reading level on target;
   images exist) before a book may be marked `published`.

## Typical workflow

```
/new-world      → interview + scaffold a world bible & art style
/new-character  → add a character bible (personality + appearance_token + evolution)
/new-story      → plan the spine, write age-appropriate pages, design interactions
/illustrate     → assemble prompts & generate consistent page images
/validate       → schema + consistency + reading-level checks
/publish        → build the static site and (optionally) deploy to GitHub Pages
```

Or run the whole thing from the **dynamic UI** in `ui/` (the Claude-Agent-SDK entrypoint).

## Conventions

- Slugs are `kebab-case`, unique within their scope. Paths are derived from slugs.
- YAML for human-authored content (worlds/characters/stories); JSON Schema validates it.
- Never hand-edit files under `site/` — they are generated.
- Image files: `worlds/<world>/stories/<story>/images/page-<NN>.png`,
  character refs: `worlds/<world>/characters/<char>.refs/`.
- Dates are absolute (ISO 8601).
- Prefer the scripts/skills over ad-hoc work so consistency invariants are preserved.

## Setup

`uv sync` (or `make setup`) creates the `.venv` from `pyproject.toml`/`uv.lock`; run tools with
`uv run python scripts/...`. (No uv? `pip install -r requirements.txt` + `python3` works too.)
Image generation defaults to Google's
**Nano Banana** (Gemini `gemini-2.5-flash-image`) — set a free `GEMINI_API_KEY` (or
`GOOGLE_API_KEY`) from Google AI Studio. Without a key it emits labeled placeholder art so the
whole pipeline still runs and validates offline. See `.env.example`.
