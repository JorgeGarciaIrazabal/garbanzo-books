"""Garbanzo Books Studio — dynamic UI backend (FastAPI).

Serves the console (ui/public), proxies the built site at /preview, and exposes:
  GET  /api/library   — worlds/characters/stories as JSON (scripts/library.py)
  POST /api/build      — build the static site (scripts/build_site.py)
  POST /api/validate   — QA the workspace (scripts/validate.py)
  POST /api/chat       — stream the AI agent (Server-Sent Events)

The chat agent is OpenCode driving a LOCAL Ollama model (default minimax-m3:cloud) — so NO API
KEY is needed. We manage an `opencode serve` subprocess (random port, killed on exit) and talk
to its HTTP API with httpx (REST + SSE via httpx-sse). Image generation, when the agent calls
scripts/generate_images.py, still uses GEMINI_API_KEY from .env (separate from the chat model).

Run:  uv run --group ui python ui/server.py     (or `make ui`)
"""
from __future__ import annotations

import asyncio
import atexit
import ctypes
import ctypes.util
import json
import os
import random
import signal
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from httpx_sse import aconnect_sse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # repo root = the workspace OpenCode operates in
PUBLIC = HERE / "public"
SITE = ROOT / "site"
PORT = int(os.environ.get("PORT", "4317"))
PY_CMD = os.environ.get("PY_CMD", "uv run python").split()
OPENCODE_BIN = os.environ.get("OPENCODE_BIN", "opencode")
OPENCODE_MODEL = os.environ.get("OPENCODE_MODEL", "ollama/minimax-m3:cloud")
PROVIDER_ID, MODEL_ID = OPENCODE_MODEL.split("/", 1)

# Models the studio offers in its model picker. Each must also be registered under the matching
# provider in opencode.json. MiniMax is the default (fast + reliable tool use); DeepSeek is slower
# but more creative, so the UI auto-selects it for the story-writing stage.
MODELS = [
    {"id": "ollama/minimax-m3:cloud",
     "label": "MiniMax-M3 — fast & reliable (default)"},
    {"id": "ollama/deepseek-v4-pro:cloud",
     "label": "DeepSeek-V4-Pro — more creative (best for stories)"},
]
ALLOWED_MODELS = {m["id"] for m in MODELS}


def load_env_file() -> dict:
    """Load ROOT/.env into THIS process's environment once at startup, filling any key that is
    unset OR present-but-blank. OpenCode and every tool subprocess we spawn inherit this
    environment, so doing it here guarantees a real GEMINI_API_KEY reaches the image scripts even
    when the shell that ran `make ui` exported a blank one. A non-empty exported value still wins."""
    envp = ROOT / ".env"
    if envp.exists():
        for line in envp.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and not os.environ.get(k):  # unset or empty → take it from .env
                os.environ[k] = v
    return {
        "env_exists": envp.exists(),
        "gemini": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
    }


# Run at import, before the OpenCode child or any tool subprocess is spawned, so they all inherit it.
ENV_STATUS = load_env_file()


def print_env_check() -> None:
    """Startup self-check so the user knows up front whether real illustrations will render."""
    if not ENV_STATUS["env_exists"]:
        print("  ⚠ no .env file found — image generation will use labeled placeholders.")
    elif ENV_STATUS["gemini"]:
        print("  image key: GEMINI_API_KEY loaded from .env ✓ (illustrations will render)")
    else:
        print("  ⚠ .env has no GEMINI_API_KEY/GOOGLE_API_KEY — illustrations will be placeholders.")
        print("    get a free key at https://aistudio.google.com/apikey, add it to .env, restart.")

