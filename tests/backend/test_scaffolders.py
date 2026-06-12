"""Tests for the scaffolding scripts: new_world.py / new_character.py / new_story.py.

These guard the "FILE SAFETY" invariant in the studio brief — the scaffolders
are the canonical way to CREATE a new YAML file, and they must produce
schema-valid documents with sensible defaults so the user can edit them in
place. Tests assert:
  * The generated YAML is loadable and schema-valid
  * Idempotency: re-running on an existing file fails loudly instead of
    silently overwriting (no data loss)
  * Foreign keys: a character/story can't be created without its world
  * Custom slug overrides win
  * Defaults follow the methodology (5-7 age band default, FK target per band)
"""
from __future__ import annotations

import pytest

from lib.model import load_yaml, validate_content


# ============================================================================ new_world.py
def test_new_world_creates_schema_valid_world(workspace, monkeypatch):
    import new_world
    monkeypatch.setattr("sys.argv", ["new_world.py", "The Whispering Woods"])
    rc = new_world.main()
    assert rc == 0
    out = workspace.worlds / "the-whispering-woods" / "world.yaml"
    assert out.exists()
    data = load_yaml(out)
    validate_content("world", data)


def test_new_world_uses_slugified_title_by_default(workspace, monkeypatch):
    import new_world
    monkeypatch.setattr("sys.argv", ["new_world.py", "Test  World—Title"])
    new_world.main()
    # Title with extra spaces + em-dash slugs cleanly
    assert (workspace.worlds / "test-world-title" / "world.yaml").exists()


def test_new_world_slug_override_wins(workspace, monkeypatch):
    import new_world
    monkeypatch.setattr("sys.argv", ["new_world.py", "Custom Title", "--slug", "my-special-id"])
    new_world.main()
    assert (workspace.worlds / "my-special-id" / "world.yaml").exists()
    assert not (workspace.worlds / "custom-title").exists()


def test_new_world_fails_when_world_already_exists(workspace, monkeypatch, capsys):
    import new_world
    monkeypatch.setattr("sys.argv", ["new_world.py", "Foo"])
    assert new_world.main() == 0
    monkeypatch.setattr("sys.argv", ["new_world.py", "Foo"])
    assert new_world.main() == 1  # MUST NOT overwrite — return non-zero
    err = capsys.readouterr().err
    assert "already exists" in err


def test_new_world_writes_companion_style_guide(workspace, monkeypatch):
    import new_world
    monkeypatch.setattr("sys.argv", ["new_world.py", "My World"])
    new_world.main()
    sg = workspace.worlds / "my-world" / "style-guide.md"
    assert sg.exists()
    text = sg.read_text()
    assert "My World" in text
    # Palette table is in the style guide
    assert "| Hex |" in text


def test_new_world_creates_companion_dirs(workspace, monkeypatch):
    import new_world
    monkeypatch.setattr("sys.argv", ["new_world.py", "My World"])
    new_world.main()
    wdir = workspace.worlds / "my-world"
    assert (wdir / "characters").is_dir()
    assert (wdir / "stories").is_dir()
    assert (wdir / "assets").is_dir()


def test_new_world_default_age_band_is_5_7(workspace, monkeypatch):
    import new_world
    monkeypatch.setattr("sys.argv", ["new_world.py", "Foo"])
    new_world.main()
    data = load_yaml(workspace.worlds / "foo" / "world.yaml")
    assert data["target_age_bands"] == ["5-7"]


def test_new_world_accepts_multiple_age_flags(workspace, monkeypatch):
    import new_world
    monkeypatch.setattr("sys.argv",
                        ["new_world.py", "Multi", "--age", "3-5", "--age", "5-7"])
    new_world.main()
    data = load_yaml(workspace.worlds / "multi" / "world.yaml")
    assert data["target_age_bands"] == ["3-5", "5-7"]


# ============================================================================ new_character.py
def _make_world(workspace, monkeypatch, slug="ww", title="WW"):
    import new_world
    monkeypatch.setattr("sys.argv", ["new_world.py", title, "--slug", slug])
    new_world.main()


def test_new_character_requires_existing_world(workspace, monkeypatch, capsys):
    import new_character
    monkeypatch.setattr("sys.argv", ["new_character.py", "no-such-world", "Hero"])
    rc = new_character.main()
    assert rc == 1
    assert "no world" in capsys.readouterr().err.lower()


