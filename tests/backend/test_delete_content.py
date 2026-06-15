"""Tests for ``scripts/delete_content.py`` — the destructive story/world delete.

The contract under test:
  * deleting a story removes only that story's dir; the world and siblings survive
  * deleting a world removes the whole world dir (characters + stories included)
  * a bad / unresolvable target deletes nothing and exits 2
  * the interactive prompt aborts (exit 1, nothing deleted) unless --yes is given
"""
from __future__ import annotations

import sys

import delete_content


def _run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["delete_content.py", *argv])
    return delete_content.main()


def _patch_worlds(workspace, monkeypatch):
    # delete_content does `from lib.model import WORLDS`, so it holds its own rebinding.
    monkeypatch.setattr(delete_content, "WORLDS", workspace.worlds)


def test_delete_story_removes_only_that_story(workspace, factories, write_world, monkeypatch):
    _patch_worlds(workspace, monkeypatch)
    _, wdir = write_world(slug="ww", stories=[factories.story(slug="s1", world="ww"),
                                              factories.story(slug="s2", world="ww")])
    assert _run(monkeypatch, "ww/s1", "--yes") == 0
    assert not (wdir / "stories" / "s1").exists()
    assert (wdir / "stories" / "s2" / "story.yaml").exists()  # sibling untouched
    assert (wdir / "world.yaml").exists()                      # world untouched


def test_delete_world_removes_everything(workspace, factories, write_world, monkeypatch):
    _patch_worlds(workspace, monkeypatch)
    _, wdir = write_world(slug="ww", characters=[factories.character(slug="hero", world="ww")],
                          stories=[factories.story(slug="s1", world="ww")])
    assert _run(monkeypatch, "ww", "--yes") == 0
    assert not wdir.exists()


def test_bad_target_deletes_nothing(workspace, factories, write_world, monkeypatch):
    _patch_worlds(workspace, monkeypatch)
    _, wdir = write_world(slug="ww", stories=[factories.story(slug="s1", world="ww")])
    assert _run(monkeypatch, "ww/nope", "--yes") == 2
    assert _run(monkeypatch, "ghost-world", "--yes") == 2
    assert (wdir / "stories" / "s1" / "story.yaml").exists()


def test_prompt_aborts_without_yes(workspace, factories, write_world, monkeypatch):
    _patch_worlds(workspace, monkeypatch)
    _, wdir = write_world(slug="ww", stories=[factories.story(slug="s1", world="ww")])
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    assert _run(monkeypatch, "ww/s1") == 1
    assert (wdir / "stories" / "s1" / "story.yaml").exists()  # nothing deleted


def test_prompt_confirms_with_y(workspace, factories, write_world, monkeypatch):
    _patch_worlds(workspace, monkeypatch)
    _, wdir = write_world(slug="ww", stories=[factories.story(slug="s1", world="ww")])
    monkeypatch.setattr("builtins.input", lambda *_: "y")
    assert _run(monkeypatch, "ww/s1") == 0
    assert not (wdir / "stories" / "s1").exists()
