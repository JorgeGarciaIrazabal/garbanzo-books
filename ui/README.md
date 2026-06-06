# Garbanzo Books Studio — dynamic UI

A web console that drives this whole workspace through an AI agent — **no API key required**.
The agent is **[OpenCode](https://opencode.ai)** running a **local Ollama model**
(`minimax-m3:cloud` by default). Type what you want ("make a book for ages 5–7 about a shy
dragon"), and the studio runs the skills, scripts, and tools in the repo to build it — then you
browse the result and preview the live site, all in one screen.

## Prerequisites (one-time)
- **Ollama** running locally, with the model pulled:
  ```bash
  ollama pull minimax-m3:cloud      # a free Ollama cloud account is enough; no API key in this app
  ```
- **OpenCode** installed and on your PATH: https://opencode.ai (`opencode --version`).
- **Node 18+**.

The model + provider are configured in the repo's [`opencode.json`](../opencode.json) (a local
Ollama provider pointing at `http://localhost:11434/v1`, plus `permission: allow` so the agent
can run the build/validate tools without prompting).

## Run it
```bash
cd ui
npm install        # installs @opencode-ai/sdk
npm start          # → http://localhost:4317
```
Open **http://localhost:4317**.

> The agent only powers the **chat** box. The **Library**, **Build site**, **Validate**, and
> **Preview** features work even without Ollama/OpenCode running.

## What the screen gives you
- **Studio console (left):** a streaming chat with the agent. It captures the OpenCode
  `session` id so follow-up messages keep context (untick *new session* to continue). Quick
  chips seed common requests (new book / world / character / story). Tool runs (bash, edits)
  stream in as they happen.
- **Library (right):** every world → its stories and characters, read live from `worlds/`.
- **Preview (right):** an iframe of the built static site, refreshed after each build.
- **Validate / Build site** buttons run `scripts/validate.py` and `scripts/build_site.py`.

## How it works
`server.mjs` (Node `http`) serves the console and the built site, shells out to the Python
tools for library/build/validate, and uses **`@opencode-ai/sdk`** for chat: it starts an
embedded OpenCode server (in the repo root, so it picks up `opencode.json` + `CLAUDE.md`),
creates a session, streams `message.part.updated` events over SSE, and closes the embedded
server cleanly on exit. Image generation (when the agent calls `generate_images.py`) still uses
your `GEMINI_API_KEY` from `.env` — that's separate from the chat model.

## Config (env)
| Var | Default | Purpose |
|---|---|---|
| `OPENCODE_MODEL` | `ollama/minimax-m3:cloud` | provider/model OpenCode uses for chat |
| `PORT` | `4317` | UI server port |
| `PY_CMD` | `uv run python` | how the server runs the Python tools (set `python3` if you don't use uv) |

No `ANTHROPIC_API_KEY` (or any chat API key) is needed.
