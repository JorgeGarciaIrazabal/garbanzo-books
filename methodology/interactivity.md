# Games & Interactivity

> **Read `fun-first.md` first.** Interactions are *games*, full stop — a fun break that's
> part of the romp. They are NOT hidden reading drills. If it feels like a worksheet, cut it.

> **REAL GAMES ONLY.** Every game in a new book is an **arcade game** — a real-time game on
> the embedded engine with a game loop, movement, and physics: the `arcade-*` family below.
> No drag-and-drop chores, no find-in-the-picture, no tap boards, no quizzes, no `custom`
> declarative boards. Those older minigame types still *play* in already-published books
> (see "Legacy types" at the very end) but must never appear in a new story — the validator
> warns on every one, and the quality gate counts them against the book. The one non-arcade
> survivor is the branching **`choice`** — a narrative fork, not a minigame — used rarely.

> **The story is the product. Games are optional add-ons — never the other way round.**
> The book must be a complete, satisfying read for a kid who plays **zero** games. So:
> - A game **never changes the story.** It does not advance the plot, reveal anything the text
>   doesn't, or gate the next page. Adding, editing, or removing a game must never require
>   touching `page.text`.
> - A game **never changes the illustrations.** The art is drawn for the *story*; the arcade
>   game plays fullscreen *backdropped by* the page art and skins its sprites from the story —
>   it must never dictate what the picture contains or require editing an `image.prompt`.
> - Games are **skippable.** Every interaction is optional; the reader can ignore it and read on.
> - **Write the story and art first, add games last.** Never write a page to set up a game.

An interaction is a **fun break** — the child puts the story down for 20–60 seconds and
*plays*: slithers a snake, smashes a wall, scoots a maze, stacks a tower. The best ones do
two things at once:

1. **Are genuinely fun on their own** — a kid would play it even outside the book.
2. **Belong to *this* page** — the game is *about* what just happened, so it pulls the kid
   deeper into the story instead of yanking them out of it.

Place a game **only where a page's beat genuinely invites one** — there is NO cadence to hit
(the quality gate no longer counts games-per-page, because a quota pushes you to drop filler
games that break the read). A handful across the book is plenty; a great story with three
well-placed games beats one with a game every other page. Put the game **on the story page it
belongs to** — never on its own blank-text page that interrupts the flow. Place at a natural
beat, never mid-climax. Vary the *mechanics* across the book (the quality gate still wants ≥3
different kinds when you do add games): a snake, then a maze, then a stacker reads as a romp;
three catchers in a row reads as a level grind.

## Pick the mechanic by the page's VERB

The story hands you an action; the arcade family has a verb for it. Match the game's verb
to the page's verb and the skin writes itself.

| What just happened on the page | Game | The kid… |
|---|---|---|
| Things fall / rain / spill | `arcade-catch` | steers a catcher under them |
| Something flies / soars through gaps | `arcade-flap` | taps to flap through |
| A chase, a race, an escape | `arcade-run` | runs & jumps, collecting on the way |
| The air fills with bubbles / sparks / fireflies | `arcade-pop` | taps to pop the right ones |
| Throwing, feeding-at-a-distance, aiming | `arcade-toss` | slingshots into the target |
| Swimming / swooping / zooming in open space | `arcade-steer` | drags to steer & collect |
| Gobbling, gathering a growing line/tail | `arcade-snake` | slithers, gobbles, GROWS |
| Zapping / squirting / cleaning incoming things | `arcade-shoot` | steers; ship auto-fires |
| Lost, sneaking, finding the way through | `arcade-maze` | swipes through a real maze |
| Building, stacking, piling something up | `arcade-build` | taps to drop swinging pieces |
| Things keep popping up where they shouldn't | `arcade-whack` | bops them before they duck |
| Breaking through a wall / barrier / shell | `arcade-bounce` | paddles a ball, smashes bricks |

A genuine fork in the plot (rare!) → `choice`. That's the whole menu for a new book.

## Age bands

✓✓ = ideal, ✓ = works. The knobs do the fitting: `speed: gentle|normal|wild`, `goal`
(things to get), `size` (maze), `rows` (bounce).

