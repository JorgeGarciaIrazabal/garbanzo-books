"""Garbanzo Books Studio — dynamic UI backend (FastAPI).

Serves the console (ui/public), proxies the built site at /preview, and exposes:
  GET  /api/library       — worlds/characters/stories as JSON (scripts/library.py)
  POST /api/build         — build the studio preview, drafts included (scripts/build_site.py)
  POST /api/build/publish — build the public preview, published only (→ site_publish/)
  POST /api/story/status  — publish/unpublish ONE story via the gated scripts/publish_story.py
  POST /api/deploy        — git add/commit/push so the Pages workflow ships the site
  POST /api/validate      — QA the workspace (scripts/validate.py)
  POST /api/chat          — stream the AI agent (Server-Sent Events)

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
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from httpx_sse import aconnect_sse

import voice  # local Kokoro TTS + faster-whisper STT (read-aloud & voice input); see ui/voice.py

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # repo root = the workspace OpenCode operates in
PUBLIC = HERE / "public"
SITE = ROOT / "site"                   # studio preview build (with drafts) — what the in-app iframe shows
SITE_PUBLISH = ROOT / "site_publish"   # "what GitHub Pages will see" build (published only)
PORT = int(os.environ.get("PORT", "4317"))
PY_CMD = os.environ.get("PY_CMD", "uv run python").split()
OPENCODE_BIN = os.environ.get("OPENCODE_BIN", "opencode")
OPENCODE_MODEL = os.environ.get("OPENCODE_MODEL", "ollama/nemotron-3-ultra:cloud")
PROVIDER_ID, MODEL_ID = OPENCODE_MODEL.split("/", 1)

# Models the studio offers in its model picker. Each must also be registered under the matching
# provider in opencode.json. Three tiers, each tuned to a different job:
#   - Nemotron-3-Ultra  : fast + reliable, the default for world/character/building/validation
#   - DeepSeek-V4-Pro   : slower but more creative, used when the agent is writing the STORY
#   - MiniMax-M3        : best for information gathering (web search, summarising, looking things up)
# The "auto" sentinel lets the studio pick the right model per stage (see STAGE_TO_MODEL).
MODELS = [
    {"id": "ollama/nemotron-3-ultra:cloud",
     "label": "Nemotron-3-Ultra — fast & reliable (default for craft)"},
    {"id": "ollama/deepseek-v4-pro:cloud",
     "label": "DeepSeek-V4-Pro — more creative (best for stories)"},
    {"id": "ollama/minimax-m3:cloud",
     "label": "MiniMax-M3 — best for research & information gathering"},
    {"id": "auto",
     "label": "Auto (switch by stage) — recommended"},
]
ALLOWED_MODELS = {m["id"] for m in MODELS}

# Stage tag → model. The agent emits [[stage:<name>]] (see STUDIO_BRIEF) at the end of its message
# to tell the studio what kind of step it just finished. In Auto mode, the NEXT turn uses the model
# mapped below. (OpenCode's HTTP API binds a model at prompt time, so we can't switch mid-turn —
# the next user reply is the natural place to swap.) The "craft" stages all share the fast default
# because they're tool-heavy; "story" is the only creative stage; "research" routes to MiniMax.
STAGE_TO_MODEL = {
    "craft":     "ollama/nemotron-3-ultra:cloud",
    "world":     "ollama/nemotron-3-ultra:cloud",
    "character": "ollama/nemotron-3-ultra:cloud",
    "build":     "ollama/nemotron-3-ultra:cloud",
    "validate":  "ollama/nemotron-3-ultra:cloud",
    "done":      "ollama/nemotron-3-ultra:cloud",
    "story":     "ollama/deepseek-v4-pro:cloud",
    "research":  "ollama/minimax-m3:cloud",
}


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

SPEED — every tool round trip costs a full model pass, so batch your context gathering:
- Writing a story in an EXISTING world? Run "uv run python scripts/story_context.py <world>"
  FIRST — it prints the world bible, full cast (personalities, voices, catchphrases, stages),
  existing story slugs, the age-band table, and the exact scaffold command in ONE call.
  Do NOT separately read world.yaml + each character yaml — the pack has it all.
- Illustrations render pages in parallel already (generate_images.py --jobs, default 4);
  run it ONCE for the whole story, never page-by-page.

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
one short sentence and stop. The form is a fenced code block in your normal MESSAGE TEXT — there
is NO tool named "form"; never attempt a tool call named "form" (it will error). Likewise NEVER
call any interactive "question"/"ask" tool (it is disabled).

MODEL STAGES — the console can AUTO-PICK a model tuned to whatever step you're about to do, but
only if you tell it which step that is. Emit exactly ONE of the following on its OWN line at the
END of your message (the tag is hidden from the user — never mention it):
  [[stage:story]]     whenever the NEXT thing you'll do is write or revise the STORY text/pages
                      (emit it on the confirmation message right before you start writing, and keep
                      emitting it on messages WHILE you are writing the story).
  [[stage:craft]]     for tool-heavy craft work that is NOT a story — scaffolding/validating files,
                      reading-level work, building the site, image prompts, etc.
  [[stage:world]]     specifically when you are world-building (creating or editing a world.yaml).
  [[stage:character]] specifically when you are designing a character (creating or editing a
                      character bible / reference art).
  [[stage:build]]     specifically when you are generating page images or building the static site.
  [[stage:research]]  specifically when you are gathering information (web search, reading docs,
                      looking things up) before making a decision.
  [[stage:done]]      when the user's request is complete and you are signing off.

If you forget, the console falls back to the fast default. The exact text of the tag is matched —
no extra spaces inside the brackets, the word after the colon is lowercase.

FILE SAFETY — the workspace must never be left with a broken file. Content YAML under worlds/
is NEVER written or edited as text. Two rules cover everything:
- CREATE with the scaffolding scripts (new_world.py, new_character.py, new_story.py) — they
  write valid, atomic YAML with every stub pre-filled. Check a script's usage (positional
  args!) with --help BEFORE guessing flags — e.g. new_story.py takes
  `<world> "<Title>" --age 5-7 --year 6 --pages 14 [--slug s]` as positionals, not
  --world/--title. For a story ALWAYS scaffold all the page stubs up front with --pages N.
  A story has TWO separate age knobs — never conflate them:
    --age <band>  = READING level: who reads the WORDS (sentence length, words/page,
                    word choice). Bands: 0-3, 3-5, 5-7, 7-9, 9-12.
    --year <N>    = TARGET age: one number, the age the CONTENT is pitched at — humor,
                    stakes, themes (stored as target_year). A book can be --age 5-7
                    --year 7: seven-year-old jokes and jeopardy in beginning-reader words.
- EDIT with the JSON-patch scripts (edit_world.py, edit_character.py, edit_story.py): you emit
  a SMALL JSON payload on stdin (a heredoc), the script deep-merges it, validates the merged
  document against the schema, and writes atomically. A bad patch changes NOTHING and prints
  every schema error at once — fix the JSON and re-run; the file on disk is never broken.
  NEVER use your write/edit file tools on worlds/**/*.yaml — YAML indentation by hand is how
  files break. (write/edit tools are still fine for style-guide.md and other non-YAML files.)
    uv run python scripts/edit_story.py <world>/<story> meta <<'JSON'
    {"logline": "...", "spine": {...}}
    JSON
    uv run python scripts/edit_story.py <world>/<story> pages <<'JSON'
    [{"number": 3, "text": "...", "image": {"prompt": "...", "characters_present": [...], "alt": "..."}}]
    JSON
    uv run python scripts/edit_story.py <world>/<story> interaction <N> <<'JSON'   # game on page N
    {"type": "...", "prompt": "...", "data": {...}}
    JSON
    uv run python scripts/edit_world.py <world> <<'JSON' ...           # same for world.yaml
    uv run python scripts/edit_character.py <world>/<char> <<'JSON' ...  # and character yamls
  Merge rules: nested objects merge key-by-key; story pages merge by "number" (send partial
  page objects); other lists replace wholesale; JSON null deletes a key.
- Keep every patch SMALL — fill a story's metadata + spine in one call, then the pages in
  batches of 3-4 pages per call. One giant 300+ line generation takes minutes on the local
  model and the studio looks frozen the whole time.
- When the whole artifact is filled in, run "uv run python scripts/validate.py worlds/<world>"
  (or the specific story path) and FIX any failures before moving on or telling the user a step
  is done — the edit scripts guarantee schema-validity, but validate.py also checks
  cross-file consistency (rosters, tokens, images). Do not mark a book published while
  validation fails.

IMAGE GENERATION — the GEMINI_API_KEY is ALREADY configured in this workspace's .env and loaded
into your environment. ALWAYS assume it is present and just run "uv run python
scripts/generate_images.py ..." — do not ask the user whether to generate images, do not skip the
step "in case the key is missing", do not propose placeholders as an alternative, and do not
suggest the user set up a key. Just run the tool. If (and only if) the script itself exits with an
error about a missing/invalid key, STOP IMMEDIATELY, surface that one short error to the user, and
do not retry — never silently fall back to placeholder art."""

