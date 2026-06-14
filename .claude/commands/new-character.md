---
description: Add a character bible (personality + locked appearance_token + evolution) to a world.
argument-hint: <world-slug> <character name/idea>
---

Use the **character-design** skill to create a character for world **$1** from this brief:
**$ARGUMENTS**

This command is **gate ① (character description)** in the studio's four-gate flow
(① character description → ② story description → ③ character images → ④ story images). It
produces the character's **TEXT bible only**. The reference-sheet *image* is a separate, later,
separately-confirmed step (gate ③, via `/illustrate --character`) — **do not generate it here.**

Steps:
1. Complete the **pre-flight checklist** in `CLAUDE.md` (schemas + methodology + principles);
   `consistency.md` is the most central doc here. Inherit the world's tone & target reader ages.
2. Define personality (traits, motivation, flaws, voice), then an appearance built for the
   **silhouette test** with 2–4 named distinguishing features and per-part palette hexes.
3. Write a stable, concrete `appearance_token`. Plan an `evolution` track if the character
   should grow across the series.
4. Scaffold with `uv run python scripts/new_character.py <world> "<Name>"` and fill the YAML.
5. Validate: `uv run python scripts/validate.py worlds/<world>`.
6. **✋ GATE ① — human confirmation.** Present the character bible (personality + appearance
   token + evolution) to the user and ask them to **approve or request modifications**. Loop
   until approved. Only after the description is signed off does the character feed a story
   (gate ②); the reference sheet is generated later via `/illustrate --character <world>/<slug>`
   and confirmed at gate ③.

**Delegation:** for a large or iterative character pass, hand this to the
**character-designer** agent (its own context window); for a quick pass, run the skill inline.
See *Skills, agents, and commands* in `CLAUDE.md`.
