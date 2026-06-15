"""Garbanzo Books Studio — dynamic UI backend (FastAPI).

Serves the console (ui/public), proxies the built site at /preview, and exposes:
  GET  /api/library       — worlds/characters/stories as JSON (scripts/library.py)
  POST /api/build         — build the studio preview, drafts included (scripts/build_site.py)
  POST /api/build/publish — build the public preview, published only (→ site_publish/)
  POST /api/story/status  — publish/unpublish ONE story via the gated scripts/publish_story.py
  POST /api/story/delete  — permanently delete ONE story (scripts/delete_content.py)
  POST /api/world/delete  — permanently delete a WHOLE world (scripts/delete_content.py)
  POST /api/deploy        — git add/commit/push so the Pages workflow ships the site
  POST /api/validate      — QA the workspace (scripts/validate.py)
  POST /api/chat          — stream the AI agent (Server-Sent Events)

This module owns the HTTP surface; the moving parts live in focused siblings:
  config.py          — env knobs + the chat-model roster
  studio_prompts.py  — the agent's system briefs (STUDIO_BRIEF / KIDS_BRIEF)
  opencode_client.py — the `opencode serve` subprocess lifecycle (the shared `oc`)
  chat.py            — the SSE chat turn (chat_stream) + tool/stage helpers
  voice.py           — local Kokoro TTS + faster-whisper STT

The chat agent is OpenCode driving a LOCAL Ollama model — so NO API KEY is needed. Image
generation, when the agent calls scripts/generate_images.py, still uses GEMINI_API_KEY from
.env (separate from the chat model).

Run:  uv run --group ui python ui/server.py     (or `make ui`)
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

import voice  # local Kokoro TTS + faster-whisper STT (read-aloud & voice input); see ui/voice.py
# Re-exported so the rest of the codebase (and tests) can keep importing them from `server`.
from config import (ALLOWED_MODELS, MODELS, OPENCODE_MODEL, PORT,  # noqa: F401
                    PY_CMD, STAGE_TO_MODEL)
from chat import _tool_detail, _tool_event, chat_stream, sse  # noqa: F401
from opencode_client import oc, start_opencode, stop_opencode  # noqa: F401

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # repo root = the workspace OpenCode operates in
PUBLIC = HERE / "public"
SITE = ROOT / "site"                   # studio preview build (with drafts) — what the in-app iframe shows
SITE_PUBLISH = ROOT / "site_publish"   # "what GitHub Pages will see" build (published only)


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await start_opencode()
    except Exception as e:  # the rest of the UI still works without the agent
        print(f"  ! opencode failed to start: {e}")
    # Warm the speech models in the background so the first read-aloud / mic tap is instant.
    if any(voice.available().get(k) for k in ("tts", "stt")):
        asyncio.create_task(asyncio.to_thread(voice.warm))
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


def _publish_out_arg() -> str:
    """The published-only build's output dir, relative to ROOT when possible (matches /api/build/publish)."""
    if SITE_PUBLISH.is_absolute() and SITE_PUBLISH.is_relative_to(ROOT):
        return str(SITE_PUBLISH.relative_to(ROOT))
    return str(SITE_PUBLISH)


def _preview_is_stale() -> bool:
    """True if authored content under worlds/ is newer than the studio preview build.

    The library cards link straight to /preview/story/<world>/<story>/index.html — but
    /preview is a static mount on ./site/, a build *snapshot*. A draft created/edited via
    chat (not through publish/unpublish or the 🔨 Rebuild button) has a card but no built
    page yet, so the link 404s ('{"detail":"Not Found"}'). We detect that here and rebuild
    on the next library load so every card resolves."""
    stamp = SITE / "index.html"
    if not stamp.exists():
        return True  # never built
    built = stamp.stat().st_mtime
    worlds = ROOT / "worlds"
    if not worlds.exists():
        return False
    for p in worlds.rglob("*"):
        if not p.is_file():
            continue
        try:
            if p.stat().st_mtime > built:
                return True
        except OSError:
            continue
    return False


