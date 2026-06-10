# Age-Fit Language (light touch)

> **Read `fun-first.md` first.** Fun outranks everything here. This doc exists for ONE
> reason: make sure the words don't get in the way of the story. A kid who can't read the
> sentence can't enjoy the joke. That's the whole point — not a reading curriculum.

This is a *light touch*, not a phonics program. Pick words and sentence lengths a kid that
age can comfortably read, then get back to making the story rip. **Never** swap a funnier
word for a duller one, or flatten a great line, just to hit a number.

## The only table you need

Rough guidance — aim near it, don't obsess over it. When in doubt, read it **aloud**: if it
sounds like a person telling a great story, it's right; if it sounds like a telegram or a
robot, it's wrong — however good the numbers look.

The sentence column is a **typical/average** length. The *longest* sentence in the book can
run well past it (the band caps in `scripts/lib/readability.py` bound that). Vary the
shapes: a long rolling sentence, then a short punch. That contrast IS the rhythm.

| Band | Age | Typical sentence | Words/page | Word choice |
|---|---|---|---|---|
| **0–3** | 0–3 | 1 short line, 3–6 words | 0–10 | everyday naming words; lean on rhyme & repetition |
| **3–5** | 3–5 | 1 sentence, 5–10 words | 10–40 | common words; a fun repeated refrain reads great aloud |
| **5–7** | 5–7 | average 6–9 words, longest up to ~14 | 20–60 | mostly simple words a new reader can sound out; sprinkle a few exciting big ones |
| **7–9** | 7–9 | average 8–14 words, vary it | 50–150 | richer vocabulary, wordplay, the occasional delicious tricky word |
| **9–12** | 9–12 | 12–20 words, varied | full prose | full range — figurative language, voice, jokes that reward a sharp reader |

## The telegraphic trap (the #1 way books here have gone wrong)

Chasing the sentence numbers by **amputation** produces fragment-chains that no human
would ever say out loud:

> ❌ "Seoul at night. Bright lights. Palaces glow. Best snack spot. A lady watches."
>
> ❌ "Note: VP Paperweight. Name: Brad. He likes paperweights. He asks them what to do."

Every fragment is "in band," and the whole thing is unreadable — no subjects, no verbs, no
connective tissue, no voice. Kids learning to read *lean on* natural sentence structure;
fragments take that crutch away while pretending to help.

The same beats, written as short **flowing** sentences — still squarely in the 5–7 band:

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
- **If a sentence is too long, rewrite it as two natural sentences** — don't snap it into
  three stumps.
- **The read-aloud test beats every number.** If a grown-up reading it at bedtime sounds
  like a telegram, it fails, whatever `reading_level.py` says. (The script now also flags
  this: prose averaging under the band's floor fails as "telegraphic.")

Notes:
- **Younger = read-aloud.** For 0–5 the grown-up is reading it, so write for the *ear*:
  rhythm, rhyme, repetition, words that are fun to *say*. Silly sounds beat "correct" words.
- **One big idea per page** for the young bands, so the picture can carry it.
- **A few stretch words are good, not bad.** A kid *loves* a giant, ridiculous, satisfying
  word ("CATASTROPHE!"). Don't strip them out — just don't fill every line with them.

## Checking it (optional, soft)

`scripts/reading_level.py` reports a Flesch–Kincaid grade, words/page, and longest sentence.
Use it as a **soft guardrail** to catch a page that drifted way too dense for its band —
not as a target to optimise toward. The formula is blind to fun, voice, and read-aloud
rhythm, and it's unreliable below ~Grade 1 anyway. If a page reads great aloud and a kid
that age can follow it, it passes — whatever the number says.

That's it. Spend your energy on the story.
