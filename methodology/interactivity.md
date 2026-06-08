# Games & Interactivity

> **Read `fun-first.md` first.** Interactions are *games*, full stop — a fun break that's
> part of the romp. They are NOT hidden reading drills. If it feels like a worksheet, cut it.

> **The story is the product. Games are optional add-ons — never the other way round.**
> The book must be a complete, satisfying read for a kid who plays **zero** games. So:
> - A game **never changes the story.** It does not advance the plot, reveal anything the text
>   doesn't, or gate the next page. Adding, editing, or removing a game must never require
>   touching `page.text`.
> - A game **never changes the illustrations.** The art is drawn for the *story*. A game *uses*
>   what's already in the scene (e.g. find things the illustration genuinely shows) — it must
>   never dictate what the picture contains, and adding a game must never require re-illustrating
>   or editing an `image.prompt`. If your game needs something that isn't in the art, pick a
>   different game, not a different picture.
> - Games are **skippable.** Every interaction is optional; the reader can ignore it and read on.
>   (The one exception is a branching `choice`, which *is* a narrative fork — use it rarely and
>   deliberately, and make sure the book still reads as a complete story along the main path.)
> - **Write the story and art first, add games last.** Never write a page or commission art to
>   set up a game.

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

> **Rich first, quizzes last.** A game where the kid *does* something — drags, plays on the
> picture, builds, solves, makes music — beats one where they just pick an answer. Lead with
> the rich mechanics below; reach for a multiple-choice quiz only when nothing richer fits.
> Every book should have **at least one rich game** (the quality gate checks this), and varied
> *kinds* of fun across the book (the gate wants ≥3 different types). When no built-in fits
> your idea, **invent one with `custom`** (see "Inventing a game from scratch" below).

## Choosing the moment & the mechanic
- **Play ON the picture?** → `hidden-object` / `find-in-scene` (tap the things in the art),
  `tap-on-art` (tap the one right thing), `hotspot-reveal` (tap sparkles to discover),
  `place-on-scene` (drag items onto the right spots), `spot-the-difference`.
- **Drag & drop?** → `drag-sort` (into baskets), `drag-match` (drag to its pair), `jigsaw`
  (rebuild the page art), `dress-up` (drag bits onto a character), `feed-the-thing` (drag the
  good stuff into its mouth). All have an automatic keyboard/tap fallback.
- **Comprehension beat?** → `comprehension-question`, `drag-order` (sequence the events), `choice`.
- **Counting / sneaky math?** → `counting`, `pattern` (number patterns), `sorting`/`drag-sort`
  (by size/number), `balance-scale` (which side is heavier). Keep it playful, never "do the sum".
- **Sound / phonics / spelling?** → `sound-hunt`, `rhyme-complete`, `trace-letter`,
  `word-build` (tap letters to spell), `anagram` (unscramble), `fill-the-blank`.
- **Logic / problem-solving?** → `maze`, `sliding-puzzle` (unscramble the art), `sorting`,
  `odd-one-out`, `pattern`.
- **Drawing / reveal?** → `connect-dots` (reveals a drawing), `scratch-reveal` (scrub to uncover),
  `trace-letter`, `coloring`.
- **Music / rhythm?** → `melody` (listen then tap it back), `rhythm-tap` (tap to the beat),
  `song-builder` (make your own tune).
