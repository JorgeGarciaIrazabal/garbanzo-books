---
description: Generate on-model illustrations for a story's pages or a character reference sheet.
argument-hint: <world>/<story>  |  --character <world>/<char>  [--page N] [--seed N]
---

Use the **illustration-consistency** skill to illustrate: **$ARGUMENTS**

Rules:
- NEVER hand-write a full image prompt. Always run `uv run python scripts/generate_images.py` so the
  world `prompt_style_block` + palette + negative prompt and each present character's
  `appearance_token` are injected automatically, with seed + reference images.

Steps:
1. If a character sheet is requested (`--character`), generate it, QC against the silhouette &
   distinguishing-features checklist, save the approved render to `reference_images`, and fix
   `seed`.
2. For a story, run `uv run python scripts/generate_images.py worlds/<world>/stories/<story>`
   (or `--page N` for one page). Image files + alt text are written back to the pages.
3. QC each page: on-model proportions/palette, all distinguishing features, style matches,
   no negative-prompt artifacts, `text_zone` kept clear, scene matches the text.
4. Fix drift by strengthening the appearance_token, leaning on the reference image,
   re-pinning the seed, or regenerating the bad page.

(No image API key → labeled placeholders are produced so the pipeline still runs.)
You may delegate to the **illustration-director** agent.