| Game | 3–5 | 5–7 | 7–9 | 9–12 | Input |
|---|:--:|:--:|:--:|:--:|---|
| `arcade-catch` | ✓ (4+, gentle) | ✓✓ | ✓✓ | ✓ | drag left/right |
| `arcade-pop` | ✓ (4+, gentle) | ✓✓ | ✓✓ | ✓ | tap |
| `arcade-whack` | ✓ (4+, gentle) | ✓✓ | ✓✓ | ✓ | tap |
| `arcade-build` | ✓ (gentle) | ✓✓ | ✓✓ | ✓ | tap to drop |
| `arcade-flap` | | ✓✓ | ✓✓ | ✓✓ | tap to flap |
| `arcade-run` | | ✓✓ | ✓✓ | ✓✓ | tap to jump |
| `arcade-steer` | | ✓✓ | ✓✓ | ✓✓ | drag in 2D |
| `arcade-toss` | | ✓✓ | ✓✓ | ✓✓ | drag & release |
| `arcade-shoot` | | ✓ | ✓✓ | ✓✓ | drag (auto-fire) |
| `arcade-snake` | | ✓ | ✓✓ | ✓✓ | swipe 4-way |
| `arcade-maze` | | ✓ (cozy) | ✓✓ | ✓✓ | swipe 4-way |
| `arcade-bounce` | | ✓ | ✓✓ | ✓✓ | drag left/right |
| `choice` (branch) | | ✓ | ✓✓ | ✓✓ | reading independence |

Rules of thumb:
- `goal` 4–8 for 5–7s, 8–12 for 7+. A round should land in **20–60 seconds** — it's a fun
  *break*, not a level grind.
- `speed: gentle` under 7 (also derived from `interaction.difficulty`); `wild` only 9+.
- One-touch games (`catch`, `pop`, `whack`, `build`) reach down to ~4–5; swipe-steering
  (`snake`, `maze`) and aiming (`toss`) want 5–6+.
- For maze: `size: cozy` (7×5) for 5–7, `normal` (9×6) for 7–9, `big` (11×7) for 9+.
- For bounce: `rows: 1` for the young end, up to `rows: 3` for 9+.

## Design principles

- **The mechanic is the engine; the story is the skin.** Every noun in the payload
  (`player`, `food`, `targets`, `blocks`…) is an emoji or `{emoji, label}` chosen from what
  just happened on the page. Never ship a default skin — "catch the stars" is generic;
  "catch Pip's sneeze-sparks before they singe the grass" is the book.
- **One clear instruction**, in the story's voice. `prompt` is the invitation; `how` is the
  one-line control hint; `avoid_line` is the joke when the kid bonks the wrong thing. These
  three lines carry the comedy — write them like dialogue, not UI copy.
- **Always winnable.** The runtime guarantees it (see below) — your job is to make the
  *winning* feel like the story continuing: `feedback.correct` is the page's victory lap.
- **Fun is the point.** `interaction.skill` is an optional internal label only (default
  `engagement`); it must NEVER leak into what the child sees.
- **Co-reader prompts.** For read-aloud bands, set page `reading_notes` with a question to ask.

## The engine & its built-in guarantees

The arcade family runs on an embedded game engine (Kaplay, vendored — sprites, physics,
collisions, particles): a real game loop the child plays **fullscreen, backdropped by this
page's own illustration**. The runtime provides — don't design around these:

- **Always winnable, no fail states.** Touching an avoid-thing is a funny bonk (wobble +
  silly sound + your `avoid_line`), never a game-over. Progress only goes up. Each game has
  its own comic non-failure: the snake that bites its tail just ties itself in a knot 🪢 and
  trims back; the bounce ball can't fall out — the floor is bouncy; a missed tower piece
  tumbles off comically and a new one swings in; shooting a friendly just makes it wobble
  indignantly.
- **The rubber-band assist ladder.** On a stall, "🪄 Easier!" slows the game and grows the
  targets (in the maze it literally reveals the secret trail of dots to the exit), then
  "✨ Finish it!" auto-wins. The arcade version of the hint ladder.
- **Lazy + graceful.** The ~190KB engine loads only when the child taps ▶ Play. With no
  WebGL or `prefers-reduced-motion`, the same beat renders as a calm tap-board fallback —
  so design the skin to also read at a glance as static emoji.
- **A goal HUD** (progress pips + count) and a win celebration are automatic.

## Payload shapes — all 12 games, with skin ideas

Common keys on every game: nouns are `"🍎"` or `{emoji, label}`; optional `goal`,
`speed: gentle|normal|wild`, `how` (control hint, in-voice), `avoid_line` (the bonk joke).
Required keys are enforced by `scripts/lib/checks/interactivity.py`.

**`arcade-catch`** — things fall; steer the catcher under the right ones.
`{ player:"🧺", catch:["✨","🌟"], avoid:["💧"], goal:8, speed:"gentle" }`
Skins: a rain-bucket under a dragon's sneeze-sparks · a beret catching the baker's flying
croissants · open pajama pockets under a meteor shower of baby stars · abuela's paella pan
under tomatoes the seagulls keep dropping.

