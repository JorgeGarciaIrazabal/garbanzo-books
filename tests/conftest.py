"""Shared pytest fixtures for the Garbanzo Books test suite.

The toolchain resolves paths from module-level constants set at import time
(``scripts/lib/model.ROOT`` and ``WORLDS``). To run each test against an
isolated, throw-away workspace we monkey-patch those constants *before* the
SUT functions reach them, then put them back. Every fixture is function-scoped
so tests can't leak files into a sibling's tree.

The factories (``make_world``, ``make_character``, ``make_story``) build
**schema-valid** dicts you can mutate to introduce specific failures; they keep
the rest of the data well-formed so the test is studying ONE invariant at a
time.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "ui"))


# --------------------------------------------------------------------------- isolated workspace
@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A fresh repo-shaped tmp dir + the module-level path constants pointed at it.

    Returns a ``Workspace`` namespace with paths and helpers; teardown restores
    the original constants automatically (monkeypatch).
    """
    root = tmp_path
    worlds = root / "worlds"
    worlds.mkdir()
    schemas_src = REPO_ROOT / "schemas"
    schemas_dst = root / "schemas"
    schemas_dst.mkdir()
    # The validator looks for schema files via SCHEMAS; symlinking the real ones
    # keeps tests honest about the actual JSON schemas the studio ships.
    for s in schemas_src.iterdir():
        (schemas_dst / s.name).write_text(s.read_text())

    # Repoint every module that already imported the constants. The scripts/
    # directory is on sys.path (not a package), so we import them by their
    # bare names.
    import lib.model as m
    import validate as v
    import build_site as b
    import new_world as nw
    import new_character as nc
    import new_story as ns
    import reading_level as rl
    import generate_images as gi_mod

    monkeypatch.setattr(m, "ROOT", root)
    monkeypatch.setattr(m, "WORLDS", worlds)
    monkeypatch.setattr(m, "SCHEMAS", schemas_dst)
    monkeypatch.setattr(v, "WORLDS", worlds)
    monkeypatch.setattr(v, "SCHEMAS", schemas_dst)
    monkeypatch.setattr(b, "SITE", root / "site")
    monkeypatch.setattr(b, "ROOT", root)
    monkeypatch.setattr(nw, "WORLDS", worlds)
    monkeypatch.setattr(nc, "WORLDS", worlds)
    monkeypatch.setattr(ns, "WORLDS", worlds)
    # reading_level.py and generate_images.py do `from lib.model import ROOT, …`
    # so each has a separate local rebinding — patch them too.
    monkeypatch.setattr(rl, "ROOT", root)
    monkeypatch.setattr(gi_mod, "ROOT", root)

    class WS:
        def __init__(self):
            self.root = root
            self.worlds = worlds
            self.site = root / "site"
            self.schemas = schemas_dst

        def world_dir(self, slug):
            return self.worlds / slug

    return WS()


# --------------------------------------------------------------------------- data factories
def _palette():
    return [
        {"name": "cream", "hex": "#f4e1c1", "role": "background"},
        {"name": "sage", "hex": "#6b8f71", "role": "primary"},
    ]


def make_world(slug="testworld", **overrides):
    """Return a schema-valid world dict you can mutate."""
    base = {
        "slug": slug,
        "title": "Test World",
        "tagline": "A tagline.",
        "premise": "A premise.",
        "tone": ["cozy"],
        "genres": ["adventure"],
        "target_age_bands": ["5-7"],
        "languages": ["en"],
        "geography": {"overview": "TODO", "locations": []},
        "rules": ["TODO"],
        "factions": [],
        "timeline": [],
        "motifs": ["TODO"],
        "themes": ["friendship"],
        "art_style": {
            "medium": "soft watercolor",
            "line_quality": "rounded",
            "shading": "soft",
            "lighting": "warm",
            "perspective": "eye-level",
            "palette": _palette(),
            "influences": [],
            "prompt_style_block": "soft watercolor, warm muted palette, rounded shapes, cozy storybook mood",
            "negative_prompt": "photorealism, harsh shadows, scary faces, text artifacts",
            "aspect_ratio": "4:3",
            "text_treatment": {
                "placement": "lower third",
                "scrim": "cream panel 85%",
                "font_family": "Andika",
                "dyslexia_friendly": True,
            },
        },
        "tags": [],
    }
    base.update(overrides)
    return base


