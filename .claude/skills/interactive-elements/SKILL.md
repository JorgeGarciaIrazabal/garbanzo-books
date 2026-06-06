---
name: interactive-elements
description: Design small puzzles, games, and participation beats (seek-and-find, rhyme-complete, spot-the-difference, mazes, riddles, comprehension questions, branching choices, sound-hunts, etc.) that keep young readers engaged AND reinforce a target reading skill — matched to the story's age band. Use when adding interactivity to a story. Writes interaction blocks onto pages per schemas/story.schema.json.
---

# Interactive elements

Add the "small puzzles, games, and little actionable things" that keep readers hooked while
building reading skills. Read `methodology/interactivity.md` (the age→interaction map and
payload shapes) first.

## Procedure
1. **Match to the age band.** Use the mapping table — e.g. rhyme-complete & call-and-response
   for 3–5; seek-and-find, sound-hunt, spot-the-difference for 5–7; mazes, riddles, branching
   choices, comprehension for 7–12. Branching needs reading independence (7+).
2. **Pace them.** Interleave roughly one interaction every 2–4 pages, placed at natural
   beats — never interrupting an emotional climax. Note them in `interactions_summary`.
3. **Tie each to its page.** A seek-and-find hunts for things actually in *that* illustration;
   a rhyme-complete uses the page's own rhyme; a comprehension question is about what just
   happened. Add a matching `interaction` block to the page:
   - `type`, `prompt` (one clear, age-appropriate instruction), `skill` (a reading pillar or
     `engagement`), `data` (type-specific payload — see interactivity.md shapes), and
     `feedback.correct` / `feedback.try_again`.
4. **Always winnable.** Provide gentle "try again" feedback; never a dead end or fail state.
   For `choice`/branching, every `goto` must point to a real page and all branches must
   eventually reach an end page.
5. **Reinforce skills deliberately.** Cover a spread of the five pillars across the book
   (phonemic awareness, phonics, fluency, vocabulary, comprehension), not just engagement.
6. **Co-reader prompts.** For read-aloud bands, also set page `reading_notes` with a question
   the adult can ask.

## Decode-skill builders (favour these for 5–9)
- `rhyme-complete`, `sound-hunt`, `word-match`, `trace-letter` → phonemic awareness / phonics.
- `comprehension-question`, `drag-order` (sequencing) → comprehension.
- `seek-and-find`, `riddle` → vocabulary & attention.

## Quality bar
- [ ] Each interaction's `data` matches its `type`'s shape (validator checks this).
- [ ] Instruction language is within the story's reading level.
- [ ] Every branching `goto` resolves to a real page; no dead ends.
- [ ] The book covers ≥3 of the five reading pillars across its interactions.
- [ ] Interactions sit at natural beats, not emotional peaks.

## Output
`interaction` blocks on the relevant pages + `interactions_summary`. The site reader runtime
(`publishing`) renders these as playable widgets. Next: `page-layout`.
