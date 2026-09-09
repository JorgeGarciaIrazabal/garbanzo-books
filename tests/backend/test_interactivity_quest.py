"""Validator contract for `arcade-quest` — the composed game (scripts/lib/checks/
interactivity.py::_check_quest_spec). A quest payload must describe a runtime-
assemblable scenario: hero with skin, named actor groups with valid role/motion,
waves that only spawn declared groups, a valid finale, and at least one countable
role so the goal pips are reachable without the assist ladder."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from lib.checks.interactivity import (  # noqa: E402
    check_interactivity,
)
from lib.checks.report import Report  # noqa: E402


def _story(pages):
    return {"slug": "q", "title": "Q", "pages": pages}


def _world():
    class W:
        slug = "w"
    return W()


def _quest(data, **extra):
    it = {"type": "arcade-quest", "prompt": "Go!", "data": data}
    it.update(extra)
    return {"number": 1, "text": "t", "image": {"prompt": "p"}, "interaction": it}


def run(pages):
    rep = Report()
    w = _world()
    story = _story(pages)
    class S:
        slug = "q"
        data = story
    check_interactivity(rep, w, S())
    return rep, rep.fails


GOOD = {
    "hero": {"skin": "🐉", "control": "flap"},
    "actors": [
        {"name": "sparks", "skin": ["✨", "🔥"], "role": "collect", "motion": "rise", "count": 3},
        {"name": "gull", "skin": "🐦", "role": "dodge", "motion": "chase", "count": 2},
    ],
    "waves": [
        {"line": "here they come", "spawn": [{"name": "sparks", "count": 4}]},
        {"spawn": [{"name": "sparks", "count": 2}, {"name": "gull", "count": 2}]},
    ],
    "finale": {"kind": "bigOne", "skin": "🐋", "line": "the BIG one"},
    "goal": 6,
}


def test_good_quest_passes():
    rep, fails = run([_quest(GOOD)])
    assert not fails, fails
    assert rep.passes >= 1  # "interactions" ok recorded


def test_missing_hero_fails():
    d = dict(GOOD)
    d.pop("hero")
    _, fails = run([_quest(d)])
    assert any("hero" in f for f in fails), fails


def test_missing_actors_fails():
    d = dict(GOOD)
    d.pop("actors")
    _, fails = run([_quest(d)])
    assert any("actor" in f for f in fails), fails


def test_missing_finale_fails():
    d = dict(GOOD)
    d.pop("finale")
    _, fails = run([_quest(d)])
    assert any("finale" in f for f in fails), fails


def test_bad_role_fails():
    d = dict(GOOD)
    d["actors"] = [dict(GOOD["actors"][0], role="explode")]
    _, fails = run([_quest(d)])
    assert any("role" in f for f in fails), fails


def test_bad_motion_fails():
    d = dict(GOOD)
    d["actors"] = [dict(GOOD["actors"][0], motion="teleport")]
    _, fails = run([_quest(d)])
    assert any("motion" in f for f in fails), fails


def test_bad_control_fails():
    d = dict(GOOD)
    d["hero"] = {"skin": "🐉", "control": "rocket"}
    _, fails = run([_quest(d)])
    assert any("control" in f for f in fails), fails


def test_unknown_wave_spawn_fails():
    d = dict(GOOD)
    d["waves"] = [{"spawn": [{"name": "ghosts", "count": 2}]}]
    _, fails = run([_quest(d)])
    assert any("ghosts" in f or "unknown" in f for f in fails), fails


def test_duplicate_actor_names_fail():
    d = dict(GOOD)
    d["actors"] = [GOOD["actors"][0], dict(GOOD["actors"][0])]
    _, fails = run([_quest(d)])
    assert any("unique" in f for f in fails), fails


def test_no_countable_role_fails():
    d = dict(GOOD)
    d["actors"] = [{"name": "rocks", "skin": "🪨", "role": "dodge", "count": 3},
                   {"name": "gnome", "skin": "🎅", "role": "decoy", "count": 1}]
    _, fails = run([_quest(d)])
    assert any("goal" in f for f in fails), fails


def test_bad_finale_kind_fails():
    d = dict(GOOD)
    d["finale"] = {"kind": "explode", "skin": "💣"}
    _, fails = run([_quest(d)])
    assert any("finale" in f for f in fails), fails


def test_quest_counts_as_rich_and_arcade():
    """arcade-quest must be part of the arcade family — no legacy warning, and it
    counts toward the ≥3 kinds-of-fun variety gate."""
    from lib.checks.interactivity import ARCADE_TYPES, LEGACY_TYPES, RICH_TYPES
    assert "arcade-quest" in ARCADE_TYPES
    assert "arcade-quest" not in LEGACY_TYPES
    assert "arcade-quest" in RICH_TYPES


def test_quest_without_feedback_warns():
    rep = Report()
    w = _world()
    story = _story([_quest(GOOD)])
    class S:
        slug = "q"
        data = story
    check_interactivity(rep, w, S())
    assert any("feedback" in m for m in rep.warns), rep.warns