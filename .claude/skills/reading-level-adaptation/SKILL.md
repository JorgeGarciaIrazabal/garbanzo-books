---
name: reading-level-adaptation
description: Lightly age-fit a story's language so the words never get in the way of the fun — roughly right sentence length, words-per-page, and word choice for the reader's age. A light touch, NOT a reading curriculum, with NO hard rules. Use to set/check a story's age fit or to make easier/harder variants. Reads methodology/reading-pedagogy.md (per-year reader portraits); optionally mirrors with scripts/reading_level.py.
---

# Age-fit the language (light touch)

Make sure the words don't block the story — a kid who can't read the sentence can't enjoy the
joke. That's the whole job. Read `methodology/fun-first.md` first, then the **per-year reader
portraits** in `methodology/reading-pedagogy.md`. There are **no hard rules** here: the
portraits describe what a kid that age can comfortably read so you can aim there. **Never**
trade a funnier word, a great line, or the pace to hit a readability number.

## Procedure
1. **Picture the actual reader by AGE, not band.** Find the story's `target_year` and read
   that age's portrait in `reading-pedagogy.md` — a 5-year-old and a 7-year-old are different
   readers. The portrait's numbers (FK grade, words/page, sentence length) are gentle anchors
   to aim at, not targets to hit. You can optionally record them in
   `story.reading_level.target_fk_grade` / `max_words_per_page` / `max_sentence_words`, but
   they're advisory. The phonics fields (`decoding_focus`, `decodable`) are **optional** —
   only for a deliberately strict early-reader; most fun books skip them.
2. **Pass over the page text** with that age's portrait in mind:
   - Younger (3–6): write for the *ear* — rhythm, rhyme, repetition, words fun to *say*,
     one big idea per page so the picture can carry it.
   - A few giant, ridiculous, delicious stretch words are GOOD — keep them, don't sand them out.
   - Older (8–12): let the voice, wordplay, and jokes run; vary sentence shape boldly.
   - **Simplify by REWRITING, never by amputating.** A too-long sentence becomes two
     natural sentences — not a chain of fragments ("Seoul at night. Bright lights."). This is
     the one firm line, because amputated prose just isn't good writing at any age: it's
     banned in `fun-first.md` and explained in `reading-pedagogy.md` ("the telegraphic trap").
     Every sentence keeps a subject, a verb, and connective tissue (and/but/so/then/because);
     a fragment is a once-in-a-while comic beat, never the house style.
3. **Mark the tricky words as clickable hints.** After the prose is fun and flowing, add a
   `vocabulary` entry to any page that introduces a word the target reader might trip on.
   Keep it fun-first: one or two words per page at most, never a vocabulary worksheet. Use the
   rich object form so the reader can show a kid-friendly clue + read the word aloud:
   ```yaml
   vocabulary:
     - word: impenetrable
       clue: so strong that nothing can get through
       icon: 🧱
   ```
   For a stretch word that's just fun to *say* (e.g. "catastrophe"), a plain string still works
   and becomes a read-aloud button in the text.
4. **Optional soft mirror.** `uv run python scripts/reading_level.py worlds/<world>/stories/<slug>`
   reports FKGL, words/page, and longest sentence against the age. It's a mirror, not a gate —
   the validator's reading checks are advisory (warnings, never publish-blocking). Use it only
   to catch a page that drifted *way* denser than its age. If it reads great aloud and a kid
   that age can follow it, it's right whatever the number says.
5. **Multi-level variants (optional).** To publish the same romp at two ages, create sibling
   stories sharing the world/characters/spine with re-fit `text` (tag `level-easy` / `level-fluent`).

## Quality bar
- The words never get in the way of the fun — that's the only one that really matters.
- The voice fits the age in the portrait (rough, not strict — no number is a gate).
- It reads great *aloud*. If it sounds like a telegram, it fails, whatever the numbers say.
- Tricky words that stay in the story are backed by a clickable clue + read-aloud hint.

## Output
Lightly revised `pages[].text`, a populated `reading_level`, and `pages[].vocabulary` hints for any words the reader might need help with. Next: `interactive-elements`.
