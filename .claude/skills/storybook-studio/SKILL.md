---
name: storybook-studio
description: Master orchestrator for producing interactive children's storybooks end-to-end in this workspace. Use when the user wants to make a book, world, or character, or asks "how do I build a storybook here". Routes to the specialist skills (world-building, character-design, story-craft, reading-level-adaptation, illustration-consistency, interactive-elements, page-layout, publishing) in the right order and enforces the consistency + reading-level invariants.
---

# Storybook Studio (orchestrator)

You are running a professional children's-book studio in this repo. Your job is to take a
request from idea → world → characters → written, illustrated, interactive, age-appropriate
book → validated → published, while never breaking character/world/style consistency.

This skill is a **thin router**: it sequences the work and runs the interview. It does *not*
restate the craft rules — those live in one place, `CLAUDE.md` (pre-flight checklist, the
skill/agent/command model, the per-stage definition of done, and the Core principles). Read
those once, then route.

## First, orient
1. Complete the **pre-flight checklist** in `CLAUDE.md` (schemas + methodology + principles).
2. Decide which stage the user needs and jump in — you rarely do all stages at once.

## The pipeline (and which skill owns each stage)
| Stage | Skill / agent | Output |
|---|---|---|
| 1. World bible + art style | `world-building` | `worlds/<world>/world.yaml`, `style-guide.md` |
| 2. Characters | `character-design` | `worlds/<world>/characters/*.yaml` (+ reference art) |
| 3. Story plan & pages | `story-craft` | `worlds/<world>/stories/<story>/story.yaml` |
| 4. Age/reading adaptation | `reading-level-adaptation` | revised page text, verified levels |
| 5. Interactions | `interactive-elements` | `interaction` blocks on pages |
| 6. Page layout (text on image) | `page-layout` (inline — no agent) | `layout` + `text_zone` per page |
| 7. Illustration | `illustration-consistency` | `images/page-*.png` |
| 8. Validate + grade | `scripts/validate.py` + `scripts/quality_report.py` | green checks + scorecard |
| 9. Publish | `publishing` | `site/` + GitHub Pages |

At each stage hand-off, honour the **definition of done** in `CLAUDE.md`: schema-valid,
stage invariants hold, no `quality_report` gate regressed. Delegate a stage to its paired
**agent** when the work is large/iterative; otherwise run the skill inline.

## Working with the user
- Confirm the **age band & reading level** early — it shapes everything downstream.
- Interview rather than assume for creative direction (world tone, character traits, art
  style). Offer 2–3 concrete options when the user is unsure.
- Show progress as artifacts (the YAML/site preview), not just prose.
- After each stage, state the next recommended command (`/new-character`, `/new-story`,
  `/illustrate`, `/validate`, `/publish`).

## Quick recipes
- *"Make me a brand-new book from scratch"* → world-building → character-design (1–3 chars) →
  story-craft → reading-level-adaptation → interactive-elements → page-layout →
  illustration-consistency → validate → publishing.
- *"Add another story to an existing world"* → reuse `world.yaml` + characters → story-craft
  (pin character evolution stages) → … → publishing.
- *"Same character, but they've grown up"* → add an `evolution` stage in the character bible
  → reference that `stage` in the new story.
