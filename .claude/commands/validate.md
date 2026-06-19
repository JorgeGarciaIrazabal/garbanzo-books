---
description: Run full QA — schema, consistency, reading level, interactivity, accessibility — on a world/story.
argument-hint: [path, e.g. worlds/<world>/stories/<story>]  (default: everything)
---

Use the **book-validator** agent to QA: **$ARGUMENTS** (default: the whole workspace).

Steps:
1. Run `uv run python scripts/validate.py $ARGUMENTS` and read the report.
2. Cross-check the invariants by hand where useful:
   - Schema validity of world/character/story.
   - Consistency: referenced characters exist with `appearance_token`; valid pinned
     `evolution.stage`; no contradiction of world `rules`/`timeline`; art style present.
   - Language roughly age-fit (`reading_level.py` as a soft guardrail) — words don't block the fun.
   - Interactivity: data shapes correct; branching `goto`s resolve; no dead ends; games are varied.
   - Accessibility/layout: `layout` (text_position) + alt text on every page.
   - Illustration: every page has a real Gemini `.png` (SVG placeholders = hard FAIL).
3. Report an overall PASS/FAIL and an ordered, specific fix list. Offer to apply the fixes.
4. For a finished book, also run `uv run python scripts/quality_report.py $ARGUMENTS` and
   report the 7-gate scorecard — validation is "is it broken?", the scorecard is "how good is
   it?". Surface any WARN gates (voice/colour drift, missing feedback, thin pacing) as polish
   suggestions.
