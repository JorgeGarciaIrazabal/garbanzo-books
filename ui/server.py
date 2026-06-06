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

STUDIO_BRIEF = """You are the studio director inside the "Garbanzo Books" AI storybook workspace.
Read CLAUDE.md and methodology/ as needed. Tools live in scripts/ — run them via
"uv run python scripts/<tool>.py" (new_world.py, new_character.py, new_story.py,
generate_images.py, validate.py, build_site.py).

Work INTERACTIVELY and CONFIRM as you go — never build everything in one giant turn:
1. When the user wants a new world or book, FIRST ask 3-5 concise questions (theme/setting,
   target age band, tone, art-style vibe, main character ideas). Then STOP and wait.
2. Propose a short world bible + locked art style as a brief summary, scaffold ONLY the world
   (new_world.py) and edit world.yaml/style-guide.md. Then STOP and ask: "Does this world look
   right before I design characters?"
3. After approval, design 1-3 characters and generate their reference sheets
   (generate_images.py --character ...). Show what you made and STOP: "Do the characters look
   good before I write the story?"
4. After approval, write the story (new_story.py + story-craft), adapt the reading level,
   add interactions, generate page images, validate, and build. Confirm before publishing.

Keep each turn focused and short. Ask one batch of questions at a time and wait for the answer
rather than guessing. Always end a turn by stating what you did and the next decision you need.
IMPORTANT: Ask questions and request confirmation as PLAIN TEXT, then end your turn — do NOT
call any interactive "question"/"ask" tool (it is disabled). The user replies in the next message."""


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
    async with httpx.AsyncClient() as client:
        for _ in range(120):  # up to ~30s
            if proc.poll() is not None:
                raise RuntimeError(f"opencode serve exited early (code {proc.returncode})")
            try:
                await client.get(base + "/config", timeout=2.0)
                oc.proc, oc.base, oc.port = proc, base, port
                print(f"  opencode server: {base} (pid {proc.pid})")
                return
            except Exception:
                await asyncio.sleep(0.25)
    proc.kill()
    raise RuntimeError("opencode serve did not become ready in time")


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


async def chat_stream(prompt: str, session_id: str | None, request: Request):
    if not oc.base:
        yield sse({"type": "error", "text": "OpenCode unavailable — is 'opencode' installed and is Ollama running?"})
        yield sse({"type": "done"})
        return

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
                        "model": {"providerID": PROVIDER_ID, "modelID": MODEL_ID},
                        "system": STUDIO_BRIEF,
                        "tools": {"question": False, "ask": False},
                        "parts": [{"type": "text", "text": prompt}],
                    },
                )
                async for msg in es.aiter_sse():
                    if await request.is_disconnected():
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
                            title = state.get("title") or part.get("tool") or "tool"
                            yield sse({"type": "tool", "id": part.get("id"),
                                       "tool": part.get("tool") or "tool",
                                       "status": state.get("status", ""), "title": str(title)[:100]})
                    elif t == "session.error":
                        yield sse({"type": "error", "text": str(p.get("error"))[:300]})
                        break
                    elif t == "session.idle":
                        break
            yield sse({"type": "result", "text": "done · local (free)"})
        except Exception as e:
            yield sse({"type": "error", "text": str(e)[:300]})
    yield sse({"type": "done"})


@app.post("/api/chat")
async def api_chat(request: Request):
    body = await request.json()
    prompt = (body.get("prompt") or "").strip()
    session_id = body.get("sessionId")
    if not prompt:
        return JSONResponse({"error": "empty prompt"}, status_code=400)
    return StreamingResponse(chat_stream(prompt, session_id, request), media_type="text/event-stream")


# ----------------------------------------------------------------------------- static + preview
# Mounted AFTER the API routes so /api/* and /preview/* win. check_dir=False lets /preview exist
# before the first build.
app.mount("/preview", StaticFiles(directory=str(SITE), html=True, check_dir=False), name="preview")
app.mount("/", StaticFiles(directory=str(PUBLIC), html=True), name="public")


if __name__ == "__main__":
    import uvicorn
    print(f"\n  Garbanzo Books Studio  →  http://localhost:{PORT}")
    print(f"  workspace: {ROOT}")
    print(f"  agent: OpenCode + {OPENCODE_MODEL} (no API key needed)\n")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
