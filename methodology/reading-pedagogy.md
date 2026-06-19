# Age-Fit Language (light touch)

> **Read `fun-first.md` first.** Fun outranks everything here. This doc exists for ONE
> reason: make sure the words don't get in the way of the story. A kid who can't read the
> sentence can't enjoy the joke. That's the whole point — not a reading curriculum.

This is a *light touch*, not a phonics program, and there are **no hard rules** below — only
a portrait of what a kid that age can comfortably read, so you can aim the words there and
get back to making the story rip. **Never** swap a funnier word for a duller one, or flatten
a great line, just to hit a number. When the guidance and the fun disagree, the fun wins.

## Pick an age, not a band

Reading skill changes a lot from one birthday to the next — a 5-year-old and a 7-year-old
are different readers, even though both fall in the old "5–7" band. So aim at a **single
age in years** (the story's `target_year`), and picture *that* reader. The portraits below
describe each age; the coarse bands survive only as shelf labels.

The numbers in each portrait (FK grade, words/page, sentence length) are **gentle anchors,
not gates** — a place to aim, noisy by nature, and overruled by the read-aloud test every
time. Flesch–Kincaid grade ≈ US school grade ≈ *age − 5* (a 5-year-old is in kindergarten,
grade ~0), and it's genuinely unreliable below ~Grade 1, so for the youngest ages ignore the
number and trust your ear.

## Read-aloud or reading it alone? (this is the word-choice lever)

The same age splits into two very different readers, and **who holds the book decides how hard
the individual words can be** — a thing the sentence-length and words/page anchors are blind to.
This is a real setting on the story: **`reading_level.read_mode`** = `read_aloud` or `solo`. Set
it deliberately for the ambiguous ages (~4–8); leave it off and it defaults by age (read-aloud
for ≤5, solo from 6). It is the single biggest lever on vocabulary, and it also **tightens the
words-per-page cap** for a solo reader:

- **Read-aloud (`read_aloud`) — a grown-up reads it.** The default for ages ~3–6, and common up
  to ~8 for a bedtime book. The child *listens*, so a juicy, low-frequency, many-syllabled word
  is a **gift** — "hawthorn", "catastrophe", "reflected" land beautifully when a parent says
  them. Reach for rich words here; they grow a kid's ear. The page can carry more text, too,
  because the grown-up does the decoding.
- **Solo decoder (`solo`) — the child reads it alone.** Possible from ~5 and the norm by ~7. Now
  every word has to be *sounded out by a small person*, so lean on **high-frequency / decodable**
  words: short, common, regularly-spelled. A low-frequency three-syllable word ("privacy",
  "collapses", "definitely") isn't a treat — it's a wall the kid hits mid-joke and gives up. Keep
  stretch words to **one or two a page at most**, and make them ones a 6-year-old could plausibly
  attack. **And cut the words-per-page right down** — a brand-new solo reader needs short lines
  and lots of white space (the solo caps in `scripts/lib/readability.py` are roughly half the
  read-aloud cap for the young years; e.g. age 5 solo aims ~15 words/page typical / 25 max vs
  ≈ 55 read-aloud — 25 is the ceiling, not the target).

**A 5-year-old is the hinge case, and both books are real:** a *read-aloud* age-5 bedtime book
(rich words a parent voices, ~55 words/page) and a *solo* age-5 early reader (decodable words the
child sounds out, ~15 words/page typical / 25 max, short repetitive sentences) are two genuinely
different books at the same age. Pick one on purpose.

So before you fit the words, **know which book you're writing.** If it isn't obvious from the
request, *ask* — "is this one a grown-up reads aloud, or one the kid reads alone?" — set
`read_mode` to match, because the answer changes your whole vocabulary posture and the page cap,
not the sentence length. This is judgment, not a rule: no word list, no checker. When unsure for
the young ages, assume **read-aloud** (richer words welcome) — but say so, so the choice is
deliberate rather than accidental.

## The reader at each age

**Age 3 — lap reader (read *to*).** A grown-up reads every word. Write for the *ear*: one
short line a page, big rhythm, rhyme, and a refrain they can shout back. Naming words for
things they know. FK is meaningless here.
> *"Big red bus. Beep beep beep! Who's that hiding? Little sheep!"*
Anchors: ~1 line, 3–6 words; ≤ ~18 words/page.

**Age 4 — pre-reader.** Still read aloud, but they're starting to track words and *love* a
repeated pattern they can predict and finish for you. One idea a page; let the picture carry
the rest. A silly sound beats a "correct" word every time.
> *"The frog went hop. The frog went plop. The frog would NOT, would not, would not stop!"*
Anchors: 1 sentence, 5–10 words; ~35 words/page; FK ~0.

**Age 5 — kindergarten / brand-new reader.** The hinge age — decide `read_mode` (see above).
Sounding out their first words. Short, *whole* sentences (subject + verb) they can decode, with
lots of friendly repetition and a few sight words. One big new word as a treat — said with
relish — is a gift, not a problem.
> *"Pip had a plan. It was a VERY big plan. He grinned and grabbed his hat."*
Anchors: 6–9 words a sentence.
> • **Read-aloud** (a grown-up voices it): ~55 words/page; reach for a rich, fun word or two.
> • **Solo reader** (the child decodes it): aim **~15 words/page on a typical page, 25 max** —
>   short lines and white space; high-frequency/decodable words, at most one stretch word a page.
>   (25 is the *ceiling*, not the target — a brand-new 5-year-old decoder is closer to Fountas &
>   Pinnell level A–B, ~5–15 words/page; 25 sits at level C, the top of kindergarten.)
FK ~0–0.6 (don't chase it).

**Age 6 — kindergarten / Grade 1.** Reading simple sentences with growing confidence. You
can chain two clauses with *and / but / so*, build a little suspense across a page-turn, and
sprinkle the occasional juicy stretch word. **This is the hinge age** (see "Read-aloud or
reading it alone?" above): a read-*aloud* 6-year-old book can carry rich words a parent voices,
while a *solo*-reader 6-year-old book should stay mostly high-frequency and decodable with only
a stretch word or two a page. Decide which, then choose words to match.
> *"She tiptoed past the dragon, so quiet, so slow — and then her tummy gave a GIANT
> rumble."*
Anchors: 7–11 words, vary them; ~70 words/page; FK ~0.6–1.3.

**Age 7 — Grade 1–2.** Reading more on their own. Real sentences with cause and effect, a
joke that needs a beat of setup, dialogue. Vary long-and-short for rhythm. (This is the first
age where the FK number carries any signal — still soft.)
> *"Nobody believed Mia could fly. That was exactly why she climbed the tallest tree in town
> and flapped her arms like a furious chicken."*
Anchors: average 8–12 words, longest up to ~16; ~100 words/page; FK ~1.5–2.3.

**Age 8 — Grade 2–3.** Comfortable readers who enjoy a richer voice, wordplay, and a plot
with a twist. Longer paragraphs are fine; let characters argue and scheme on the page.
> *"The map was definitely a fake — the 'X' was drawn in crayon — but a fake map is still a
> map, and Theo was not about to waste a perfectly good adventure."*
Anchors: average 10–14 words, varied; ~130 words/page; FK ~2.5–3.3.

**Age 9 — Grade 3–4.** Fluent. They want voice, humor that rewards attention, vivid verbs,
and figurative language that surprises. Vary sentence shape boldly.
> *"Grandpa's invention coughed twice, sneezed a cloud of purple smoke, and then — to
> everyone's complete astonishment — politely asked for a cup of tea."*
Anchors: average 12–16 words; ~180 words/page; FK ~3.5–4.3.

**Ages 10–12 — middle grade.** Full prose. Subplots, irony, real stakes, jokes with a long
fuse, a narrator with attitude. The "words/page" cap stops mattering — pacing and chapter
rhythm take over.
> *"There are two kinds of people in the world: those who read the warning label on the
> Mysterious Glowing Jar, and those who, like Sam, found out the hard way."*
Anchors: average 12–20 words, fully varied; FK ~4.5–7.0 across the span.

**Grown-up.** Full literary range — sophisticated vocabulary, complex sentences, a real
authorial voice, humor that rewards an adult. No word caps.

## The telegraphic trap (the #1 way books here have gone wrong)

Aiming at the *short-sentence* anchors by **amputation** produces fragment-chains that no
human would ever say out loud:

> ❌ "Seoul at night. Bright lights. Palaces glow. Best snack spot. A lady watches."
>
> ❌ "Note: VP Paperweight. Name: Brad. He likes paperweights. He asks them what to do."

Every fragment is "short enough," and the whole thing is unreadable — no subjects, no verbs,
no connective tissue, no voice. Kids learning to read *lean on* natural sentence structure;
fragments take that crutch away while pretending to help. This is the one place the guidance
above is firm — not because a number says so, but because amputated prose simply isn't good
writing at any age.

The same beats, written as short **flowing** sentences — still easy for a 5–6-year-old:

> ✅ "Seoul glowed below them like a bowl of bright candy. Down in the night market, a
> lady watched them and held out one steaming bowl."
>
> ✅ "The note said the new boss was Brad. Brad loved paperweights so much that he asked
> them what to do."

Rules of thumb:

- **Every sentence has a subject and a verb.** Fragments are a *spice* — one for a beat of
  comic timing ("Uh oh.") — never the house style.
- **Sentences connect**: and, but, so, then, because. Cause-and-effect words are exactly
  what the spine is made of; use them in the prose too.
- **If a sentence runs too long, rewrite it as two natural sentences** — don't snap it into
  three stumps.
- **The read-aloud test beats every number.** If a grown-up reading it at bedtime sounds
  like a telegram, it fails, whatever the metrics say.

More notes:
- **Younger = usually read-aloud.** For ages 3–6 a grown-up is *usually* doing the reading, so
  write for the *ear*: rhythm, rhyme, repetition, words that are fun to *say*. Silly sounds beat
  "correct" words. But confirm it — a 5- or 6-year-old reading *solo* needs decodable words, not
  a parent's rich vocabulary (see "Read-aloud or reading it alone?" above).
- **One big idea per page** for the young ages, so the picture can carry it.
- **A few stretch words are good, not bad.** A kid *loves* a giant, ridiculous, satisfying
  word ("CATASTROPHE!"). Don't strip them out — just don't fill every line with them.

## Checking it (optional, soft — and never a blocker)

`scripts/reading_level.py` reports a Flesch–Kincaid grade, words/page, and longest sentence
against the chosen age. Use it as a **soft mirror** to catch a page that drifted *way* denser
than its age — not as a target to optimise toward. The validator's reading checks are
**advisory only**: they emit warnings, never a publish-blocking failure, because reading
level is a creative judgement, not a contract. The formula is blind to fun, voice, and
read-aloud rhythm, and unreliable below ~Grade 1. If a page reads great aloud and a kid that
age can follow it, it's right — whatever the number says.

That's it. Spend your energy on the story.
