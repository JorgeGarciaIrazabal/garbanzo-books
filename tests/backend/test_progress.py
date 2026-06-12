"""Tests for ``scripts/lib/progress.py`` — the live-progress side-channel.

The contract: ``report()`` atomically publishes a JSON payload the server can poll,
``finish()`` removes it, and BOTH are strictly best-effort (a broken progress channel
must never break the real work).
"""
from __future__ import annotations

import json
import time

from lib import progress


def test_report_writes_readable_payload(tmp_path, monkeypatch):
    pf = tmp_path / ".studio-progress.json"
    monkeypatch.setattr(progress, "PROGRESS_FILE", pf)
    before = time.time()
    progress.report("illustrating", 3, 16, "page 03")
    data = json.loads(pf.read_text())
    assert data["task"] == "illustrating"
    assert (data["done"], data["total"]) == (3, 16)
    assert data["detail"] == "page 03"
    assert data["ts"] >= before


def test_report_overwrites_previous_payload(tmp_path, monkeypatch):
    pf = tmp_path / ".studio-progress.json"
    monkeypatch.setattr(progress, "PROGRESS_FILE", pf)
    progress.report("illustrating", 1, 16)
    progress.report("illustrating", 2, 16)
    assert json.loads(pf.read_text())["done"] == 2
    # No leftover temp files from the atomic-rename dance.
    assert [p.name for p in tmp_path.iterdir()] == [".studio-progress.json"]


def test_finish_removes_file_and_is_idempotent(tmp_path, monkeypatch):
    pf = tmp_path / ".studio-progress.json"
    monkeypatch.setattr(progress, "PROGRESS_FILE", pf)
    progress.report("illustrating", 16, 16)
    progress.finish()
    assert not pf.exists()
    progress.finish()  # second call must not raise


def test_report_never_raises_even_when_unwritable(tmp_path, monkeypatch):
    """Best-effort contract: pointing the channel somewhere impossible must not blow up
    the calling script."""
    monkeypatch.setattr(progress, "PROGRESS_FILE",
                        tmp_path / "no-such-dir" / "deep" / "p.json")
    progress.report("illustrating", 1, 2)  # must not raise
    progress.finish()  # must not raise
