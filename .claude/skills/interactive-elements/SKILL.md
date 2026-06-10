---
name: interactive-elements
description: Design small games and puzzles that give kids an OPTIONAL fun break — games on the illustration (hidden-object, tap-on-art), true drag-and-drop (sorting, jigsaw, dress-up), drawing, spatial puzzles, music/rhythm, memory, branching choices, and bespoke `custom` games — matched to the age band. Games are add-ons that NEVER change the story text or art. Use when adding interactivity to a finished story. Writes interaction blocks onto pages per schemas/story.schema.json.
---

# Interactive elements

An interaction is a **game** — a few-second fun break where the child *does* something
delightful that is *about* what just happened in the story. It's part of the romp, not a
hidden drill. Read `methodology/fun-first.md` (the north star), then
`methodology/interactivity.md` (the mechanic→age map and exact payload shapes).

## The story is the product; games are optional add-ons
The book must be a complete, satisfying read for a kid who plays **zero** games. So a game:
- **never changes the story** — it doesn't advance the plot, reveal what the text doesn't, or
  gate the next page; adding/removing a game must NOT require touching `page.text`;
- **never changes the illustrations** — the art is drawn for the *story*; a game only *uses*
  what the picture already shows, and must never dictate the art or require editing an
  `image.prompt` / re-illustrating. If the game needs something not in the art, pick a different
  game, not a different picture;
- is **skippable** — the reader can ignore any interaction and read straight on.
You are adding games **on top of a finished story and finished art** — never editing either.
(The one exception is a branching `choice`, a real narrative fork; use it rarely and keep the
main path a complete story.)

## Mindset: would a kid play this for fun?
- Think "what would be **fun** here?", never "what reading drill fits?".
- **The story's biggest action beat deserves a REAL game.** The `arcade-*` family runs on an
  embedded game engine — fullscreen, real-time, physics, played over the page's own art:
  `arcade-catch` (things fall), `arcade-flap` (flying), `arcade-run` (chase/escape),
  `arcade-pop` (a sky full of poppables), `arcade-toss` (throwing/aiming), `arcade-steer`
  (swoop and collect). Skin EVERY noun from the page (player/catch/avoid/target are emoji
  from the story); use 1–2 per book, on the biggest beats. See "Arcade games" in
  interactivity.md for shapes + guarantees (always winnable, assist ladder, calm fallback).
- **Rich first, quizzes last.** Lead with games where the kid *does* something: plays ON the
  picture (`hidden-object`, `tap-on-art`, `hotspot-reveal`, `place-on-scene`), drags things
  (`drag-sort`, `drag-match`, `jigsaw`, `dress-up`, `feed-the-thing`), rebuilds the art
  (`jigsaw`, `sliding-puzzle`), draws (`connect-dots`, `scratch-reveal`), or makes music
  (`rhythm-tap`, `song-builder`). Reach for a multiple-choice quiz only when nothing richer
  fits. **Every book needs ≥1 rich game** (the gate checks this; arcade games count).
- **No built-in fits? Invent one with `custom`** — declare `elements` + a `win` condition and
  the engine interprets it (see "Inventing a game from scratch" in interactivity.md). Keep it
  always-winnable (the `custom` model has no fail state by design).
- Pour the story's flavour into the wording. Not "Order by size" → "Line up Pip's flames,
  biggest first!". The mechanic is the engine; the story is the skin.
- If a game is only there to "practise a skill" and wouldn't be fun on its own, cut it.
- Vary the mechanics across the book — don't ship six multiple-choice questions. Mix an on-art
  hunt, a drag game, a music beat, a puzzle, a branch.
- The renderer plays every `type` fully (true pointer drag-and-drop with a keyboard fallback,
  games layered on the page art, a real maze, audio, canvas drawing, confetti, and a sticker
  the child collects on each win). Choose the `type` whose mechanic matches your idea.

## Procedure
1. **Find the beat.** Place one interaction every 2–4 pages at a natural pause — never on an
   emotional climax. Note them in `interactions_summary`.
2. **Pick the mechanic for the moment** (see the table in interactivity.md): action beat →
   `arcade-catch` / `arcade-flap` / `arcade-run` / `arcade-pop` / `arcade-toss` / `arcade-steer`
   (a real engine game — match the arcade *verb* to the story's verb: falls→catch, flies→flap,
   chases→run, floats→pop, throws→toss, swoops→steer); on-the-art →
   `hidden-object` / `find-in-scene` / `tap-on-art` / `hotspot-reveal` / `place-on-scene`;
   drag → `drag-sort` / `drag-match` / `jigsaw` / `dress-up` / `feed-the-thing`; comprehension →
   `comprehension-question` / `drag-order` / `choice`; logic/math → `maze` / `sliding-puzzle` /
   `balance-scale` / `sorting` / `pattern` / `odd-one-out` / `counting`; word/phonics →
   `word-build` / `anagram` / `fill-the-blank` / `sound-hunt` / `rhyme-complete` / `trace-letter`;
   draw → `connect-dots` / `scratch-reveal`; music → `melody` / `rhythm-tap` / `song-builder`;
   memory → `memory` / `sequence-recall`; surprise → `tap-to-reveal` / `riddle`. No fit? `custom`.