- **Memory?** → `memory` (card pairs), `sequence-recall` (watch a pattern, repeat it).
- **Curiosity / surprise?** → `tap-to-reveal`, `coloring`, `riddle`.

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
| `hidden-object` / `find-in-scene` (on art) | | ✓✓ | ✓✓ | ✓✓ | ✓ | vocabulary, attention |
| `tap-on-art` / `hotspot-reveal` (on art) | ✓ | ✓✓ | ✓✓ | ✓ | | exploration, cause/effect |
| `place-on-scene` (drag onto art) | | ✓ | ✓✓ | ✓✓ | ✓ | matching, spatial |
| `drag-sort` / `drag-match` (true drag) | | ✓ | ✓✓ | ✓✓ | ✓ | logic, matching |
| `feed-the-thing` (drag good/bad) | | ✓✓ | ✓✓ | ✓ | | sorting, decisions |
| `dress-up` (drag bits on) | ✓ | ✓✓ | ✓ | | | free play, fine-motor |
| `jigsaw` / `sliding-puzzle` (of the art) | | ✓ | ✓✓ | ✓✓ | ✓✓ | spatial, problem-solving |
| `connect-dots` | | ✓✓ | ✓✓ | ✓ | | counting/letters, fine-motor |
| `scratch-reveal` | ✓ | ✓✓ | ✓ | | | anticipation, fine-motor |
| `balance-scale` (which is heavier) | | ✓ | ✓✓ | ✓✓ | ✓ | reasoning, sneaky math |
| `word-build` / `anagram` / `fill-the-blank` | | | ✓✓ | ✓✓ | ✓ | spelling, phonics |
| `rhythm-tap` / `song-builder` (music) | | ✓✓ | ✓✓ | ✓ | | rhythm, creativity |
| `sequence-recall` (Simon) | | ✓ | ✓✓ | ✓✓ | ✓ | working memory |
| `custom` (invent your own) | | ✓ | ✓✓ | ✓✓ | ✓✓ | anything you imagine |

Notes:
- Babies (6mo+): high-contrast art; `tap-to-reveal` / `tap-on-art` land best ~18 months.
- **Branching `choice` needs reading independence — best for 7+.**
- For the younger bands keep instructions to one short sentence; for 7+ you can layer a
  multi-step game via `steps` (e.g. find the key on the art, *then* trace it open).
- Scale puzzles by `difficulty`: e.g. a `sliding-puzzle` at `easy` is 2×2, `hard` is 4×4.

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

## Coordinates on the art (for on-the-art games)
Games that play on the illustration place things by **normalized coordinates**: `at: {x, y}`
with `x` and `y` from **0 to 1**, origin top-left (`{x:0,y:0}` = top-left corner, `{x:1,y:1}` =
bottom-right). A point can carry an optional `r` (normalized radius) for its tap size; the reader
enforces a comfortable minimum touch target. (Legacy percent 0–100 is auto-detected, and
`spot-the-difference` still uses `{x,y}` in percent.) Get coords from where the thing actually
sits in the page image. The reader recomputes positions on resize, so they stay put on any screen.

## Payload shapes (`interaction.data`) by type
The reader renders these fully — match the shape exactly. (Every type's required keys are also
enforced by `scripts/lib/checks/interactivity.py`.)

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

**On the art** (normalized `at:{x,y}`, 0..1 — see the coordinate note above)
- `hidden-object`: `{ items: [{label:"acorn", at:{x:0.31,y:0.62}}, {label:"snail", at:{x:0.7,y:0.4}}], decoys:[{at:{x:0.5,y:0.2}}] }`
- `find-in-scene`: `{ items: [{label:"the red door", at:{x:0.2,y:0.5}}, ...] }` (called out one at a time)
- `tap-on-art`: `{ target: {at:{x:0.55,y:0.4}, r:0.12}, label:"the dragon" }`
- `hotspot-reveal`: `{ hotspots: [{at:{x:0.2,y:0.3}, reveal:"a sleeping cat!", icon:"🐱"}, ...] }` (no fail; explore)
- `place-on-scene`: `{ items:[{label:"hat", icon:"👒", accepts:"head"}], slots:[{at:{x:0.5,y:0.2}, accepts:"head", label:"head"}] }`

**True drag-and-drop** (pointer drag with snapping; keyboard/tap fallback automatic)
- `drag-sort`: `{ bins:[{label:"Land",key:"land"},{label:"Sea",key:"sea"}], items:[{label:"frog",bin:"sea"},{label:"fox",bin:"land"}] }`
- `drag-match`: `{ pairs: [["🦊","fox"],["🌙","moon"]] }` (drag each left chip to its right label)
- `jigsaw`: `{ rows:2, cols:3 }` (auto-cuts the page art into pieces to rebuild)
- `dress-up`: `{ base:"🧍", parts:[{label:"hat",icon:"👒",zone:"head"}], zones:[{label:"head", at:{x:0.5,y:0.15}}] }`
- `feed-the-thing`: `{ good:["apple","carrot"], bad:["boot","rock"], target_icon:"😋" }`

