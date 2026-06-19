---
description: Write a new interactive storybook in a world, end-to-end (spine → pages → reading level → interactions → layout).
argument-hint: <world-slug> <story title/idea> [--year 6]
---

Use the **storybook-studio** orchestrator to write a new story in world **$1** from this
brief: **$ARGUMENTS**

Lead with **fun** (read `methodology/fun-first.md`, the north star — funny, surprising, real
stakes, a little mischief, NO moral-of-the-story ending).

This command is **gate ② (story description)** in the studio's four-gate flow
(① character description → ② story description → ③ character images → ④ story images). It
assumes the characters this story uses already have approved **descriptions** (locked
`appearance_token` + evolution). If a needed character doesn't exist yet, make it first with
`/new-character` and get its bible confirmed (gate ①) before writing the story. **Generate no
images here** — that's gates ③/④, after the words are signed off.

Run the stages in order, delegating to the specialist skills/agents:
1. **story-craft** — confirm the reader's **age** (`--year N`) & cast (pin each character's
   `evolution.stage`); nail the hook and "why it's fun", then write the `logline`, `spine`, and
   `pages[]` at the ~14-spread rhythm with scene-only image prompts. Scaffold:
   `uv run python scripts/new_story.py <world> "<Title>" --year <N> [--read-mode read_aloud|solo]`.
   **For a young age (~4–8), also confirm read mode up front** — read *aloud* by a grown-up (rich
   words welcome, generous words/page) or read *solo* by the kid (high-frequency / decodable words,
   stretch words rare, **tighter words/page** — e.g. age 5 ≈ 25 vs ≈ 55)? Pass `--read-mode` to set
   it (it lands in `reading_level.read_mode`; default: read-aloud for ≤5, solo from 6). Ask the user
   if the brief doesn't say; it sets the vocabulary posture AND the per-page cap for the whole book
   (see "Read-aloud or reading it alone?" in `reading-pedagogy.md`).
2. **reading-level-adaptation** — a light age-fit pass so the words don't block the fun. Keep
   word choice simple for the age: don't reach for fancy/complicated words (there is NO
   per-page "vocabulary" target any more — write for fun first). Spot-check with
   `uv run python scripts/reading_level.py <story-dir>` — if it flags telegraphic prose, fix by
   joining fragments into flowing sentences, NEVER by chopping further.
3. **Read-aloud & flow pass — the qualitative gate (DO NOT SKIP).** This is the gate that
   actually decides if the book is good; the structural scripts only check it isn't *broken*.
   Read the whole book **aloud**, page by page, and fix:
   - **Telegraphic / artificial prose** — any sentence-stump chain ("Midnight-blue robe.
     Star-gold embroidery."); rewrite as flowing sentences a person would actually say.
   - **Complicated words** — swap any word a kid that age would stumble on for the simplest
     word that still has personality. If a great word stays because it's fun or the voice needs
     it, add a rich `vocabulary` hint to that page so the reader can tap it for a clue and a
     read-aloud:
     ```yaml
     vocabulary:
       - word: impenetrable
         clue: so strong that nothing can get through it
         icon: 🧱
     ```
   - **Disconnected pages** — every page should pick up the thread from the one before
     (cause/effect/"and so"/"but then") and end on a pull to turn. Cut or rewrite pages that
     read as isolated vignettes.
   - **Flat spreads** — make sure a laugh, gasp, or cliff lands on most spreads (`fun-first.md`).
   For a deeper, adversarial pass, run **`/new-debate <world>/<story>`** (3 critic personas).
   A book that passes `validate.py` + `quality_report.py` but reads flat or choppy is NOT done.
4. **interactive-elements** — add OPTIONAL games as add-ons **on top of the finished story**,
   matched to a page's beat (not to a quota — there is no games-per-page target). **New books
   use REAL games only** — the `arcade-*` family — ≥3 different mechanics, each winnable with
   warm feedback. A game must NEVER change `page.text` or the art, NEVER advance/gate the plot,
   and NEVER live on its own blank-text page that interrupts the read — put it on a story page.
   The book must read as a complete, satisfying story with every game skipped.
5. **page-layout** — set `layout` (text_position + text_align + scrim) + alt text per page.
6. **Prepare the story for sign-off.** The words and games are final now. Run
   `uv run python scripts/validate.py worlds/<world>/stories/<story>` (must be clean) and
   `uv run python scripts/quality_report.py <world>/<story>` (no gate failing), and do the
   read-aloud/flow pass (step 3) one last time. The scripts only prove it isn't broken — your
   read-aloud judgement is what proves it's good. Fix anything flat, choppy, or fancy here.
7. **✋ GATE ② — human confirmation (DO NOT SKIP).** Present the finished story to the user —
   read it to them and summarise what to look at — and explicitly ask them to **approve or
   request modifications**. Do not move toward images until they say go; if they ask for
   changes, revise and re-present. Spending image budget on un-approved words is the waste
   this gate exists to prevent.
8. Only after the user approves: the images come next, in **two more human-gated steps** —
   **③ character images** (`/illustrate --character <world>/<char>` for any character whose
   reference sheet/seed isn't locked yet → user confirms the sheets), then **④ story images**
   (`/illustrate <world>/<story>` → user confirms the pages) — then `/validate` and `/publish`.

Keep characters in voice and never contradict the world `rules`/`timeline`. Validate with
`uv run python scripts/validate.py worlds/<world>/stories/<story>` at the end.
