"""Tests for the JSON-patch edit scripts: edit_story.py / edit_world.py / edit_character.py.

These guard the agent-safe write path: the studio agent emits small JSON patches
instead of editing YAML text, and the edit scripts must

  * deep-merge the patch and write schema-valid YAML atomically
  * merge story pages by `number` (partial page objects)
  * REJECT a patch whose merged document violates the schema — file unchanged
  * reject malformed JSON loudly — file unchanged
  * treat JSON null as "delete this key"
  * tolerate a markdown code fence around the JSON (local models add them)
"""
from __future__ import annotations

import io
import json

from lib.model import load_yaml, validate_content


def _run(monkeypatch, module, argv, patch=None):
    """Invoke an edit script's main() with argv and an optional JSON patch on stdin."""
    monkeypatch.setattr("sys.argv", argv)
    if patch is not None:
        text = patch if isinstance(patch, str) else json.dumps(patch)
        monkeypatch.setattr("sys.stdin", io.StringIO(text))
    return module.main()


# ============================================================================ edit_story.py meta
def test_meta_merges_top_level_fields(workspace, write_world, factories, monkeypatch):
    import edit_story
    write_world(stories=[factories.story()])
    rc = _run(monkeypatch, edit_story, ["edit_story.py", "testworld/test-story", "meta"],
              {"logline": "New logline.", "spine": {"until_one_day": "A twist!"}})
    assert rc == 0
    data = load_yaml(workspace.worlds / "testworld" / "stories" / "test-story" / "story.yaml")
    assert data["logline"] == "New logline."
    # nested merge: only the patched spine key changed
    assert data["spine"]["until_one_day"] == "A twist!"
    assert data["spine"]["every_day"] == "Hero did the thing."
    validate_content("story", data)


def test_meta_rejects_pages_key_with_hint(workspace, write_world, factories, monkeypatch, capsys):
    import edit_story
    write_world(stories=[factories.story()])
    rc = _run(monkeypatch, edit_story, ["edit_story.py", "testworld/test-story", "meta"],
              {"pages": []})
    assert rc == 1
    assert "pages subcommand" in capsys.readouterr().err


def test_null_deletes_a_key(workspace, write_world, factories, monkeypatch):
    import edit_story
    write_world(stories=[factories.story()])
    rc = _run(monkeypatch, edit_story, ["edit_story.py", "testworld/test-story", "meta"],
              {"moral": None})
    assert rc == 0
    data = load_yaml(workspace.worlds / "testworld" / "stories" / "test-story" / "story.yaml")
    assert "moral" not in data


def test_fenced_json_is_accepted(workspace, write_world, factories, monkeypatch):
    import edit_story
    write_world(stories=[factories.story()])
    rc = _run(monkeypatch, edit_story, ["edit_story.py", "testworld/test-story", "meta"],
              '```json\n{"logline": "Fenced."}\n```')
    assert rc == 0
    data = load_yaml(workspace.worlds / "testworld" / "stories" / "test-story" / "story.yaml")
    assert data["logline"] == "Fenced."


# ============================================================================ edit_story.py pages
def test_pages_merge_by_number_keeps_untouched_fields(workspace, write_world, factories,
                                                      monkeypatch):
    import edit_story
    write_world(stories=[factories.story()])
    rc = _run(monkeypatch, edit_story, ["edit_story.py", "testworld/test-story", "pages"],
              [{"number": 1, "text": "Rewritten page one.",
                "image": {"prompt": "new scene"}}])
    assert rc == 0
    data = load_yaml(workspace.worlds / "testworld" / "stories" / "test-story" / "story.yaml")
    p1 = next(p for p in data["pages"] if p["number"] == 1)
    assert p1["text"] == "Rewritten page one."
    assert p1["image"]["prompt"] == "new scene"
    # untouched siblings of the patched keys survive the merge
    assert p1["image"]["alt"] == "the hero runs"
    assert p1["layout"]["scrim"] is True
    # other pages untouched
    assert next(p for p in data["pages"] if p["number"] == 2)["text"] == "The hero was glad."
    validate_content("story", data)


def test_pages_appends_new_page_and_sorts(workspace, write_world, factories, monkeypatch):
    import edit_story
    write_world(stories=[factories.story()])
    new_page = {"number": 3, "kind": "story", "text": "A brand new page.",
                "image": {"prompt": "a new scene", "alt": "new scene"}}
    rc = _run(monkeypatch, edit_story, ["edit_story.py", "testworld/test-story", "pages"],
              new_page)  # single object is accepted too
    assert rc == 0
    data = load_yaml(workspace.worlds / "testworld" / "stories" / "test-story" / "story.yaml")
    assert [p["number"] for p in data["pages"]] == [0, 1, 2, 3]
    validate_content("story", data)


def test_pages_without_number_is_rejected(workspace, write_world, factories, monkeypatch, capsys):
    import edit_story
    write_world(stories=[factories.story()])
    rc = _run(monkeypatch, edit_story, ["edit_story.py", "testworld/test-story", "pages"],
              [{"text": "no number"}])
    assert rc == 1
    assert "number" in capsys.readouterr().err