**Drawing / reveal**
- `connect-dots`: `{ dots:[{n:1,at:{x:0.2,y:0.8}},{n:2,at:{x:0.4,y:0.3}},...], order:"number" }` (`order:"letter"` for A,B,C)
- `scratch-reveal`: `{ reveal:"🎁", threshold:0.5 }` (scrub to uncover; threshold = fraction to clear)

**Spatial / logic**
- `sliding-puzzle`: `{ rows:3, cols:3 }` (slide tiles of the page art; scale with `difficulty`)
- `balance-scale`: `{ left:["🍎","🍎"], right:["🍎"], answer:"left" }` (`answer` = "left"|"right"|"equal", or a number)

**Word / phonics**
- `word-build`: `{ letters:["C","A","T","X","O"], answer:"cat" }` (tap letters in order; extras allowed)
- `anagram`: `{ scrambled:"tac", answer:"cat" }`
- `fill-the-blank`: `{ sentence:"The fox sat on a ___.", answer:"box", options:["box","dog","sun"] }` (omit `options` to spell it)

**Music / rhythm**
- `rhythm-tap`: `{ pattern:[1,0,1,1], tempo:90 }` (hear the beat, tap the drum to it; always wins)
- `song-builder`: `{ palette:["C","D","E","G","A"], bars:6 }` (tap notes into a strip, hear your tune; free play)

**Memory**
- `sequence-recall`: `{ sequence:["red","blue","red","green"] }` (watch it light up, tap it back, Simon-style)

## Inventing a game from scratch — `custom`
When no built-in fits, declare your own game as **data** (no code). List `elements` (the
interactive bits) and a `win` condition; the reader interprets it using the same toolkit. There
is no fail state in the model, so a custom game is **winnable by construction** — and the reader
adds a hint ladder + gentle auto-solve as the final backstop.

Element `kind`s: `draggable`, `dropzone`, `target`/`hotspot`, `toggle`, `tile`. Win `mode`s:
`all-placed`, `matched-pairs`, `ordered`, `sequence`, `all-found`, `toggled-all`, or `expression`
(combine with `all`/`any`/`not`). Put `at:{x,y}` on elements to play on the page art.

```yaml
# "Pack the picnic basket — only the food!"  (a drag game, played on the art)
interaction:
  type: custom
  prompt: Pack the basket — only the yummy things!
  data:
    stage: scene
    elements:
      - { id: apple,  kind: draggable, emoji: "🍎", group: food, at: {x: 0.2, y: 0.8} }
      - { id: cake,   kind: draggable, emoji: "🍰", group: food, at: {x: 0.35, y: 0.85} }
      - { id: boot,   kind: draggable, emoji: "🥾", group: junk, at: {x: 0.5, y: 0.82} }
      - { id: basket, kind: dropzone,  label: Basket, accepts: [food], at: {x: 0.8, y: 0.55}, r: 0.2 }
    win: { mode: all-placed }     # every food draggable lands in an accepting zone
    hints: ["Food goes IN the basket.", "The boot is NOT food!"]
  feedback: { correct: "Picnic packed! 🧺", try_again: "Hmm — that's not food!" }
```

Other quick shapes: `win:{mode:"all-found"}` with `hotspot` elements (tap every sparkle on the
art); `win:{mode:"ordered", order:[a,b,c]}` (tap/place in that order); `win:{mode:"matched-pairs",
pairs:[[chip,zone],...]}`. Every id named in `win` must be a declared element (the validator
checks this), and for `all-placed` every draggable needs a zone that `accepts` it.

## Multi-step games & rewards
- **`steps`** chains beats into one game: `interaction.steps: [ {type:hidden-object,...},
  {type:trace-letter,...} ]`. The whole game is solved only after the last beat; each beat is
  itself winnable. (Steps may not nest steps.)
- **`reward`** is optional theming for the sticker the child earns: `reward: {label:"Dragon
  Scale", emoji:"🐉", id:"dragon-scale"}`. Without it the reader awards a default sticker. A
  stable `id` lets the same collectible recur across a series. Each solved game drops a sticker
  into a tray; the last page shows the full collection — a reason to play every game and re-read.

(Sources: kingsresearch.com; en.wikipedia.org/Interactive_children's_book; lunesia.app;
littlescholarsnyc.com; teachearlyyears.com)
