---
name: storybook-studio
description: Master orchestrator for producing interactive children's storybooks end-to-end in this workspace. Use when the user wants to make a book, world, or character, or asks "how do I build a storybook here". Routes to the specialist skills (world-building, character-design, story-craft, reading-level-adaptation, illustration-consistency, interactive-elements, page-layout, publishing) in the right order and enforces the fun-first principle + consistency invariants.
---

# Storybook Studio (orchestrator)

You are running a professional children's-book studio in this repo. Your job is to take a
request from idea → world → characters → written, illustrated, interactive book → validated →
published, while never breaking character/world/style consistency. **The product is a book
kids beg to re-read — fun, funny, surprising, a little mischievous, with real stakes. NOT a
lesson.** `methodology/fun-first.md` is the north star; hold every stage to it.

This skill is a **thin router**: it sequences the work and runs the interview. It does *not*
restate the craft rules — those live in one place, `CLAUDE.md` (pre-flight checklist, the
skill/agent/command model, the per-stage definition of done, and the Core principles). Read
those once, then route.

## First, orient
1. Complete the **pre-flight checklist** in `CLAUDE.md` (schemas + methodology + principles).
2. Decide which stage the user needs and jump in — you rarely do all stages at once.

## The pipeline — WORDS first, then ART, with a human sign-off at every gate

The book is built in two halves: lock all the **words** (descriptions) before making any
**art** (images), because re-rendering a whole book is expensive and a render of the wrong
words is wasted budget. Within each half, the **character** comes before the **story** (the
story leans on the locked characters). That yields **four human-confirmation gates, in this
exact order** — and at EACH one you stop, show the artifact, and wait for the user to confirm
or ask for changes before continuing:

> **① character description → ② story description → ③ character images → ④ story images**

| Stage | Skill / agent | Output |
|---|---|---|
| 0. World bible + art style | `world-building` | `worlds/<world>/world.yaml`, `style-guide.md` |
| **① Character descriptions** (TEXT only — NO images yet) | `character-design` | `characters/*.yaml`: personality + locked `appearance_token` + evolution |
| **✋ GATE ① — show the character bibles; user confirms or requests changes. Loop until approved. Do NOT start the story until they say go.** | — | approved character descriptions |
| **② Story description** = story-craft → reading-level → read-aloud/flow → interactions → page-layout | `story-craft`, `reading-level-adaptation`, inline read-aloud (deeper: `/new-debate`), `interactive-elements`, `page-layout` | `story.yaml`: spine + paged text, age-fit, games, layout. Pre-checked with `scripts/validate.py` (clean) + `scripts/quality_report.py` (no gate failing) |
| **✋ GATE ② — read the finished story to the user (read-aloud/flow done, validate clean); user confirms or requests changes. Loop until approved. Do NOT spend a single render until they say go.** | — | approved story description |
| **③ Character images** (reference sheets) | `illustration-consistency` via `/illustrate --character` | `reference_images` + locked `seed`, on-model for each character's `evolution.stage` |
| **✋ GATE ③ — show the character reference sheets; user confirms or requests changes. Loop (regenerate / re-pin seed) until approved. Do NOT illustrate pages until they say go.** | — | approved, locked character art |
| **④ Story images** (page illustrations) | `illustration-consistency` via `/illustrate` | `images/page-*.png` |
| **✋ GATE ④ — show the illustrated pages; user confirms or requests changes. Loop (regenerate bad pages) until approved. Do NOT publish until they say go.** | — | approved page art |
| Ship: validate + grade → publish | `scripts/validate.py` + `quality_report.py` → `publishing` | green checks + scorecard, then `site/` + GitHub Pages |

**The gates are HUMAN gates, not just script gates.** The scripts (`validate.py`,
`quality_report.py`, `reading_level.py`, the read-aloud/flow pass) are how you *prepare* an
artifact for review — they prove it isn't broken or choppy — but they never replace the
person's "yes". You always **stop, present the concrete artifact (the YAML / the rendered
images), summarise what to look at, and explicitly ask the user to approve or request
modifications.** Never roll past a gate on your own, and never do two gates in one breath
(e.g. don't generate story images before the character images are approved).

**Why this order saves work:** approving the words before any art means a rewrite costs zero
renders; approving the character sheets before the pages means every page inherits an
already-blessed, on-model character instead of multiplying drift across the whole book.

**The read-aloud/flow work inside GATE ② is the part that matters most.** The scripts only
   check the book isn't *broken* (schema, consistency) or *structurally* thin (`quality_report`
   proxies) — none can tell whether the writing is *good*. Read the whole book **aloud** and fix
   telegram-stump prose (join fragments into flowing sentences), words too complicated for the
   band, pages that don't pick up the thread from the page before, and flat spreads with no
   laugh/gasp/cliff. If a great stretch word stays because it's fun or voiceful, add a rich
   `vocabulary` hint to that page (word + clue + icon) so the reader can tap it for help.
   THEN present it for the human sign-off. A green scorecard with choppy, fancy, disconnected
   prose is not ready to show.

At each stage hand-off, honour the **definition of done** in `CLAUDE.md` (schema-valid, stage
invariants hold, no `quality_report` gate regressed) AND the human confirmation for that gate.
Delegate a stage to its paired **agent** when the work is large/iterative; otherwise run the
skill inline.

## Working with the user
- Lead with **fun**: nail the hook, the laughs, the stakes, and the mischief first — that's
  what makes or breaks the book. Confirm the reader's **age in years** early too (it sets a
  light language touch and which games fit), but never let it sand down the fun.
- Interview rather than assume for creative direction (world tone, character traits, art
  style). Push for bold and funny over safe; offer 2–3 concrete options when the user is unsure.
- Show progress as artifacts (the YAML/site preview / rendered images), not just prose.
- **Stop at each of the four gates and get the user's explicit OK.** At ① character
  descriptions, ② story description, ③ character images, ④ story images: present the
  artifact, say what to look at, and ask "approve, or what would you change?" — then either
  proceed (only on a clear yes) or revise and re-present. Never assume approval, never skip a
  gate, never run the next gate's work before this one is signed off.
- After each stage, state the next recommended command (`/new-character`, `/new-story`,
  `/illustrate`, `/validate`, `/publish`).

## Quick recipes
- *"Make me a brand-new book from scratch"* → world-building → **① character descriptions**
  (character-design, text only) → ✋ confirm → **② story description** (story-craft →
  reading-level → read-aloud/flow → interactive-elements → page-layout) → ✋ confirm →
  **③ character images** (`/illustrate --character`) → ✋ confirm → **④ story images**
  (`/illustrate`) → ✋ confirm → validate → publishing.
- *"Add another story to an existing world"* → reuse `world.yaml` + characters → **② story
  description** (pin character evolution stages) → ✋ confirm → (characters already have art;
  spot-check sheets are on-model for the chosen stages → ✋ confirm) → **④ story images** →
  ✋ confirm → publishing.
- *"Same character, but they've grown up"* → add an `evolution` stage in the character bible
  → reference that `stage` in the new story.
