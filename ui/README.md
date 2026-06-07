# Garbanzo Books Studio — dynamic UI

A web console that drives this whole workspace through an AI agent — **no API key required**.
The agent is **[OpenCode](https://opencode.ai)** running a **local Ollama model**
(`minimax-m3:cloud` by default). Type what you want ("make a book for ages 5–7 about a shy
dragon"), and the studio runs the skills, scripts, and tools in the repo to build it — then you
browse the result and preview the live site, all in one screen.

The studio is a Python FastAPI server (`server.py`); there is no Node toolchain involved.

## Prerequisites (one-time)
- **Ollama** running locally, with the model pulled:
  ```bash
  ollama pull minimax-m3:cloud      # a free Ollama cloud account is enough; no API key in this app
  ```
- **OpenCode** installed and on your PATH: https://opencode.ai (`opencode --version`).

The model + provider are configured in the repo's [`opencode.json`](../opencode.json) (a local
Ollama provider pointing at `http://localhost:11434/v1`, plus `permission: allow` so the agent
can run the build/validate tools without prompting).

## Run it
From the repo root:
```bash
make ui
# or, directly:
uv run --group ui python ui/server.py
```
Open **http://localhost:4317** (override with `PORT=…`).

> The agent only powers the **chat** box. The **Library**, **Build site**, **Validate**, and
> **Preview** features work even without Ollama/OpenCode running — in that case the server
> emits a graceful `"OpenCode unavailable"` event on the chat SSE stream.

## What the screen gives you
- **Studio console (left):** a streaming chat with the agent. It captures the OpenCode
  `session` id so follow-up messages keep context (untick *new session* to continue). Quick
  chips seed common requests (new book / world / character / story). Tool runs (bash, edits)
  stream in as they happen.
- **Library (right):** every world → its stories and characters, read live from `worlds/`.
- **Preview (right):** an iframe of the built static site, refreshed after each build.
- **Validate / Build site** buttons run `scripts/validate.py` and `scripts/build_site.py`.
- **Talk & listen (local models, no API key):** a 🎤 mic in the composer records your message and
  transcribes it with **faster-whisper** (`distil-large-v3`, int8) on the server; **🔊 Read aloud**
  speaks the studio's replies with **Kokoro-82M**. Every assistant bubble also gets its own *Read
  aloud* button. Both models run on CPU, nothing leaves the box, and they're warmed in the
  background at startup so the first tap is instant. They come from the `tts` dependency group
  (`uv sync --group tts`) — the `make ui` target installs it for you. If the group isn't installed,
  the speech controls disable themselves and typing still works. The models + endpoints live in
  [`voice.py`](voice.py) (`/api/voice`, `/api/tts`, `/api/stt`); see
  `experiments/tts-stt-emotion/REPORT.md` for why these two were chosen.
- **🧒 Kids mode:** turns the studio into a child-friendly flow — the agent asks **one question
  at a time**, rendered full-screen with big picture buttons. Each question is read aloud
  automatically (Kokoro), and every step has a **Tap & talk** button so a child can answer by
  voice (whisper). The toggle also tells the agent to keep its language short, simple, and warm.
  Both toggles persist across reloads.

## How it works
`server.py` (FastAPI) serves the console (this dir's `public/`) and the built site at `/preview`,
shells out to the Python tools for library/build/validate, and proxies OpenCode for chat: it
starts an embedded `opencode serve` (in the repo root, so it picks up `opencode.json` +
`CLAUDE.md`), creates a session, streams `message.part.updated` events over SSE, and closes
the embedded server cleanly on exit (the child is killed via `PR_SET_PDEATHSIG` so it cannot
outlive the UI). Image generation (when the agent calls `generate_images.py`) still uses your
`GEMINI_API_KEY` from `.env` — that's separate from the chat model.

## Config (env)
| Var | Default | Purpose |
|---|---|---|
| `OPENCODE_MODEL` | `ollama/minimax-m3:cloud` | provider/model OpenCode uses for chat |
| `PORT` | `4317` | UI server port |
| `PY_CMD` | `uv run python` | how the server runs the Python tools (set `python3` if you don't use uv) |
| `OPENCODE_BIN` | `opencode` | path to the `opencode` binary (for testing, point at a no-op shim) |

No `ANTHROPIC_API_KEY` (or any chat API key) is needed.
