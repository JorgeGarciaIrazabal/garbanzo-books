---
name: story-craft
description: Plan and write a well-structured picture-book story using the professional pipeline — premise/hook, the Pixar story spine, deliberate page-turns, ~14-spread pacing, and page-by-page text. Use when writing or restructuring a story. Produces worlds/<world>/stories/<slug>/story.yaml with spine + pages, ready for reading-level adaptation, interactions, layout, and illustration.
---

# Story-craft

Turn an idea into a paced, page-by-page book that **kids beg to re-read**. Read
`methodology/fun-first.md` first (the north star), then `methodology/storybook-pipeline.md`.
This skill owns structure & prose — but structure serves the fun, never replaces it. A
well-built skeleton with no jokes and no jeopardy is a dead book. Later skills adapt the
language, add games, lay out text, and illustrate.

## Procedure
0. **Load the world in one call**: `uv run python scripts/story_context.py <world>` prints the
   world bible, full cast (personality/voice/catchphrases/stages), existing story slugs, and
   the age-band table — faster than reading each yaml separately.
1. **Pick the world + cast + the two age knobs.** A story has TWO separate targets — never
   conflate them:
   - `target_year` — one number: the age the CONTENT is pitched at (humor, stakes, themes).
   - `age_band` + `reading_level` — who reads the WORDS (sentence length, words/page, word
     choice; defer fine-tuning to `reading-level-adaptation`, but set targets now).
   They can diverge (e.g. `target_year: 7` content in `age_band: 5-7` words). Pin each
   character's `evolution.stage` for this book.
2. **Hook + why it's fun.** One-sentence `logline` (protagonist + goal + obstacle) AND a
   clear answer to "where are the laughs / stakes / mischief / surprise?". Pressure-test by
   pitching it aloud — if it doesn't make you grin or lean in, fix it before writing pages.
   (A feeling underneath is welcome; never spell it out.)
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
   - **Deliberate page-turns** — end spreads on a cliff/threat/uh-oh so the turn *must* happen.
   - **Land a laugh or a gasp on most spreads** — slapstick, a twist, a cheeky narrator aside,
     a running gag paying off. Reach for the fun levers in `fun-first.md` on any flat page.
5. **Write prose that flows — the read-aloud test.** Page text is a storyteller's voice,
   not a telegram. Every sentence has a subject and a verb; sentences connect with
   cause-and-effect words (and, but, so, then, because); shapes vary — a longer rolling
   sentence, then a short punch. NEVER chop prose into fragment-chains
   ("Seoul at night. Bright lights. Palaces glow.") to stay inside a word target — that's
   the **telegraphic trap** (`reading-pedagogy.md`), it's on the fun-first ban list, and
   `reading_level.py` fails it. A lone fragment for comic timing ("Uh oh.") is a spice,
   not the house style. Read every page *aloud*: if it doesn't sound like a person telling
   a great story, rewrite it.
6. **End on the payoff, not a lesson.** Close on the funniest or most satisfying image and
   *stop*. No character explaining what they learned, no "and that's how…" moral. Let a
   naughty hero get away with it (or earn a funnier comeuppance, never a moral one).
7. **Front/back matter** — title page (page 0) and an end page; optional dedication.
8. **Scaffold & save**: `uv run python scripts/new_story.py <world> "<Title>" --age 5-7 --year 6
   --pages 14` to create every page stub (`--age` = reader band, `--year` = content age), then
   fill the content with **JSON patches** — never edit the YAML text directly:
   ```bash
   uv run python scripts/edit_story.py <world>/<slug> meta <<'JSON'
   {"logline": "...", "summary": "...", "spine": {...}, "characters": [...]}
   JSON
   uv run python scripts/edit_story.py <world>/<slug> pages <<'JSON'
   [{"number": 1, "text": "...", "image": {"prompt": "...", "characters_present": ["pip"], "alt": "..."}}]
   JSON
   ```
   Pages merge by `number` (send partial objects, 3-4 pages per call); the tool validates the
   merged document against the schema and refuses to write anything invalid.

## Craft checklist
- [ ] **It's FUN** — laughs, stakes, or mischief land on most spreads; a kid would beg for
      the next page. (This is the gate that matters most — see `fun-first.md`.)
- [ ] **No moral-of-the-story ending**; the plot isn't a values-delivery vehicle.
- [ ] Logline names protagonist, goal, obstacle; the "why it's fun" is clear.
- [ ] Spine beats are causally linked; the flaw drives the middle.
- [ ] Page-turns placed at tension peaks, ending on cliffs/uh-ohs; varied rhythm.
- [ ] Every page advances plot OR character OR world OR a laugh (cut pages that don't).
- [ ] Each `image.prompt` is scene-only with `characters_present` listed.
- [ ] Characters act from their `personality` (let them be naughty/clever/flawed); nothing
      contradicts world `rules`/`timeline`.
- [ ] **The prose flows aloud** — real sentences with subjects, verbs, and connective
      tissue; varied shapes; no telegraphic fragment-chains chasing a readability number.
- [ ] Words roughly age-fit — a light touch, never traded for a joke or the pace.

## Output
`worlds/<world>/stories/<slug>/story.yaml` with `spine` + `pages[]`.
Next: `reading-level-adaptation`, then `interactive-elements`.