# ------------------------------------------------------------------------------- library + builds
@app.get("/api/library")
async def api_library():
    # Keep the studio preview in sync with disk: if a draft was created/edited since the last
    # build, rebuild (drafts included) before returning, so the cards we hand back link to
    # pages that actually exist. Best-effort — a build hiccup must never break the library.
    if _preview_is_stale():
        try:
            await run_tool(["scripts/build_site.py", "--include-drafts"])
        except Exception:
            pass
    res = await run_tool(["scripts/library.py"])
    if res["ok"]:
        return Response(content=res["output"], media_type="application/json")
    return JSONResponse({"worlds": [], "error": res["output"]}, status_code=500)


@app.post("/api/build")
async def api_build():
    """Studio preview build: includes drafts. What the in-app /preview/ iframe shows, so
    the author can browse their WIP. Lands in ./site/ (and would be uploaded by the
    --include-drafts flag, but the GH Pages deploy workflow does NOT use this — it builds
    ./site/ from a published-only run, so end users never see drafts)."""
    return JSONResponse(await run_tool(["scripts/build_site.py", "--include-drafts"]))


@app.post("/api/build/publish")
async def api_build_publish():
    """Published-only build into ./site_publish/. This is the EXACT shape the GH Pages
    workflow will deploy — letting the author preview 'what will go live' before pushing.
    Does not touch ./site/, so the studio's in-app preview is unaffected."""
    return JSONResponse(await run_tool(["scripts/build_site.py", "--out", _publish_out_arg()]))


@app.get("/api/publish/status")
async def api_publish_status():
    """Report whether a publish-preview build exists and how to deploy it. The studio
    uses this to label the 'Public preview' tab ('last build: 2 min ago' or 'no build
    yet — click Publish to preview') and to surface the manual deploy command.

    We do not auto-trigger the GH Pages deploy from the studio: that needs a git push
    (or a gh workflow run), which is the user's action, not ours. The instruction we
    surface mirrors what /publish + the deploy-pages workflow do."""
    exists = (SITE_PUBLISH / "index.html").exists()
    last_built = None
    if exists:
        try:
            last_built = (SITE_PUBLISH / "index.html").stat().st_mtime
        except OSError:
            pass
    # out_dir is shown in the UI; prefer the path relative to ROOT so the user sees the
    # real repo path, but fall back to the absolute path (e.g. in tests) so we never crash.
    try:
        out_dir = str(SITE_PUBLISH.relative_to(ROOT))
    except ValueError:
        out_dir = str(SITE_PUBLISH)
    # Current branch, so the UI can warn when a push won't trigger the Pages deploy
    # (the deploy-pages workflow only runs on main).
    branch = None
    try:
        rc, out = await run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if rc == 0:
            branch = out.strip() or None
    except Exception:
        pass
    return {
        "built": exists,
        "branch": branch,
        "last_built_mtime": last_built,
        "out_dir": out_dir,
        "deploy_instructions": (
            "Push to main — the .github/workflows/deploy-pages.yml workflow will build "
            "and publish ./site/ to GitHub Pages. Enable Settings → Pages → Source: "
            "GitHub Actions once if you haven't.\n\n"
            "Or trigger the workflow manually:\n"
            "  gh workflow run deploy-pages.yml\n\n"
            "Or deploy the gh-pages branch directly:\n"
            "  scripts/build_site.py --deploy   (prints the git commands)"
        ),
    }


# ------------------------------------------------------------------------------- story / world ops
@app.post("/api/story/status")
async def api_story_status(request: Request):
    """Flip one story between draft and published via scripts/publish_story.py — which runs
    the FULL validator gate before allowing 'published', so a broken book can't be flipped.
    Body: {"world": "<slug>", "story": "<slug>", "status": "published"|"draft"}."""
    body = await request.json()
    wslug = (body.get("world") or "").strip()
    sslug = (body.get("story") or "").strip()
    status = (body.get("status") or "").strip()
    if not wslug or not sslug or status not in ("published", "draft"):
        return JSONResponse({"ok": False, "output": "need world, story and a valid status"},
                            status_code=400)
    args = ["scripts/publish_story.py", f"{wslug}/{sslug}"]
    if status == "draft":
        args.append("--draft")
    return JSONResponse(await run_tool(args))


