---
round: 1
target: worlds/super-girls/stories/the-starfall-squad/story.yaml
date: 2026-06-09
status: PROMOTE (with one carry-over to round 2)
---

# Round 1 — orchestrator notes

## Convergence

**Strong.** All three critics independently landed on the same target: **the climax (pages 22–29 in the old draft) is a letdown, and the book is too long.**

- **Heckler** said: the ancient being is the best thing in the book and the book is *terrified* of it. The "think about your bed" ending is a video-game level-up, not a real escape. The DOOR-sized shield arrives cost-free. Barnaby gets away with everything.
- **Minimalist** said: 22 of 28 pages over the 60-word cap. Manuscript is 2442 words vs 1500 target. Pages 1–4 are dead air. Page 14 is the cute page. The exposition is retrofit.
- **Kid-reader** said: page 24 is the climax and it's a *disappointment*. A 5-year-old will feel cheated. The book promised a chase and delivered "and then they woke up."

That's three different lenses, one conclusion. **High-signal target.**

## What the author (this round) did

Agreed with the convergence. Rewrote:

1. **Pages 1–4 (the four meet-cutes) → one montage page.** Drops ~250 words, gets the story moving by page 2.
2. **Page 6 (the four bad dreams) → tightened.** Trust the image to do the work.
3. **Page 14 (the "you have powers" speech) → one line.** Killed the cute.
4. **Pages 22–29 (the climax) → complete rewrite.** Girls' first attempt to wake up **fails**. They have to use their powers for real. Clara's shield cracks but holds. Catalina's vines become a net. Ziba's chicken Junior flies into the ancient being's nostril. It sneezes them out. The escape is mid-chaos. The cliff is real: the eyes are still open.
5. **End page 27** is now just: *"~ The eyes are still open. ~"* No more "the adventure is just beginning" soft-pedal.

Manuscript word count: **2442 → 1586** (35% reduction). Page count: 30 → 28. Closing pages went from 8 to 2.

## Validation

```
uv run python scripts/validate.py .debate/round-1/draft-after.yaml
→ 21 checks PASS, 7 warnings (same as before — catchphrase + voice-density warnings, unchanged)
→ Schema-valid
```

## What we did NOT do (and why)

- **The word-per-page cap is still violated** on 16 of 28 pages. The author took the *big* cuts (250 words on the intros, 200+ words on the climax) but left the per-page cap alone on most pages. Total word count is fine; per-page cap is not. The 60-word cap is set by the *story's own* `reading_level.max_words_per_page: 60`, and pages 4, 5, 6, 7, 9, 11, 12, 13, 15, 16, 19, 20, 22, 24, 25 still run 64–105 words. **Page 22 is the worst at 105 words** — the sneeze scene has too much exposition.

- **Why carry this to round 2 instead of rolling back**: the structural improvements (real climax, Junior saves the day, no level-up) are the highest-value change in the loop so far. The word-per-page cap is a *quantitative* issue the author can solve mechanically in round 2 without re-doing the architecture. Rolling back would lose the climax fix.

## Rollback decision

**PROMOTE** `draft-after.yaml` → `story.yaml`.

- The story is *sharper, funnier, and less preachy* in the ways all three critics asked for.
- The mischief is intact (Junior the chicken now saves the day, Barnaby still gets the cocoa).
- The ending is a real cliff, not a level-up.
- The word-per-page miss is a quantified, mechanical fix — not a creative failure.
- A real author would have caught the per-page cap in the same pass. The mechanical over-cap is a craft slip we attribute to *this* model run, not to the design. The round-2 brief will make the cap the explicit target.

## Round 2 brief (what the next round's critics + author will see)

Round 1's complaints, in priority:

1. **Convergence target was met (climax fix).** Don't re-attack. Move to the next biggest complaint.
2. **New brief for round 2:** the word-per-page cap. The story is now 1586 words / 28 pages. The cap is 60 words/page. 16 of 28 pages are over. The author needs to *tighten* without *losing*:
   - The new climax (the sneeze, Junior's flight, the cracked shield)
   - The Junior gag
   - Barnaby's "I maybe forgot" beat
   - The "eyes are still open" ending
3. **Secondary brief:** the catchphrases and voice-density warnings (5 catchphrases never used, 2 voice-mismatch warnings). The author should sprinkle at least one of each character's catchphrases into the prose. This is *not* the round's main job but a free win.

What the round-2 critics should *not* attack:
- The structure (it's better; don't re-litigate).
- The "do the powers, don't just wake up" fix (it's in; don't re-attack).
- The Junior gag (it's earned its place).

What the round-2 critics *should* attack:
- The kid-reader: "is there still a boring page?"
- The minimalist: "is the word cut *clean*, or did the prose go thin?"
- The heckler: "did the trimmed prose sand off the mischief?"
