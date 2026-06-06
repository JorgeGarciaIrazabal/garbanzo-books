---
description: Add a character bible (personality + locked appearance_token + evolution) to a world.
argument-hint: <world-slug> <character name/idea>
---

Use the **character-design** skill to create a character for world **$1** from this brief:
**$ARGUMENTS**

Steps:
1. Read `methodology/consistency.md`, `schemas/character.schema.json`, and the world's
   `world.yaml` (inherit tone & age band).
2. Define personality (traits, motivation, flaws, voice), then an appearance built for the
   **silhouette test** with 2–4 named distinguishing features and per-part palette hexes.
3. Write a stable, concrete `appearance_token`. Plan an `evolution` track if the character
   should grow across the series.
4. Scaffold with `uv run python scripts/new_character.py <world> "<Name>"` and fill the YAML.
5. Recommend generating a reference sheet via `/illustrate --character <world>/<slug>` and
   recording `reference_images` + `seed`.
6. Validate: `uv run python scripts/validate.py worlds/<world>`.

You may delegate to the **character-designer** agent.
