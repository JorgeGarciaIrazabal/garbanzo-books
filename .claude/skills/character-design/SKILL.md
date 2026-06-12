---
name: character-design
description: Design a consistent, memorable character bible — personality (for behaviour/voice consistency), a locked visual appearance_token (for illustration consistency), reference art + seed (image anchors), and an evolution track so the character can grow across a series without losing identity. Use when adding or revising a character. Produces worlds/<world>/characters/<slug>.yaml validated against schemas/character.schema.json.
---

# Character design

Characters carry the series. Build them so they always *act* and *look* the same — yet can
grow. Read `methodology/consistency.md` (character toolkit) first.

## Procedure
1. **Anchor to a world** — every character has `world: <slug>`. Inherit its tone & age band.
2. **Personality first** (drives behaviour & dialogue consistency):
   - `traits` (3–5), `motivation` (what they want most), `flaws` (the growth edges that fuel
     arcs), `strengths`, `fears`, `quirks`, `values`.
   - `voice` — `speech_style`, `catchphrases`, `vocabulary_level` (age-appropriate).
3. **Design the look for the silhouette test** (`appearance`):
   - `build`, `height` (relative scale matters), `skin`, `hair`, `eyes`, signature `outfit`.
   - `distinguishing_features` — 2–4 unmistakable identifiers that survive a black-silhouette
     test and read at any size (e.g. "star patch over left eye", "always carries a brass
     lantern"). This is what keeps the character recognisable.
   - `color_palette` — exact `hex` per part (coat/hair/boots). Locked.
   - `silhouette_notes` — what makes them recognisable in pure outline; ensure it's *distinct*
     from other characters in the world.
4. **Write the `appearance_token`** — the #1 visual-consistency lever. A single dense
   descriptor string injected verbatim into every image prompt featuring them. Format:
   `NAME: <species/age/build>, <hair+hex>, <eyes+hex>, <signature outfit+hexes>,
   <distinguishing features>, <default expression>`. Make it concrete (proportions, colours),
   not vague adjectives. Keep it stable forever; only `evolution` stages may extend it.
5. **Plan evolution** (optional but powerful) — ordered `evolution` stages, each with a stable
   `stage` id, `summary`, `personality_delta`, and `appearance_delta` (visible changes
   appended to the token when active) and what `unlocked_by` it. Lets the same character be a
   timid sapling in book 1 and brave in book 4 — without becoming a different character.
6. **Create reference art** (strongly recommended): illustrate a character sheet
   (`/illustrate --character <slug>`) and save it to `reference_images`; set a stable `seed`.
   These anchor every future render.
7. **Scaffold & save**: `uv run python scripts/new_character.py <world> "<Name>"`, then fill the
   bible with a **JSON patch** — never edit the YAML text directly:
   ```bash
   uv run python scripts/edit_character.py <world>/<slug> <<'JSON'
   {"appearance_token": "...", "personality": {...}, "appearance": {...}, "evolution": [...]}
   JSON
   ```
   (Nested objects merge; lists replace wholesale; the tool schema-validates before writing.)
   Then `uv run python scripts/validate.py worlds/<world>`.

## Quality bar
- Silhouette test: black out the figure — still recognisable? Distinct from castmates?
- Does the `appearance_token` alone let an image model draw them on-model?
- Is the personality specific enough to predict how they'd react on any page?
- Do evolution stages preserve core identity (same distinguishing features) while changing?

## Output
`worlds/<world>/characters/<slug>.yaml` + optional `<slug>.refs/` art. Next: `/new-story`.