# Appended to the brief when the console is in KIDS MODE — the person answering is a young child
# using big icon buttons, voice in, and voice out (the console reads your replies aloud and renders
# each form as ONE big question at a time). Tailor your language and forms to that.
KIDS_BRIEF = """

KIDS MODE IS ON. A young child is answering — using big picture buttons and talking out loud, and
the console READS YOUR REPLIES ALOUD. Adapt everything for them:
- Keep every reply VERY short (1-2 simple, warm sentences). Use easy, concrete words. No jargon,
  no file paths, no tool names, no markdown headings/code in messages to the child.
- When you need input, ALWAYS use the form protocol, and ask only ONE question per form (a single
  field; never more than two). Give 3-4 concrete, picture-able "select" options in plain kid words,
  each something a child can imagine (e.g. "a sleepy dragon", "a brave little mouse").
- Cheer them on for their choices. Do the technical work quietly between questions."""


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


@app.get("/api/library")
async def api_library():
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
    out_arg = str(SITE_PUBLISH.relative_to(ROOT)) if SITE_PUBLISH.is_absolute() and SITE_PUBLISH.is_relative_to(ROOT) else str(SITE_PUBLISH)
    return JSONResponse(await run_tool(["scripts/build_site.py", "--out", out_arg]))


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
def sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

