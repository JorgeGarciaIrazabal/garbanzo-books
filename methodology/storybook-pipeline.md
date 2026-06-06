# The Professional Storybook Pipeline

How top studios and publishers move from idea to finished book. Follow the gates in order;
each one de-risks the next.

## 1. Concept / premise
Start with a one-sentence **hook** and a single **emotional truth**. Pressure-test the
premise *before* any art exists. A good premise names a relatable protagonist, what they
want, and what's in the way.

## 2. The Story Spine
A fill-in-the-blanks armature (improv origin, Kenn Adams; adopted at Pixar c.1997 and
popularised through story artist Emma Coats' "22 rules"):

> Once upon a time ___. Every day ___. **Until one day** ___. **Because of that** ___.
> Because of that ___. **Until finally** ___. **Ever since then** ___.

Every beat must *cause* the next — consequence drives plot, never coincidence. This maps
directly onto `story.yaml → spine`. Pair it with the Pixar discipline: *what is the one
thing the character wants, and what stands in the way?*

## 3. Manuscript & word-count targets by age
| Format | Age | Word count |
|---|---|---|
| Board book | 0–3 | ≤ 100 (often 0–50) |
| Early/concept picture book | 2–4 | 200–400 |
| Standard picture book | 3–7 | 400–600 (sweet spot ~500; sub-500 increasingly favoured) |
| Nonfiction picture book | 5–9 | 1,000–2,000 (≤ 3,000) |
| Early/leveled reader | 5–8 | 1,000–2,500 |
| Chapter book | 6–9 | 4,000–12,000 |
| Middle grade | 8–12 | 25,000–50,000 (young MG 15,000–35,000) |

(Sources: marykole.com; highlightsfoundation.org; self-publishingschool.com)

## 4. The 32-page convention & signatures
Picture books are almost always **32 pages** because of binding physics: paper folds into
16-page *signatures*; two sewn together = 32. Other valid counts (16, 24, 40, 48) are also
multiples of 8. Of 32 pages, ~3–4 are front/back matter (title, copyright, dedication),
leaving **~28–30 story pages ≈ 14 double-page spreads** plus opening/closing singles.
(Sources: champandnessie.com; debbieohi.com)

Our digital books aren't bound, so the count is flexible — but the **~14-spread rhythm** is
still an excellent pacing target for a standard picture book, and keeping a sensible,
deliberate page count makes a better-paced read than sprawl.

## 5. Storyboard vs. dummy
- **Storyboard** — a thumbnail grid showing the whole book at once, to plan pacing and the
  emotional arc. (In this workspace: the `pages[]` outline + the optional color script.)
- **Dummy** — a folded, bound mock-up that simulates real page-turns at trim size. (Here:
  the built preview in `site/` you click through before illustrating in full.)

## 6. Page-turn dynamics
The page-turn is a storytelling device. End a spread on a **question, threat, or
cliffhanger** so the turn delivers surprise, payoff, or comic timing. Plan deliberate turns
at tension peaks and vary the rhythm — don't resolve everything on the same page it's raised.

## 7. Production craft & gates
1. **Character model sheets / turnarounds** (front, 3/4, profile, back) — lock proportions
   before full art. → our character `reference_images`.
2. **Style guide** — fixes line weight, palette, texture, lighting. → world `art_style` +
   `style-guide.md`.
3. **Color script** — maps the emotional colour arc spread-by-spread (a Pixar staple).
4. **Art direction + revision rounds** — thumbnails → rough sketches → line → colour, with
   editorial/AD notes at each gate.
5. **Sensitivity reading** — cultural, disability, racial accuracy; done late-manuscript /
   dummy stage, *before* final art.

## The gate checklist (don't skip ahead)
- [ ] One-sentence hook + emotional truth agreed
- [ ] Spine complete, each beat causes the next
- [ ] Word count within the age-band target
- [ ] Page/spread outline with deliberate page-turns
- [ ] Characters have model sheets/reference art; style guide locked
- [ ] Color/mood arc planned across the book
- [ ] Sensitivity pass before final illustration

(Sources: aerogrammestudio.com; storyprompt.com; highlightsfoundation.org; taralazar.com;
champandnessie.com; debbieohi.com)