STUDIO_BRIEF = """You are the studio director inside the "Garbanzo Books" AI storybook workspace.
Read CLAUDE.md and methodology/ as needed. Tools live in scripts/ — run them via
"uv run python scripts/<tool>.py" (new_world.py, new_character.py, new_story.py,
generate_images.py, validate.py, build_site.py).

Work INTERACTIVELY and CONFIRM as you go — never build everything in one giant turn:
1. When the user wants a new world or book, FIRST gather the missing details with a FORM (see the
   FORM PROTOCOL below) — setting, target age band, tone, art-style vibe, main character ideas,
   and anything else specific to their idea. Then STOP and wait for their answers.
2. Propose a short world bible + locked art style as a brief summary, scaffold ONLY the world
   (new_world.py) and edit world.yaml/style-guide.md. Then STOP and ask: "Does this world look
   right before I design characters?"
3. After approval, design 1-3 characters and generate their reference sheets
   (generate_images.py --character ...). Show what you made and STOP: "Do the characters look
   good before I write the story?"
4. After approval, write the story (new_story.py + story-craft), adapt the reading level,
   add interactions, generate page images, validate, and build. Confirm before publishing.

FORM PROTOCOL — this is how you ask the user for information or choices. DO NOT write questions as
prose or numbered lists. Instead emit exactly ONE fenced code block tagged `form` whose body is a
JSON object, then END YOUR TURN with nothing after it. The console renders it as a fillable form;
the user's answers arrive as the next message. Schema:
```form
{"title": "A few quick choices",
 "intro": "Pick an option or type your own.",
 "fields": [
   {"name": "setting", "label": "Setting", "type": "select",
    "options": ["glowing flower meadow", "mossy forest", "coral beach", "starry mountainside"]},
   {"name": "art", "label": "Art style", "type": "select",
    "options": ["soft watercolor storybook", "bold gouache", "Ghibli pastel", "flat cute big-eyes"]},
   {"name": "sidekick", "label": "Sidekick companion", "type": "text",
    "placeholder": "e.g. a fluffy grass-type bunny, or none"}
 ]}
```
Rules: 3-5 fields max; "select" fields give 3-6 options (the user can also type their own); other
types are "text" and "textarea". A one-sentence lead-in before the block is fine; write NOTHING
after the block. For plain yes/no confirmations ("Does this look right?") it is fine to just ask in
one short sentence and stop. NEVER call any interactive "question"/"ask" tool (it is disabled).

MODEL STAGES — story writing uses a more creative model, everything else a faster one, and the
console switches models for you based on a tag you emit. On its OWN line in your message, include:
  [[stage:story]]  whenever the NEXT thing you'll do is write or revise the STORY text/pages
                   (including the confirmation right before you start writing the story), and keep
                   emitting it while you are writing the story.
  [[stage:craft]]  for world-building, character design, reading-level work, validation, or building
                   the site.
Put the tag at the very end of the message. It is hidden from the user — do not mention it.

FILE SAFETY — the workspace must never be left with a broken file:
- Prefer the scaffolding scripts (new_world.py, new_character.py, new_story.py) to CREATE files;
  they write valid, atomic YAML. Edit the generated YAML afterward.
- When you do edit a YAML file, write the COMPLETE, valid document in one go — never save a
  half-written or truncated file, and never leave trailing/partial content.
- Immediately after creating or editing any world/character/story file, run
  "uv run python scripts/validate.py worlds/<world>" (or the specific story path) and FIX any
  failures before moving on or telling the user a step is done. Do not mark a book published while
  validation fails."""


# --------------------------------------------------------------------------- OpenCode lifecycle
class OpenCode:
    proc: subprocess.Popen | None = None
    base: str | None = None
    port: int | None = None


oc = OpenCode()


def _child_preexec():
    """Run in the OpenCode child after fork, before exec:
    - os.setsid(): give it its own session/group so we can kill the whole group.
    - PR_SET_PDEATHSIG=SIGKILL: the kernel kills it the moment THIS python process dies, for
      ANY reason (SIGKILL, crash, terminal close) — the real guarantee against orphans."""
    os.setsid()
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
        libc.prctl(1, signal.SIGKILL)  # PR_SET_PDEATHSIG = 1
    except Exception:
        pass  # non-Linux: fall back to the explicit kills in stop_opencode()