# Per-session last-seen [[stage:...]] tag. The agent emits these at the END of an assistant turn
# (see STUDIO_BRIEF). In Auto mode the server uses this to pick the model for the NEXT turn.
# Keyed by OpenCode session id. Capped so a long-running studio doesn't leak memory.
LAST_STAGE_BY_SESSION: dict[str, str] = {}
_LAST_STAGE_MAX = 256
_STAGE_TAG_RE = __import__("re").compile(r"\[\[stage:(\w+)\]\]", __import__("re").IGNORECASE)


def _remember_stage(sid: str | None, stage: str | None) -> None:
    if not sid or not stage:
        return
    stage = stage.lower()
    # Only record stages the model router knows about — anything else is ignored.
    if stage in STAGE_TO_MODEL:
        LAST_STAGE_BY_SESSION[sid] = stage
        # Cap + drop the oldest entry if we grow past the limit.
        if len(LAST_STAGE_BY_SESSION) > _LAST_STAGE_MAX:
            # dicts are insertion-ordered in py3.7+, so the first key is the oldest.
            oldest = next(iter(LAST_STAGE_BY_SESSION))
            if oldest != sid:
                LAST_STAGE_BY_SESSION.pop(oldest, None)


def _tool_event(part: dict) -> dict:
    """Build the SSE payload for a tool part: the compact human line (title) PLUS the full
    input/output so the studio can render the row as an expandable section. Output is capped —
    it's for eyeballing progress/debugging, not for re-parsing."""
    state = part.get("state", {}) or {}
    tool = part.get("tool") or "tool"
    ev: dict = {"type": "tool", "id": part.get("id"), "tool": tool,
                "status": state.get("status", ""),
                "title": str(_tool_detail(tool, state))[:140]}
    inp = state.get("input") or {}
    if inp:
        try:
            ev["input"] = json.dumps(inp, ensure_ascii=False)[:3000]
        except Exception:
            ev["input"] = str(inp)[:3000]
    out = state.get("output")
    if isinstance(out, str) and out.strip():
        ev["output"] = out[:8000]
    err = state.get("error")
    if err:
        ev["error"] = str(err)[:2000]
    return ev


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