# ============================================================================ rejection = no write
def test_schema_violating_patch_changes_nothing(workspace, write_world, factories, monkeypatch,
                                                capsys):
    import edit_story
    write_world(stories=[factories.story()])
    spath = workspace.worlds / "testworld" / "stories" / "test-story" / "story.yaml"
    before = spath.read_text()
    # additionalProperties: false → a typo'd key must be rejected, with its path reported
    rc = _run(monkeypatch, edit_story, ["edit_story.py", "testworld/test-story", "pages"],
              [{"number": 1, "txet": "typo'd key"}])
    assert rc == 1
    err = capsys.readouterr().err
    assert "unchanged" in err and "txet" in err
    assert spath.read_text() == before


def test_malformed_json_changes_nothing(workspace, write_world, factories, monkeypatch, capsys):
    import edit_story
    write_world(stories=[factories.story()])
    spath = workspace.worlds / "testworld" / "stories" / "test-story" / "story.yaml"
    before = spath.read_text()
    rc = _run(monkeypatch, edit_story, ["edit_story.py", "testworld/test-story", "meta"],
              '{"logline": "missing brace"')
    assert rc == 1
    assert "not valid JSON" in capsys.readouterr().err
    assert spath.read_text() == before


def test_missing_story_is_a_target_error(workspace, write_world, monkeypatch, capsys):
    import edit_story
    write_world()
    rc = _run(monkeypatch, edit_story, ["edit_story.py", "testworld/no-such", "meta"],
              {"logline": "x"})
    assert rc == 2
    assert "no story file" in capsys.readouterr().err


# ============================================================================ interaction
def test_interaction_set_and_remove(workspace, write_world, factories, monkeypatch):
    import edit_story
    write_world(stories=[factories.story()])
    spath = workspace.worlds / "testworld" / "stories" / "test-story" / "story.yaml"
    rc = _run(monkeypatch, edit_story,
              ["edit_story.py", "testworld/test-story", "interaction", "2"],
              {"type": "seek-and-find", "prompt": "Find the hidden star!",
               "data": {"targets": [{"name": "star", "hint": "look up"}]}})
    assert rc == 0
    data = load_yaml(spath)
    page2 = next(p for p in data["pages"] if p["number"] == 2)
    assert page2["interaction"]["type"] == "seek-and-find"
    validate_content("story", data)

    rc = _run(monkeypatch, edit_story,
              ["edit_story.py", "testworld/test-story", "interaction", "2", "--remove"])
    assert rc == 0
    data = load_yaml(spath)
    assert "interaction" not in next(p for p in data["pages"] if p["number"] == 2)


def test_interaction_on_unknown_page_is_rejected(workspace, write_world, factories, monkeypatch,
                                                 capsys):
    import edit_story
    write_world(stories=[factories.story()])
    rc = _run(monkeypatch, edit_story,
              ["edit_story.py", "testworld/test-story", "interaction", "99"],
              {"type": "choice", "prompt": "?"})
    assert rc == 1
    assert "no page 99" in capsys.readouterr().err


# ============================================================================ edit_world.py
def test_edit_world_merges_nested_art_style(workspace, write_world, monkeypatch):
    import edit_world
    write_world()
    rc = _run(monkeypatch, edit_world, ["edit_world.py", "testworld"],
              {"tagline": "Better tagline.",
               "art_style": {"prompt_style_block": "bold gouache, thick brushwork"}})
    assert rc == 0
    data = load_yaml(workspace.worlds / "testworld" / "world.yaml")
    assert data["tagline"] == "Better tagline."
    assert data["art_style"]["prompt_style_block"] == "bold gouache, thick brushwork"
    # nested merge keeps the rest of art_style
    assert data["art_style"]["medium"] == "soft watercolor"
    validate_content("world", data)


def test_edit_world_rejects_schema_violation(workspace, write_world, monkeypatch, capsys):
    import edit_world
    write_world()
    wpath = workspace.worlds / "testworld" / "world.yaml"
    before = wpath.read_text()
    rc = _run(monkeypatch, edit_world, ["edit_world.py", "testworld"],
              {"target_age_bands": "5-7"})  # must be a list
    assert rc == 1
    assert wpath.read_text() == before
    assert "unchanged" in capsys.readouterr().err


# ============================================================================ edit_character.py
def test_edit_character_merges_personality(workspace, write_world, factories, monkeypatch):
    import edit_character
    write_world(characters=[factories.character()])
    rc = _run(monkeypatch, edit_character, ["edit_character.py", "testworld/hero"],
              {"appearance_token": "HERO: blue cloak (#224488), silver boots",
               "personality": {"motivation": "to map every star"}})
    assert rc == 0
    data = load_yaml(workspace.worlds / "testworld" / "characters" / "hero.yaml")
    assert data["appearance_token"].startswith("HERO: blue cloak")
    assert data["personality"]["motivation"] == "to map every star"
    # nested merge keeps the untouched personality fields
    assert data["personality"]["traits"] == ["brave", "curious"]
    validate_content("character", data)


def test_edit_character_accepts_yaml_path_target(workspace, write_world, factories, monkeypatch):
    import edit_character
    write_world(characters=[factories.character()])
    rc = _run(monkeypatch, edit_character,
              ["edit_character.py", "worlds/testworld/characters/hero.yaml"],
              {"one_liner": "A hero with a map."})
    assert rc == 0
    data = load_yaml(workspace.worlds / "testworld" / "characters" / "hero.yaml")
    assert data["one_liner"] == "A hero with a map."
