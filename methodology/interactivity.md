# Games & Interactivity

> **Read `fun-first.md` first.** Interactions are *games*, full stop — a fun break that's
> part of the romp. They are NOT hidden reading drills. If it feels like a worksheet, cut it.

An interaction is a **fun break** — a moment where the child puts the story down for a few
seconds and *does* something delightful: solves a puzzle, plays a tune, escapes a maze, finds
the hidden thing. The best ones do two things at once:

1. **Are genuinely fun on their own** — you'd play it even outside the book.
2. **Belong to *this* page** — the game is *about* what just happened, so it pulls the kid
   deeper into the story instead of yanking them out of it.

(If a kid sharpens a real skill by playing — counting, rhyming, repeating a melody — lovely.
That's a side effect. Never the pitch, never visible, never the reason the game is there.)

**Be wildly creative.** A page can carry a logic puzzle, a sneaky bit of math (as sorting,
counting, a pattern), a music challenge (play the dragon's song back), a maze, a mystery, a
memory game, a "help the hero pick" branch. Invent the framing that fits *this* story beat.
The renderer below plays each `type` fully — pick the type whose mechanic matches your idea
and pour the story's flavour into `prompt`, the labels, and `feedback`.

Interleave roughly one every 2–4 pages, placed at a natural beat — never mid-climax.

## Choosing the moment & the mechanic
- **Comprehension beat?** → `comprehension-question`, `drag-order` (sequence the events), `choice`.
- **Counting / sneaky math?** → `counting`, `pattern` (number patterns), `sorting` (by size/number),
  `word-match` (equation → answer). Keep it playful, never "do the sum".
- **Sound / phonics?** → `sound-hunt`, `rhyme-complete`, `trace-letter`.
- **Logic / problem-solving?** → `maze`, `sorting` (categorise), `odd-one-out`, `pattern`.
- **Music / rhythm?** → `melody` (listen then tap it back, Simon-style).
- **Search & attention?** → `seek-and-find`, `spot-the-difference`.
- **Curiosity / surprise?** → `tap-to-reveal`, `coloring` (free play), `riddle`.

## Interaction types mapped to age bands
✓✓ = ideal, ✓ = works.

| Interaction | 0–3 | 3–5 | 5–7 | 7–9 | 9–12 | Builds |
|---|:--:|:--:|:--:|:--:|:--:|---|
| Lift-the-flap / `tap-to-reveal` | ✓ | ✓✓ | ✓ | | | anticipation, cause/effect |
| `rhyme-complete` | ✓ | ✓✓ | ✓ | | | phonemic awareness |
| `counting` | ✓ | ✓✓ | ✓ | ✓ | | numeracy (hidden math) |
| `seek-and-find` | | ✓✓ | ✓✓ | ✓ | ✓ | vocabulary, attention |
| `spot-the-difference` | | ✓ | ✓✓ | ✓✓ | ✓ | attention, detail |
| `sound-hunt` | | ✓ | ✓✓ | ✓ | | phonics |
| `word-match` / `trace-letter` | | ✓ | ✓✓ | ✓ | | phonics, decoding |
| `memory` (card pairs) | | ✓ | ✓✓ | ✓✓ | ✓ | recall, vocabulary |
| `melody` (music challenge) | | ✓ | ✓✓ | ✓✓ | ✓ | rhythm, auditory memory |
| `riddle` | | ✓ | ✓✓ | ✓✓ | ✓ | vocabulary, inference |
| `coloring` (free play) | ✓ | ✓✓ | ✓ | | | calm break, fine-motor |
| `pattern` (what comes next) | | ✓ | ✓✓ | ✓✓ | ✓ | logic, sneaky math |
| `sorting` (categorise / by size) | | ✓ | ✓✓ | ✓✓ | ✓ | logic, classification, math |
| `odd-one-out` | | ✓ | ✓✓ | ✓✓ | ✓ | logic, reasoning |
| `maze` | | ✓ | ✓✓ | ✓✓ | ✓ | problem-solving |
| `comprehension-question` | | ✓ | ✓✓ | ✓✓ | ✓✓ | comprehension |
| `drag-order` (sequence events) | | ✓ | ✓✓ | ✓✓ | ✓ | comprehension, recall |
| Decision points / `choice` | | | ✓ | ✓✓ | ✓✓ | agency, comprehension |

Notes:
- Babies (6mo+): high-contrast art; `tap-to-reveal` lands best ~18 months.
- **Branching `choice` needs reading independence — best for 7+.**
- For the younger bands keep instructions to one short sentence; for 7+ you can layer a
  two-step puzzle (e.g. listen to the melody *then* tap it back).

## Design principles
- **One clear instruction**, in the story's own age-appropriate language. The flavour lives in
  the wording: not "Order these by size" but "Line up Pip's flames — biggest first!".
- **Always winnable.** Gentle "try again", never a dead end or a fail state. The reader gives
  encouraging feedback and a celebration on success automatically — write warm `feedback` text.
- **Tie it to the page.** A seek-and-find hunts for things actually in *that* illustration; a
  sorting game sorts things from *this* scene; a melody is the song a character just sang.
- **Fun is the point.** `interaction.skill` is an optional, internal label only (use it or
  set `engagement`); it must NEVER leak into what the child sees. Never frame a game as a
  "drill" or a "practice." If a game isn't fun without its skill label, it's the wrong game.
- **Co-reader prompts.** For read-aloud bands, set page `reading_notes` with a question to ask.

## Payload shapes (`interaction.data`) by type
The reader renders these fully — match the shape exactly.

**Quiz family** (pick the right answer)
- `rhyme-complete`: `{ sentence: "The fox sat on a ___", answer: "box", distractors: ["dog","sun"] }`
- `riddle`: `{ question: "I glow but I'm not the sun…", answer: "Pip", hint: "He's orange", distractors: [...] }`
- `comprehension-question`: `{ question: "Why was Pip scared?", options: ["...","..."], answer_index: 1 }`
- `odd-one-out`: `{ items: ["apple","pear","drum","plum"], answer: "drum", hint: "three are fruit" }`
- `pattern`: `{ sequence: ["🔺","🟦","🔺","🟦"], answer: "🔺", options: ["🔺","🟦","⭐"], hint: "..." }`
  (use numbers for sneaky math: `sequence:[2,4,6,8], answer:10`)

**Find / attention**
- `seek-and-find`: `{ items: ["acorn","blue bird","..."] }`
- `sound-hunt`: `{ sound: "s", words: ["sun","sock","snake"], decoys: ["moon","leaf"] }`
- `spot-the-difference`: `{ count: 3, spots: [{x:40,y:55},{x:72,y:30},{x:18,y:80}] }`
  (`x`/`y` are % positions over the page image; optional `r` = % size. Omit `spots` for an honour-system version.)

**Logic / math**
- `counting`: `{ what: "mushrooms", answer: 6 }`
- `sorting`: `{ bins: ["Land","Water"], items: [{label:"frog", bin:"Water"}, {label:"fox", bin:"Land"}] }`
  (`bin` may match the bin label, a `key`, or its index. Great for "big vs small", "before vs after".)
- `maze`: `{ grid: "S.#..\n.#.#.\n...#E", start:[0,0], end:[2,4] }`
  (grid may be a multi-line string or array of rows; `#`/`B`/`X` = wall, `S`/`E` mark start/end,
  anything else = open. `start`/`end` are `[row,col]` fallbacks if no S/E markers.)

**Matching / memory / reveal**
- `word-match`: `{ pairs: [["cat","🐱"],["sun","☀️"],["2+2","4"]] }` (connect left → right; works for math too)
- `memory`: `{ pairs: [["cat","🐱"],["dog","🐶"]] }` (flip cards, find the matching pair)
  — if you only give `{ sequence: [...] }`, `memory` falls back to a put-in-order game.
- `tap-to-reveal`: `{ cards: [{front:"🌰", back:"acorn"}, {front:"❓", back:"a friend!"}] }`
- `drag-order`: `{ sequence: ["wake","wash","walk"] }` (child rearranges to match this order)

**Music & creative**
- `melody`: `{ notes: ["C","E","G","C"] }` (the reader plays the tune; the child taps it back on
  pitch pads. Use note names C D E F G A B, add `#` for sharps, `2` for the upper octave e.g. `C2`.)
- `coloring`: `{ regions: ["sky","grass","sun","house"], palette: ["#e07a8b","#7a9cc6","#6b8f71"] }`
  (free-play colour-in; always a happy ending — purely a calm break.)

**Branching**
- `choice`: `{ options: [{ label: "Open the door", goto: 12 }, { label: "Run home", goto: 18 }] }`
  (every `goto` must be a real page number; all branches must still reach an ending.)

(Sources: kingsresearch.com; en.wikipedia.org/Interactive_children's_book; lunesia.app;
littlescholarsnyc.com; teachearlyyears.com)
