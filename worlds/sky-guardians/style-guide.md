# Sky Guardians — Style Guide

> The locked visual identity for this world. Every illustration is assembled from the
> `art_style` block in `world.yaml`; this doc is the human-readable art direction.

## Palette
| Swatch | Hex | Role |
|---|---|---|
| sky-cobalt | `#1a3c6e` | primary |
| sunburst-orange | `#e86c00` | accent |
| cloud-cream | `#fff8e7` | background |
| grass-emerald | `#2d7d32` | primary |
| villain-suit-gray | `#5a5a5a` | shadow |
| robot-copper | `#b87333` | accent |
| cherry-blossom | `#ffb7c5` | accent |
| han-river-teal | `#009688` | primary |

## Look & feel
- **Medium:** bold gouache with visible brush texture
- **Line:** confident, slightly irregular, hand-painted edges
- **Lighting:** strong directional light, cast shadows as graphic shapes
- **Mood:** funny, adventurous, mischievous, clever — dynamic energy on every page

## Composition rules
- **Clara flying:** low-angle hero shots, wind in her bangs, dynamic motion lines
- **GlobeCorp scenes:** tilted Dutch angles, sterile symmetry broken by absurd details
- **Gears close-ups:** his tool chest open, holographic probability numbers floating
- **Text zone:** lower third reserved — keep it clear of busy detail; opaque cream scrim at 90%
- **Korean locations:** minhwa influence — flat perspective in backgrounds, symbolic color, decorative cloud/wave motifs

## Do
- Keep characters on-model (use appearance_tokens + reference sheets).
- Reserve lower third as calm negative space for text overlay.
- Stay within the 8-color palette above.
- Exaggerate expressions — Clara's mischievous grin, Gears's panic spirals, villains' bureaucratic deadpan.
- Include at least one "GlobeCorp form" or clipboard as visual gag per villain scene.

## Don't
- No photorealism, airbrushing, soft gradients, or cel shading.
- No thin line art or anime style — bold gouache shapes only.
- No text baked into the art (text is overlaid by the reader).
- Don't break the world's `rules` (see world.yaml).
- No scary/distorted faces — even villains are funny, not frightening.
- Don't clutter — bold graphic readability for 5-year-olds.

## Character visual anchors
- **Clara:** light skin, blunt bangs, light brown hair in practical bob, expressive eyes, always in motion (flying, mid-leap, perched). Outfit: colorful layered clothes, sneakers with wings drawn on in marker.
- **Gears:** vintage tin-robot aesthetic — copper/brass body, articulated joints, lens eyes that change shape with emotion (⚙️ 😰 💡), chest panel opens to dimensional tool pocket. Antenna wobbles when he worries.
- **GlobeCorp executives:** identical ill-fitting charcoal suits, clipboards, rectangular glasses, deadpan expressions. Leader rotates — each book a new "Regional VP of Optimization" with a distinct silly trait (one collects ornamental paperweights, one speaks only in acronyms, etc.).

## Reference images to generate
1. Clara character sheet (front, side, flying poses, expressions)
2. Gears character sheet (front, tool chest open, worried/excited faces)
3. GlobeCorp executive template (suit, clipboard, deadpan)
4. Seoul Sparkle District establishing shot (neon, palaces, cherry blossom drones)
5. Jeju Wind Caves interior (basalt columns, wind visible as brushstroke lines)
6. DMZ Peace Park (cranes, wildflowers, absurd giant slide cutting through)