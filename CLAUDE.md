# Garbanzo Books — AI Storybook Workspace

This repository is an **AI workspace for producing interactive children's storybooks** that
kids beg to re-read — **fun, funny, surprising, a little mischievous, with real stakes and
a relentless page-turn pull.** We make irresistible romps, NOT lessons. Professional craft
(narrative structure, deep **character / world / style consistency**, full-page illustrations
with embedded text, and small games that are a fun break, not a drill) is all in service of
that one goal: make kids *love reading*. Finished books are published to **GitHub Pages**,
organised as `world → story → tags`.

**The north star is `methodology/fun-first.md`. Read it before writing anything. It outranks
every other rule here.**

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
  **age knob** — **`target_year`** (one number, the reader's AGE in years): it pitches the
  CONTENT (humor, stakes, themes) AND, via the per-year curve in `scripts/lib/readability.py`,
  the advisory `reading_level` anchors for the WORDS (sentence length, words/page, word choice).
  Books are chosen by year, **not by age band** (the old `age_band` field is deprecated/derived).
  Plus the character roster (with each character's evolution `stage` for this book), and
  **`pages[]`**. Each page = embedded `text` + an `image`
  (scene-only prompt — style & character tokens are injected automatically) + an optional
  **`interaction`** (puzzle/game/comprehension beat) + target `vocabulary`.

## Core principles (always uphold these)

1. **Fun is the whole job.** We make books kids beg to re-read — funny, surprising, a
   little mischievous, with real stakes and a page-turn pull. We are NOT in the lesson
   business: no moral-of-the-story endings, no plot that's secretly a values delivery
   vehicle, no sanded-down conflict-free niceness. If a choice trades delight for a tidy
   message, kill the message. `methodology/fun-first.md` is the north star every other
   rule below serves.
2. **Consistency is assembled, not hoped for.** Never write a full image prompt by hand.
   A prompt = `scene` (from the page) + `appearance_token` of each character present +
   the world `prompt_style_block` + `palette` + `negative_prompt`. Use
   `scripts/generate_images.py`, which assembles this for you. Reuse `seed`s and
   `reference_images`.
3. **Personality is a contract — and let them be naughty.** Characters act from their
   `personality` (traits, motivation, flaws). Heroes can scheme, break rules, talk back,
   and make a glorious mess — mischief is funny, not a crime to be punished on the last
   page. The world `rules` are inviolable; continuity follows the `timeline`.
4. **Age-fit the words, never the fun.** Pick words a kid that age can actually read so
   nothing blocks the story — short sentences for the little ones, richer language as they
   grow. That's a *light touch*, not a curriculum. Never sand down a joke, a great word, or
   the excitement to hit a readability number.
5. **Full-page image, text on top.** Pages are full-bleed illustrations; text sits in a
   reserved zone with a scrim for legibility. Keep that zone clear in the image prompt.
6. **Games are optional add-ons — the story is the product.** Interleave interactions as
   *games* that are a delightful 20–60-second break, never a hidden reading drill. **REAL
   games only:** every game in a new book is from the `arcade-*` family on the embedded game
   engine — fullscreen, real-time, physics, skinned by the story — twelve mechanics:
   `snake`, `shoot`, `maze`, `build`, `whack`, `bounce`, `catch`, `flap`, `run`, `pop`,
   `toss`, `steer`. Match the game's verb to the page's verb and vary the mechanics (≥3
   kinds per book). Legacy minigames (drag-and-drop, find-in-picture, tap boards, jigsaws,
   quizzes, `custom`) survive in already-published books only — never in a new story (the
   validator warns; the quality gate flags). Preview any game live in the Game Lab
   (`make game-lab`). And a game **never changes the story or the art**:
   it must not advance the plot, gate a page, or require editing `page.text` or an `image.prompt`;
   the book must be a complete, satisfying read for a kid who skips every game. Add games on top
   of a finished story + finished art; match the game to the story beat, not to a skill quota.
7. **Validate before publish.** `scripts/validate.py` checks schema validity and consistency
   (every character referenced exists; appearance_tokens present; images exist) before a book
   may be marked `published`. `scripts/quality_report.py` then grades *how good* the book is
   against the pipeline gates — the first of which is simply: **is it fun?**

## Before acting (pre-flight)

**Every skill and agent shares this checklist — read it once here instead of each restating
its own.** Before producing or editing any world/character/story:

1. Read the **schema** for what you're touching (`schemas/world|character|story.schema.json`) —
   it is the data contract.
2. Read **`methodology/fun-first.md` first — it's the north star** — then the doc(s) relevant
   to the stage (`methodology/`): `storybook-pipeline.md` (structure & gates), `reading-pedagogy.md`
   (light-touch age-fit of language), `consistency.md` (visual + behavioural identity), `interactivity.md`
   (games), `accessibility.md` (legible text-on-image).
3. Re-read the **Core principles** above — they are inviolable (fun is the whole job,
   consistency is assembled, personality is a contract, age-fit the words not the fun).
4. Load the owning `world.yaml` (+ any referenced `characters/*.yaml`) so you inherit the locked
   tone, art style, rules, and appearance tokens. Never invent details that contradict them.

A specialist skill/agent may name the *one* methodology doc most central to its craft, but it
should point here rather than maintain its own divergent read-list.

## Skills, agents, and commands

Three layers, one job each — don't confuse them:

- **Skill** (`.claude/skills/<name>/SKILL.md`) — *the procedure*: the how-to for one craft
  (world-building, character-design, story-craft, …). The source of method.
- **Agent** (`.claude/agents/<name>.md`) — *a delegated worker* that runs a skill in its **own
  context window**. Use one when a stage is large or iterative and you want it handled
  independently; for a quick single-author pass, just run the skill inline. An agent adds
  isolation, not a different method — it follows the same skill. (`book-validator` is the
  exception: a read-only QA *gate*, not a craft specialist.)
- **Command** (`.claude/commands/<name>.md`) — *the user entry point* (`/new-world`, `/new-story`,
  …) that kicks off a skill or the orchestrator.

`page-layout` has no paired agent by design — it always runs inline as part of a story pass.

## Definition of done (every stage)

A stage is not "done" — and must not hand off to the next — until:

1. The artifact is **schema-valid** (`uv run python scripts/validate.py worlds/<world>` reports no
   new failures for it).
2. Its **stage-specific invariants** hold (e.g. reading level on target after leveling; every page
   illustrated before publish).
3. For a finished book, `uv run python scripts/quality_report.py <world>/<story>` is reviewed and
   no gate regressed.
4. For a story, the **read-aloud & flow gate** passes — the single most important check, and the
   one no script can make for you. Read the whole book aloud and confirm: the prose flows (no
   telegraphic sentence-stumps), the words are simple enough for the band (no fancy-word
   stuffing — there is no per-page "vocabulary" target), every page picks up the thread from the
   one before, and a laugh/gasp/cliff lands on most spreads. The scripts only prove a book isn't
   *broken* or structurally thin; they cannot tell you it's *good*. A green scorecard with
   choppy, fancy, disconnected prose is NOT done. Deeper pass: `/new-debate <world>/<story>`.

Never mark a story `published` with outstanding validator failures — the publish gate blocks it.

## Building a book: WORDS first, then ART — four human-confirmed gates

A book is produced in two halves — lock all the **words** before making any **art** (a render
of the wrong words is wasted budget) — and within each half the **character** precedes the
**story**. That gives **four gates, in this exact order, each ending in a HUMAN sign-off**:

> **① character description → ② story description → ③ character images → ④ story images**

At every gate the agent **stops, shows the concrete artifact (the YAML / the rendered images),
and asks the user to approve or request modifications** — and does NOT proceed (or start the
next gate's work) until the user confirms. The scripts (`validate.py`, `quality_report.py`,
`reading_level.py`, the read-aloud/flow pass) *prepare* an artifact for review; they never
replace the person's "yes". The `storybook-studio` skill owns the full sequence; the commands
below each own one or two gates.

## Typical workflow

```
/new-world      → interview + scaffold a world bible & art style
/new-character  → GATE ① write the character bible (text only) → human confirms
/new-story      → GATE ② plan the spine, write pages, age-fit, games, layout → human confirms
/illustrate --character …  → GATE ③ generate character reference sheets → human confirms
/illustrate <world>/<story> → GATE ④ generate page images → human confirms
/validate       → schema + consistency + reading-level checks
/publish        → build the static site and (optionally) deploy to GitHub Pages
```

Or run the whole thing end-to-end with `/new-book` (it walks all four gates), or from the
**dynamic UI** in `ui/` (the Claude-Agent-SDK entrypoint).

## Conventions

- Slugs are `kebab-case`, unique within their scope. Paths are derived from slugs.
- YAML for human-authored content (worlds/characters/stories); JSON Schema validates it.
- **Content YAML is created by the scaffolders and edited via JSON patches — never as raw
  text.** `scripts/edit_world.py`, `scripts/edit_character.py` and `scripts/edit_story.py`
  take a small JSON payload on stdin (heredoc) or `--file`, deep-merge it (story pages merge
  by `number`; JSON `null` deletes a key; other lists replace), validate the merged document
  against the schema, and write atomically. A bad patch changes nothing and reports every
  schema error at once — so a broken YAML file on disk is impossible.
- Never hand-edit files under `site/` or `site_publish/` — they are generated.
- Image files: `worlds/<world>/stories/<story>/images/page-<NN>.png`,
  character refs: `worlds/<world>/characters/<char>.refs/`.
- Dates are absolute (ISO 8601).
- Prefer the scripts/skills over ad-hoc work so consistency invariants are preserved.

## Preview vs Publish (the two-build pattern)

There are TWO ways to build the site, and they go to different places — this is intentional.

| Build      | What it includes | Where it lands   | Used by |
| ---------- | ---------------- | ---------------- | ------- |
| **Preview** (studio) | published + drafts | `./site/`      | The in-app "Studio preview" tab in `ui/`. Lets the author browse their WIP. **NEVER deployed** — drafts are not for end users. |
| **Publish** (public) | published only     | `./site_publish/` | The in-app "Public preview" tab in `ui/`. The EXACT shape GitHub Pages will deploy. |
| **CI** (deploy-pages workflow) | published only | `./site/`  | What GitHub Pages actually serves. The workflow always builds published-only — drafts can never leak to the public site. |

In the studio UI the whole flow is button-driven and non-agentic (the buttons call the
scripts directly via the FastAPI server — no need to ask the AI to "build" or "publish"):

- **🚀 Publish / ⏏ Unpublish on each library card** — flips ONE story between draft and
  published via `scripts/publish_story.py`, which runs the FULL validator gate first, so a
  broken book can never be flipped. The studio then rebuilds both previews automatically.
- **🔨 Rebuild** (Preview tab) — studio preview, drafts included.
- **🔨 Build** then **🚀 Deploy** (Publish tab) — build the published-only site, then
  commit & push from the server (`/api/deploy`); the push triggers the deploy-pages
  workflow. Validate/quality remain available as small check buttons on the same tab, and
  the manual commands (`git push`, `gh workflow run deploy-pages.yml`) sit in a fold-out.

Library cards in the studio show all stories (drafts + published) with a clear `draft` /
`published` pill. Drafts link to the studio preview build (`/preview/...`); published stories
link straight to the public preview build (`/publish-preview/...`) — so the "Read" button
never lands the user on a 404.

CLI equivalents:
```bash
# Publish/unpublish one story (runs the validator gate before publishing)
uv run python scripts/publish_story.py <world>/<story> [--draft]

# Studio preview — drafts included, into ./site/
uv run python scripts/build_site.py --include-drafts

# Public preview — published only, into ./site_publish/
uv run python scripts/build_site.py --out site_publish

# What GitHub Pages actually gets (CI runs this)
uv run python scripts/build_site.py
```

## Image generation key — ALWAYS CHECK FIRST

Before running `/illustrate` (or anything that calls `scripts/generate_images.py`),
verify the image-gen key is present:

```bash
make check-gemini
```

- ✓ key found → `/illustrate` will render real images with the Nano Banana provider
- ✗ key missing → `/illustrate` falls back to labeled SVG placeholders, and the book
  can't actually be marked `published` without the user adding a key

The key lives in `.env` as `GEMINI_API_KEY=...` (or `GOOGLE_API_KEY=...`). A real
exported env var beats the .env value. A blank exported value is treated as unset,
so the .env value always fills in.

The server (`ui/server.py`) loads `.env` exactly the same way at startup, and every
subprocess it spawns (including the agent's tool calls) inherits the result. So
restarting `make ui` is required after editing `.env` for the new key to reach the
agent's image-generation calls.

If the key is missing AND the user asked for a new book, do NOT silently switch to
placeholders — run `make check-gemini`, report the result, and ask the user how to
proceed (e.g. "Add a key to `.env` and I'll re-run, or shall I generate placeholders
for now?").

## Setup

`uv sync` (or `make setup`) creates the `.venv` from `pyproject.toml`/`uv.lock`; run tools with
`uv run python scripts/...`. (No uv? `pip install -r requirements.txt` + `python3` works too.)
Image generation defaults to Google's
**Nano Banana** (Gemini `gemini-2.5-flash-image`) — set a free `GEMINI_API_KEY` (or
`GOOGLE_API_KEY`) from Google AI Studio. Without a key it emits labeled placeholder art so the
whole pipeline still runs and validates offline. See `.env.example`.
