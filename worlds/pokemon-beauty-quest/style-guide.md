# The World of Beautiful Pokémon — Style Guide

> The locked visual identity for this world. Every illustration is assembled from the
> `art_style` block in `world.yaml`; this doc is the human-readable art direction that
> every illustrator (human or AI) must read first.

## Locked palette

| Swatch | Hex | Role |
|---|---|---|
| sky-lavender | `#C7BEE8` | sky / background primary |
| cloud-white | `#FBF8F3` | cloud / highlight |
| peach-light | `#FFD9B5` | warm accent / light fill |
| meadow-green | `#A7D49B` | ground / vegetation |
| golden-hour | `#F5C36E` | warm highlight / sparkle |
| ribbon-pink | `#F2A6C2` | Clara + Lumi accent |
| deep-indigo | `#3A4A7A` | outline / night shadow |
| cream-fur | `#FBE7C6` | Lumi + creature fur |
| sky-cyan | `#A9E0E8` | distant sky / cool accent |

No colour outside this palette. If you need a Pokémon colour, you may tint one of
these — but the sky, the clouds, and the warm light must read as these exact hexes
on every page.

## Look & feel

- **Medium:** clean anime cel-shaded illustration in the **official Pokémon anime
  style** (Satoshi Tajiri / Ken Sugimori / OLM studio). Think Ash + Misty + Eevee-era
  *Pokémon* show, not the games, not Legends Arceus, not a Western cartoon.
- **Lines:** medium-weight indigo `#3A4A7A` outlines, **slightly varied** so it feels
  hand-drawn, never perfectly mechanical. Same line weight on all characters.
- **Shading:** soft cel-shading with **two tones per surface** (one base + one shadow).
  Rounded shadow edges. No harsh black. No realistic gradients.
- **Lighting:** always **warm golden-hour or pink-sky light**. Soft rim light on every
  character, even at night. **Sparkle motes** drift in the air on every single page
  (this is the world's signature — do not omit).
- **Perspective:** slightly low **child-eye-level** camera, character-centered.
  Full-bleed illustrations. **Layered background** — a clear near (character) / mid
  (companion Pokémon / nearby object) / far (sky / distant land) depth.
- **Composition rule:** the **lower third** of every page must stay calm and free of
  busy detail — it is reserved for the text scrim. Reserve that zone when prompting.
- **Mood:** bright, kind, wonder-filled. No grim. No scary. No combat.

## Do

- Keep Clara and Lumi **on-model** by reusing the appearance tokens + reference
  sheets. Never paraphrase.
- Stay strictly within the locked palette above.
- Use the same **ribbon-pink** for Clara's bow and Lumi's scarf — the kid learns to
  find them on the page.
- Use the **mismatched eyes** as Lumi's "tell" — the kid will look for them.
- Re-use the **seed** declared on each character bible for every image featuring
  that character. Same seed = more stable identity.
- Keep the **sky, the clouds, and the warm light** present in every single
  illustration, even at night, even indoors. This is what makes the world feel
  like one place.

## Don't

- No **photorealism, 3D renders, harsh shadows, scary faces, sharp teeth, claws,
  weapons, blood, dark gory tones, or grim colours**.
- No **battle, no Pokéball, no combat** of any kind. Pokémon here are friends.
- No **chibi / super-deformed** style. Standard Pokémon anime proportions only.
- No **humans besides Clara**. (This world has exactly one human: Clara.)
- No **text, letters, words, watermark, signature, logo** in any image. Text is
  overlaid by the reader at runtime.
- No **modern buildings, cars, cities**. The world is sky + nature only.
- Don't break the world's `rules` (see `world.yaml`): no combat, no answer to the
  beauty quest, no scary tone, no splitting Clara and Lumi for long.

## Composition template (every page)

```
┌───────────────────────────────┐  ← top: sky + clouds + sparkle motes
│           far layer           │
│      ┌─────────────────┐      │
│      │   mid layer     │      │  ← Pokémon, Lumi, far-off land
│      │  ┌───────────┐  │      │
│      │  │  near     │  │      │  ← Clara + Lumi, big and clear
│      │  └───────────┘  │      │
│      └─────────────────┘      │
│   ░░░░░░░░░░░░░░░░░░░░░░░░░   │  ← lower third: clear, soft scrim zone
│   ░  text scrim + words   ░   │
└───────────────────────────────┘
```

## Aesthetic references (style anchors only — do not copy)

- **Pokémon anime** (1997–onwards, OLM studio) for character line, eye shape, and
  proportions.
- **Ken Sugimori official art** for clean colour and Pokédex-style poses.
- **Studio Ghibli sky paintings** (*Castle in the Sky*, *Kiki's Delivery Service*) for
  warm, layered, dream-like sky backgrounds.
- **Eievui / Eevee evolution fan art** (the kind, soft, character-driven side of the
  fandom) for the gentle, friendly tone.

## Recurring motifs (must appear in art)

1. **Sparkle motes** drifting in the air (always).
2. **Lavender-peach sky** in the upper background (always).
3. **Soft cloud silhouettes** in the mid-distance (where biome permits).
4. **Lumi's ribbon-pink scarf** catching the breeze.
5. **A hidden shimmer** — one small thing on the page that twinkles slightly
   brighter than the rest. A clue for the reader to find.
