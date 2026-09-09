---
name: interactive-elements
description: Design REAL arcade games that give kids an OPTIONAL fun break — a composed arcade-quest DESIGNED for the page's beat (stage, hero, actor roles & motions, waves, finale) or one of the twelve single-mechanic presets (snake, shooter, maze, stacker, whack-a-mole, breakout, catch, flap, run, pop, toss, steer) skinned from the story, plus rare branching choices — matched to the reader's age. Games are add-ons that NEVER change the story text or art. Use when adding interactivity to a finished story. Writes interaction blocks onto pages per schemas/story.schema.json.
---

# Interactive elements

An interaction is a **REAL game** — a 20–60-second fun break where the child *plays* a
real-time arcade game that is *about* what just happened in the story. It's part of the
romp, not a drill. Read `methodology/fun-first.md` (the north star), then
`methodology/interactivity.md` (the composer spec, the preset verb→game map, payload
shapes, and skin ideas).

## Compose first: `arcade-quest` — the game is built for the book

**The default move is to COMPOSE a bespoke game for the page's beat**, not pick a preset.
A quest is a little scripted scenario you write from the page:

| Part | What you write |
|---|---|
| `stage` | view (`side`/`sky`/`topdown`), parallax `bands`, `floor`, `scroll` |
| `hero` | the page's protagonist + `control` (`walk`/`hop`/`flap`/`steer`/`drive`) |
| `actors` | freely-named groups — role (`collect`/`rescue`/`dodge`/`bonk`/`squash`/`decoy`/`guard`) + motion (`drift`/`fall`/`rise`/`sine`/`chase`/`flee`/`hover`/`march`/`still`) + `from` + `count` + a joke `line` |
| `waves` | escalation beats with story-written banner lines |
| `finale` | the beat's payoff: `reach`/`clear`/`bigOne`/`tower`, with its own skin + line |

