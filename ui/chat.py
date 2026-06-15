"""The chat turn: stream the OpenCode agent to the browser as Server-Sent Events.

chat_stream() subscribes to OpenCode's global event stream, fires the prompt, and translates
its events (assistant text, reasoning, tool calls, status) into the compact SSE the console
renders. It also runs the Auto model-routing (per the agent's [[stage:...]] tags) and a
watchdog that distinguishes "model is slowly generating" from "OpenCode died".
"""
from __future__ import annotations

import asyncio
import json
import re

import httpx
from fastapi import Request
from httpx_sse import aconnect_sse

from config import ALLOWED_MODELS, OPENCODE_MODEL, STAGE_TO_MODEL
from opencode_client import oc
from studio_prompts import KIDS_BRIEF, STUDIO_BRIEF


def sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


# Per-session last-seen [[stage:...]] tag. The agent emits these at the END of an assistant turn
# (see STUDIO_BRIEF). In Auto mode the server uses this to pick the model for the NEXT turn.
# Keyed by OpenCode session id. Capped so a long-running studio doesn't leak memory.
LAST_STAGE_BY_SESSION: dict[str, str] = {}
_LAST_STAGE_MAX = 256
_STAGE_TAG_RE = re.compile(r"\[\[stage:(\w+)\]\]", re.IGNORECASE)


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
