---
name: interactive-elements
description: Design small games, puzzles, and participation beats that give kids a FUN BREAK from reading while deepening the story — logic puzzles, sneaky math, music challenges, mazes, seek-and-find, memory, sorting, branching choices, and more — matched to the age band. Use when adding interactivity to a story. Writes interaction blocks onto pages per schemas/story.schema.json.
---

# Interactive elements

An interaction is a **game** — a few-second fun break where the child *does* something
delightful that is *about* what just happened in the story. It's part of the romp, not a
hidden drill. Read `methodology/fun-first.md` (the north star), then
`methodology/interactivity.md` (the mechanic→age map and exact payload shapes).

## Mindset: would a kid play this for fun?
- Think "what would be **fun** here?", never "what reading drill fits?". A page can carry a
  logic puzzle, a maze, a memory game, a music challenge (play the dragon's song back), a
  mystery, a "help the hero choose" branch, or a bit of sneaky math (counting, patterns,
  sorting by size) — pick whatever's the most fun for this beat.
- Pour the story's flavour into the wording. Not "Order by size" → "Line up Pip's flames,
  biggest first!". The mechanic is the engine; the story is the skin.
- If a game is only there to "practise a skill" and wouldn't be fun on its own, cut it.
- Vary the mechanics across the book — don't ship six multiple-choice questions. Mix a search,
  a logic puzzle, a music beat, a sorting game, a branch.
- The renderer plays every `type` fully (taps, drags, a real maze, audio melodies, canvas
  letter-tracing, confetti on success). Choose the `type` whose mechanic matches your idea.

## Procedure
1. **Find the beat.** Place one interaction every 2–4 pages at a natural pause — never on an
   emotional climax. Note them in `interactions_summary`.
2. **Pick the mechanic for the moment** (see the table in interactivity.md):
   comprehension → `comprehension-question` / `drag-order` / `choice`; logic/math → `maze` /
   `sorting` / `pattern` / `odd-one-out` / `counting`; phonics → `sound-hunt` / `rhyme-complete`
   / `trace-letter`; music → `melody`; attention → `seek-and-find` / `spot-the-difference`;
   surprise → `tap-to-reveal` / `riddle` / `coloring`.
3. **Tie it to *this* page.** The game uses things actually in the illustration / the rhyme on
   the page / the event that just happened.
4. **Write the block:** `type`, `prompt` (one clear, in-voice instruction), `data` (match the
   exact shape in interactivity.md), and warm `feedback.correct` / `feedback.try_again`.
   `skill` is an optional internal label (use `engagement` by default) — it must never leak
   into what the child sees.
5. **Always winnable.** Never a dead end or fail state. For `choice`/branching, every `goto`
   points to a real page and all branches still reach an ending. (The reader auto-celebrates
   wins and gives gentle retries — your `feedback` text is the voice of that.)
6. **Co-reader prompts.** For read-aloud bands, set page `reading_notes` with a question to ask.

## Match to the age band
- **3–5:** one-step games — `tap-to-reveal`, `rhyme-complete`, `counting`, simple `seek-and-find`,
  `coloring`, easy `memory`/`sorting` (2 bins).
- **5–7:** the sweet spot for `sound-hunt`, `spot-the-difference`, `word-match`, `pattern`,
  `odd-one-out`, small `maze`, `melody`.
- **7–12:** layer it — multi-step `maze`, multi-bin `sorting`, number `pattern`s (sneaky math),
  longer `melody`, branching `choice`, sequencing with `drag-order`.

## Keep the games varied
Mix the *kinds* of fun across the book — a search, a maze, a music beat, a sorting game, a
branch, a riddle. Don't ship six multiple-choice questions. Variety is about fun and surprise,
not about ticking skill boxes.

## Quality bar
- [ ] Each game would be **fun on its own** — a kid would play it even outside the book.
- [ ] Mechanics are **varied** across the book (not all quizzes).
- [ ] Each interaction's `data` matches its `type`'s shape (the validator checks required keys).
- [ ] Instruction is short, in the story's voice, readable at the band.
- [ ] Each game is tied to its page; nothing reads like a worksheet.
- [ ] Every branching `goto` resolves to a real page; no dead ends.
- [ ] Interactions sit at natural beats, not emotional peaks.

## Output
`interaction` blocks on the relevant pages + `interactions_summary`. The site reader runtime
(`publishing`) renders these as playable widgets with animations and celebration. Next:
`page-layout`.
