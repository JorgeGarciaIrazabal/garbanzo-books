"""Tests for ``scripts/lib/model.py`` — the core data model.

Covers the contracts the rest of the toolchain depends on:
  * slugify rules (kebab-case, ascii-only, idempotent)
  * dump_yaml is atomic + always round-trippable
  * load_yaml raises ContentError on bad YAML / non-mapping roots (NOT a raw traceback)
  * load_world is RESILIENT — one bad character/story does not sink the whole world
  * character_with_stage extends the appearance_token only when an evolution stage matches
  * validate_content rejects schema-invalid data (and is a no-op if jsonschema is missing)
  * load_dotenv only fills UNSET-OR-BLANK keys (a real exported value still wins)
"""
from __future__ import annotations

import os
import sys

import pytest
import yaml

from lib import model
from lib.model import (
    ContentError, character_with_stage, dump_yaml, find_story, load_dotenv,
    load_world, load_yaml, slugify, validate_content,
)


# =============================================================================== slugify
@pytest.mark.parametrize("text,expected", [
    ("Hello World", "hello-world"),
    ("  Mixed   Spaces  ", "mixed-spaces"),
    ("Punc!tu@ation#", "punc-tu-ation"),
    ("UPPER lower", "upper-lower"),
    ("multiple---hyphens", "multiple-hyphens"),
    ("trim-edges-", "trim-edges"),
    ("-leading-and-trailing-", "leading-and-trailing"),
    ("with_underscore_chars", "with-underscore-chars"),
    ("digits 123 stay", "digits-123-stay"),
])
def test_slugify_normalizes_to_kebab_case(text, expected):
    assert slugify(text) == expected


def test_slugify_is_idempotent():
    once = slugify("Some Title Here")
    twice = slugify(once)
    assert once == twice
    assert "--" not in twice


def test_slugify_rejects_non_ascii_letters_with_hyphens():
    # Accents/non-ASCII are not part of the safe slug grammar.
    assert slugify("café au lait") == "caf-au-lait"


