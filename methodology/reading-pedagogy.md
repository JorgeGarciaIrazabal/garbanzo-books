# Reading Pedagogy & Leveling

How to choose and age-adapt language so a book actually teaches/encourages reading. Stories
declare an `age_band` + `reading_level`; this doc defines what those mean and how we verify
them (`scripts/reading_level.py`).

## The five pillars of reading
(National Reading Panel, 2000)
1. **Phonemic awareness** — hearing & manipulating spoken sounds.
2. **Phonics** — mapping graphemes ↔ phonemes (decoding).
3. **Fluency** — accurate, fast, expressive reading; built by repeated/guided oral reading.
4. **Vocabulary** — word knowledge (Tier 1 everyday / Tier 2 academic / Tier 3 domain).
5. **Comprehension** — making meaning.

Design interactions (see [interactivity.md](interactivity.md)) to exercise specific pillars,
and tag each with `interaction.skill`.

## Leveling systems (citable)
- **Lexile** — text + reader measure, 0L–1600L+; below-zero shown **BR** (Beginning Reader;
  BR700L easiest). Kindergarten band ≈ BR40L–230L.
- **Fountas & Pinnell Guided Reading Levels (A–Z)** — A–B ≈ K, C–I ≈ G1, J–M ≈ G2, N–P ≈ G3.
- **DRA** (Developmental Reading Assessment) — numeric A–80.
- **ATOS / Accelerated Reader** — grade-level + book level.

> Cross-system correlation charts are **not empirically validated** — treat as approximate.

## Decodable vs. predictable text
- **Decodable** — restricted to phonics patterns already taught. After `s a t p i n` a reader
  can decode *sat, pin, tap, nip*. Supports systematic synthetic phonics. Set
  `reading_level.decodable: true` and a `decoding_focus` to enforce this in early readers.
- **Predictable / leveled** — repeated sentence frames + picture cues. Engaging and great for
  pre-readers and read-alouds, but Science-of-Reading advocates caution it can cue *guessing*
  over decoding for kids who are learning to sound out. Use predictable text for read-aloud
  bands (0–5) and prefer decodable for independent decoders (5–7).

## Synthetic phonics scope & sequence
Explicit, systematic, part-to-whole. Classic order:
`s a t p i n` → `m d g o c k` → `ck e u r` → `h b f l` → ... → consonant digraphs
(`sh ch th ng`) → long vowels / vowel teams (`ai ee igh oa`) → r-controlled, diphthongs.
A decodable book should only use patterns at or before its declared `decoding_focus`.

## Sight / high-frequency words
- **Dolch** — 220 service words + 95 nouns.
- **Fry** — 1,000 words in groups of 100.
- **Heart words / tricky words** — irregular HFWs (the, was, said) taught as exceptions
  because parts aren't yet decodable. List allowed exceptions in `decoding_focus`.

## Per-age-band specification (targets)
| Band | Age | Sentence length | Words/page | Vocab | Font (print) | Decoding focus | Lexile |
|---|---|---|---|---|---|---|---|
| **0–3** board | 0–3 | 1 line, 3–6 words | 0–10 | Tier 1 naming words | 20–30 pt+ | print/picture awareness, rhyme | — |
| **3–5** pre-reader | 3–5 | 1 sentence, 5–10 | 10–40 | Tier 1, repetition | 18–24 pt | phonemic awareness, letter sounds | BR |
| **5–7** early (K–1) | 5–7 | 5–8 words | 20–60 | decodable + first sight words | 14–18 pt | s-a-t-p-i-n, CVC blending | BR–300L |
| **7–9** (G2–3) | 7–9 | 8–14 words, some compound | 50–150 | Tier 1–2, digraphs/vowel teams | 12–14 pt | multisyllable, fluency | ~300–650L |
| **9–12** middle grade | 9–12 | 12–20 words, varied | full prose | Tier 2–3, figurative | 11–12 pt | comprehension, vocab depth | ~600–1000L |

(Lexile bands: K BR40–230L; G1 165–570L; G2 425–795L; G3 645–985L.)

## Readability formulas (what the validator computes)
**Flesch Reading Ease (FRE)** — higher = easier:
```
FRE = 206.835 − 1.015 × (words/sentences) − 84.6 × (syllables/words)
```
**Flesch–Kincaid Grade Level (FKGL)** — ≈ U.S. grade:
```
FKGL = 0.39 × (words/sentences) + 11.8 × (syllables/words) − 15.59
```

### Limits for early readers (important)
Both formulas reward short words/sentences but **ignore decodability, sight-word load,
picture support, and concept difficulty**. A decodable CVC book and a predictable
high-frequency-word book can score the same grade yet teach very differently. FKGL is
**unreliable below ~Grade 1** (few sentences → volatile ratios). So:
- For bands 0–3 and 3–5: don't trust FKGL; check words/page, sentence length, and rhyme/repetition instead.
- For bands 5–7+: use FKGL **as a guardrail**, alongside the decoding focus and per-page word caps.

(Sources: reallygreatreading.com; readnaturally.com; hub.lexile.com; fivefromfive.com.au;
readingrockets.org; readsters.com; en.wikipedia.org/Flesch–Kincaid; readable.com)
