---
name: page-layout
description: Compose full-page (full-bleed) illustrations with text embedded legibly on top — choosing the text position, scrim, alignment, and font treatment per page so words stay readable over art and meet kids' accessibility needs. Use when setting page layout, fixing text legibility over images, or designing the text-on-image treatment. Reads methodology/accessibility.md; sets layout per page.
---

# Page layout (text on the image)

Our books are **full-page images with the text inside them**. This skill makes that text
always legible. Read `methodology/accessibility.md` first.

## Procedure
1. **Pick the text position per page.** Set `layout.text_position` — this is the SINGLE
   source of truth for where text sits. It drives BOTH the reader render AND the image
   prompt's reserved calm zone (the generator keeps that area low-detail automatically),
   so the two can never drift. The enum is: `top`, `bottom`, `left`, `right`, `center`,
   `lower-third`, `upper-third`. Default comes from the world `art_style.text_treatment.placement`.
2. **Set the rest of `layout`**: `text_align` (left for body; center only for very short
   lines), `scrim: true` (a soft rounded panel behind the text for contrast).
3. **Honour the type rules** (the site CSS enforces most, but design for them):
   - Sans-serif, open counters; offer a dyslexia-friendly toggle.
   - Font size scales with the reader's age (toddler 20–30pt → middle-grade 11–12pt; web base
     ≥16px, larger for younger readers).
   - Line length ~45–60 chars (fewer for young readers — often one phrase per line).
   - Generous letter+word spacing and line height (≥1.5).
   - Contrast ≥4.5:1; off-white/cream over busy art via the scrim, not pure black-on-white.
4. **Vary placement for rhythm** but keep it predictable enough that kids know where to look.
5. **Alt text.** Ensure every page image has descriptive `image.alt` for screen readers.

## Quality bar
- [ ] Text never sits on busy art without a negative-space zone or scrim.
- [ ] `layout.text_position` set on every page (it reserves the calm zone AND places the text).
- [ ] Body text left-aligned; line length within range; contrast adequate.
- [ ] Font size appropriate to the reader's age; dyslexia-friendly option available.
- [ ] Every image has alt text.

## Output
`layout` (+ `image.alt`) on every page, ready for illustration and the site renderer.
Next: `illustration-consistency`, then `/validate`.
