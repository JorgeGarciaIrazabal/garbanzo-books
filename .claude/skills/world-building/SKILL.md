---
name: world-building
description: Create a rich, reusable story world (a "world bible") with geography, rules, factions, timeline, motifs, themes, AND a locked art-style guide that guarantees visual consistency across every illustration and story. Use when the user wants a new world/universe/setting, or to extend an existing one. Produces worlds/<slug>/world.yaml + style-guide.md validated against schemas/world.schema.json.
---

# World-building

A world is the foundation everything else inherits. Build it like a series bible so dozens of
stories can live in it coherently. Read `methodology/consistency.md` (world bible section) and
`methodology/storybook-pipeline.md` first.

## Procedure
1. **Interview** the user for the creative core (offer options if they're unsure):
   - Premise / hook (what makes this world special) and **tone** (cozy? adventurous? silly?).
   - Target **age band(s)** — this constrains tone, complexity, and palette.
   - The kind of stories it should produce; recurring **themes** (courage, friendship…).
2. **Design the bible** — fill each `world.yaml` field deliberately:
   - `geography.locations` — 3–6 evocative places, each with a `mood`; mark `recurring: true`
     for ones you'll revisit.
   - `rules` — the inviolable laws (how magic/tech/nature works *and its limits*). These are
     the consistency contract; stories may never contradict them.
   - `factions` — groups and their `values` (sources of conflict & allies).
   - `timeline` — ordered eras/events grounding continuity.
   - `motifs` — recurring symbols, objects, refrains, colour meanings.
3. **Lock the art style** (`art_style`) — the most important consistency lever:
   - `medium`, `line_quality`, `shading`, `lighting`, `perspective`.
   - `palette` — 4–7 named swatches with `hex` and `role` (primary/accent/shadow/sky).
   - `prompt_style_block` — the **exact phrase appended to every image prompt**. Pack it:
     medium + mood + palette hexes + texture + lighting. Keep it stable forever.
   - `negative_prompt` — what to avoid everywhere (photorealism, scary faces, text artifacts,
     extra fingers, harsh shadows).
   - `aspect_ratio` (default 4:3) and `text_treatment` (placement, scrim, font,
     dyslexia_friendly).
4. **Scaffold the files** — run `uv run python scripts/new_world.py "<Title>"` (or write the YAML
   following `schemas/world.schema.json`; see `templates/README.md`). Then flesh out
   `style-guide.md` as the human-readable art
   direction (with the palette swatches and 2–3 do/don't examples).
5. **Validate**: `uv run python scripts/validate.py worlds/<slug>` (schema check).

## Quality bar
- Could a *different* illustrator read `style-guide.md` + `prompt_style_block` and produce
  on-brand art? If not, it's underspecified.
- Are the `rules` specific enough to generate conflict and prevent contradictions?
- Does the palette have enough range for varied scenes while staying recognisable?
- Is the world age-appropriate in tone for every band in `target_age_bands`?

## Output
- `worlds/<slug>/world.yaml` (valid against `schemas/world.schema.json`)
- `worlds/<slug>/style-guide.md`
- `worlds/<slug>/characters/` and `stories/` directories ready for content.

Next: `/new-character` to populate the cast.
