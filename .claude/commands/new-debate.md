---
description: Run a multi-LLM, multi-persona debate over a story draft to make it sharper, funnier, and less preachy. Author + 3 critic subagents, free-form critique, up to 3 rounds, rollback on regression. Use after drafting or whenever a story needs to get better.
argument-hint: <world>/<story> [--rounds 3]
---

Use the **debate-loop** skill (`.claude/skills/debate-loop/SKILL.md`) to run a multi-LLM
debate over the story at **$1**. Read that skill first — it defines the protocol, the
personas, the stop conditions, and what the orchestrator (you) must NOT do.

**Argument parsing:** `$1` is `<world>/<story>`. Parse it as the world slug, a slash, the
story slug. Optional `--rounds N` (default 3) caps the number of rounds; max is 3.

## Pre-flight (do not skip)

1. Read `.claude/skills/debate-loop/SKILL.md` end to end. Follow it.
2. Confirm the four subagent persona files exist in `.opencode/agents/`:
   - `story-heckler.md` (model: deepseek-v4-pro:cloud, chaos lens)
   - `story-minimalist.md` (model: nemotron-3-ultra:cloud, craft lens)
   - `story-kid-reader.md` (model: minimax-m3:cloud, kid-voice lens)
   - `story-debate-author.md` (model: nemotron-3-ultra:cloud, writes revisions)
   If any are missing, stop and tell the user to set them up and restart opencode.
3. Confirm `worlds/<w>/world.yaml` and the `characters/*.yaml` referenced in the story
   exist and are valid. Read them so the author can inherit tone, art style, and
   appearance tokens.
4. Confirm `worlds/<w>/stories/<s>/story.yaml` exists and is schema-valid by running
   `uv run python scripts/validate.py worlds/<w>/stories/<s>`. If the validator fails on
   schema, stop and tell the user — schema errors will eat the critics' word budget.
5. Create the `.debate/` working directory at
   `worlds/<w>/stories/<s>/.debate/`. This is where each round's drafts and critiques
   land.

## The loop (per round)

For each round N (1, 2, 3 — or until convergence):

1. **Snapshot.** Copy the current `story.yaml` to
   `worlds/<w>/stories/<s>/.debate/round-<N>/draft-before.yaml`.
2. **Run the three critics in parallel.** Use the `task` tool three times in one message
   with `subagent_type: story-heckler`, `story-minimalist`, `story-kid-reader`. Each
   gets the brief described in the skill, the current draft (read from
   `round-<N>/draft-before.yaml`), the world + character bibles, the previous round's
   critique files (if any), and the file path to write its critique to
   (`round-<N>/critique-<role>.md`).
3. **Run the author.** After the three critics return, use the `task` tool with
   `subagent_type: story-debate-author`. Pass the three critiques, the draft, the
   world/characters, and the file path
   `round-<N>/draft-after.yaml` to write the revised `story.yaml` to.
4. **Decide convergence** (orchestrator judgment). Read the three critiques:
   - All three pointing at the same thing → strong convergence, next round is focused
     on the *next* biggest complaint.
   - Two of three on the same thing → moderate convergence.
   - All three on different things → no convergence, next round broadens.
5. **Validate the revised draft.** Run
   `uv run python scripts/validate.py worlds/<w>/stories/<s>/.debate/round-<N>/draft-after.yaml`.
   If it fails, you have a schema break — call the round a regression, rollback, and
   tell the user.
6. **Promote or rollback.** Compare the revised draft to the prior. Orchestrator judgment:
   - If the draft is **sharper / funnier / less preachy** (your read, informed by the
     critiques), copy `round-<N>/draft-after.yaml` over `story.yaml`.
   - If the draft **softened** the fun, the mischief, or the ending — or the author
     caved to a weak critique — keep the old `story.yaml`. Note it in `round-<N>/notes.md`.
   - If you're unsure, prefer rollback. The user can re-run with a different brief.
7. **Write `round-<N>/notes.md`** — your convergence call, the rollback decision, and
   anything the next round (or the user) should know.

## After the loop

1. Run the final `story.yaml` through `scripts/quality_report.py`:
   `uv run python scripts/quality_report.py <w>/<s>`. Record the gate scores.
2. Write `worlds/<w>/stories/<s>/.debate/final-verdict.md`:
   - One-paragraph summary of what changed across the rounds.
   - The three biggest things the critics pushed for and what happened to each.
   - The three biggest things the author *defended* and why.
   - The quality report gate scores.
   - A short "what the user should look at" list (e.g. "pages 7 and 14 were rewritten
     — the heckler wanted the green-eyes scene scarier; the author raised the stakes
     without making it gory").
3. Run `uv run python scripts/validate.py worlds/<w>/stories/<s>` one last time.
4. Tell the user the debate is done, where the artifacts are, what the verdict said, and
   the final gate scores. **Do not publish.** That's a separate `/publish` step.

## Hard limits (re-read the skill on these)

- The orchestrator NEVER writes story text itself. If you find yourself reaching for
  `edit` on `story.yaml`, stop and re-delegate to `story-debate-author`.
- Max 3 rounds. Past 3 the marginal improvement drops.
- If the author loses the mischief twice in a row, stop and tell the user — the
  critics are winning the wrong argument.
- The `moral:` field stays empty. No exceptions. The schema allows it; the north star
  forbids it.