**`arcade-flap`** — tap to flap; fly through the gaps.
`{ player:"🕊️", obstacle:"☁️", gates:6 }`
Skins: a dragon through cloud canyon · a bumblebee through the laundry lines · a paper
plane across the classroom while the teacher's back is turned · a flying carpet between
minarets at dusk.

**`arcade-run`** — auto-run, tap to jump (double-jump allowed); gather `collect`, then the
`finish` marker arrives.
`{ player:"🏃", obstacles:["🪨"], collect:"⭐", goal:7, finish:"🏰" }`
Skins: race the rolling cheese-wheel downhill · escape the tickle-monster through the
pillow fort · the knight late for her own coronation, grabbing dropped crown-jewels.

**`arcade-pop`** — things drift up; tap to pop the right ones.
`{ pop:["🫧"], avoid:["🐝"], goal:10 }`
Skins: pop the witch's stinky-brew bubbles before they reach the village · pop the sleeping
giant's snore-bubbles (but not the dreaming butterflies) · burst the hiccup-balloons the
dragon keeps burping.

**`arcade-toss`** — drag back like a slingshot (aim dots show the arc), release to throw.
`{ projectile:"🍎", target:{emoji:"🧺",label:"the basket"}, goal:4 }`
Skins: toss berries into Mo's basket · lob water-balloons into the dragon's hiccupping
mouth to put out the fire · flick rolled-up socks into the laundry basket across the room.

**`arcade-steer`** — drag to steer in 2D; collect things, bounce off drifting baddies.
`{ player:"🚀", collect:"⭐", avoid:["🪨","☄️"], goal:8 }`
Skins: a submarine gathering pearls between ticklish jellyfish · an owl collecting the
spilled stars before sunrise · a witch's broom scooping lost bats out of the storm.

**`arcade-snake`** — classic snake: swipe 4-way to slither; gobble `food` and GROW a tail.
Eating yourself = a comic knot (🪢, tail trims back), never a game-over; `avoid` decoys
scurry away when bitten. `body` optionally skins the tail segments.
`{ player:"🐍", body:"💛", food:["🍎","🍐"], avoid:["🌶️"], goal:8, speed:"gentle" }`
Skins: the noodle-dragon slurping dumplings, growing longer with each one · a conga line
at the jungle fiesta — every animal gobbled joins the dance line · the very hungry goat
eating the laundry off the line (but NOT the cactus) · a tide-pool eel collecting pearls.

**`arcade-shoot`** — a gentle shooter: drag to steer on one axis; the ship **auto-fires**
(taps add bonus shots). Hitting an `avoid` just makes it wobble indignantly.
`{ player:"🚀", shot:"🫧", targets:["🪼","👾"], avoid:["⭐"], goal:9 }`
Skins: the bathtub rocket bubble-blasting ticklish space-jellies · a squirt-gun hosing the
mud-gremlins off grandma's roses (don't soak the cat) · the pillow-cannon de-spooking the
attic ghosts one *poof* at a time.

**`arcade-maze`** — a REAL maze, freshly carved every play (so replays stay fun): swipe to
scoot cell-by-cell to the `exit`; optional `collect` sprinkles up to 3 pickups along the way.
The assist ladder reveals the solution trail. `size: cozy|normal|big`.
`{ player:"🐭", exit:"🧀", collect:"✨", size:"normal" }`
Skins: the mouse through the castle cellar to the birthday cake · the lost penguin through
the cracking ice cave, scooping fish · sneaking through the library stacks to the Forbidden
Pop-Up Book before the lights go out.

