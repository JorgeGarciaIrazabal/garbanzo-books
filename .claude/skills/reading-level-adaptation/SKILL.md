---
name: reading-level-adaptation
description: Adapt a story's language to a target age band and reading level — sentence length, vocabulary tier, words-per-page, decodable vs predictable text, sight words, and phonics focus — then verify with readability tooling. Use when setting/checking a story's reading level, simplifying or leveling text, or producing the same story at multiple reading levels. Reads methodology/reading-pedagogy.md; verifies with scripts/reading_level.py.
---

# Reading-level adaptation

Adapt the *language* without changing the heart of the story. Read
`methodology/reading-pedagogy.md` for the per-band targets and formulas.

## Procedure
1. **Confirm the target.** Set `story.reading_level`:
   - `target_fk_grade` (+ `fk_grade_tolerance`), optional `lexile_range`, `fountas_pinnell`.
   - `max_words_per_page`, `max_sentence_words` from the band table.
   - `decoding_focus` (phonics patterns + allowed sight words), and `decodable: true` for
     independent decoders (bands 5–7+) when you want strict phonics control.
2. **Rewrite page text to hit the band** (use the table in reading-pedagogy.md):
   - Shorten sentences; prefer concrete Tier-1 words for young bands, introduce Tier-2 words
     deliberately (and add them to the page `vocabulary` + glossary).
   - For **0–5**: lean on rhyme, repetition, and predictable refrains (great for read-aloud).
   - For **5–7**: prefer **decodable** text — use words built from taught phonics patterns
     plus listed sight/heart words; keep within `decoding_focus`.
   - For **7–12**: vary sentence structure, allow figurative language, grow vocabulary depth.
   - Keep one idea per page; respect words-per-page caps.
3. **Verify with tooling**:
   `uv run python scripts/reading_level.py worlds/<world>/stories/<slug>` → reports FKGL, Flesch
   Reading Ease, words/page, longest sentence, and (if `decodable`) flags words outside the
   phonics focus. Iterate until within tolerance.
4. **Remember the formula limits** (reading-pedagogy.md): for bands 0–5, FKGL is unreliable —
   judge by words/page, sentence length, rhyme & repetition instead, and treat FKGL as a
   soft guardrail only.
5. **Multi-level variants (optional).** To publish the same story at two levels, create
   sibling stories sharing the world/characters/spine but with different `reading_level` and
   re-leveled `text` (tag them, e.g. `level-easy` / `level-fluent`).

## Quality bar
- FKGL within `target_fk_grade ± tolerance` for bands 5–12.
- No sentence exceeds `max_sentence_words`; no page exceeds `max_words_per_page`.
- If `decodable`, every word is decodable under `decoding_focus` or a listed sight word.
- New/Tier-2 words are captured in page `vocabulary` for the glossary.

## Output
Revised `pages[].text`, populated `reading_level`, and a passing `reading_level.py` report.
Next: `interactive-elements`.