3. **Tie it to *this* page — using what's already there.** The game uses things the illustration
   genuinely shows, the rhyme on the page, or the event that just happened. Pick targets/coords
   from the existing art; **never** ask for the picture or the text to change to fit the game.
4. **Write the block:** `type`, `prompt` (one clear, in-voice instruction), `data` (match the
   exact shape in interactivity.md; on-art coords are `at:{x,y}` in 0..1), and warm
   `feedback.correct` / `feedback.try_again`. Optional: `steps` (chain beats), `reward`
   (`{label,emoji,id}` to theme the sticker), `difficulty`. `skill` is an optional internal
   label (use `engagement` by default) — it must never leak into what the child sees.
5. **Always winnable.** Never a dead end or fail state. For `choice`/branching, every `goto`
   points to a real page and all branches still reach an ending. (The reader auto-celebrates
   wins and gives gentle retries — your `feedback` text is the voice of that.)
6. **Co-reader prompts.** For read-aloud bands, set page `reading_notes` with a question to ask.

## Match to the age band
- **3–5:** one-step games — `tap-on-art`, `hotspot-reveal`, `tap-to-reveal`, `rhyme-complete`,
  `counting`, simple `hidden-object`, `connect-dots`, `feed-the-thing`, `coloring`, `dress-up`;
  from ~4–5, one-touch arcade (`arcade-catch` / `arcade-pop`) at `speed: gentle`, small `goal`.
- **5–7:** the sweet spot for `hidden-object`, `find-in-scene`, `place-on-scene`, `drag-sort`,
  `drag-match`, `spot-the-difference`, `jigsaw` (small), `sliding-puzzle` (2×2/3×3), `word-build`,
  `rhythm-tap`, `sequence-recall`, `pattern`, `odd-one-out`, small `maze`, `melody`; all arcade
  types at `gentle`/`normal` (goal 4–8).
- **7–12:** layer it — multi-step games via `steps`, bigger `jigsaw`/`sliding-puzzle`, `anagram`,
  `fill-the-blank`, `balance-scale`, `song-builder`, branching `choice`, bespoke `custom`
  games, and arcade at `normal`/`wild` (goal 8–12).

## Keep the games varied
Mix the *kinds* of fun across the book — a search, a maze, a music beat, a sorting game, a
branch, a riddle. Don't ship six multiple-choice questions. Variety is about fun and surprise,
not about ticking skill boxes.

## Quality bar
- [ ] The story still reads as a **complete, satisfying book with every game skipped** — games
      add nothing the text/art needed, and you changed **no** `page.text` or `image.prompt`.
- [ ] Each game would be **fun on its own** — a kid would play it even outside the book.
- [ ] Mechanics are **varied** (≥3 kinds) and **at least one is rich** (on-art / drag / puzzle /
      music / `custom`), not all quizzes.
- [ ] Each interaction's `data` matches its `type`'s shape (the validator checks required keys);
      on-art coords are `at:{x,y}` inside the frame (0..1) and point at things the art shows.
- [ ] Every arcade game is **skinned from its page** (no default stars-and-baskets), its `how`
      and `avoid_line` are in the story's voice, `goal`/`speed` fit the band, and there are at
      most 1–2 arcade games per book — on the biggest action beats.
- [ ] Every `custom` `win` references only declared `elements`, and stays always-winnable.
- [ ] Instruction is short, in the story's voice, readable at the band.
- [ ] Every branching `goto` resolves to a real page; no dead ends; the main path is a full story.
- [ ] Interactions sit at natural beats, not emotional peaks.

## Preview while you design — the Game Lab
`make game-lab` builds the studio preview and opens the **Game Lab**: paste any interaction
YAML, pick a page image as the backdrop, and play the game instantly — including the arcade
games on the real engine. Iterate there before writing the block into story.yaml.

## Output
`interaction` blocks on the relevant pages + `interactions_summary`. The site reader runtime
(`publishing`) renders these as playable widgets — board games in the play card, arcade games
fullscreen on the engine — with animations, stickers, and celebration. Next: `page-layout`.
