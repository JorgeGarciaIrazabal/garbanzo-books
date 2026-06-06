---
name: story-craft
description: Plan and write a well-structured picture-book story using the professional pipeline — premise/hook, the Pixar story spine, deliberate page-turns, ~14-spread pacing, and page-by-page text. Use when writing or restructuring a story. Produces worlds/<world>/stories/<slug>/story.yaml with spine + pages, ready for reading-level adaptation, interactions, layout, and illustration.
---

# Story-craft

Turn an idea into a paced, page-by-page book. Read `methodology/storybook-pipeline.md` first.
This skill owns structure & prose; later skills adapt the language, add interactions, lay out
text, and illustrate.

## Procedure
1. **Pick the world + cast + age band.** Confirm the `age_band` and a target `reading_level`
   (defer the fine-tuning to `reading-level-adaptation`, but set targets now — they shape
   sentence length and word choice). Pin each character's `evolution.stage` for this book.
2. **Hook + emotional truth.** One-sentence `logline` (protagonist + goal + obstacle) and the
   single feeling the book is about. Pressure-test before writing pages.
3. **Build the `spine`** (cause → effect, never coincidence):
   `once_upon_a_time / every_day / until_one_day / because_of_that[] / until_finally /
   ever_since_then`. Make sure each beat *causes* the next, and the protagonist's `flaw`
   drives the middle.
4. **Storyboard the pages.** Aim for the **~14-spread rhythm** for a standard picture book
   (fewer for younger bands). For each page set:
   - `text` — the words on the page (keep within the band's words/page target).
   - `image.prompt` — **scene only** (who/where/action/emotion). Do NOT add style or character
     descriptions; the illustrator injects `appearance_token`s + world style automatically.
     List `characters_present` (slugs).
   - `kind` — title / story / interaction / comprehension / end.
   - **Deliberate page-turns** — end tense spreads on a question/threat so the turn pays off.
5. **Show, don't tell the moral.** Let the resolution dramatize the `theme`/`moral`.
6. **Front/back matter** — title page (page 0) and an end page; optional dedication.
7. **Scaffold & save**: `uv run python scripts/new_story.py <world> "<Title>" --age 5-7` then write
   the pages into `story.yaml`.

## Craft checklist
- [ ] Logline names protagonist, goal, obstacle.
- [ ] Spine beats are causally linked; the flaw drives the middle.
- [ ] Page-turns placed at tension peaks; varied rhythm.
- [ ] Every page advances plot OR character OR world (cut pages that don't).
- [ ] Each `image.prompt` is scene-only with `characters_present` listed.
- [ ] Characters act from their `personality`; nothing contradicts world `rules`/`timeline`.
- [ ] Word count within the age-band target (see reading-pedagogy.md).

## Output
`worlds/<world>/stories/<slug>/story.yaml` with `spine` + `pages[]`.
Next: `reading-level-adaptation`, then `interactive-elements`.
