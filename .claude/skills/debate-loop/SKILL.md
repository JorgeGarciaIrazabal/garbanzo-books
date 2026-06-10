---
name: debate-loop
description: Orchestrate a multi-LLM, multi-persona debate over a story draft to push it from "competent" to "kids beg to re-read". The author is a subagent; three critic subagents (a chaos advocate, a craft minimalist, a kid-reader skeptic) each review the same draft with their distinct lens and push back in free-form prose. The author revises against the strongest, most actionable critiques. Use after a story is drafted (or when iterating an existing draft) to make it sharper, funnier, and less preachy. Lives in CLAUDE.md as a core craft stage; invoked by /new-debate.
---

# Debate loop — making a story actually good

A single LLM author produces a competent draft. A *structured disagreement* between an author and
several different critics, each with their own lens and their own model, produces a story that
kids actually want to re-read. This skill defines the protocol.

> The north star is `methodology/fun-first.md`. Read it first. If the debate ever drifts to
> "should we teach X?" or "is the message clear?" — kill the question. **Fun is the whole job.**

## Why a debate, and why multiple models

- **Author + critic split** forces the author to *defend* choices, not just produce them.
  A lone model will write, then grade its own work — and grade generously.
- **Different lenses** (chaos, craft, kid-voice) catch different failure modes. A "funny" page
  can still be a structure disaster; a tight structure can still be boring. One critic sees one,
  another sees the other.
- **Different models** matter even with the same system prompt. A more creative model will
  catch "this isn't actually weird enough"; a faster/more economical model will catch "this
  is overwritten"; an information-gathering model roleplaying a kid catches "a 6-year-old
  wouldn't laugh at this."

## The personas (one critic per lens, one model per critic)

| Critic | Lens | Model (Ollama) | What they push for |
|---|---|---|---|
| **`story-heckler`** | Chaos & mischief (Dahl/Pilkey/Adventure Time) | `ollama/deepseek-v4-pro:cloud` | Raise the stakes, add real danger, find the boring pages, kill the lessons, defend the mischief |
| **`story-minimalist`** | Craft & economy (Mo Willems / Sendak) | `ollama/nemotron-3-ultra:cloud` | Cut pages, tighten prose, kill the cute, make every spread earn its turn |
| **`story-kid-reader`** | The 6-year-old at bedtime | `ollama/minimax-m3:cloud` | Would a kid this age laugh? Would they turn the page? Is the joke at the right altitude? |
| **`story-debate-author`** | The author (writes & revises) | `ollama/nemotron-3-ultra:cloud` | Reads the critiques, revises, defends choices that should stand |

The orchestrator (this skill, run by the primary agent — i.e. you) sequences them. Each is a
*separate* subagent invocation with its own context window and its own model. Their prompts
are in `.opencode/agents/`. The orchestrator NEVER rewrites the story itself — it passes the
draft between roles.

## The protocol (one round)

For each round, the orchestrator does, in order:

1. **Snapshot the current draft.** Read `worlds/<w>/stories/<s>/story.yaml`. Note the round
   number and the previous critics' notes (if any). Save the current draft to
   `worlds/<w>/stories/<s>/.debate/round-<N>/draft-before.yaml` so we can diff.
2. **Run the three critics in parallel** — they each get the draft + world + character bibles
   + the previous round's critiques + a one-line brief: *"Give me your single biggest
   free-form complaint about this story, and one specific concrete change that would fix it.
   200 words max. No scoring, no rubrics. Be the character you are."* They each write to
   `.debate/round-<N>/critique-<role>.md`.
3. **Run the author.** Give them the draft + the three critiques + the world + the characters
   + the instruction: *"For each critique: agree / disagree / partially agree, with a one-line
   reason. Then make the changes you agreed with, leave the ones you didn't. Do not soften
   the story to satisfy a critique — defend a choice if the fun depends on it. Write the
   revised story.yaml in full to .debate/round-<N>/draft-after.yaml."*
4. **The orchestrator decides convergence.** If all three critics in this round agreed their
   single biggest complaint was the *same* page/line (convergence on a target), the next
   round starts focused. If the critiques are all over the map, the next round is broad.
