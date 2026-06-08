---
description: Write a new interactive storybook in a world, end-to-end (spine → pages → reading level → interactions → layout).
argument-hint: <world-slug> <story title/idea> [--age 5-7]
---

Use the **storybook-studio** orchestrator to write a new story in world **$1** from this
brief: **$ARGUMENTS**

Lead with **fun** (read `methodology/fun-first.md`, the north star — funny, surprising, real
stakes, a little mischief, NO moral-of-the-story ending). Then run the stages in order,
delegating to the specialist skills/agents:
1. **story-craft** — confirm age band & cast (pin each character's `evolution.stage`); nail the
   hook and "why it's fun", then write the `logline`, `spine`, and `pages[]` at the ~14-spread
   rhythm with scene-only image prompts. Scaffold: `uv run python scripts/new_story.py <world> "<Title>" --age <band>`.
2. **reading-level-adaptation** — a light age-fit pass so the words don't block the fun;
   optionally spot-check with `uv run python scripts/reading_level.py <story-dir>`.
3. **interactive-elements** — add varied, genuinely-fun games as OPTIONAL add-ons on top of the
   finished story: rich-first (on-art / drag / puzzle / music / `custom`), ≥1 rich + ≥3 kinds,
   winnable, tied to each page — but never changing `page.text` or the art. The book must read
   as a complete story with every game skipped.
4. **page-layout** — set `layout` + `image.text_zone` + alt text per page.
5. Suggest `/illustrate <world>/<story>` next, then `/validate` and `/publish`.

Keep characters in voice and never contradict the world `rules`/`timeline`. Validate with
`uv run python scripts/validate.py worlds/<world>/stories/<story>` at the end.
