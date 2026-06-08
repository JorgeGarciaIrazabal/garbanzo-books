---
description: Make a complete interactive storybook from scratch — world, characters, story, illustrations, validation, publish.
argument-hint: <one-line book idea> [--age 5-7]
---

Use the **storybook-studio** orchestrator to produce a complete book from this idea:
**$ARGUMENTS**

Lead with **fun** — nail the hook, the laughs, the stakes, and the mischief first (read
`methodology/fun-first.md`, the north star). Confirm the **age band** up front too (it sets a
light language touch and which games fit), but never let it sand down the fun. Then drive the
pipeline:
1. **world-building** → create (or reuse) a world + locked art style.
2. **character-design** → 1–3 characters with appearance tokens (+ reference sheets via
   `/illustrate --character`).
3. **story-craft** → spine + paged story (pin character evolution stages); make it a romp.
4. **reading-level-adaptation** → a light age-fit pass so the words don't block the fun.
5. **interactive-elements** → add varied, genuinely-fun games tied to each page.
6. **page-layout** → text zones, layout, alt text.
7. **illustration-consistency** → generate page images (`scripts/generate_images.py`).
8. `/validate` → fix everything the validator flags.
9. **publishing** → build the site and (optionally) deploy.

Interview the user for creative direction where it matters; show artifacts (YAML + site
preview) as you go; end with the published URL and the world→story→tags paths.