@app.post("/api/story/delete")
async def api_story_delete(request: Request):
    """Permanently delete ONE story (its whole dir) via scripts/delete_content.py, then rebuild
    both previews so the library/ribbons reflect disk. Body: {"world": "<slug>", "story": "<slug>"}."""
    body = await request.json()
    wslug = (body.get("world") or "").strip()
    sslug = (body.get("story") or "").strip()
    if not wslug or not sslug:
        return JSONResponse({"ok": False, "output": "need world and story"}, status_code=400)
    res = await run_tool(["scripts/delete_content.py", f"{wslug}/{sslug}", "--yes"])
    if res["ok"]:  # keep the studio + public previews in sync with what's now on disk
        await run_tool(["scripts/build_site.py", "--include-drafts"])
        await run_tool(["scripts/build_site.py", "--out", _publish_out_arg()])
    return JSONResponse(res)


@app.post("/api/world/delete")
async def api_world_delete(request: Request):
    """Permanently delete a WHOLE world (bible + every character AND story) via
    scripts/delete_content.py, then rebuild both previews. Body: {"world": "<slug>"}."""
    body = await request.json()
    wslug = (body.get("world") or "").strip()
    if not wslug:
        return JSONResponse({"ok": False, "output": "need world"}, status_code=400)
    res = await run_tool(["scripts/delete_content.py", wslug, "--yes"])
    if res["ok"]:
        await run_tool(["scripts/build_site.py", "--include-drafts"])
        await run_tool(["scripts/build_site.py", "--out", _publish_out_arg()])
    return JSONResponse(res)


# ------------------------------------------------------------------------------------ git / deploy
async def run_git(args: list[str]) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "git", *args, cwd=str(ROOT),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    return proc.returncode or 0, out.decode("utf-8", "replace")


@app.post("/api/deploy")
async def api_deploy():
    """Ship to GitHub Pages: commit everything and push. The push triggers the
    deploy-pages workflow (on main), which rebuilds published-only — so drafts can
    never leak even though we `git add -A`. Reports each git step's output so auth
    or remote problems surface in the UI instead of failing silently."""
    log: list[str] = []
    rc, out = await run_git(["add", "-A"])
    log.append("$ git add -A\n" + out)
    if rc != 0:
        return JSONResponse({"ok": False, "output": "\n".join(log)})
    rc, out = await run_git(["diff", "--cached", "--quiet"])
    if rc != 0:  # staged changes exist → commit them
        rc, out = await run_git(["commit", "-m", "publish storybooks (studio deploy)"])
        log.append("$ git commit\n" + out)
        if rc != 0:
            return JSONResponse({"ok": False, "output": "\n".join(log)})
    else:
        log.append("(nothing new to commit — pushing what's here)")
    rc, out = await run_git(["push"])
    log.append("$ git push\n" + out)
    return JSONResponse({"ok": rc == 0, "output": "\n".join(log)})


# --------------------------------------------------------------------------------------- progress
@app.get("/api/progress")
async def api_progress():
    """Live progress from long-running scripts (scripts/lib/progress.py side-channel).
    The agent's bash tool only surfaces a script's stdout when the command FINISHES, so
    e.g. generate_images.py writes {task, done, total, detail, ts} to
    .studio-progress.json after each page; the activity strip polls this while busy.
    A stale file (crashed/killed script) reads as inactive — never a lying banner."""
    pf = ROOT / ".studio-progress.json"
    try:
        data = json.loads(pf.read_text(encoding="utf-8"))
        age = max(0.0, time.time() - float(data.get("ts") or 0))
        if age > 120:
            return {"active": False}
        return {"active": True, "age": round(age, 1),
                "task": data.get("task"), "done": data.get("done"),
                "total": data.get("total"), "detail": data.get("detail")}
    except Exception:
        return {"active": False}


# ----------------------------------------------------------------------------------- QA endpoints
@app.post("/api/validate")
async def api_validate():
    return JSONResponse(await run_tool(["scripts/validate.py"]))


@app.post("/api/quality")
async def api_quality():
    # The 7-gate quality scorecard (how *good* the books are, beyond pass/fail validation).
    return JSONResponse(await run_tool(["scripts/quality_report.py"]))


