---
description: Make a complete interactive storybook from scratch — world, characters, story, illustrations, validation, publish.
argument-hint: <one-line book idea> [--year 6]
---

Use the **storybook-studio** orchestrator to produce a complete book from this idea:
**$ARGUMENTS**

Lead with **fun** — nail the hook, the laughs, the stakes, and the mischief first (read
`methodology/fun-first.md`, the north star). Confirm the reader's **age in years** up front
too (it sets a light language touch and which games fit), but never let it sand down the fun.

Build the book **WORDS first, then ART**, with a **human sign-off at four gates, in order:
① character description → ② story description → ③ character images → ④ story images.** At
each gate you STOP, show the artifact, and ask the user to approve or request changes — and
you do NOT continue (or start the next gate's work) until they say go. Locking the words
before any render means a rewrite costs zero image budget.

0. **world-building** → create (or reuse) a world + locked art style.
1. **① Character descriptions** — `character-design`: 1–3 characters with personality + a
   locked `appearance_token` + evolution track. **TEXT ONLY — generate no images yet.**
   → **✋ GATE ①:** show the character bibles, ask the user to confirm or change. Loop until approved.
2. **② Story description** — `story-craft` (spine + paged romp; pin each character's evolution
   stage) → `reading-level-adaptation` (light age-fit) → **read-aloud & flow pass** (fix
   telegraphic prose / fancy words / disconnected or flat pages; deeper pass: `/new-debate`) →
   `interactive-elements` (optional `arcade-*` games on top, matched to beats) → `page-layout`
   (text zones, alt text). Pre-check: `scripts/validate.py` clean + `scripts/quality_report.py`
   no failing gate.
   → **✋ GATE ②:** read the finished story to the user, ask to confirm or change. Loop until
   approved. Spend NO renders before this yes.
3. **③ Character images** — `illustration-consistency` via `/illustrate --character <world>/<char>`:
   generate each reference sheet, QC on-model, save to `reference_images`, lock `seed`.
   → **✋ GATE ③:** show the reference sheets, ask to confirm or change (regenerate / re-pin
   seed). Loop until approved. Don't illustrate pages before this yes.
4. **④ Story images** — `illustration-consistency` via `/illustrate <world>/<story>`: generate
   page art that inherits the approved character sheets + world style.
   → **✋ GATE ④:** show the illustrated pages, ask to confirm or change (regenerate bad pages).
   Loop until approved. Don't publish before this yes.
5. `/validate` → fix everything the validator flags.
6. **publishing** → build the site and (optionally) deploy.

Interview the user for creative direction where it matters; show artifacts (YAML + rendered
images + site preview) as you go; end with the published URL and the world→story→tags paths.
