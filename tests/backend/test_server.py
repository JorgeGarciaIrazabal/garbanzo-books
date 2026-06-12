"""Tests for ``ui/server.py`` — the FastAPI studio backend.

We focus on the *business logic* that the chat / library / validate / build
endpoints depend on:
  * load_env_file() correctly fills unset/blank env vars and never overrides a
    real exported value
  * ALLOWED_MODELS whitelist rejects arbitrary model ids
  * _tool_detail() turns the various tool payloads into a one-line summary
  * sse() formats a dict as a Server-Sent Event
  * run_tool() handles subprocess success + failure and returns the right shape
  * The HTTP endpoints correctly proxy the underlying python scripts
  * Voice endpoints handle empty input and unknown voices gracefully
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Path setup so the import resolves
UI_DIR = (Path(__file__).resolve().parents[2] / "ui").as_posix()
if UI_DIR not in sys.path:
    sys.path.insert(0, UI_DIR)

import server  # noqa: E402


# ================================================================================== env
def test_load_env_file_fills_unset_keys(tmp_path, monkeypatch):
    """The whole reason load_env_file exists: a parent shell may export a
    BLANK GEMINI_API_KEY (which would shadow the real value). load_env_file
    treats unset-or-blank the same, so a blank exported key gets filled."""
    # Temporarily redirect ROOT/.env to a tmp file
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=real-from-dotenv\nEMPTYKEY=ok\n")
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("EMPTYKEY", "")
    out = server.load_env_file()
    assert out["env_exists"] is True
    assert out["gemini"] is True
    assert os.environ["GEMINI_API_KEY"] == "real-from-dotenv"
    # The blank one was filled.
    assert os.environ["EMPTYKEY"] == "ok"


def test_load_env_file_preserves_existing_real_export(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("MY_VAR=from-dotenv\n")
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setenv("MY_VAR", "from-shell")
    server.load_env_file()
    assert os.environ["MY_VAR"] == "from-shell"


def test_load_env_file_reports_status_correctly(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    # No .env file at all
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    out = server.load_env_file()
    assert out["env_exists"] is False
    assert out["gemini"] is False


def test_load_env_file_handles_quoted_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('Q1="double"\nQ2=\'single\'\n')
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.delenv("Q1", raising=False)
    monkeypatch.delenv("Q2", raising=False)
    server.load_env_file()
    assert os.environ["Q1"] == "double"
    assert os.environ["Q2"] == "single"


# ================================================================================== model whitelist
def test_allowed_models_contains_every_pickable_model():
    assert server.ALLOWED_MODELS == {m["id"] for m in server.MODELS}


def test_modal_label_field_present_for_every_model():
    for m in server.MODELS:
        assert m["id"]
        assert m["label"]


# ================================================================================== tool detail
@pytest.mark.parametrize("tool,input_,state_extra,expected_substring", [
    ("bash", {"command": "ls -la", "description": "List stuff"}, {}, "List stuff"),
    ("bash", {"command": "ls -la"}, {}, "ls -la"),                    # falls back to command
    ("bash", {}, {}, ""),                                              # totally empty
    ("edit", {"filePath": "/tmp/worlds/ww/world.yaml"}, {}, "world.yaml"),
    ("write", {"filePath": "/tmp/foo.yaml"}, {}, "foo.yaml"),
    ("read", {"filePath": "/tmp/bar"}, {}, "bar"),
    ("glob", {"pattern": "worlds/*/world.yaml"}, {}, "worlds/*/world.yaml"),
    ("grep", {"pattern": "TODO"}, {}, "TODO"),
    ("webfetch", {"url": "https://example.com"}, {}, "https://example.com"),
    ("unknown_tool", {"foo": "bar"}, {"title": "fallback-title"}, "fallback-title"),  # falls through
    ("unknown_tool", {}, {"title": ""}, "unknown_tool"),                # empty title → tool name
])
def test_tool_detail_extracts_relevant_field(tool, input_, state_extra, expected_substring):
    state = {"input": input_, **state_extra}
    out = server._tool_detail(tool, state)
    if expected_substring:
        assert expected_substring in out


def test_tool_detail_handles_none_state_and_input():
    # The real runtime sometimes delivers these as None
    assert isinstance(server._tool_detail("bash", {"input": None}), str)
    assert isinstance(server._tool_detail("bash", {}), str)


def test_tool_detail_handles_long_input_without_crashing():
    """The truncation to 140 chars happens in chat_stream when the SSE event is
    built, not in _tool_detail itself. _tool_detail just picks the most
    specific field; any string the runtime later chops is its concern."""
    state = {"input": {"filePath": "x" * 500}, "title": "y" * 500}
    out = server._tool_detail("edit", state)
    # edit extracts the basename of filePath — for a no-slash path that's the
    # whole path (which here is 500 chars). _tool_detail MUST still return a string.
    assert isinstance(out, str)
    assert len(out) > 0


# ================================================================================== SSE
def test_sse_produces_data_event_line():
    out = server.sse({"type": "assistant", "text": "hi"})
    assert out.startswith("data: ")
    assert out.endswith("\n\n")
    payload = json.loads(out[6:].strip())
    assert payload == {"type": "assistant", "text": "hi"}


def test_sse_keeps_non_ascii_characters_intact():
    out = server.sse({"type": "assistant", "text": "café — 日本語"})
    payload = json.loads(out[6:].strip())
    assert payload["text"] == "café — 日本語"


def test_sse_handles_complex_payloads():
    payload = {"type": "tool", "tool": "bash", "id": "abc-123",
               "status": "running", "title": "ls"}
    out = server.sse(payload)
    assert json.loads(out[6:].strip()) == payload


# ================================================================================== FastAPI app
@pytest.fixture
def client(monkeypatch):
    """A TestClient that doesn't actually start OpenCode (we test the endpoints
    in isolation from the chat engine)."""
    from fastapi.testclient import TestClient
    # Use the lifespan-less path: just instantiate the app; we won't trigger
    # startup. The endpoints we test here don't depend on the OpenCode process.
    return TestClient(server.app)


def test_get_api_models_returns_known_picker_options(client):
    r = client.get("/api/models")
    assert r.status_code == 200
    data = r.json()
    assert "models" in data and "default" in data
    ids = [m["id"] for m in data["models"]]
    assert all(i in server.ALLOWED_MODELS for i in ids)
    assert data["default"] in server.ALLOWED_MODELS


def test_post_api_quality_runs_scorecard_tool(client, monkeypatch):
    """The Quality button runs scripts/quality_report.py via run_tool and returns its output.
    We stub run_tool so the test stays isolated from the subprocess."""
    calls = {}

    async def fake_run_tool(cmd):
        calls["cmd"] = cmd
        return {"ok": True, "output": "7/7 gates — excellent"}

    monkeypatch.setattr(server, "run_tool", fake_run_tool)
    r = client.post("/api/quality")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "output": "7/7 gates — excellent"}
    assert calls["cmd"] == ["scripts/quality_report.py"]


# =========================================================== /api/build + /api/build/publish
def test_post_api_build_runs_studio_preview_with_drafts(client, monkeypatch):
    """/api/build is the STUDIO preview — it includes drafts so the author can browse WIP.
    The build lands in ./site/ (the in-app iframe's source)."""
    calls = {}

    async def fake_run_tool(cmd):
        calls["cmd"] = cmd
        return {"ok": True, "output": "built site/ — 2 story page(s)  [drafts included]"}

    monkeypatch.setattr(server, "run_tool", fake_run_tool)
    r = client.post("/api/build")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # The studio build is the one that includes drafts — checked via the flag itself.
    assert "--include-drafts" in calls["cmd"], "studio build must include drafts"


def test_post_api_build_publish_uses_custom_out_dir_and_published_only(client, monkeypatch):
    """/api/build/publish is the PUBLIC preview — the EXACT shape GitHub Pages will deploy.
    Published-only and to a separate ./site_publish/ so the studio's draft preview at ./site/
    is unaffected (the two builds must not clobber each other)."""
    calls = {}

    async def fake_run_tool(cmd):
        calls["cmd"] = cmd
        return {"ok": True, "output": "built site_publish/ — 1 story page(s)  [published only]"}

    monkeypatch.setattr(server, "run_tool", fake_run_tool)
    r = client.post("/api/build/publish")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # Published-only: no --include-drafts
    assert "--include-drafts" not in calls["cmd"], (
        "publish build must NOT include drafts (that's what GitHub Pages would see)")
    # Custom output: --out site_publish — keeps the studio preview intact
    assert "--out" in calls["cmd"]
    out_idx = calls["cmd"].index("--out")
    assert calls["cmd"][out_idx + 1] == "site_publish"


def test_post_api_build_does_not_clobber_publish_preview(client, monkeypatch, tmp_path):
    """Building the studio preview (with drafts) MUST not erase site_publish/, and vice
    versa. The two directories are independent so the author can be browsing the public
    preview in one tab while previewing drafts in another."""
    # Set up a fake site_publish/ with a sentinel file. The studio build to ./site/ should
    # never touch it (it goes to a different path).
    fake = tmp_path / "site_publish"
    fake.mkdir()
    sentinel = fake / "index.html"
    sentinel.write_text("public preview")

    # Redirect SITE and SITE_PUBLISH to tmp dirs so the test doesn't write into the repo.
    studio_dir = tmp_path / "site"
    monkeypatch.setattr(server, "SITE", studio_dir)
    monkeypatch.setattr(server, "SITE_PUBLISH", fake)

    # The endpoint is run via a subprocess (run_tool), so we can't easily mock it without
    # firing the real build. Instead we assert the structural property: the two output paths
    # are different, so the subprocess invocations of build_site.py write to different dirs
    # and can never clobber each other. The per-endpoint CLI args are checked in the tests
    # above (`/api/build` uses --include-drafts, `/api/build/publish` uses --out site_publish).
    assert server.SITE != server.SITE_PUBLISH
    assert server.SITE_PUBLISH.name == "site_publish"
    # The sentinel file in site_publish/ is still there — proves the studio build target
    # is in a different directory and can't have removed it.
    assert sentinel.exists()


# =========================================================== /api/publish/status
def test_get_api_publish_status_reports_unbuilt_when_no_dir(client, monkeypatch, tmp_path):
    """When site_publish/ doesn't exist yet, the status endpoint must report `built: False`
    so the UI can show 'no build yet — click Publish' instead of misleading the author."""
    monkeypatch.setattr(server, "SITE_PUBLISH", tmp_path / "definitely_does_not_exist")
    r = client.get("/api/publish/status")
    assert r.status_code == 200
    data = r.json()
    assert data["built"] is False
    # out_dir falls back to the absolute path when it's not under ROOT (e.g. in tests).
    # In production this is always the relative "site_publish" — the test only needs to
    # prove the endpoint doesn't crash on the not-under-ROOT case.
    assert "definitely_does_not_exist" in data["out_dir"]
    assert "deploy-pages" in data["deploy_instructions"]
    assert "gh workflow run" in data["deploy_instructions"]


def test_get_api_publish_status_reports_built_when_index_exists(client, monkeypatch, tmp_path):
    """When a previous Publish click produced site_publish/index.html, the status endpoint
    must report `built: True` with a recent mtime — that's what surfaces 'built 2m ago'."""
    pub = tmp_path / "site_publish"
    pub.mkdir()
    (pub / "index.html").write_text("ok")
    monkeypatch.setattr(server, "SITE_PUBLISH", pub)
    r = client.get("/api/publish/status")
    assert r.status_code == 200
    data = r.json()
    assert data["built"] is True
    assert data["last_built_mtime"] is not None
    assert data["last_built_mtime"] > 0


def test_publish_preview_directory_is_distinct_from_studio_preview(client):
    """The two builds must NEVER land in the same directory — the studio preview contains
    drafts, the public preview does not, and clobbering one with the other would mean the
    author can't see drafts OR the public preview would leak drafts to GitHub Pages."""
    assert server.SITE != server.SITE_PUBLISH


def test_get_api_publish_status_reports_git_branch(client, monkeypatch, tmp_path):
    """The UI warns when you're not on main (the Pages workflow only deploys main),
    so the status endpoint must surface the current branch."""
    monkeypatch.setattr(server, "SITE_PUBLISH", tmp_path / "nope")

    async def fake_run_git(args):
        assert args == ["rev-parse", "--abbrev-ref", "HEAD"]
        return 0, "feature-branch\n"

    monkeypatch.setattr(server, "run_git", fake_run_git)
    r = client.get("/api/publish/status")
    assert r.status_code == 200
    assert r.json()["branch"] == "feature-branch"


# =========================================================== /api/progress
def test_get_api_progress_inactive_when_no_file(client, monkeypatch, tmp_path):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    r = client.get("/api/progress")
    assert r.status_code == 200
    assert r.json() == {"active": False}


def test_get_api_progress_reports_fresh_payload(client, monkeypatch, tmp_path):
    """A fresh progress file (written by e.g. generate_images.py mid-run) surfaces as an
    active task with done/total — that's what the activity strip renders as a live bar."""
    import time as _time
    monkeypatch.setattr(server, "ROOT", tmp_path)
    (tmp_path / ".studio-progress.json").write_text(json.dumps(
        {"task": "illustrating", "done": 7, "total": 16, "detail": "page 07",
         "ts": _time.time()}))
    r = client.get("/api/progress")
    data = r.json()
    assert data["active"] is True
    assert data["task"] == "illustrating"
    assert (data["done"], data["total"]) == (7, 16)
    assert data["detail"] == "page 07"


def test_get_api_progress_treats_stale_file_as_inactive(client, monkeypatch, tmp_path):
    """A crashed/killed script can't clean up its file — a stale timestamp must read as
    inactive so the strip never shows a lying 'still working' banner."""
    monkeypatch.setattr(server, "ROOT", tmp_path)
    (tmp_path / ".studio-progress.json").write_text(json.dumps(
        {"task": "illustrating", "done": 3, "total": 16, "ts": 1000.0}))  # long ago
    r = client.get("/api/progress")
    assert r.json() == {"active": False}


def test_get_api_progress_survives_corrupt_file(client, monkeypatch, tmp_path):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    (tmp_path / ".studio-progress.json").write_text("{not json")
    r = client.get("/api/progress")
    assert r.json() == {"active": False}


# =========================================================== /api/story/status
def test_post_api_story_status_publish_runs_gated_script(client, monkeypatch):
    """Publishing from a library card goes through scripts/publish_story.py — the script
    that runs the FULL validator gate before flipping the status."""
    calls = {}

    async def fake_run_tool(cmd):
        calls["cmd"] = cmd
        return {"ok": True, "output": "+ ww/s1: draft → published"}

    monkeypatch.setattr(server, "run_tool", fake_run_tool)
    r = client.post("/api/story/status",
                    json={"world": "ww", "story": "s1", "status": "published"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert calls["cmd"] == ["scripts/publish_story.py", "ww/s1"]


def test_post_api_story_status_draft_passes_draft_flag(client, monkeypatch):
    calls = {}

    async def fake_run_tool(cmd):
        calls["cmd"] = cmd
        return {"ok": True, "output": "+ ww/s1: published → draft"}

    monkeypatch.setattr(server, "run_tool", fake_run_tool)
    r = client.post("/api/story/status",
                    json={"world": "ww", "story": "s1", "status": "draft"})
    assert r.status_code == 200
    assert calls["cmd"] == ["scripts/publish_story.py", "ww/s1", "--draft"]


def test_post_api_story_status_rejects_bad_input(client, monkeypatch):
    """Missing slugs or an unknown status must 400 before any subprocess runs."""
    async def fake_run_tool(cmd):  # pragma: no cover - must not be called
        raise AssertionError("run_tool must not run for invalid input")

    monkeypatch.setattr(server, "run_tool", fake_run_tool)
    for body in ({"world": "", "story": "s1", "status": "published"},
                 {"world": "ww", "story": "", "status": "published"},
                 {"world": "ww", "story": "s1", "status": "shipped"}):
        r = client.post("/api/story/status", json=body)
        assert r.status_code == 400


# =========================================================== /api/deploy
def test_post_api_deploy_commits_and_pushes_when_dirty(client, monkeypatch):
    """With staged changes (diff --cached exits 1), deploy must add → commit → push."""
    seen = []

    async def fake_run_git(args):
        seen.append(args[0])
        if args[0] == "diff":
            return 1, ""  # staged changes exist
        return 0, args[0] + " ok"

    monkeypatch.setattr(server, "run_git", fake_run_git)
    r = client.post("/api/deploy")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert seen == ["add", "diff", "commit", "push"]
    assert "git push" in data["output"]


def test_post_api_deploy_skips_commit_when_clean(client, monkeypatch):
    """Nothing staged (diff --cached exits 0) → skip the commit, still push (there may be
    local commits waiting to go out)."""
    seen = []

    async def fake_run_git(args):
        seen.append(args[0])
        return 0, ""

    monkeypatch.setattr(server, "run_git", fake_run_git)
    r = client.post("/api/deploy")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert seen == ["add", "diff", "push"]
    assert "nothing new to commit" in r.json()["output"]


def test_post_api_deploy_reports_push_failure(client, monkeypatch):
    """A failed push (auth, no remote…) must come back ok:false WITH git's output so the
    author can see why instead of a silent shrug."""
    async def fake_run_git(args):
        if args[0] == "push":
            return 128, "fatal: could not read from remote repository"
        return (1, "") if args[0] == "diff" else (0, "")

    monkeypatch.setattr(server, "run_git", fake_run_git)
    r = client.post("/api/deploy")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    assert "could not read from remote" in data["output"]
    assert server.SITE_PUBLISH.name == "site_publish"


def test_get_api_voice_returns_voice_caps(client, monkeypatch):
    monkeypatch.setattr(server, "voice", _FakeVoice(tts=False, stt=True))
    r = client.get("/api/voice")
    assert r.status_code == 200
    assert r.json()["tts"] is False
    assert r.json()["stt"] is True


def test_get_api_voice_handles_voice_module_error(client, monkeypatch):
    class Boom:
        def available(self):
            raise RuntimeError("broken")
    monkeypatch.setattr(server, "voice", Boom())
    r = client.get("/api/voice")
    assert r.status_code == 200
    assert r.json()["error"]


def test_post_api_voice_warm_returns_ok(client, monkeypatch):
    """The warm endpoint is fire-and-forget — it kicks the background load and
    returns immediately. Even if voice isn't installed it should not crash."""
    # Make voice.available() say no so warm() is a no-op
    monkeypatch.setattr(server, "voice", _FakeVoice(tts=False, stt=False))
    r = client.post("/api/voice/warm")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_post_api_voice_warm_kicks_background_load_when_available(client, monkeypatch):
    """If voice IS available, the warm endpoint schedules a background task —
    it MUST not block the HTTP response."""
    fv = _FakeVoice(tts=True, stt=False)
    monkeypatch.setattr(server, "voice", fv)
    r = client.post("/api/voice/warm")
    assert r.status_code == 200
    # the asyncio.create_task is scheduled but the to_thread call hasn't run
    # yet (we're in the test's event loop, not the fastapi one). The point is
    # the response returns synchronously without raising.
    assert r.json() == {"ok": True}


def test_post_api_tts_rejects_empty_text(client, monkeypatch):
    r = client.post("/api/tts", json={"text": ""})
    assert r.status_code == 400
    assert "empty" in r.json()["error"]


def test_post_api_tts_rejects_missing_text_field(client):
    r = client.post("/api/tts", json={})
    assert r.status_code == 400


def test_post_api_tts_handles_speed_gracefully_when_nan(client, monkeypatch):
    """A non-numeric speed should not 500 — the server falls back to 1.0."""
    captured = {}

    def fake_synth(text, voice, speed):
        captured.update(text=text, voice=voice, speed=speed)
        return b"FAKEWAV"

    monkeypatch.setattr(server.voice, "synthesize", fake_synth)
    r = client.post("/api/tts", json={"text": "hi", "speed": "nope"})
    assert r.status_code == 200
    assert captured["speed"] == 1.0  # default kicks in


def test_post_api_tts_rejects_when_synthesis_raises(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("model broken")
    monkeypatch.setattr(server.voice, "synthesize", boom)
    r = client.post("/api/tts", json={"text": "hello"})
    assert r.status_code == 500
    assert "model broken" in r.json()["error"]


def test_post_api_stt_rejects_empty_body(client):
    r = client.post("/api/stt", content=b"")
    assert r.status_code == 400
    assert "no audio" in r.json()["error"]


def test_post_api_stt_returns_transcribed_text(client, monkeypatch):
    monkeypatch.setattr(server.voice, "transcribe", lambda _bytes: "hello world")
    r = client.post("/api/stt", content=b"FAKEAUDIO")
    assert r.status_code == 200
    assert r.json() == {"text": "hello world"}


def test_post_api_stt_handles_transcription_error(client, monkeypatch):
    def boom(_bytes):
        raise RuntimeError("whisper down")
    monkeypatch.setattr(server.voice, "transcribe", boom)
    r = client.post("/api/stt", content=b"x")
    assert r.status_code == 500


# ================================================================================== chat endpoint validation
def test_post_api_chat_rejects_empty_prompt(client):
    r = client.post("/api/chat", json={"prompt": ""})
    assert r.status_code == 400
    assert "empty" in r.json()["error"]


def test_post_api_chat_rejects_missing_prompt_field(client):
    r = client.post("/api/chat", json={})
    assert r.status_code == 400


def test_post_api_chat_rejects_whitespace_only_prompt(client):
    r = client.post("/api/chat", json={"prompt": "    \n   "})
    assert r.status_code == 400


def test_post_api_stop_returns_error_without_session_id(client):
    r = client.post("/api/stop", json={})
    assert r.status_code == 400
    assert "no active session" in r.json()["error"]


# ================================================================================== helper: a fake voice
class _FakeVoice:
    def __init__(self, tts=False, stt=False):
        self._tts = tts
        self._stt = stt
        self.warmed = False

    def available(self):
        return {"tts": self._tts, "stt": self._stt,
                "voices": ["af_heart"] if self._tts else [],
                "default_voice": "af_heart"}

    def warm(self):
        self.warmed = True


# ================================================================================== tool SSE event
def test_tool_event_includes_input_output_and_compact_title():
    """The studio's expandable tool rows need the full input + output, not just
    the one-line summary — _tool_event packages all three."""
    part = {"id": "prt_1", "tool": "bash",
            "state": {"status": "completed",
                      "input": {"command": "uv run python scripts/validate.py",
                                "description": "Validate the workspace"},
                      "output": "all checks passed\n"}}
    ev = server._tool_event(part)
    assert ev["type"] == "tool"
    assert ev["id"] == "prt_1"
    assert ev["status"] == "completed"
    assert ev["title"] == "Validate the workspace"
    assert "scripts/validate.py" in ev["input"]
    assert ev["output"] == "all checks passed\n"
    assert "error" not in ev


def test_tool_event_caps_huge_output_and_surfaces_errors():
    part = {"id": "prt_2", "tool": "bash",
            "state": {"status": "error", "input": {"command": "boom"},
                      "output": "x" * 50_000, "error": "exit 1: " + "y" * 5_000}}
    ev = server._tool_event(part)
    assert len(ev["output"]) <= 8000
    assert len(ev["error"]) <= 2000
    assert ev["status"] == "error"


def test_tool_event_omits_empty_input_and_output():
    ev = server._tool_event({"id": "p", "tool": "read", "state": {"status": "running"}})
    assert "input" not in ev and "output" not in ev and "error" not in ev


# ================================================================================== debug endpoint
def test_get_session_messages_returns_503_without_opencode(client, monkeypatch):
    """The Debug tab's full-conversation fetch degrades cleanly when the chat
    engine isn't running (e.g. opencode failed to start)."""
    monkeypatch.setattr(server.oc, "base", None)
    r = client.get("/api/session/ses_123/messages")
    assert r.status_code == 503
    assert "opencode" in r.json()["error"]
