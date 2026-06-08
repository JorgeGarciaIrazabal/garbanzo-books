"""Tests for ``scripts/quality_report.py`` — the 7-gate quality scorecard.

Each gate is exercised from a schema-valid factory story that is mutated to fail one
gate at a time, so a regression points straight at the offending gate.
"""
from __future__ import annotations

import quality_report as qr
from lib.model import Story, World


def _world(factories, characters=None):
    wdata = factories.world(slug="ww")
    chars = {c["slug"]: c for c in (characters or [factories.character(slug="hero", world="ww")])}
    return World(slug="ww", data=wdata, path=None, characters=chars)


def _story(factories, **overrides):
    return Story(slug="s1", data=factories.story(slug="s1", world="ww", **overrides), path=None)


def _gate(gates, name):
    return next(g for g in gates if g.name == name)


def _full_story(factories):
    """A story rich enough to pass every gate, for one-failure-at-a-time tests.
    Fun-first: the games are VARIED kinds of fun and include rich (non-quiz) ones."""
    pages = [{"number": 0, "kind": "title", "text": "T", "image": {"prompt": "t", "alt": "t", "file": "images/p0.png"}}]
    games = {
        3: {"type": "rhyme-complete", "data": {"answer": "x"}},
        7: {"type": "drag-sort", "data": {"bins": [{"label": "In", "key": "in"}],
                                          "items": [{"label": "sock", "bin": "in"}]}},
        11: {"type": "sequence-recall", "data": {"sequence": ["A", "B", "C"]}},
    }
    for i in range(1, 13):
        page = {
            "number": i, "kind": "story", "text": "The hero ran fast and had fun today.",
            "image": {"prompt": "scene", "characters_present": ["hero"], "alt": "a", "file": f"images/p{i}.png"},
            "layout": {"text_position": "lower-third"},
        }
        if i in games:
            page["interaction"] = {"prompt": "go", "skill": "engagement",
                                   "feedback": {"correct": "Yes!", "try_again": "Again"}, **games[i]}
        pages.append(page)
    return _story(factories, pages=pages, cover={"image": "images/cover.png"})


def test_full_story_scores_all_gates(factories):
    char = factories.character(slug="hero", world="ww")
    char["reference_images"] = ["hero.refs/sheet.png"]
    char["seed"] = 42
    w = _world(factories, characters=[char])
    gates = qr.score_story(w, _full_story(factories))
    passed, total, label = qr.grade(gates)
    assert passed == total == 7
    assert label == "excellent"


def test_premise_gate_warns_on_thin_logline(factories):
    w = _world(factories)
    st = _story(factories, logline="Hi.")
    assert _gate(qr.score_story(w, st), "Premise & hook").ok is False


def test_spine_gate_warns_when_beats_missing(factories):
    w = _world(factories)
    st = _story(factories)
    st.data["spine"]["until_finally"] = ""
    assert _gate(qr.score_story(w, st), "Story spine").ok is False


def test_manuscript_gate_warns_when_page_over_cap(factories):
    w = _world(factories)
    st = _story(factories)
    st.data["pages"][1]["text"] = " ".join(["word"] * 200)
    assert _gate(qr.score_story(w, st), "Manuscript length").ok is False


def test_pacing_gate_warns_when_no_interactions(factories):
    w = _world(factories)
    st = _story(factories)  # factory story has no interactions
    assert _gate(qr.score_story(w, st), "Pacing & page-turns").ok is False


def test_character_art_gate_warns_without_reference(factories):
    char = factories.character(slug="hero", world="ww")
    char["reference_images"] = []
    w = _world(factories, characters=[char])
    assert _gate(qr.score_story(w, _full_story(factories)), "Character art").ok is False


def test_engagement_gate_warns_when_all_games_are_quizzes(factories):
    """Fun-first: a book whose every game is the same pick-an-answer quiz fails the gate —
    it lacks variety AND lacks a rich game a kid actually DOES."""
    char = factories.character(slug="hero", world="ww")
    char["reference_images"] = ["x.png"]
    w = _world(factories, characters=[char])
    st = _full_story(factories)
    for p in st.data["pages"]:
        if p.get("interaction"):
            p["interaction"]["type"] = "comprehension-question"  # collapse to one quiz type
            p["interaction"]["data"] = {"question": "?", "options": ["a", "b"], "answer_index": 0}
    assert _gate(qr.score_story(w, st), "Fun & games").ok is False


def test_finish_gate_warns_without_cover(factories):
    w = _world(factories)
    st = _full_story(factories)
    st.data["cover"] = {"image": ""}
    assert _gate(qr.score_story(w, st), "Accessibility & finish").ok is False


def test_grade_labels_scale_with_passes(factories):
    from quality_report import Gate
    allpass = [Gate("g", True, "") for _ in range(7)]
    assert qr.grade(allpass)[2] == "excellent"
    half = [Gate("g", i < 4, "") for i in range(7)]
    assert qr.grade(half)[2] == "developing"