def test_new_character_creates_yaml_with_evolution_base_stage(workspace, monkeypatch):
    _make_world(workspace, monkeypatch)
    import new_character
    monkeypatch.setattr("sys.argv", ["new_character.py", "ww", "Pip the Hedgehog"])
    rc = new_character.main()
    assert rc == 0
    out = workspace.worlds / "ww" / "characters" / "pip-the-hedgehog.yaml"
    assert out.exists()
    data = load_yaml(out)
    # Base evolution stage exists so stage=base always resolves
    assert any(s.get("stage") == "base" for s in data["evolution"])
    assert data["world"] == "ww"
    assert data["name"] == "Pip the Hedgehog"


def test_new_character_starts_with_locked_appearance_token_placeholder(workspace, monkeypatch):
    _make_world(workspace, monkeypatch)
    import new_character
    monkeypatch.setattr("sys.argv", ["new_character.py", "ww", "Hero"])
    new_character.main()
    data = load_yaml(workspace.worlds / "ww" / "characters" / "hero.yaml")
    # Scaffolders fill the appearance_token with a TODO marker so the validator
    # will WARN until the user fills it in.
    assert data["appearance_token"]
    assert "TODO" in data["appearance_token"]


def test_new_character_fails_when_already_exists(workspace, monkeypatch):
    _make_world(workspace, monkeypatch)
    import new_character
    monkeypatch.setattr("sys.argv", ["new_character.py", "ww", "Hero"])
    assert new_character.main() == 0
    monkeypatch.setattr("sys.argv", ["new_character.py", "ww", "Hero"])
    assert new_character.main() == 1


def test_new_character_slug_override_wins(workspace, monkeypatch):
    _make_world(workspace, monkeypatch)
    import new_character
    monkeypatch.setattr("sys.argv",
                        ["new_character.py", "ww", "Pip", "--slug", "p1"])
    new_character.main()
    assert (workspace.worlds / "ww" / "characters" / "p1.yaml").exists()


# ============================================================================ new_story.py
def test_new_story_requires_existing_world(workspace, monkeypatch, capsys):
    import new_story
    monkeypatch.setattr("sys.argv", ["new_story.py", "no-such", "S1"])
    rc = new_story.main()
    assert rc == 1
    assert "no world" in capsys.readouterr().err.lower()


def test_new_story_creates_story_yaml_with_images_dir(workspace, monkeypatch):
    _make_world(workspace, monkeypatch)
    import new_story
    monkeypatch.setattr("sys.argv", ["new_story.py", "ww", "Pip and the Lost Star"])
    rc = new_story.main()
    assert rc == 0
    out = workspace.worlds / "ww" / "stories" / "pip-and-the-lost-star" / "story.yaml"
    assert out.exists()
    assert (out.parent / "images").is_dir()


def test_new_story_default_age_band_is_5_7(workspace, monkeypatch):
    _make_world(workspace, monkeypatch)
    import new_story
    monkeypatch.setattr("sys.argv", ["new_story.py", "ww", "Test"])
    new_story.main()
    data = load_yaml(workspace.worlds / "ww" / "stories" / "test" / "story.yaml")
    assert data["age_band"] == "5-7"


def test_new_story_age_band_sets_fk_target_and_word_caps(workspace, monkeypatch):
    """The per-band defaults must follow methodology — bigger kids get a higher
    FK target and a higher words-per-page cap."""
    from lib.readability import BANDS
    _make_world(workspace, monkeypatch)
    import new_story

    # 5-7 story
    monkeypatch.setattr("sys.argv",
                        ["new_story.py", "ww", "Early", "--slug", "early", "--age", "5-7"])
    new_story.main()
    early = load_yaml(workspace.worlds / "ww" / "stories" / "early" / "story.yaml")

    # 7-9 story
    monkeypatch.setattr("sys.argv",
                        ["new_story.py", "ww", "Older", "--slug", "older", "--age", "7-9"])
    new_story.main()
    older = load_yaml(workspace.worlds / "ww" / "stories" / "older" / "story.yaml")

    # FK target rises with band
    assert older["reading_level"]["target_fk_grade"] > early["reading_level"]["target_fk_grade"]
    # Word-per-page cap matches the band table
    assert early["reading_level"]["max_words_per_page"] == BANDS["5-7"]["max_words_per_page"]
    assert older["reading_level"]["max_words_per_page"] == BANDS["7-9"]["max_words_per_page"]