5. **Promote or rollback.** If the author produced a stronger draft (orchestrator judgment —
   see "stop conditions"), copy `.debate/round-<N>/draft-after.yaml` over `story.yaml`. If
   the author *worsened* the draft (caved to a weak critique, lost the mischief, etc.),
   keep the old `story.yaml` and adjust the next round's brief.
6. **Stop conditions** — see below.

## Free-form critique only — explicitly

You asked for free-form, not a rubric. So the critics do **not** grade. They do not produce
a score. They do not fill a checklist. Each critic writes one short free-form piece that
ends with: *"My single biggest complaint is ____, and the one concrete change I'd make is ____."*

That is the only requirement. Everything before it is the critic in character.

The orchestrator does **not** tell the critics what the story is missing. The orchestrator
just passes the draft. The critics' *personas* (their lenses) are what shape the critique.

## What convergence looks like

- **All three critics complaining about the same thing.** High signal — that is the next fix.
- **Two of three complaining about the same thing.** Worth addressing.
- **All three complaining about different things.** The next round broadens — the brief asks
  critics to pick a *top* complaint, not cover everything. We don't try to fix twelve things
  in one round.
- **One critic says "the mischief is gone" while the others say "the structure is tight".**
  The author is over-correcting. Rollback or soften.

## Stop conditions

- **Max 3 rounds.** Past 3 rounds the marginal improvement drops and the model tends to
  either loop or sand the story down. If we still have critique at round 3, the user judges.
- **Convergence on a target that got fixed.** If all three critics agreed in round N about
  complaint X, the author fixed X, and round N+1's critics move to fresh complaints — done.
- **Orchestrator judgment that the draft is now *worse***. Stop and tell the user.
- **The author keeps losing the mischief** in successive revisions. Stop, tell the user, the
  critic is winning the wrong argument.

## What the orchestrator NEVER does

- **Never writes story text itself.** The author is a subagent. If you find yourself reaching
  for the `edit` tool on `story.yaml`, stop. Hand the work to the author subagent.
- **Never "averages" the critiques.** The author picks; the orchestrator doesn't try to
  satisfy everyone. A good author will reject some critiques — that's fine, that's the
  defense.
- **Never invents requirements the critics didn't ask for.** If the heckler says "this
  ending is a moral", the author fixes the ending — not the structure, not the prose, not
  the character voice.
- **Never publishes.** `/new-debate` ends with a `story.yaml` and a `quality_report` run.
  The user decides.

## Outputs

For a debate over `worlds/<w>/stories/<s>/story.yaml`:

```
worlds/<w>/stories/<s>/.debate/
  round-1/
    draft-before.yaml
    critique-heckler.md
    critique-minimalist.md
    critique-kid-reader.md
    draft-after.yaml
    notes.md         # orchestrator's convergence call + rollback decision
  round-2/
    ...
  round-3/
    ...
  final-verdict.md  # one-page summary: what changed, what was rejected, what the user should look at
```

The user reads `final-verdict.md` to judge. They do NOT have to read all nine critique files.

## How this composes with the rest of the pipeline

- **Author role** = an *enhanced* `story-writer`. Same skills, same schema, same outputs — but
  with the debate-loop protocol loaded so it knows it is in a loop, will be challenged, and
  should defend.
- **Critic roles** = new subagents. They have read-only tools; they do not edit `story.yaml`.
  Their job is the *critique file*, not the artifact.
- **`/new-debate`** = the user entry point. It's a wrapper that runs the loop. The existing
  `/new-story` and `/new-book` commands stay — but for any "good" output, the recommended path
  is: draft → `/new-debate` → validate → publish.
- **Validation** = unchanged. `scripts/validate.py` and `scripts/quality_report.py` run on the
  final `story.yaml` after the loop ends.

## First-run checklist

Before the first run, ensure:

1. `.opencode/agents/story-heckler.md`, `story-minimalist.md`, `story-kid-reader.md`,
   `story-debate-author.md` exist with `mode: subagent` and a `model:` field.
2. OpenCode has been restarted since the agent files were added (so the new subagent types
   register with the `task` tool).
3. `worlds/<w>/stories/<s>/story.yaml` is schema-valid (run `uv run python scripts/validate.py
   worlds/<w>/stories/<s>` first — if it fails on schema, fix that *before* the debate, or
   the critics will spend their 200 words on schema errors).
4. The `world.yaml` and any referenced `characters/*.yaml` are present and valid.
