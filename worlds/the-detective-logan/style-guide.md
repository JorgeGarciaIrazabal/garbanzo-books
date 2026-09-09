# The Detective Logan — Style Guide

**World:** `the-detective-logan` · **Readers:** ages 5–7 · **Tone:** madcap, adventurous, mysterious

## The one-sentence look
Every page looks like Logan drew it himself: **waxy crayon + hand-drawn ink on textured paper**, wobbly lines you can feel, colors that scribble slightly past the edges — a kid-detective case file that came alive.

## Locked palette
| Swatch | Hex | Role |
| --- | --- | --- |
| Case-File Cream | `#f6ead2` | paper, backgrounds, text scrims |
| Detective Navy | `#2e4a7d` | coats, night scenes, outlines |
| Notebook Red | `#d94f3d` | Logan's notebook, string, alarms, clues |
| Maple Gold | `#f2b134` | streetlamps, highlights, "aha!" moments |
| Mosswood Green | `#6a994e` | park, forest, bushes to hide in |
| Foggy Dusk Blue | `#8ecae6` | skies, fog, mystery mood |
| Crayon Charcoal | `#4a423c` | shadows, suspects, mystery silhouettes |

**Do:** keep at least cream + navy + one accent in every scene; use red sparingly — red means *clue*.
**Don't:** introduce neons, purples, or smooth airbrushed color; never lose the paper texture.

## Medium & line
- Waxy crayon fills + hand-drawn ink outlines, double-sketched, pressure visible.
- Shading = crayon hatching and scribbles, *slightly outside the lines on purpose*.
- Lighting = one warm source per scene (streetlamp, flashlight beam, sunny window), big flat storybook shadows.

## Composition tendencies
- Cozy wide shots for Main Street and the Shack; **low-angle dramatic close-ups** for reveals.
- Sneaky over-the-shoulder spying shots when Logan & Poppy are on a stakeout.
- Leave a quiet zone in the **lower third** for the story text (cream rounded panel).

## Motifs to sprinkle (not every page — but somewhere)
Red notebook · magnifying glass · red string wall · 3:33 clock faces · missing-item posters · leftover clue pieces.

## Do / Don't examples
- **Do:** a night scene lit by one gold streetlamp, navy shadows with crayon hatch-marks, fog in dusk blue.
- **Don't:** photoreal faces, 3D shading, scary villains with sharp teeth — suspects are silly, not creepy.
- **Do:** a messy Shack with string connecting clues *and* a banana. **Don't:** tidy vector-clean rooms.

## Prompt assembly (automatic)
Full prompt = page `scene` + each character's `appearance_token` + `prompt_style_block` + palette + `negative_prompt`. Never hand-write the whole thing — run `scripts/generate_images.py`.