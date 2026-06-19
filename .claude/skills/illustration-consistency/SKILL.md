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
        + composition note that keeps the page's text_position zone clear
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
3. **Best-of-N visual QC** (built in — runs automatically when Ollama is up):
   after each render, the candidate is scored by a local Ollama vision model against the
   page's spec (page text + expected characters + their appearance_tokens + the world
   style block + the locked palette + the reserved text_zone). The grader returns
   `{score, ok, reason, flags}` where `flags` can include `duplicate_characters`,
   `wrong_characters`, `missing_characters`, `scene_mismatch`, `style_inconsistent`,
   `text_zone_cluttered`, `anatomy_issue`, `too_dark`, `low_detail`, etc. If the score is
   below `--qc-threshold` (default 7.0), the seed is varied and a new candidate is generated
   — up to `--qc-retries+1` (default 3) candidates. The first one that passes wins; if none
   pass, the highest-scored one ships with its flags in the QC log. Each page writes a
   `page-NN.qc.json` sidecar recording every attempt's score, flags, and reason so the
   decision is auditable. `duplicate_characters` / `anatomy_issue` short-circuit the loop
   (a re-roll won't fix a prompt problem). Disable with `--qc-off`, override the model with
   `--qc-model gemma3:4b` (or set `VISION_QC_MODEL`), and override the endpoint with
   `OLLAMA_HOST`. If Ollama is unreachable, QC degrades to a permissive verdict — the first
   render ships, and the `qc.json` records `qc_unavailable` so the audit trail is honest.
4. **Human QC** every page against the bible:
   - Each character on-model: proportions, palette hexes, all `distinguishing_features` present.
   - Style matches `prompt_style_block` (medium, line, lighting); no `negative_prompt` items.
   - The `text_position` zone is low-detail/clear so the scrim + text will be legible.
   - Scene matches the page text and emotion; honours world `rules` (no anachronisms).
   - The per-page `page-NN.qc.json` log is clean (no `style_inconsistent`,
     `wrong_characters`, or `anatomy_issue` flags on the winning attempt).
5. **Fix drift**: strengthen the `appearance_token` (more concrete features/hexes), reuse the
   approved reference image more heavily, re-pin the seed, or regenerate just the bad page
   (`--page N` + a stronger prompt). If a character looks different at an evolution stage,
   that's intended only if the story pins that `stage` (which appends `appearance_delta`).

## QC provider — Local Ollama vision (RECOMMENDED)
The best-of-N loop above is powered by a local Ollama vision model so the whole pipeline
stays **API-key-free for QC** (image renders go through antigravity/nano-banana, not Ollama).
Any vision-capable model works; `gemma3:4b` is the default and is small enough to run on
CPU in a few seconds per page. To set it up:

```bash
ollama pull gemma3:4b        # one-time, ~3 GB
# Ollama must be running on $OLLAMA_HOST (default http://localhost:11434)
```

The grader inspects the rendered image for: characters present, characters on-model, no
duplicates, scene matches the page text, art style matches the world bible, text-zone
legible, and no clear anatomy issues. Each attempt's verdict is written to `page-NN.qc.json`
so the QC decision is reproducible and reviewable.

## Image provider — Antigravity (default) / Nano Banana (fallback)
`generate_images.py` defaults to `--provider antigravity` — the local Antigravity CLI (`agy`)
via your Google OAuth session, so **no API key is needed**. Install `agy` and sign in with
Google before illustrating. Override the model with `ANTIGRAVITY_MODEL` (default
`gemini-3.1-flash-image`). Note: agy's tool interface doesn't accept inline reference images,
so on-model consistency relies on the dense `appearance_token` text in the assembled prompt.

Fallback: `--provider nano-banana` (Google Gemini's image model, `gemini-2.5-flash-image`).
Get a **free** key at https://aistudio.google.com/apikey and set `GEMINI_API_KEY` (or
`GOOGLE_API_KEY`). Nano Banana's superpower for us: it accepts each character's **reference
image as input**, so once you've approved a character sheet, every page can be anchored to
it — the single best lever for character consistency. Override the model with
`GEMINI_IMAGE_MODEL` (e.g. `gemini-3-pro-image` = "Nano Banana Pro"). Note: Gemini images
carry an invisible SynthID watermark.

## Never accept placeholders
SVG placeholders are a **development-only** fallback baked into the script for offline
debugging. They are **NOT acceptable output**. If `generate_images.py` writes a `.svg` for any
page or character sheet, treat it as a hard failure:
1. Stop. Do not commit. Do not mark the story `published`.
2. Fix the root cause — install/sign in to `agy` (antigravity), or set `GEMINI_API_KEY` and
   run with `--provider nano-banana`, enable billing if the free quota was exhausted, or pick
   a different model via `GEMINI_IMAGE_MODEL` — then re-run until every page has a real `.png`.
3. Delete any leftover `.svg` placeholders the script may have written and re-point the page
   `image.file` to the `.png` (the script does this for you when the real provider succeeds).
Do **not** pass `--provider placeholder`. (`--provider openai` with `OPENAI_API_KEY` is the
only acceptable alternative if both antigravity and Gemini are unavailable.)

## Output
`worlds/<world>/stories/<slug>/images/page-*.png` (winner), per-page `page-NN.prompt.txt`
(the exact assembled prompt that produced it), per-page `page-NN.qc.json` (every QC
attempt's score/flags/reason), character `reference_images`, alt text on each page. Next:
`/validate` then `publishing`.
