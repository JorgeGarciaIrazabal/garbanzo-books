"""Tests for ``scripts/publish_story.py`` — the gate-checked draft↔published flip.

The contract under test:
  * publishing runs the validator FIRST and writes nothing when the gate fails
  * unpublishing (--draft) never runs the gate (taking a book down must always work)
  * the flip is written to disk atomically via dump_yaml
  * idempotent no-ops and bad targets exit with honest codes (0 / 2)

We monkeypatch the imported check functions to make the gate deterministic — the
checkers themselves have their own test suites.
"""
from __future__ import annotations

import sys

import publish_story
from lib.model import load_yaml


def _run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["publish_story.py", *argv])
    return publish_story.main()


def _write(write_world, factories, status="draft"):
    story = factories.story(slug="s1", world="ww", status=status)
    slug, wdir = write_world(slug="ww", characters=[factories.character(slug="hero", world="ww")],
                             stories=[story])
    return wdir / "stories" / "s1" / "story.yaml"


def _silence_gate(monkeypatch):
    monkeypatch.setattr(publish_story, "check_world", lambda rep, world: None)
    monkeypatch.setattr(publish_story, "check_story", lambda rep, world, story: None)


def test_publish_flips_status_when_gate_passes(workspace, factories, write_world, monkeypatch, capsys):
    sy = _write(write_world, factories, status="draft")
    _silence_gate(monkeypatch)
    assert _run(monkeypatch, "ww/s1") == 0
    assert load_yaml(sy)["status"] == "published"
    assert "draft → published" in capsys.readouterr().out


def test_publish_blocked_by_validator_failure_writes_nothing(workspace, factories, write_world,
                                                             monkeypatch, capsys):
    """A failing gate must leave the file EXACTLY as it was — draft on disk, exit 1,
    and the failure printed so the UI can show the author what to fix."""
    sy = _write(write_world, factories, status="draft")
    monkeypatch.setattr(publish_story, "check_world", lambda rep, world: None)
    monkeypatch.setattr(publish_story, "check_story",
                        lambda rep, world, story: rep.fail("ww/s1: page 3 not illustrated"))
    assert _run(monkeypatch, "ww/s1") == 1
    assert load_yaml(sy)["status"] == "draft"
    out = capsys.readouterr().out
    assert "NOT published" in out
    assert "page 3 not illustrated" in out


def test_unpublish_never_runs_the_gate(workspace, factories, write_world, monkeypatch, capsys):
    """Taking a story down must always work — even when the book currently fails
    validation (that can be exactly WHY you're unpublishing it)."""
    sy = _write(write_world, factories, status="published")

    def boom(*a, **kw):  # pragma: no cover - the assertion is that this never runs
        raise AssertionError("the gate must not run for --draft")

    monkeypatch.setattr(publish_story, "check_world", boom)
    monkeypatch.setattr(publish_story, "check_story", boom)
    assert _run(monkeypatch, "ww/s1", "--draft") == 0
    assert load_yaml(sy)["status"] == "draft"


def test_same_status_is_a_quiet_no_op(workspace, factories, write_world, monkeypatch, capsys):
    _write(write_world, factories, status="draft")
    _silence_gate(monkeypatch)
    assert _run(monkeypatch, "ww/s1", "--draft") == 0
    assert "already draft" in capsys.readouterr().out


def test_accepts_full_paths_as_target(workspace, factories, write_world, monkeypatch):
    sy = _write(write_world, factories, status="draft")
    _silence_gate(monkeypatch)
    assert _run(monkeypatch, "worlds/ww/stories/s1") == 0
    assert load_yaml(sy)["status"] == "published"


def test_unknown_world_or_story_exits_2(workspace, factories, write_world, monkeypatch, capsys):
    _write(write_world, factories)
    assert _run(monkeypatch, "nope/s1") == 2
    assert _run(monkeypatch, "ww/nope") == 2
    assert _run(monkeypatch, "just-one-part") == 2
