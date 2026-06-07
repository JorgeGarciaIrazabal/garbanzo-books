"""Tests for ``scripts/library.py`` — the workspace → JSON exporter the UI eats.

This script's job is purely a *contract*: produce a JSON document the frontend
can render. We test the shape (every key the UI relies on), how palette hex
values get the `#` prefix, that character `has_reference` flips on when the
character lists any reference image, that stages are listed, and that errors
from malformed files propagate (and don't fatal-fail the export).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _run_library(workspace_root):
    """Invoke library.py as a subprocess against an isolated workspace.

    library.py uses module-level constants (ROOT/WORLDS) determined at import
    time, so we re-invoke it via subprocess with cwd set, plus we point WORLDS
    via a PYTHONPATH override that includes a tiny shim. Simpler: subprocess
    the script with cwd=workspace_root so its relative scripts/lib import works.
    """
    # The library script needs to find scripts/lib on sys.path. We give it the
    # REAL scripts/ via PYTHONPATH but a fake cwd by importing a copy.
    # Simpler approach: write a runner that monkey-patches ROOT/WORLDS.
    runner = workspace_root / "_run_library.py"
    runner.write_text(f"""
import sys
sys.path.insert(0, {str(REPO / 'scripts')!r})
import lib.model as m
from pathlib import Path
m.ROOT = Path({str(workspace_root)!r})
m.WORLDS = Path({str(workspace_root / 'worlds')!r})
import runpy
runpy.run_path({str(REPO / 'scripts' / 'library.py')!r}, run_name='__main__')
""")
    r = subprocess.run([sys.executable, str(runner)], capture_output=True, text=True)
    return r


def test_library_emits_empty_worlds_array_when_no_content(workspace):
    r = _run_library(workspace.root)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data == {"worlds": [], "errors": []}


def test_library_lists_world_with_required_fields(workspace, write_world, factories):
    write_world(slug="ww", characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    r = _run_library(workspace.root)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert len(data["worlds"]) == 1
    w = data["worlds"][0]
    # The UI relies on EVERY one of these keys — guard them.
    for k in ("slug", "title", "tagline", "premise", "age_bands", "themes",
              "palette", "characters", "stories"):
        assert k in w, f"library output missing {k}"


def test_library_palette_hex_is_hash_prefixed(workspace, write_world, factories):
    """The palette swatches must arrive with a leading `#` (the schema allows
    both forms; the UI assumes one)."""
    # Mix of #-prefixed and bare hex in source
    custom_palette = [
        {"name": "a", "hex": "#aabbcc", "role": "x"},
        {"name": "b", "hex": "ddeeff", "role": "y"},
    ]
    w = factories.world()
    w["art_style"]["palette"] = custom_palette
    del w["slug"]  # write_world re-sets it
    write_world(slug="ww", world_overrides=w)
    r = _run_library(workspace.root)
    data = json.loads(r.stdout)
    hexes = [s["hex"] for s in data["worlds"][0]["palette"]]
    assert all(h.startswith("#") for h in hexes), hexes


def test_library_character_has_reference_flips_true_when_refs_present(workspace, write_world,
                                                                       factories):
    c1 = factories.character(slug="a", world="ww", reference_images=[])
    c2 = factories.character(slug="b", world="ww",
                             reference_images=["characters/b.refs/sheet.png"])
    write_world(slug="ww", characters=[c1, c2])
    r = _run_library(workspace.root)
    data = json.loads(r.stdout)
    by_slug = {c["slug"]: c for c in data["worlds"][0]["characters"]}
    assert by_slug["a"]["has_reference"] is False
    assert by_slug["b"]["has_reference"] is True


def test_library_character_stages_lists_evolution_stage_ids(workspace, write_world, factories):
    c = factories.character(slug="hero", world="ww")
    # factory already gives ['base', 'brave']
    write_world(slug="ww", characters=[c])
    r = _run_library(workspace.root)
    data = json.loads(r.stdout)
    char = data["worlds"][0]["characters"][0]
    assert char["stages"] == ["base", "brave"]


def test_library_story_counts_interaction_pages(workspace, write_world, factories):
    pages = [
        {"number": 0, "kind": "title", "text": "T", "image": {"prompt": "x"}},
        {"number": 1, "kind": "story", "text": "go", "image": {"prompt": "x"},
         "interaction": {"type": "seek-and-find", "prompt": "go",
                         "data": {"items": ["a"]}}},
        {"number": 2, "kind": "story", "text": "go", "image": {"prompt": "x"}},
        {"number": 3, "kind": "story", "text": "go", "image": {"prompt": "x"},
         "interaction": {"type": "rhyme-complete", "prompt": "go",
                         "data": {"answer": "x"}}},
    ]
    write_world(slug="ww", characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww", pages=pages)])
    r = _run_library(workspace.root)
    data = json.loads(r.stdout)
    story = data["worlds"][0]["stories"][0]
    assert story["pages"] == 4
    assert story["interactions"] == 2


def test_library_propagates_malformed_file_errors(workspace, write_world, factories):
    slug, wdir = write_world(slug="ww",
                              characters=[factories.character(slug="ok", world="ww")])
    (wdir / "characters" / "broken.yaml").write_text("a: [oops")
    r = _run_library(workspace.root)
    assert r.returncode == 0  # NOT fatal — the rest of the library must still load
    data = json.loads(r.stdout)
    assert len(data["worlds"]) == 1
    assert any("broken.yaml" in e for e in data["errors"])
    # Bad file did NOT poison the good characters
    assert [c["slug"] for c in data["worlds"][0]["characters"]] == ["ok"]


def test_library_status_field_defaults_to_draft(workspace, write_world, factories):
    write_world(slug="ww", characters=[factories.character(slug="hero", world="ww")],
                stories=[factories.story(slug="s1", world="ww")])
    r = _run_library(workspace.root)
    data = json.loads(r.stdout)
    assert data["worlds"][0]["stories"][0]["status"] == "draft"
