---
name: illustration-consistency
description: Generate page and character illustrations that stay perfectly on-model across a whole book and series — by assembling prompts from the world art-style block + each character's appearance_token + locked palette + negative prompt + seed + reference images. Use when illustrating pages, making a character reference sheet, or fixing visual drift. Always go through scripts/generate_images.py; never hand-write a full prompt.
---

# Illustration consistency

Consistency is **assembled**, not hoped for. Read `methodology/consistency.md` (prompt
engineering levers) first. The golden rule: a page's `image.prompt` is the *scene only* — the
tooling injects style + character identity so every image matches.

## How a final prompt is assembled (done by scripts/generate_images.py)
```
PROMPT  = page image.prompt (scene/action/emotion)
        + appearance_token for each slug in characters_present
        + world art_style.prompt_style_block
        + "palette: " + world palette hexes (+ per-character color_palette)
        + composition note that keeps the page's text_zone clear
NEGATIVE = world art_style.negative_prompt
SEED     = character.seed (single hero) or a story-stable seed
REFS     = character.reference_images (image-to-image / reference anchor)
ASPECT   = world art_style.aspect_ratio
```

## Procedure
1. **Illustrate the character sheet FIRST** (lock identity before pages):
   `uv run python scripts/generate_images.py --character <world>/<char>` → produces a
   turnaround/hero sheet. Review it against the silhouette + distinguishing-features
   checklist, save the approved file to the character's `reference_images`, and fix `seed`.
2. **Generate pages**:
   `uv run python scripts/generate_images.py worlds/<world>/stories/<slug>` → renders each page,
   injecting the tokens above and writing `images/page-NN.png` + alt text back into the page.
   Use `--page N` to (re)render one, `--seed N` to override.
3. **QC every page** against the bible:
   - Each character on-model: proportions, palette hexes, all `distinguishing_features` present.
   - Style matches `prompt_style_block` (medium, line, lighting); no `negative_prompt` items.
   - The `text_zone` is low-detail/clear so the scrim + text will be legible.
   - Scene matches the page text and emotion; honours world `rules` (no anachronisms).
4. **Fix drift**: strengthen the `appearance_token` (more concrete features/hexes), reuse the
   approved reference image more heavily, re-pin the seed, or regenerate just the bad page.
   If a character looks different at an evolution stage, that's intended only if the story
   pins that `stage` (which appends `appearance_delta`).

## Image provider — Google "Nano Banana" (default)
`generate_images.py` defaults to `--provider nano-banana` (Google Gemini's image model,
`gemini-2.5-flash-image`). Get a **free** key at https://aistudio.google.com/apikey and set
`GEMINI_API_KEY` (or `GOOGLE_API_KEY`). Nano Banana's superpower for us: it accepts each
character's **reference image as input**, so once you've approved a character sheet, every
page can be anchored to it — the single best lever for character consistency. Override the
model with `GEMINI_IMAGE_MODEL` (e.g. `gemini-3-pro-image` = "Nano Banana Pro"). Note:
Gemini images carry an invisible SynthID watermark.

## No API key?
With no key set, `generate_images.py` automatically falls back to labeled **placeholder** SVGs
(scene + character + seed on a palette-coloured card) so the whole pipeline still runs,
validates, and builds. Add a key and re-run to get real art; everything else stays the same.
(`--provider openai` is also available with `OPENAI_API_KEY`.)

## Output
`worlds/<world>/stories/<slug>/images/page-*.png`, character `reference_images`, alt text on
each page. Next: `/validate` then `publishing`.
