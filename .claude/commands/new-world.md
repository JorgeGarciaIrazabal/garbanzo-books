---
description: Create a new story world (world bible + locked art style) from an idea.
argument-hint: <world idea / title> [age band(s)]
---

Use the **world-building** skill to create a new world from this brief: **$ARGUMENTS**

Steps:
1. Read `CLAUDE.md`, `methodology/consistency.md`, and `schemas/world.schema.json`.
2. If the brief is thin, ask a few sharp questions (tone, target age band(s), recurring
   themes, art-style feel) — offer 2–3 concrete options where helpful.
3. Scaffold with `uv run python scripts/new_world.py "<Title>"`, then flesh out `world.yaml`
   (geography, rules, factions, timeline, motifs, themes) and lock the `art_style`
   (palette hexes, `prompt_style_block`, `negative_prompt`, text treatment).
4. Write `style-guide.md` with swatches and do/don't notes.
5. Validate: `uv run python scripts/validate.py worlds/<slug>`.
6. Summarise the world and suggest `/new-character`.

You may delegate to the **world-architect** agent.