async def chat_stream(prompt: str, session_id: str | None, model: str | None, request: Request,
                      kids: bool = False):
    if not oc.base:
        yield sse({"type": "error", "text": "OpenCode unavailable — is 'opencode' installed and is Ollama running?"})
        yield sse({"type": "done"})
        return

    # Resolve the requested model. "auto" (or any unknown value) means: pick the model that matches
    # the stage tag from the agent's LAST turn in this session. Falls back to the default if the
    # session is new, no tag was emitted yet, or the tag is unknown.
    chosen: str
    if model == "auto" or model not in ALLOWED_MODELS:
        last_stage = LAST_STAGE_BY_SESSION.get(session_id) if session_id else None
        chosen = STAGE_TO_MODEL.get(last_stage or "", OPENCODE_MODEL)
    else:
        chosen = model
    # Belt: if a stale "auto" sneaks in with no resolved stage, use the default rather than crash.
    if chosen == "auto":
        chosen = OPENCODE_MODEL
    provider_id, model_id = chosen.split("/", 1)
    system_brief = STUDIO_BRIEF + (KIDS_BRIEF if kids else "")
    # Tell the client which model we actually picked (so the picker can reflect Auto decisions).
    yield sse({"type": "model", "model": chosen, "stage": LAST_STAGE_BY_SESSION.get(session_id) if session_id else None})

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
                        "system": system_brief,
                        "tools": {"question": False, "ask": False},
                        "parts": [{"type": "text", "text": prompt}],
                    },
                )
                # Watchdog loop: OpenCode goes COMPLETELY silent while the model streams a
                # long tool call's arguments (e.g. a whole story.yaml in one `write`) — a
                # session once sat 6½ minutes with zero events and the studio looked frozen.
                # Waking every 30s lets us (a) tell the UI "still generating" and (b) notice
                # a closed tab and abort the agent instead of letting it run unattended.
                events = es.aiter_sse()
                silent_secs = 0
                while True:
                    try:
                        msg = await asyncio.wait_for(anext(events), timeout=30.0)
                    except asyncio.TimeoutError:
                        if await request.is_disconnected():
                            try:
                                await client.post(f"/session/{sid}/abort")
                            except Exception:
                                pass
                            break
                        silent_secs += 30
                        # Distinguish "model is slowly generating" from "OpenCode died":
                        # a quick health probe. A dead process must surface as an ERROR,
                        # not an eternal series of 'still working' pings.
                        try:
                            await client.get("/config", timeout=5.0)
                        except Exception:
                            yield sse({"type": "error",
                                       "text": "OpenCode stopped responding — the agent "
                                               "process looks dead (crash or Ollama down). "
                                               "Restart `make ui`, then send "
                                               "“continue where you left off”; finished "
                                               "steps are already saved."})
                            break
                        yield sse({"type": "stall", "seconds": silent_secs})
                        continue
                    except StopAsyncIteration:
                        break
                    silent_secs = 0
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
                            # Stage tag detection: the agent appends a [[stage:foo]] on its own line
                            # at the end of a turn. We only trust the LAST one we see (and only
                            # ones we know how to route) so an echo in earlier text can't poison
                            # the choice for the next turn.
                            m = _STAGE_TAG_RE.findall(full)
                            if m:
                                _remember_stage(sid, m[-1])
                                yield sse({"type": "stage", "stage": m[-1].lower()})
                        elif part.get("type") == "reasoning" and part.get("text") and role != "user":
                            # The model's chain-of-thought, streamed like text but as its own
                            # event type so the studio can show it in a collapsible section.
                            full = part["text"]
                            prev = text_len.get(part.get("id"), 0)
                            if len(full) > prev:
                                yield sse({"type": "reasoning", "id": part.get("id"),
                                           "text": full[prev:]})
                                text_len[part["id"]] = len(full)
                        elif part.get("type") == "tool":
                            yield sse(_tool_event(part))
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
