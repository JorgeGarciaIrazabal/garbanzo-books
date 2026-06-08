---
name: reading-level-adaptation
description: Lightly age-fit a story's language so the words never get in the way of the fun — roughly right sentence length, words-per-page, and word choice for the age band. A light touch, NOT a reading curriculum. Use to set/check a story's age fit or to make easier/harder variants. Reads methodology/reading-pedagogy.md; optionally checks with scripts/reading_level.py.
---

# Age-fit the language (light touch)

Make sure the words don't block the story — a kid who can't read the sentence can't enjoy the
joke. That's the whole job. Read `methodology/fun-first.md` first, then the short table in
`methodology/reading-pedagogy.md`. **Never** trade a funnier word, a great line, or the pace
to hit a readability number.

## Procedure
1. **Set a rough target.** `story.reading_level.target_fk_grade` (+ `fk_grade_tolerance`), and
   optionally `max_words_per_page` / `max_sentence_words` from the band table. The deeper
   phonics fields (`decoding_focus`, `decodable`) are **optional** — only bother with them if
   you're deliberately making a strict early-reader; most fun books should skip them.
2. **Pass over the page text** with the band table as a guide:
   - Younger bands (0–5): write for the *ear* — rhythm, rhyme, repetition, words fun to *say*.
   - Keep sentences roughly in range and one big idea per page so the picture can carry it.
   - A few giant, ridiculous, delicious stretch words are GOOD — keep them, don't sand them out.
   - Older bands (7–12): let the voice, wordplay, and jokes run; vary sentence shape.
3. **Optional soft check.** `uv run python scripts/reading_level.py worlds/<world>/stories/<slug>`
   reports FKGL, words/page, and longest sentence. Use it only to catch a page that drifted
   *way* too dense — not as a target to optimise toward. If it reads great aloud and a kid that
   age can follow it, it passes whatever the number says.
4. **Multi-level variants (optional).** To publish the same romp at two levels, create sibling
   stories sharing the world/characters/spine with re-fit `text` (tag `level-easy` / `level-fluent`).

## Quality bar
- The words never get in the way of the fun — that's the only one that really matters.
- Sentences/words-per-page are roughly in band (rough, not strict).
- It reads great *aloud* for the younger bands.

## Output
Lightly revised `pages[].text` and a populated `reading_level`. Next: `interactive-elements`.
