---
description: Create a new story world (world bible + locked art style) from an idea.
argument-hint: <world idea / title> [reader age(s) in years]
---

Use the **world-building** skill to create a new world from this brief: **$ARGUMENTS**

Steps:
1. Complete the **pre-flight checklist** in `CLAUDE.md` (schemas + methodology + principles);
   `consistency.md` is the most central doc here.
2. If the brief is thin, ask a few sharp questions (tone, target reader age(s) in years,
   recurring themes, art-style feel) — offer 2–3 concrete options where helpful.
3. Scaffold with `uv run python scripts/new_world.py "<Title>" --year 5 --year 6 --year 7`,
   then flesh out `world.yaml`
   (geography, rules, factions, timeline, motifs, themes) and lock the `art_style`
   (palette hexes, `prompt_style_block`, `negative_prompt`, text treatment).
4. Write `style-guide.md` with swatches and do/don't notes.
5. Validate: `uv run python scripts/validate.py worlds/<slug>`.
6. Summarise the world and suggest `/new-character`.

**Delegation:** for a large or iterative world build, hand this to the **world-architect**
agent (its own context window); for a quick pass, run the skill inline. See *Skills, agents,
and commands* in `CLAUDE.md`.
