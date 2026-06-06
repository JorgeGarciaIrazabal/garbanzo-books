# Character, World & Style Consistency

The single hardest problem in AI-assisted books is keeping the same character and the same
world *looking and behaving the same* across dozens of images and many stories. We solve it
the way studios do — with locked references — plus prompt-assembly discipline.

## Visual character consistency (the studio toolkit)
- **Model sheet / character study** — the definitive appearance, proportions, expressions. →
  store under `worlds/<world>/characters/<char>.refs/` and list in `reference_images`.
- **Turnaround** — front, 3/4, profile, back at fixed height guides.
- **Expression & pose sheet** — emotional range, all on-model.
- **Locked colour palette** — exact hex per body part (`appearance.color_palette`).
- **Silhouette test** — black out the figure; if it's still recognisable by outline alone,
  the design is strong. Force *distinct* silhouettes between characters.
- **Named distinguishing features** — 2–4 non-negotiable identifiers ("red striped scarf,
  gap tooth, left-ear cowlick") repeated in every image. (`appearance.distinguishing_features`)

## The world bible (series consistency)
A world bible enforces continuity across books. Ours lives in `world.yaml` + `style-guide.md`:
- **Geography** — locations and their mood.
- **Rules** — how magic/tech/physics works *and its limits*. Inviolable.
- **Factions / relationships** — groups and their values.
- **Timeline** — canonical events & ages; stories must not contradict it.
- **Motifs** — recurring symbols, catchphrases, colour meanings.
- **Character roster** — appearance tokens + voice.
- **Style canon** — the art `prompt_style_block`, palette, and do's/don'ts.

## Illustration prompt engineering (the consistency levers)
Generate every image by **assembling**, never free-handing:

```
PROMPT = <page scene description>
       + <appearance_token of each character present>
       + <world art_style.prompt_style_block>
       + "palette: " + <world palette hexes> [+ per-character color_palette]
       + <composition/text-zone note>
NEGATIVE = <world art_style.negative_prompt>
SEED    = character.seed (or story-stable seed)
REFS    = character.reference_images (image-to-image / reference anchor)
```

Levers, in order of impact:
1. **Reference images** — the strongest anchor. Approve a character turnaround/keyframe
   first, then feed it as the *character reference* for every page. Distinguish a *character
   reference* (borrows identity) from a *style reference* (borrows look/palette).
2. **Locked style block** — a fixed `prompt_style_block` in *every* prompt. Style drift
   causes character drift, so freeze style first.
3. **Per-character appearance token** — a reusable identity block of *stable physical
   traits/proportions*, not loose adjectives. Paste verbatim each time.
4. **Seed reuse** — fix the seed so same prompt → near-identical output. Seeds anchor
   composition more than identity, so combine with refs.
5. **Palette locking** — name exact colours per element in every prompt; optionally
   colour-correct in post to hit hex targets.

### Production workflow
1. Approve the **character sheet** first (the `/illustrate --character` step).
2. Use it as the locked reference + token + style block for **all** pages.
3. Batch pages with a consistent seed family.
4. **Human QC** every page against the bible's silhouette + named-feature checklist.

## Personality & behaviour consistency
Visual isn't enough — characters must *act* in character. Every story keeps each character
acting from their `personality` (traits, motivation, flaws). Evolution is allowed but
*tracked*: a story pins each character to an `evolution.stage`, which may extend the
appearance token and shift behaviour without breaking core identity. Honour `relationships`
and the world `rules`/`timeline` so the series stays coherent.

(Sources: blog.cg-wire.com; characterhub.com; clipstudio.net; gensgpt.com 2026 character-
consistency guide; venice.ai; leonardo.ai; getimg.ai; scenario.com)
