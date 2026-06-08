# The Professional Storybook Pipeline

> **Read `fun-first.md` first.** This pipeline is the skeleton; fun is the muscle and the
> blood. A perfectly-structured book with no jokes and no jeopardy is a dead book. Every
> gate below serves the romp — never the other way round.

How top studios and publishers move from idea to finished book. Follow the gates in order;
each one de-risks the next.

## 1. Concept / premise
Start with a one-sentence **hook** and answer the only question that matters: **why is this
fun?** Where are the laughs, the stakes, the mischief, the surprise? Pressure-test it *before*
any art exists by pitching it out loud — if it doesn't make you grin or lean in, it's not
ready. A good premise names a protagonist a kid roots for, what they want badly, and the
gloriously bad thing in the way. (An emotional core is welcome — but it lives *underneath*
the fun and is never spelled out.)

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
5. **Don't-punch-down check** — a quick, light pass: is any joke built on a lazy stereotype
   of a real group of people? Fix only that. This is NOT a pass to sand the edges, danger,
   mischief, or scares off the story — villains, peril, gross-out, and rule-breaking heroes
   all stay. (See the "one line of decency" in `fun-first.md`.)

## The gate checklist (don't skip ahead)
- [ ] **Is it FUN?** Real laughs, real stakes, or real mischief on the page — would a kid
      grab the next page before you finish this one? (If no, nothing else matters yet.)
- [ ] One-sentence hook agreed; the "why is this fun" answered
- [ ] Spine complete, each beat causes the next; no moral-of-the-story ending
- [ ] Words roughly age-fit (light touch — never at the cost of a joke or the pace)
- [ ] Page/spread outline with deliberate page-turns ending on cliffs/uh-ohs
- [ ] Characters have model sheets/reference art; style guide locked
- [ ] Color/mood arc planned across the book
- [ ] Quick don't-punch-down check before final illustration

(Sources: aerogrammestudio.com; storyprompt.com; highlightsfoundation.org; taralazar.com;
champandnessie.com; debbieohi.com)