Roles are where the comedy lives: the `decoy` that comically refuses ("That's a lantern,
not a snack!"), the `guard` that shoves the hero back like a bouncy doorman, the `dodge`
chili that bounces everyone. Waves make the game RISE like the page. The finale gives the
beat its payoff. See interactivity.md for the full worked example (Nudo's dumpling rescue).

**Pick a preset instead ONLY when one mechanic fits the beat exactly** — then the twelve
single-mechanic games:

## The presets, when one fits exactly

| The page's verb | Game | | The page's verb | Game |
|---|---|---|---|---|
| falls / rains | `arcade-catch` | | gobble & grow | `arcade-snake` |
| flies through gaps | `arcade-flap` | | zap incoming things | `arcade-shoot` |
| chase / race / escape | `arcade-run` | | lost / sneaking through | `arcade-maze` |
| sky full of poppables | `arcade-pop` | | build / stack up | `arcade-build` |
| throw / aim | `arcade-toss` | | things keep popping up | `arcade-whack` |
| swoop & collect | `arcade-steer` | | break through a wall | `arcade-bounce` |

…or **compose an `arcade-quest`** when the beat is richer than one verb (the default).

**Never use the legacy types** (drag-and-drop, find-in-picture, tap boards, jigsaw, quizzes,
`custom`, the static `maze`…). They survive in already-published books only; the validator
warns on every one in a new story and the quality gate counts them against the book. The
single non-arcade survivor is the branching `choice` — a true narrative fork — used rarely.

## The story is the product; games are optional add-ons

The book must be a complete, satisfying read for a kid who plays **zero** games. So a game:
- **never changes the story** — it doesn't advance the plot, reveal what the text doesn't, or
  gate the next page; adding/removing a game must NOT require touching `page.text`;
- **never changes the illustrations** — the game plays *backdropped by* the page art and
  skins its sprites from the story; it must never dictate the art or require editing an
  `image.prompt` / re-illustrating;
- is **skippable** — the reader can ignore any interaction and read straight on.
You are adding games **on top of a finished story and finished art** — never editing either.
(The one exception is a branching `choice`, a real narrative fork; use it rarely and keep the
main path a complete story.)

## Mindset: would a kid play this for fun?

- Think "what would be **fun** here?", never "what reading drill fits?".
- **Match the game's verb to the page's verb** (table above) and the skin writes itself:
  dumplings spill → `arcade-snake` slurps them up; a wall blocks the way → `arcade-bounce`
  smashes it; the popcorn escapes → `arcade-whack` bops it back in.
- **The mechanic is the engine; the story is the skin.** Skin EVERY noun (`player`, `food`,
  `targets`, `blocks`…) as an emoji or `{emoji, label}` from the page. Never ship a default
  skin: "catch the stars" is generic; "catch Pip's sneeze-sparks" is the book.
- The three voice lines carry the comedy — write them like dialogue, not UI copy:
  `prompt` (the invitation), `data.how` (the control hint), `data.avoid_line` (the bonk joke).
- Vary the mechanics across the book (the gate wants ≥3 kinds) — a snake, then a maze, then
  a stacker is a romp; three catchers in a row is a level grind.
- The runtime guarantees every game is **always winnable** (funny bonks instead of fail
  states, the "🪄 Easier!" → "✨ Finish it!" assist ladder, calm tap-board fallback without
  WebGL). Don't design around these — spend your effort on the skin and the jokes.

## Procedure

1. **Find the beat.** Add a game ONLY where a page's beat genuinely invites one — there is no
   cadence to hit (the quality gate no longer counts games-per-page). A few well-placed games
   beat a game every other page. Put the game on the **story page it belongs to**, never on a
   blank-text page that breaks the read; never on an emotional climax. Note them in
   `interactions_summary`.
2. **Sketch the beat as a game.** Ask: what does the page's world look like (stage), who does
   the kid control (hero + control), what fills the field (actor groups: roles + motions + a
   joke line each), how does it escalate (waves with banner lines), and what's the payoff
   (finale kind + skin)? If one preset verb covers ALL of that, take the preset; otherwise
   compose an `arcade-quest`. A genuine plot fork (rare) → `choice`.
3. **Skin everything from *this* page.** Hero, actors, bands, floor, finale — all emoji from
   what the art and text already show. The `decoy`/`dodge`/`guard` roles are comedy
   opportunities: the ladybug who's helping, the chili the dragon must NOT eat, the cat who
   guards the counter.
4. **Write the block:** `type`, `prompt` (one clear, in-voice invitation), `data` (the
   composed scenario or the preset's exact shape in interactivity.md), and warm
   `feedback.correct` / `feedback.try_again`. Optional: `reward` (`{label,emoji,id}`
   to theme the sticker), `difficulty`. `skill` is an optional internal label (default
   `engagement`) — it must never leak into what the child sees.
5. **Fit the knobs to the band:** quests — 2–3 waves, 2–3 groups, `goal` ≤ 10 + `speed:
   gentle` under 7; presets — `goal` 4–8 for 5–7s, 8–12 for 7+; maze `size: cozy|normal|big`;
   bounce `rows: 1–3`. A round lands in 20–60 seconds.
6. **Co-reader prompts.** For read-aloud bands, set page `reading_notes` with a question to ask.

## Match to the reader's age (`target_year`)

- **~4:** one-touch only — quests with `hero.control: walk/steer` at `speed: gentle`, 1–2
  waves, small `goal` (4–6), one-touch finales (`reach`, `clear`); presets `arcade-catch`,
  `arcade-pop`, `arcade-whack`, `arcade-build`.
- **~5–7:** quests with `hop`/`flap`/`steer` heroes and comedic `decoy`/`guard` actors;
  presets — all one-touch games plus steering (`arcade-flap`, `arcade-run`,
  `arcade-steer`), aiming (`arcade-toss`), gentle swipe games (`arcade-snake`,
  `arcade-maze` at `size: cozy`), `gentle`/`normal`, goal 4–8.
- **~7–12:** everything — quests with `chase`/`flee` motions, `bigOne` timing finales and
  multi-wave escalation; presets `arcade-shoot`, `arcade-bounce` (`rows` up to 3),
  `arcade-maze` at `normal`/`big`, branching `choice` — at `normal` (or `wild` for 9+),
  goal 8–12.

## Quality bar

- [ ] The story still reads as a **complete, satisfying book with every game skipped** — games
      add nothing the text/art needed, and you changed **no** `page.text` or `image.prompt`.
- [ ] **Every game is an `arcade-*` type** (composed quest or preset; or a rare `choice`).
      Zero legacy types.
- [ ] Each game would be **fun on its own** — a kid would play it even outside the book.
- [ ] Each game **belongs to its page**: composed for the beat (quest) or verb-matched
      (preset), and every noun is **skinned from the page** (no default stars-and-baskets);
      wave banners, `how` and actor `line`s are in the story's voice.
- [ ] Mechanics are **varied** — ≥3 different games across the book (different quests count
      as different games when their scenario differs: stage/roles/waves/finale).
- [ ] `goal`/`speed`/knobs fit the reader's age; each round lands in 20–60 seconds.
- [ ] Each `data` payload matches its `type`'s shape (the validator checks required keys,
      quest wave references, roles/motions, and goal reachability).
- [ ] Warm `feedback.correct` / `try_again` in the story's voice — the win is the story's
      victory lap.
- [ ] Any `choice` `goto` resolves to a real page; no dead ends; the main path is a full story.
- [ ] Games sit at natural beats, not emotional peaks.

## Preview while you design — the Game Lab

`make game-lab` builds the studio preview and opens the **Game Lab**: pick a composed-quest
template (the rescue / the heist / minimal) or any of the twelve preset templates, pick a
page image as the backdrop, edit the YAML, and play the game instantly on the real engine.
Iterate there before writing the block into story.yaml.

## Saving a game — JSON patch, never YAML edits

Write each finished block with `edit_story.py` (it schema-validates the merged story and
refuses to write anything invalid; `--remove` deletes a game):
```bash
uv run python scripts/edit_story.py <world>/<story> interaction <page> <<'JSON'
{"type": "arcade-snake", "prompt": "...", "data": {...}, "feedback": {...}}
JSON
```
Update `interactions_summary` via `edit_story.py <world>/<story> meta`.

## Output

`interaction` blocks on the relevant pages + `interactions_summary`. The site reader runtime
(`publishing`) renders these as fullscreen engine games with animations, stickers, and
celebration. Next: `page-layout`.
