---
description: Generate on-model illustrations for a story's pages or a character reference sheet.
argument-hint: <world>/<story>  |  --character <world>/<char>  [--page N] [--seed N]
---

Use the **illustration-consistency** skill to illustrate: **$ARGUMENTS**

Rules:
- NEVER hand-write a full image prompt. Always run `uv run python scripts/generate_images.py` so the
  world `prompt_style_block` + palette + negative prompt and each present character's
  `appearance_token` are injected automatically, with seed + reference images.

This command owns the two **image** gates of the studio's four-gate flow (① character
description → ② story description → ③ character images → ④ story images). Image generation
spends real budget (Nano Banana) and re-rendering is expensive, so words are locked first and
every render ends in a **human sign-off**.

**A `--character` pass = GATE ③ (character images).**
1. Generate the reference sheet, QC against the silhouette & distinguishing-features checklist.
   Fix drift by strengthening the `appearance_token`, re-pinning the seed, or regenerating.
2. **✋ GATE ③ — human confirmation.** Show the sheet to the user and ask them to **approve or
   request modifications**. Loop (regenerate / re-pin seed) until approved. Only on approval
   save the render to `reference_images` and lock `seed`. Don't illustrate story pages with
   characters whose sheets aren't approved.

**A STORY pass = GATE ④ (story images).** Pre-flight (confirm BOTH before any page render):
- **Gate ② is signed off** — the written book is approved by the user, `validate.py` is clean,
  `quality_report.py` has no failing gate, and it reads well aloud. If not, finish/approve the
  words first.
- **Gate ③ is signed off** — every character in the roster has an *approved* reference sheet +
  locked `seed`, on-model for its `evolution.stage` (`methodology/consistency.md`). If any is
  missing/unapproved, do the `--character` pass above first.
Then:
3. Run `uv run python scripts/generate_images.py worlds/<world>/stories/<story>`
   (or `--page N` for one page). Image files + alt text are written back to the pages.
4. QC each page: on-model proportions/palette, all distinguishing features, style matches,
   no negative-prompt artifacts, the text_position zone kept clear, scene matches the text. Fix drift by
   strengthening the appearance_token, leaning on the reference image, re-pinning the seed, or
   regenerating the bad page.
5. **✋ GATE ④ — human confirmation.** Show the illustrated pages to the user and ask them to
   **approve or request modifications**. Loop (regenerate flagged pages) until approved. Don't
   move to `/validate` + `/publish` until they say go.

(Real Gemini PNGs are REQUIRED. If `GEMINI_API_KEY` / `GOOGLE_API_KEY` is unset the script
falls back to SVG placeholders — treat that as a hard failure: set the key, re-run, and
verify every page has a real `.png` before continuing. Never accept `.svg` output for a page
or character sheet.)

**Delegation:** for a large or iterative illustration pass, hand this to the
**illustration-director** agent (its own context window); for a quick pass, run the skill
inline. See *Skills, agents, and commands* in `CLAUDE.md`.