# =============================================================================== load_yaml
def test_load_yaml_returns_dict_for_normal_file(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text("a: 1\nb: hello\n")
    assert load_yaml(p) == {"a": 1, "b": "hello"}


def test_load_yaml_empty_file_returns_empty_dict(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("")
    assert load_yaml(p) == {}


def test_load_yaml_raises_ContentError_for_malformed_yaml(tmp_path):
    p = tmp_path / "bad.yaml"
    # An unclosed flow sequence is a hard YAML error.
    p.write_text("a: [1, 2, 3\n")
    with pytest.raises(ContentError) as exc:
        load_yaml(p)
    # ContentError messages carry a relative path so callers can blame the file.
    assert "bad.yaml" in str(exc.value)


def test_load_yaml_raises_ContentError_for_non_mapping_root(tmp_path):
    p = tmp_path / "list.yaml"
    p.write_text("- a\n- b\n")
    with pytest.raises(ContentError) as exc:
        load_yaml(p)
    assert "mapping" in str(exc.value)


def test_load_yaml_propagates_FileNotFoundError(tmp_path):
    # Missing files are a different, expected, condition — not a ContentError.
    with pytest.raises(FileNotFoundError):
        load_yaml(tmp_path / "does-not-exist.yaml")


# =============================================================================== dump_yaml
def test_dump_yaml_writes_round_trippable_data(tmp_path):
    data = {"title": "Hello", "list": [1, 2, 3], "nested": {"k": "v"}}
    p = tmp_path / "out.yaml"
    dump_yaml(data, p)
    assert load_yaml(p) == data


def test_dump_yaml_preserves_key_order(tmp_path):
    data = {"z_first": 1, "a_second": 2, "m_third": 3}
    p = tmp_path / "ordered.yaml"
    dump_yaml(data, p)
    keys_in_file = [line.split(":")[0] for line in p.read_text().splitlines() if ":" in line]
    assert keys_in_file == ["z_first", "a_second", "m_third"]


def test_dump_yaml_creates_parent_dirs(tmp_path):
    deep = tmp_path / "a" / "b" / "c" / "deep.yaml"
    dump_yaml({"ok": True}, deep)
    assert deep.exists()
    assert load_yaml(deep) == {"ok": True}


def test_dump_yaml_is_atomic_leaves_no_tmp_file(tmp_path):
    """The atomic-rename strategy means there is never a half-written file lying
    around — readers always see either the previous file or the new one."""
    p = tmp_path / "atomic.yaml"
    dump_yaml({"k": "v"}, p)
    # Confirm no leftover .tmp files (the function cleans up after itself).
    leftovers = [f for f in tmp_path.iterdir() if f.name.startswith(".atomic.yaml.")]
    assert leftovers == []


def test_dump_yaml_allows_unicode(tmp_path):
    data = {"title": "Café — 日本語", "emoji": "🌟"}
    p = tmp_path / "u.yaml"
    dump_yaml(data, p)
    text = p.read_text(encoding="utf-8")
    # allow_unicode=True means characters are written as-is, not escaped.
    assert "Café" in text
    assert "日本語" in text


# =============================================================================== validate_content
def test_validate_content_passes_on_valid_world(workspace, factories):
    # Should NOT raise.
    validate_content("world", factories.world())


def test_validate_content_rejects_missing_required_field(workspace, factories):
    bad = factories.world()
    del bad["premise"]  # required
    with pytest.raises(ContentError) as exc:
        validate_content("world", bad)
    assert "premise" in str(exc.value)


def test_validate_content_rejects_bad_slug_pattern(workspace, factories):
    bad = factories.world(slug="Has Spaces And CAPS")
    with pytest.raises(ContentError):
        validate_content("world", bad)


def test_validate_content_skips_when_schema_missing(workspace, factories, monkeypatch):
    # No schema on disk → no-op (offline-friendly).
    monkeypatch.setattr(model, "SCHEMAS", workspace.root / "no-such-dir")
    validate_content("world", {"this": "is", "not": "schema-valid"})


# =============================================================================== load_dotenv
def test_load_dotenv_fills_unset_keys(tmp_path, monkeypatch):
    envp = tmp_path / ".env"
    envp.write_text('FOO=bar\nBAZ="quoted value"\n')
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAZ", raising=False)
    load_dotenv(envp)
    assert os.environ["FOO"] == "bar"
    assert os.environ["BAZ"] == "quoted value"


def test_load_dotenv_overrides_blank_env(tmp_path, monkeypatch):
    """The whole reason this helper exists: a parent shell may export an EMPTY
    GEMINI_API_KEY (which would otherwise shadow the real .env value and silently
    force placeholder art). load_dotenv treats blank-or-unset the same."""
    envp = tmp_path / ".env"
    envp.write_text("GEMINI_API_KEY=real-key\n")
    monkeypatch.setenv("GEMINI_API_KEY", "")  # blank — should be overridden
    load_dotenv(envp)
    assert os.environ["GEMINI_API_KEY"] == "real-key"


def test_load_dotenv_does_not_override_real_exported_value(tmp_path, monkeypatch):
    """A non-empty exported value wins — the real environment always beats .env."""
    envp = tmp_path / ".env"
    envp.write_text("MYVAR=from-dotenv\n")
    monkeypatch.setenv("MYVAR", "from-shell")
    load_dotenv(envp)
    assert os.environ["MYVAR"] == "from-shell"


def test_load_dotenv_handles_comments_and_blank_lines(tmp_path, monkeypatch):
    envp = tmp_path / ".env"
    envp.write_text("# a comment\n\nA=1\n# another\nB=2\n")
    monkeypatch.delenv("A", raising=False)
    monkeypatch.delenv("B", raising=False)
    load_dotenv(envp)
    assert os.environ["A"] == "1"
    assert os.environ["B"] == "2"


def test_load_dotenv_strips_surrounding_quotes(tmp_path, monkeypatch):
    envp = tmp_path / ".env"
    envp.write_text("K1=\"double\"\nK2='single'\n")
    monkeypatch.delenv("K1", raising=False)
    monkeypatch.delenv("K2", raising=False)
    load_dotenv(envp)
    assert os.environ["K1"] == "double"
    assert os.environ["K2"] == "single"


def test_load_dotenv_no_file_is_silent(tmp_path):
    # Doesn't raise — many setups don't have an .env, and that's fine.
    load_dotenv(tmp_path / "nope.env")


# =============================================================================== load_world
def test_load_world_loads_a_well_formed_world(write_world, factories):
    slug, _ = write_world(
        slug="ww",
        characters=[factories.character(slug="hero", world="ww")],
        stories=[factories.story(slug="s1", world="ww")],
    )
    w = load_world(slug)
    assert w.slug == "ww"
    assert "hero" in w.characters
    assert len(w.stories) == 1
    assert w.stories[0].slug == "s1"
    assert w.errors == []


def test_load_world_skips_one_bad_character_without_failing(workspace, write_world, factories):
    """The system invariant: a single half-written character must not blank out
    the entire world — the good characters and the world itself still load."""
    slug, wdir = write_world(
        slug="ww",
        characters=[factories.character(slug="good", world="ww")],
    )
    (wdir / "characters" / "broken.yaml").write_text("a: [oops\n")
    w = load_world(slug)
    assert "good" in w.characters
    assert "broken" not in w.characters
    assert any("broken.yaml" in e for e in w.errors)


def test_load_world_skips_one_bad_story_without_failing(workspace, write_world, factories):
    slug, wdir = write_world(
        slug="ww",
        stories=[factories.story(slug="ok", world="ww")],
    )
    bad_dir = wdir / "stories" / "bad"
    bad_dir.mkdir(parents=True)
    (bad_dir / "story.yaml").write_text("title: : :\n")
    w = load_world(slug)
    assert [s.slug for s in w.stories] == ["ok"]
    assert any("bad" in e for e in w.errors)


def test_load_world_missing_world_yaml_raises(workspace):
    (workspace.worlds / "noworld").mkdir()
    with pytest.raises(FileNotFoundError):
        load_world("noworld")


def test_load_world_without_stories_skips_them(write_world, factories):
    slug, _ = write_world(slug="ww", stories=[factories.story(slug="s1", world="ww")])
    w = load_world(slug, with_stories=False)
    assert w.stories == []


def test_load_all_worlds_returns_only_valid_worlds_plus_errors(write_world, factories):
    from lib.model import load_all_worlds
    write_world(slug="alpha")
    write_world(slug="beta")
    # Add an entirely broken world dir
    bad = factories.world(slug="gamma")
    bad_wdir = (write_world.__self__.worlds if hasattr(write_world, '__self__') else None)
    # Just make a broken world.yaml directly
    from lib.model import WORLDS
    broken = WORLDS / "gamma"
    broken.mkdir()
    (broken / "world.yaml").write_text("title: : :\n")
    errs = []
    worlds = load_all_worlds(errors=errs)
    slugs = sorted(w.slug for w in worlds)
    assert "alpha" in slugs and "beta" in slugs
    # The broken world MAY still appear if its YAML happens to parse;
    # but its error must be reported if it didn't.
    if "gamma" not in slugs:
        assert any("gamma" in e for e in errs)


# =============================================================================== find_story
def test_find_story_returns_story_from_disk(write_world, factories):
    slug, _ = write_world(slug="ww", stories=[factories.story(slug="s1", world="ww")])
    s = find_story("ww", "s1")
    assert s.slug == "s1"
    assert s.data["title"] == "Test Story"


def test_find_story_missing_raises(workspace):
    with pytest.raises(FileNotFoundError):
        find_story("nope", "nada")


# =============================================================================== character_with_stage
def test_character_with_stage_returns_original_when_no_stage_given(factories):
    c = factories.character()
    out = character_with_stage(c, None)
    assert out is c  # unchanged identity


def test_character_with_stage_extends_appearance_token_for_matching_stage(factories):
    c = factories.character()
    out = character_with_stage(c, "brave")
    # Original character is not mutated
    assert c["appearance_token"] == out["appearance_token"].split(" [")[0]
    assert "[brave: a brave-medal pinned to the coat]" in out["appearance_token"]


def test_character_with_stage_returns_original_for_unknown_stage(factories):
    c = factories.character()
    out = character_with_stage(c, "totally-made-up-stage")
    assert out == c


def test_character_with_stage_handles_empty_appearance_delta(factories):
    c = factories.character()
    # base stage has empty appearance_delta — token should NOT be extended.
    out = character_with_stage(c, "base")
    assert out["appearance_token"] == c["appearance_token"]
    assert "[base:" not in out["appearance_token"]


def test_character_with_stage_preserves_core_identity(factories):
    """Evolution may extend the token, but the core identity descriptor must remain
    intact — otherwise the character "changes person" mid-series."""
    c = factories.character()
    base_token = c["appearance_token"]
    for stage in ("base", "brave"):
        out = character_with_stage(c, stage)
        assert out["appearance_token"].startswith(base_token)


# =============================================================================== Story dataclass
def test_story_dir_and_images_dir_resolve_relative_to_yaml(write_world, factories):
    slug, _ = write_world(slug="ww", stories=[factories.story(slug="s1", world="ww")])
    w = load_world(slug)
    s = w.stories[0]
    assert s.dir.name == "s1"
    assert s.images_dir.name == "images"
    assert s.images_dir.parent == s.dir