def test_new_story_rejects_unknown_age_band(workspace, monkeypatch):
    _make_world(workspace, monkeypatch)
    import new_story
    monkeypatch.setattr("sys.argv",
                        ["new_story.py", "ww", "Test", "--age", "99-100"])
    # argparse choices=[…] enforces this — script exits with SystemExit(2)
    with pytest.raises(SystemExit):
        new_story.main()


def test_new_story_fails_when_already_exists(workspace, monkeypatch):
    _make_world(workspace, monkeypatch)
    import new_story
    monkeypatch.setattr("sys.argv", ["new_story.py", "ww", "Dup"])
    assert new_story.main() == 0
    monkeypatch.setattr("sys.argv", ["new_story.py", "ww", "Dup"])
    assert new_story.main() == 1


def test_new_story_starts_in_draft_status(workspace, monkeypatch):
    """Brand new stories must start as DRAFT — the studio brief says drafts are
    excluded from publish until explicitly upgraded."""
    _make_world(workspace, monkeypatch)
    import new_story
    monkeypatch.setattr("sys.argv", ["new_story.py", "ww", "Draftie"])
    new_story.main()
    data = load_yaml(workspace.worlds / "ww" / "stories" / "draftie" / "story.yaml")
    assert data["status"] == "draft"


def test_new_story_has_title_and_first_story_page(workspace, monkeypatch):
    _make_world(workspace, monkeypatch)
    import new_story
    monkeypatch.setattr("sys.argv", ["new_story.py", "ww", "Foo"])
    new_story.main()
    data = load_yaml(workspace.worlds / "ww" / "stories" / "foo" / "story.yaml")
    kinds = [p.get("kind") for p in data["pages"]]
    assert "title" in kinds
    assert "story" in kinds


def test_new_story_target_year_defaults_to_band_midpoint(workspace, monkeypatch):
    """target_year (CONTENT age, one number) defaults from the reader band so every new
    story carries both knobs; --year overrides it independently of --age."""
    _make_world(workspace, monkeypatch)
    import new_story
    monkeypatch.setattr("sys.argv", ["new_story.py", "ww", "Mid", "--age", "5-7"])
    new_story.main()
    data = load_yaml(workspace.worlds / "ww" / "stories" / "mid" / "story.yaml")
    assert data["target_year"] == 6
    validate_content("story", data)


def test_new_story_year_flag_overrides_default(workspace, monkeypatch):
    _make_world(workspace, monkeypatch)
    import new_story
    monkeypatch.setattr("sys.argv",
                        ["new_story.py", "ww", "Diverge", "--age", "5-7", "--year", "8"])
    new_story.main()
    data = load_yaml(workspace.worlds / "ww" / "stories" / "diverge" / "story.yaml")
    # content pitched at an 8-year-old, words for a beginning reader — they may diverge
    assert data["target_year"] == 8
    assert data["age_band"] == "5-7"
    validate_content("story", data)


def test_new_story_rejects_out_of_range_year(workspace, monkeypatch, capsys):
    _make_world(workspace, monkeypatch)
    import new_story
    monkeypatch.setattr("sys.argv", ["new_story.py", "ww", "Bad", "--year", "99"])
    assert new_story.main() == 1
    assert "--year" in capsys.readouterr().err


def test_new_story_pages_flag_scaffolds_page_stubs(workspace, monkeypatch):
    """--pages N pre-builds the page boilerplate so the (slow) author model only fills in
    text + scene prompts. Title page 0 + N consecutive story stubs, each schema-shaped."""
    _make_world(workspace, monkeypatch)
    import new_story
    monkeypatch.setattr("sys.argv", ["new_story.py", "ww", "Big", "--pages", "14"])
    new_story.main()
    data = load_yaml(workspace.worlds / "ww" / "stories" / "big" / "story.yaml")
    pages = data["pages"]
    assert len(pages) == 15  # title + 14 story stubs
    assert pages[0]["kind"] == "title"
    assert [p["number"] for p in pages] == list(range(15))
    for p in pages[1:]:
        assert p["kind"] == "story"
        assert p["image"]["text_zone"]      # layout boilerplate pre-filled
        assert p["layout"]["scrim"] is True
