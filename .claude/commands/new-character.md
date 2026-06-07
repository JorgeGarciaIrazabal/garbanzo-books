---
description: Add a character bible (personality + locked appearance_token + evolution) to a world.
argument-hint: <world-slug> <character name/idea>
---

Use the **character-design** skill to create a character for world **$1** from this brief:
**$ARGUMENTS**

Steps:
1. Complete the **pre-flight checklist** in `CLAUDE.md` (schemas + methodology + principles);
   `consistency.md` is the most central doc here. Inherit the world's tone & age band.
2. Define personality (traits, motivation, flaws, voice), then an appearance built for the
   **silhouette test** with 2–4 named distinguishing features and per-part palette hexes.
3. Write a stable, concrete `appearance_token`. Plan an `evolution` track if the character
   should grow across the series.
4. Scaffold with `uv run python scripts/new_character.py <world> "<Name>"` and fill the YAML.
5. Recommend generating a reference sheet via `/illustrate --character <world>/<slug>` and
   recording `reference_images` + `seed`.
6. Validate: `uv run python scripts/validate.py worlds/<world>`.

**Delegation:** for a large or iterative character pass, hand this to the
**character-designer** agent (its own context window); for a quick pass, run the skill inline.
See *Skills, agents, and commands* in `CLAUDE.md`.