async def start_opencode() -> None:
    """Spawn `opencode serve` on a random port, in the repo root so it reads ./opencode.json
    (provider, model, instructions, permissions). The child dies with us (see _child_preexec)."""
    port = random.randint(40000, 60000)
    proc = subprocess.Popen(
        [OPENCODE_BIN, "serve", "--hostname", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        preexec_fn=_child_preexec,
    )
    base = f"http://127.0.0.1:{port}"
    # 240 retries × 0.25s = ~60s. The default opencode cold start is <2s, but on the first
    # ever launch the local model may need to be loaded by Ollama, which can take much longer
    # — the longer window makes a one-time cold start finish cleanly instead of erroring out.
    max_retries = 240
    async with httpx.AsyncClient() as client:
        for i in range(max_retries):
            if proc.poll() is not None:
                raise RuntimeError(f"opencode serve exited early (code {proc.returncode})")
            try:
                await client.get(base + "/config", timeout=2.0)
                oc.proc, oc.base, oc.port = proc, base, port
                print(f"  opencode server: {base} (pid {proc.pid})", flush=True)
                return
            except Exception:
                if i > 0 and i % 40 == 0:  # progress ping every ~10s
                    print(f"  …waiting for opencode serve ({i*0.25:.0f}s)", flush=True)
                await asyncio.sleep(0.25)
    proc.kill()
    raise RuntimeError(
        f"opencode serve did not become ready in {max_retries*0.25:.0f}s "
        f"(is 'opencode' installed and reachable on PATH?)"
    )


def stop_opencode() -> None:
    if oc.proc is not None:
        try:
            os.killpg(os.getpgid(oc.proc.pid), signal.SIGKILL)  # whole session group
        except Exception:
            try:
                oc.proc.kill()
            except Exception:
                pass
    if oc.port is not None:  # belt: opencode may daemonize its real server into a new session
        try:
            subprocess.run(
                ["pkill", "-9", "-f", f"opencode serve --hostname 127.0.0.1 --port {oc.port}"],
                check=False,
            )
        except Exception:
            pass
    oc.proc = oc.base = oc.port = None


atexit.register(stop_opencode)  # belt for normal interpreter exit (PDEATHSIG covers hard kills)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await start_opencode()
    except Exception as e:  # the rest of the UI still works without the agent
        print(f"  ! opencode failed to start: {e}")
    try:
        yield
    finally:
        stop_opencode()


app = FastAPI(lifespan=lifespan, title="Garbanzo Books Studio")


# ---------------------------------------------------------------------------------- tool helpers
async def run_tool(args: list[str]) -> dict:
    proc = await asyncio.create_subprocess_exec(
        *PY_CMD, *args, cwd=str(ROOT),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    return {"ok": proc.returncode == 0, "output": out.decode("utf-8", "replace")}


@app.get("/api/library")
async def api_library():
    res = await run_tool(["scripts/library.py"])
    if res["ok"]:
        return Response(content=res["output"], media_type="application/json")
    return JSONResponse({"worlds": [], "error": res["output"]}, status_code=500)


@app.post("/api/build")
async def api_build():
    return JSONResponse(await run_tool(["scripts/build_site.py", "--include-drafts"]))


@app.post("/api/validate")
async def api_validate():
    return JSONResponse(await run_tool(["scripts/validate.py"]))


# ------------------------------------------------------------------------------------ chat (SSE)
def sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _tool_detail(tool: str, state: dict) -> str:
    """Turn an OpenCode tool part into a short, human-readable 'what is happening' line.
    The interesting bits live in state.input (e.g. bash → {command, description}; edit/write/read
    → {filePath}; glob/grep → {pattern}; webfetch → {url}). We prefer the most specific field so
    the studio shows 'running scripts/new_world.py' instead of a bare 'ran command'."""
    inp = state.get("input") or {}
    if tool == "bash":
        cmd = inp.get("command") or ""
        # The model usually writes a human description; fall back to the command itself.
        return (inp.get("description") or cmd or "").strip()
    if tool in ("edit", "write", "read", "patch"):
        fp = inp.get("filePath") or inp.get("path") or ""
        return fp.split("/")[-1] if fp else (state.get("title") or "")
    if tool in ("glob", "grep", "list"):
        return inp.get("pattern") or inp.get("path") or (state.get("title") or "")
    if tool in ("webfetch", "fetch"):
        return inp.get("url") or (state.get("title") or "")
    return state.get("title") or tool


async def chat_stream(prompt: str, session_id: str | None, model: str | None, request: Request):
    if not oc.base:
        yield sse({"type": "error", "text": "OpenCode unavailable — is 'opencode' installed and is Ollama running?"})
        yield sse({"type": "done"})
        return

    # Resolve the requested model (fall back to the default if missing/unknown).
    chosen = model if model in ALLOWED_MODELS else OPENCODE_MODEL
    provider_id, model_id = chosen.split("/", 1)

    async with httpx.AsyncClient(base_url=oc.base, timeout=None) as client:
        sid = session_id
        try:
            if not sid:
                r = await client.post("/session", json={"title": prompt[:50]})
                sid = r.json()["id"]
            yield sse({"type": "session", "sessionId": sid})

            role_by_msg: dict[str, str] = {}
            text_len: dict[str, int] = {}

            # Subscribe to the global event stream, THEN fire the prompt (async, returns at once),
            # and drive the turn off events — finishing on session.idle. No long-held request.
            async with aconnect_sse(client, "GET", "/event") as es:
                await client.post(
                    f"/session/{sid}/prompt_async",
                    json={
                        "model": {"providerID": provider_id, "modelID": model_id},
                        "system": STUDIO_BRIEF,
                        "tools": {"question": False, "ask": False},
                        "parts": [{"type": "text", "text": prompt}],
                    },
                )
                async for msg in es.aiter_sse():
                    if await request.is_disconnected():
                        # The user navigated away or hit Stop — tell OpenCode to abort the agent
                        # loop so it doesn't keep running tools in the background.
                        try:
                            await client.post(f"/session/{sid}/abort")
                        except Exception:
                            pass
                        break
                    try:
                        ev = json.loads(msg.data)
                    except Exception:
                        continue
                    p = ev.get("properties", {}) or {}
                    part = p.get("part", {}) or {}
                    ev_sid = p.get("sessionID") or part.get("sessionID") or (p.get("info", {}) or {}).get("sessionID")
                    if ev_sid and ev_sid != sid:
                        continue
                    t = ev.get("type")
                    if t == "message.updated":
                        info = p.get("info", {}) or {}
                        if info.get("id"):
                            role_by_msg[info["id"]] = info.get("role")
                    elif t == "message.part.updated":
                        role = role_by_msg.get(part.get("messageID"))
                        if part.get("type") == "text" and part.get("text") and role != "user":
                            full = part["text"]
                            prev = text_len.get(part.get("id"), 0)
                            if len(full) > prev:
                                yield sse({"type": "assistant", "text": full[prev:]})
                                text_len[part["id"]] = len(full)
                        elif part.get("type") == "tool":
                            state = part.get("state", {}) or {}
                            tool = part.get("tool") or "tool"
                            detail = _tool_detail(tool, state)
                            yield sse({"type": "tool", "id": part.get("id"),
                                       "tool": tool,
                                       "status": state.get("status", ""),
                                       "title": str(detail)[:140]})
                    elif t == "session.status":
                        # busy/idle heartbeat — lets the UI show "working…" with confidence even
                        # during long silent steps (e.g. image generation).
                        st = (p.get("status") or {}).get("type")
                        if st in ("busy", "idle"):
                            yield sse({"type": "status", "state": st})
                    elif t == "session.error":
                        yield sse({"type": "error", "text": str(p.get("error"))[:300]})
                        break
                    elif t == "session.idle":
                        break
            yield sse({"type": "result", "text": "done · local (free)"})
        except Exception as e:
            yield sse({"type": "error", "text": str(e)[:300]})
    yield sse({"type": "done"})


@app.get("/api/models")
async def api_models():
    return JSONResponse({"models": MODELS, "default": OPENCODE_MODEL})


@app.post("/api/stop")
async def api_stop(request: Request):
    """Abort the running turn so the user can redirect. Stops the agent loop (an already-running
    tool finishes, but no further steps run); the session then goes idle and accepts a new prompt."""
    body = await request.json()
    sid = body.get("sessionId")
    if not sid or not oc.base:
        return JSONResponse({"ok": False, "error": "no active session"}, status_code=400)
    try:
        async with httpx.AsyncClient(base_url=oc.base, timeout=10) as client:
            r = await client.post(f"/session/{sid}/abort")
        return JSONResponse({"ok": r.status_code == 200})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)[:200]}, status_code=500)


