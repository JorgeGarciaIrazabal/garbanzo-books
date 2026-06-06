---
description: Make a complete interactive storybook from scratch — world, characters, story, illustrations, validation, publish.
argument-hint: <one-line book idea> [--age 5-7]
---

Use the **storybook-studio** orchestrator to produce a complete book from this idea:
**$ARGUMENTS**

Drive the full pipeline, confirming the **age band & reading level** up front (it shapes
everything):
1. **world-building** → create (or reuse) a world + locked art style.
2. **character-design** → 1–3 characters with appearance tokens (+ reference sheets via
   `/illustrate --character`).
3. **story-craft** → spine + paged story (pin character evolution stages).
4. **reading-level-adaptation** → hit & verify the target level.
5. **interactive-elements** → add age-matched, skill-building interactions.
6. **page-layout** → text zones, layout, alt text.
7. **illustration-consistency** → generate page images (`scripts/generate_images.py`).
8. `/validate` → fix everything the validator flags.
9. **publishing** → build the site and (optionally) deploy.

Interview the user for creative direction where it matters; show artifacts (YAML + site
preview) as you go; end with the published URL and the world→story→tags paths.