# ----------------------------------------------------------------------------- speech (TTS / STT)
@app.get("/api/voice")
async def api_voice():
    """Report which local speech backends are installed so the UI can enable/disable its controls."""
    try:
        return JSONResponse(voice.available())
    except Exception as e:
        return JSONResponse({"tts": False, "stt": False, "error": str(e)[:200]})


@app.post("/api/voice/warm")
async def api_voice_warm():
    """Fire-and-forget background model load so the first read-aloud / mic click is instant."""
    asyncio.create_task(asyncio.to_thread(voice.warm))
    return JSONResponse({"ok": True})


@app.post("/api/tts")
async def api_tts(request: Request):
    """JSON {text, voice?, speed?} → a WAV the browser plays. Kokoro-82M, on CPU, no API key."""
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "empty text"}, status_code=400)
    voice_id = body.get("voice") or voice.DEFAULT_VOICE
    try:
        speed = float(body.get("speed") or 1.0)
    except (TypeError, ValueError):
        speed = 1.0
    try:
        wav = await asyncio.to_thread(voice.synthesize, text, voice_id, speed)
    except Exception as e:
        return JSONResponse({"error": str(e)[:300]}, status_code=500)
    return Response(content=wav, media_type="audio/wav")


@app.post("/api/stt")
async def api_stt(request: Request):
    """Raw audio bytes in the request body (any browser blob: webm/opus, ogg, wav) → {text}.
    faster-whisper decodes it in-process via PyAV, so no system ffmpeg is required."""
    data = await request.body()
    if not data:
        return JSONResponse({"error": "no audio"}, status_code=400)
    try:
        text = await asyncio.to_thread(voice.transcribe, data)
    except Exception as e:
        return JSONResponse({"error": str(e)[:300]}, status_code=500)
    return JSONResponse({"text": text})


# ------------------------------------------------------------------------------------ chat (SSE)
@app.get("/api/session/{sid}/messages")
async def api_session_messages(sid: str):
    """Debug view: the FULL OpenCode conversation for a session — every message with all its
    parts (text, reasoning, tool calls with inputs/outputs, step markers). The studio's Debug
    tab renders this so the author can inspect exactly what the agent saw and did."""
    if not oc.base:
        return JSONResponse({"error": "opencode not running"}, status_code=503)
    try:
        async with httpx.AsyncClient(base_url=oc.base, timeout=30) as client:
            r = await client.get(f"/session/{sid}/message")
            return JSONResponse(r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)[:300]}, status_code=500)


@app.get("/api/models")
async def api_models():
    return JSONResponse({
        "models": MODELS,
        "default": OPENCODE_MODEL,
        "stage_to_model": STAGE_TO_MODEL,
    })


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
    kids = bool(body.get("kids"))
    if not prompt:
        return JSONResponse({"error": "empty prompt"}, status_code=400)
    return StreamingResponse(chat_stream(prompt, session_id, model, request, kids),
                             media_type="text/event-stream")


# ----------------------------------------------------------------------------- static + preview
# Mounted AFTER the API routes so /api/*, /preview/* and /publish-preview/* win.
# check_dir=False lets the preview dirs exist before the first build.
class NoCacheStatic(StaticFiles):
    """Local dev UI — never let the browser cache the console assets, so an edit to
    app.js/styles.css always shows up on a normal reload (no Ctrl+Shift+R needed)."""
    def is_not_modified(self, *args, **kwargs) -> bool:  # disable 304 revalidation
        return False

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp


# /preview = studio preview build (with drafts, lands in ./site/).
# /publish-preview = published-only build (lands in ./site_publish/) — the EXACT shape
# GitHub Pages will deploy. Both keep normal caching; only the console is no-cache.
app.mount("/preview", StaticFiles(directory=str(SITE), html=True, check_dir=False), name="preview")
app.mount("/publish-preview", StaticFiles(directory=str(SITE_PUBLISH), html=True, check_dir=False),
          name="publish_preview")
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
    _vc = voice.available()
    if _vc.get("tts") or _vc.get("stt"):
        print(f"  speech: Kokoro TTS {'✓' if _vc.get('tts') else '✗'}  ·  "
              f"faster-whisper STT {'✓' if _vc.get('stt') else '✗'}  (local, warming in background)")
    else:
        print("  speech: read-aloud/voice disabled — install with `uv sync --group tts`.")
    print_env_check()
    print("", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