**`arcade-build`** — a piece swings overhead on a pendulum; tap to drop it on the tower.
Generous wiggle-room + auto-snug; a missed piece tumbles off comically and a new one swings
in. The tower rides down a storey when it outgrows the screen.
`{ blocks:["📦","🧱"], goal:6, speed:"gentle" }`
Skins: stack the giant's breakfast pancake-tower to the sky · pile the dragon's gold so the
hoard inspector approves · rebuild the sandcastle turret before the tide comes back · stack
the sleeping cats gently (they wobble — they're cats).

**`arcade-whack`** — a 3×3 field of burrows; critters pop up, linger, duck back down. Tap
the `whack` ones before they hide; `avoid` ones just wobble at you.
`{ whack:["🐹"], avoid:["🐞"], goal:8 }`
Skins: bop the escaping popcorn back into the pot before movie night is ruined · the
garden moles stealing abuela's carrots (spare the ladybug) · push the hiccupping frogs
back into the pond · whack the gophers, NOT the gnome.

**`arcade-bounce`** — breakout: drag the paddle, bounce the `ball` up, smash every brick.
The floor is bouncy too — a miss is a giggle, never a lost ball. `rows: 1–3` (6 bricks/row).
`{ player:"🏓", ball:"⭐", bricks:["🧱"], rows:2 }`
Skins: bounce the meatball to smash the Great Spaghetti Wall · crack the ice wall sealing
the dragon's egg · the trampoline-bunny smashing the grumpy king's broccoli fortress ·
bounce the cannonball-cheese through the mousetrap barricade.

### A full example

```yaml
# Page beat: Pip the dragon sneezes a fountain of sparks over the meadow.
interaction:
  type: arcade-catch
  prompt: Catch Pip's sneeze-sparks before they singe the grass!
  data:
    player: { emoji: "🪣", label: "Clara's rain-bucket" }
    catch: ["✨", "🔥"]
    avoid: [{ emoji: "🐞", label: "ladybug" }]
    goal: 8
    speed: gentle
    how: Drag the bucket — catch every spark!
    avoid_line: Not the ladybug! She's helping!
  feedback: { correct: "The meadow is safe — Pip looks very sorry. 🐉", try_again: "Quick, under the sparks!" }
  reward: { label: "Spark Catcher", emoji: "✨", id: "spark-catcher" }
```

```yaml
# Page beat: the dumpling cart tips over and Nudo the noodle-dragon gives chase.
interaction:
  type: arcade-snake
  prompt: Help Nudo slurp up every runaway dumpling!
  data:
    player: { emoji: "🐉", label: "Nudo the noodle-dragon" }
    body: "🍜"
    food: ["🥟", "🥠"]
    avoid: [{ emoji: "🌶️", label: "the EXTRA-spicy chili" }]
    goal: 8
    speed: gentle
    how: Swipe to slither — every dumpling makes Nudo LONGER!
    avoid_line: Not the chili! Nudo breathes enough fire already!
  feedback: { correct: "Nudo is one very long, very happy dragon. 🐉", try_again: "Curl back around!" }
  reward: { label: "Dumpling Slurper", emoji: "🥟", id: "dumpling-slurper" }
```

Preview any payload instantly in the **Game Lab** (`make game-lab`) — edit the YAML, pick a
page image as the backdrop, and play it on the real engine without rebuilding the book.

## Branching `choice` — the one non-arcade survivor

`choice` is a narrative fork, not a minigame:
`{ options: [{ label: "Open the door", goto: 12 }, { label: "Run home", goto: 18 }] }`
Every `goto` must be a real page number; all branches must still reach an ending, and the
main path must read as a complete story. Needs reading independence — best 7+. Use rarely.

## Multi-step games & rewards

- **`steps`** chains beats into one game (each beat itself winnable; steps may not nest).
  With the arcade family, prefer one great game over a chain — use `steps` sparingly.
- **`reward`** themes the sticker the child earns: `{label:"Dragon Scale", emoji:"🐉",
  id:"dragon-scale"}`. A stable `id` lets a collectible recur across a series. Each solved
  game drops a sticker into the tray; the last page shows the collection — a reason to play
  every game and re-read.

## Legacy types — published books only, never in new stories

Everything that is not `arcade-*` or `choice` is **legacy**: the renderer keeps playing
them so already-published books don't break, but they must not appear in any new story —
the validator warns on each one and the quality gate flags the book. Do not "upgrade" a
published book's games either (see the no-retrofit rule); this reference exists only for
maintaining what's already live.

Legacy catalogue (type → required `data` keys, per `scripts/lib/checks/interactivity.py`):
quiz family (`rhyme-complete`, `riddle`, `comprehension-question`, `odd-one-out`, `pattern`,
`counting`, `fill-the-blank`); find/attention (`seek-and-find`, `sound-hunt`,
`spot-the-difference`, `hidden-object`, `find-in-scene`, `tap-on-art`, `hotspot-reveal`);
drag (`drag-sort`, `drag-match`, `drag-order`, `place-on-scene`, `jigsaw`, `dress-up`,
`feed-the-thing`, `sorting`); logic (`maze` — the static grid one, superseded by
`arcade-maze` —, `sliding-puzzle`, `balance-scale`); word (`word-build`, `anagram`,
`word-match`, `trace-letter`); music (`melody`, `rhythm-tap`, `song-builder`); memory
(`memory`, `sequence-recall`); misc (`tap-to-reveal`, `scratch-reveal`, `connect-dots`,
`coloring`, `custom`).

On-art legacy games place things by normalized coordinates `at:{x,y}` in 0..1 (origin
top-left; optional `r` radius; legacy percent 0–100 auto-detected). The validator still
checks coords sit in-frame and `custom` wins reference declared elements — again, only so
published books keep validating.

(Sources: kingsresearch.com; en.wikipedia.org/Interactive_children's_book; lunesia.app;
littlescholarsnyc.com; teachearlyyears.com)
