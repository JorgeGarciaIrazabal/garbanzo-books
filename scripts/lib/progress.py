"""Live progress side-channel for long-running scripts.

The studio runs scripts inside the agent's bash tool, whose stdout only reaches the UI
when the command FINISHES — so a multi-minute job (illustrating 16 pages) looks frozen
the whole time. Any script can instead call ``report()`` after each unit of work; it
atomically writes ``ROOT/.studio-progress.json`` and the studio's activity strip polls
``GET /api/progress`` while the agent is busy, turning the dead air into
"🎨 illustrate 7/16 — page 07".

Strictly best-effort: progress is decoration, so failures here must never break the
actual work (every call swallows its own errors). The file is deleted by ``finish()``
and ignored by the server once stale, so a crashed script can't leave a lying banner.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from .model import ROOT

PROGRESS_FILE = ROOT / ".studio-progress.json"
STALE_AFTER_S = 120  # the server treats older payloads as dead (crashed/killed script)


def report(task: str, done: int, total: int, detail: str = "") -> None:
    """Atomically publish '<task> is at <done>/<total> (<detail>)'. Never raises."""
    try:
        payload = json.dumps({"task": task, "done": int(done), "total": int(total),
                              "detail": detail, "ts": time.time()})
        fd, tmp = tempfile.mkstemp(dir=str(PROGRESS_FILE.parent),
                                   prefix=".progress.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, PROGRESS_FILE)
    except Exception:
        pass


def finish() -> None:
    """Remove the progress file (job done or aborted). Never raises."""
    try:
        PROGRESS_FILE.unlink(missing_ok=True)
    except Exception:
        pass
