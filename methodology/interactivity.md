# Engagement & Interactivity

What keeps kids turning pages: **agency, anticipation, predictable repetition, and physical
or verbal participation**. Interactive elements also build fine-motor skill, vocabulary, and
comprehension. Interleave one roughly every 2–4 pages; don't let them interrupt the story's
emotional flow — place them at natural beats.

## Interaction types mapped to age bands
✓✓ = ideal, ✓ = works.

| Interaction | 0–3 | 3–5 | 5–7 | 7–9 | 9–12 | Builds |
|---|:--:|:--:|:--:|:--:|:--:|---|
| Touch/texture (physical) | ✓✓ | ✓ | | | | sensory, print awareness |
| Lift-the-flap / tap-to-reveal (18mo+) | ✓ | ✓✓ | ✓ | | | anticipation, cause/effect |
| Call-and-response / repeated refrain | ✓✓ | ✓✓ | ✓ | | | phonemic awareness, fluency |
| "Read it again" / predictable text | ✓✓ | ✓✓ | ✓ | | | fluency, confidence |
| Rhyme completion (fill last word) | ✓ | ✓✓ | ✓ | | | phonemic awareness |
| Counting / number games | ✓ | ✓✓ | ✓ | | | numeracy, vocabulary |
| Seek-and-find / search | | ✓✓ | ✓✓ | ✓ | ✓ | vocabulary, attention |
| Spot-the-difference | | ✓ | ✓✓ | ✓✓ | ✓ | attention, detail |
| Sound-hunt (find the /s/ words) | | ✓ | ✓✓ | ✓ | | phonics |
| Word-match / trace-letter | | ✓ | ✓✓ | ✓ | | phonics, decoding |
| Simple riddles | | ✓ | ✓✓ | ✓✓ | ✓ | vocabulary, inference |
| Mazes | | ✓ | ✓✓ | ✓✓ | ✓ | problem-solving |
| Comprehension questions | | ✓ | ✓✓ | ✓✓ | ✓✓ | comprehension |
| Decision points / branching | | | ✓ | ✓✓ | ✓✓ | agency, comprehension |
| Memory / sequencing (drag-order) | | ✓ | ✓✓ | ✓✓ | ✓ | recall, comprehension |

Notes:
- Babies (6mo+): high-contrast art + texture. Lift-the-flap & sound interaction land best ~18 months.
- Preschoolers: simple problem-solving + narrative participation.
- **Branching / decision interactivity needs reading independence — best for 7+.**

## Design principles for each interaction
- **One clear instruction**, in the same age-appropriate language as the story.
- **Always winnable** — provide gentle "try again" feedback, never a dead end or a fail state.
- **Tie it to the page** — a seek-and-find should hunt for things actually in that
  illustration; a rhyme-complete should use the page's own rhyme.
- **Reinforce a target skill** — set `interaction.skill` (a reading pillar or `engagement`).
- **Reward warmly** — `feedback.correct` celebrates; `feedback.try_again` encourages.
- **Co-reader prompts** — for read-aloud bands, `reading_notes` gives the adult a question
  to ask ("What do you think Pip will do?").

## Payload shapes (`interaction.data`) by type
- `seek-and-find`: `{ items: ["acorn","blue bird","..."] }`
- `spot-the-difference`: `{ count: 5, image_b: "page-07b.png" }`
- `counting`: `{ target: 6, what: "mushrooms", answer: 6 }`
- `rhyme-complete`: `{ sentence: "The fox sat on a ___", answer: "box", distractors: ["dog","sun"] }`
- `word-match`: `{ pairs: [["cat","🐱"],["sun","☀️"]] }`
- `sound-hunt`: `{ sound: "s", words: ["sun","sock","snake"], decoys: ["moon"] }`
- `riddle`: `{ question: "...", answer: "owl", hint: "..." }`
- `comprehension-question`: `{ question: "Why was Pip scared?", options: ["...","..."], answer_index: 1 }`
- `choice` (branching): `{ options: [{ label: "Open the door", goto: 12 }, { label: "Run home", goto: 18 }] }`
- `maze`: `{ grid: "...", start: [0,0], end: [4,4] }`
- `trace-letter`: `{ letter: "s", word: "sun" }`
- `memory` / `drag-order`: `{ sequence: ["wake","wash","walk"] }`

(Sources: kingsresearch.com; en.wikipedia.org/Interactive_children's_book; lunesia.app;
littlescholarsnyc.com; teachearlyyears.com)
