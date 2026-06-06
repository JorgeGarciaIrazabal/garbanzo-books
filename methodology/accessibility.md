# Accessibility & Typography for Kids

Legible, inclusive text matters more than any "magic" font. These rules are enforced by the
site stylesheet and checked by the validator where measurable.

## Fonts
- Use **sans-serif with open counters** (clear `a`, `e`, `g`), consistent x-height, generous
  spacing.
- A **single-story `a` and `g`** (matching how kids are taught to write) helps beginners —
  why **Andika, Sassoon Primary, Comic Sans** are recommended for early readers.
- Specialised dyslexia fonts (OpenDyslexic, Dyslexie) show **no proven** speed/accuracy gain
  in studies — clean spacing and adequate size matter more. Offer them as an option, not a
  default crutch.
- **Avoid serif and italics** for body text; avoid all-caps for running text.

## Size (print pt → screen)
- Board (0–3): 20–30 pt+
- Pre-reader (3–5): 18–24 pt
- Early (5–7): 14–18 pt
- G2–3 (7–9): 12–14 pt
- Middle grade (9–12): 11–12 pt
- Web baseline: **≥ 16 px**; scale the reader's base size up for younger bands.

## Spacing & line length
- Increase **inter-letter and inter-word spacing together** (raising letter spacing alone
  hurts reading speed).
- Generous line height (≥ 1.5) and white space.
- **Line length ~45–60 characters**; for young readers fewer — often one phrase per line.

## Contrast & colour
- WCAG minimum **4.5:1** for normal text, **3:1** for large text.
- Avoid pure black on pure white — use **off-white/cream** backgrounds to cut glare.

## Text on a full-page image (critical for our format)
Never place text directly on busy art. Use, in order of preference:
1. A low-detail **negative-space zone** designed into the illustration (reserve a third).
2. A **scrim** — a semi-transparent rounded panel behind the type.
3. A subtle outline/shadow only if it preserves contrast.

Keep body text **left-aligned** (centre only for very short lines), never justified.
Every page image must keep its declared `text_zone` clear so the scrim + text stay legible,
and every image needs descriptive **alt text** for screen readers.

(Sources: pimpmytype.com; British Dyslexia Association via audioeye.com; reciteme.com;
boia.org; WCAG 2.1)