def make_character(slug="hero", world="testworld", **overrides):
    base = {
        "slug": slug,
        "world": world,
        "name": "Test Hero",
        "role": "protagonist",
        "species": "human",
        "pronouns": "they/them",
        "one_liner": "A test hero.",
        "personality": {
            "traits": ["brave", "curious"],
            "motivation": "to be tested",
            "fears": ["bugs"],
            "flaws": ["impulsive"],
            "strengths": ["resilient"],
            "quirks": ["counts everything"],
            "values": ["honesty"],
        },
        "voice": {"speech_style": "warm", "catchphrases": [], "vocabulary_level": "simple"},
        "appearance": {
            "age_appearance": "child",
            "build": "small",
            "height": "knee-high",
            "skin": "tan",
            "hair": "black",
            "eyes": "brown",
            "outfit": "red coat",
            "distinguishing_features": ["yellow boots", "tiny pendant"],
            "color_palette": [
                {"part": "coat", "hex": "#c0392b"},
                {"part": "boots", "hex": "#f1c40f"},
            ],
            "silhouette_notes": "recognisable in pure outline",
        },
        "appearance_token": f"{slug.upper()}: a small {slug}, red coat (#c0392b), yellow boots (#f1c40f), tiny pendant",
        "reference_images": [],
        "seed": 4242,
        "relationships": [],
        "evolution": [
            {
                "stage": "base",
                "order": 0,
                "summary": "Starting state.",
                "personality_delta": "",
                "appearance_delta": "",
                "unlocked_by": "",
            },
            {
                "stage": "brave",
                "order": 1,
                "summary": "After the arc.",
                "personality_delta": "more confident",
                "appearance_delta": "a brave-medal pinned to the coat",
                "unlocked_by": "the first story",
            },
        ],
        "tags": [],
    }
    base.update(overrides)
    return base


def make_story(slug="test-story", world="testworld", **overrides):
    base = {
        "slug": slug,
        "world": world,
        "title": "Test Story",
        "logline": "Hero wants thing but obstacle.",
        "summary": "A summary.",
        "age_band": "5-7",
        "reading_level": {
            "target_fk_grade": 1.0,
            "fk_grade_tolerance": 1.5,
            "max_words_per_page": 60,
            "max_sentence_words": 8,
            "decoding_focus": "",
            "decodable": False,
        },
        "themes": ["friendship"],
        "moral": "Be kind.",
        "characters": [{"slug": "hero", "stage": "base", "role_in_story": "protagonist"}],
        "spine": {
            "once_upon_a_time": "Hero lived here.",
            "every_day": "Hero did the thing.",
            "until_one_day": "Until the thing happened.",
            "because_of_that": ["Because of that, X.", "Because of that, Y."],
            "until_finally": "Until finally.",
            "ever_since_then": "Ever since.",
        },
        "pages": [
            {
                "number": 0,
                "kind": "title",
                "text": "Test Story",
                "image": {"prompt": "title scene", "characters_present": [],
                          "alt": "title", "text_zone": "center"},
                "layout": {"text_position": "center", "text_align": "center", "scrim": True},
            },
            {
                "number": 1,
                "kind": "story",
                "text": "The hero ran. The dog sat. The cat had fun.",
                "image": {"prompt": "hero runs", "characters_present": ["hero"],
                          "alt": "the hero runs", "text_zone": "lower third"},
                "layout": {"text_position": "lower-third", "text_align": "center", "scrim": True},
                "vocabulary": ["ran"],
            },
            {
                "number": 2,
                "kind": "story",
                "text": "The hero was glad.",
                "image": {"prompt": "hero smiles", "characters_present": ["hero"],
                          "alt": "smile", "text_zone": "lower third"},
                "layout": {"text_position": "lower-third", "text_align": "center", "scrim": True},
            },
        ],
        "interactions_summary": [],
        "status": "draft",
        "tags": ["friendship"],
        "cover": {"image": "", "image_prompt": "", "alt": ""},
    }
    base.update(overrides)
    return base


@pytest.fixture
def factories():
    """Expose the data factories. Tests should always start from these to keep
    fixtures isolated from any in-place mutation."""

    class F:
        world = staticmethod(lambda **kw: copy.deepcopy(make_world(**kw)))
        character = staticmethod(lambda **kw: copy.deepcopy(make_character(**kw)))
        story = staticmethod(lambda **kw: copy.deepcopy(make_story(**kw)))

    return F()


# ---------------------------------------------------------------------- builders that hit disk
@pytest.fixture
def write_world(workspace, factories):
    """Write a world + (optionally) characters + (optionally) stories to disk
    in the isolated workspace, returning the world slug. Useful for any test
    that needs ``load_world(slug)`` to find real files."""
    from lib.model import dump_yaml

    def _build(slug="testworld", world_overrides=None, characters=None, stories=None,
               image_files=None):
        w = factories.world(slug=slug, **(world_overrides or {}))
        wdir = workspace.worlds / slug
        dump_yaml(w, wdir / "world.yaml")
        (wdir / "characters").mkdir(parents=True, exist_ok=True)
        (wdir / "stories").mkdir(parents=True, exist_ok=True)
        (wdir / "assets").mkdir(parents=True, exist_ok=True)
        for c in characters or []:
            dump_yaml(c, wdir / "characters" / f"{c['slug']}.yaml")
        for s in stories or []:
            sdir = wdir / "stories" / s["slug"]
            dump_yaml(s, sdir / "story.yaml")
            (sdir / "images").mkdir(parents=True, exist_ok=True)
            # Write any expected image files so the validator's "image file exists"
            # check passes when the story declares one.
            for rel in image_files or []:
                (sdir / rel).parent.mkdir(parents=True, exist_ok=True)
                (sdir / rel).write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG magic
        return slug, wdir

    return _build