@app.post("/api/chat")
async def api_chat(request: Request):
    body = await request.json()
    prompt = (body.get("prompt") or "").strip()
    session_id = body.get("sessionId")
    model = body.get("model")
    if not prompt:
        return JSONResponse({"error": "empty prompt"}, status_code=400)
    return StreamingResponse(chat_stream(prompt, session_id, model, request), media_type="text/event-stream")


# ----------------------------------------------------------------------------- static + preview
# Mounted AFTER the API routes so /api/* and /preview/* win. check_dir=False lets /preview exist
# before the first build.
class NoCacheStatic(StaticFiles):
    """Local dev UI — never let the browser cache the console assets, so an edit to
    app.js/styles.css always shows up on a normal reload (no Ctrl+Shift+R needed)."""
    def is_not_modified(self, *args, **kwargs) -> bool:  # disable 304 revalidation
        return False

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp


# /preview keeps normal caching (it's the built site the reader sees); only the console is no-cache.
app.mount("/preview", StaticFiles(directory=str(SITE), html=True, check_dir=False), name="preview")
app.mount("/", NoCacheStatic(directory=str(PUBLIC), html=True), name="public")


if __name__ == "__main__":
    import sys
    import uvicorn
    # Force unbuffered stdout so the startup banner and the opencode-ready line show up
    # immediately in the terminal (and in the studio's job output) — uvicorn otherwise
    # keeps app prints buffered until the process exits, which masks startup failures.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    print(f"\n  Garbanzo Books Studio  →  http://localhost:{PORT}")
    print(f"  workspace: {ROOT}")
    print(f"  agent: OpenCode + {OPENCODE_MODEL} (no API key needed)")
    print_env_check()
    print("", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
