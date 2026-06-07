"""Unit tests for the new consistency / quality checkers under ``scripts/lib/checks``.

Each checker is exercised in isolation with an in-memory ``World``/``Story`` and a
fresh ``Report`` — the same style as ``test_prompt_assembly`` — so a failure points
straight at one invariant.
"""
from __future__ import annotations

from lib.checks import (Report, check_appearance_token, check_color_consistency,
                        check_interactivity, check_publish_gate, check_reading,
                        check_relationships, check_render_readiness, check_voice,
                        check_world_rules)
from lib.model import Story, World


def _world(factories, characters=None):
    wdata = factories.world(slug="ww")
    chars = {c["slug"]: c for c in (characters or [factories.character(slug="hero", world="ww")])}
    return World(slug="ww", data=wdata, path=None, characters=chars)


def _story(factories, **overrides):
    return Story(slug="s1", data=factories.story(slug="s1", world="ww", **overrides), path=None)


# ----------------------------------------------------------------- A5 colour consistency
def test_color_consistency_warns_on_token_hex_not_in_palette(factories):
    rep = Report()
    c = factories.character(slug="hero", world="ww")
    # token mentions a green the palette doesn't lock
    c["appearance_token"] = "HERO: red coat (#c0392b), green scarf (#11aa22)"
    c["appearance"]["color_palette"] = [{"part": "coat", "hex": "#c0392b"}]
    w = _world(factories, characters=[c])
    check_color_consistency(rep, w)
    assert any("#11aa22" in warn for warn in rep.warns)


def test_color_consistency_quiet_when_token_hexes_all_in_palette(factories):
    rep = Report()
    w = _world(factories)  # factory token hexes match its palette
    check_color_consistency(rep, w)
    assert rep.warns == []


# ----------------------------------------------------------------- B1 relationship integrity
def test_relationship_to_unknown_character_fails(factories):
    rep = Report()
    c = factories.character(slug="hero", world="ww")
    c["relationships"] = [{"character": "ghost", "relation": "friend"}]
    w = _world(factories, characters=[c])
    check_relationships(rep, w)
    assert any("ghost" in f and "consistency" in f for f in rep.fails)


def test_relationship_to_known_character_passes(factories):
    rep = Report()
    hero = factories.character(slug="hero", world="ww")
    pal = factories.character(slug="pal", world="ww")
    hero["relationships"] = [{"character": "pal", "relation": "friend"}]
    w = _world(factories, characters=[hero, pal])
    check_relationships(rep, w)
    assert rep.fails == []


# ----------------------------------------------------------------- B3 appearance_token contract
def test_token_without_hex_warns(factories):
    rep = Report()
    c = factories.character(slug="hero", world="ww")
    c["appearance_token"] = "HERO: a small round hero who is brave and kind and curious always"
    w = _world(factories, characters=[c])
    check_appearance_token(rep, w)
    assert any("no hex" in warn for warn in rep.warns)


def test_token_with_placeholder_warns(factories):
    rep = Report()
    c = factories.character(slug="hero", world="ww")
    c["appearance_token"] = "HERO: TODO red coat (#c0392b) fill in the rest of this descriptor"
    w = _world(factories, characters=[c])
    check_appearance_token(rep, w)
    assert any("placeholder" in warn for warn in rep.warns)


def test_strong_token_is_quiet(factories):
    rep = Report()
    w = _world(factories)  # factory token has hexes and is long enough
    check_appearance_token(rep, w)
    assert rep.warns == []


# ----------------------------------------------------------------- A1 voice consistency
def test_voice_warns_when_catchphrase_never_used(factories):
    rep = Report()
    c = factories.character(slug="hero", world="ww")
    c["voice"]["catchphrases"] = ["Onward and acorns!"]
    w = _world(factories, characters=[c])
    st = _story(factories)  # factory pages never say it
    check_voice(rep, w, st)
    assert any("catchphrase" in warn for warn in rep.warns)


def test_voice_quiet_when_catchphrase_used_despite_punctuation(factories):
    rep = Report()
    c = factories.character(slug="hero", world="ww")
    c["voice"]["catchphrases"] = ["Onward and acorns!"]
    w = _world(factories, characters=[c])
    st = _story(factories)
    st.data["pages"][1]["text"] = "Hero grinned. onward, and ACORNS — let's go!"
    check_voice(rep, w, st)
    assert not any("catchphrase" in warn for warn in rep.warns)


def test_voice_warns_on_gentle_character_shouting(factories):
    rep = Report()
    c = factories.character(slug="hero", world="ww")
    c["voice"]["speech_style"] = "soft, gentle, almost a whisper"
    w = _world(factories, characters=[c])
    st = _story(factories)
    st.data["pages"][1]["text"] = "STOP RIGHT NOW, said the hero."  # hero is alone on p1
    check_voice(rep, w, st)
    assert any("shouts" in warn for warn in rep.warns)


def test_voice_does_not_attribute_when_two_characters_share_the_page(factories):
    rep = Report()
    hero = factories.character(slug="hero", world="ww")
    hero["voice"]["speech_style"] = "soft and gentle"
    pal = factories.character(slug="pal", world="ww")
    w = _world(factories, characters=[hero, pal])
    st = _story(factories, characters=[{"slug": "hero"}, {"slug": "pal"}])
    st.data["pages"][1]["image"]["characters_present"] = ["hero", "pal"]
    st.data["pages"][1]["text"] = "STOP THAT NOISE!"
    check_voice(rep, w, st)
    assert not any("shouts" in warn for warn in rep.warns)


# ----------------------------------------------------------------- A2 world-rule affirmation
def test_world_rules_unknown_id_fails(factories):
    rep = Report()
    w = _world(factories)
    w.data["rules"] = ["magic is gentle", "kindness wins"]
    st = _story(factories, affirms_rules=["r9"])
    check_world_rules(rep, w, st)
    assert any("r9" in f for f in rep.fails)


def test_world_rules_valid_id_passes(factories):
    rep = Report()
    w = _world(factories)
    w.data["rules"] = ["magic is gentle", "kindness wins"]
    st = _story(factories, affirms_rules=["r1"])
    check_world_rules(rep, w, st)
    assert rep.fails == []


def test_published_story_affirming_no_rules_warns(factories):
    rep = Report()
    w = _world(factories)
    w.data["rules"] = ["magic is gentle"]
    st = _story(factories, status="published")
    check_world_rules(rep, w, st)
    assert any("affirms no world rules" in warn for warn in rep.warns)


def test_world_rules_support_explicit_ids(factories):
    rep = Report()
    w = _world(factories)
    w.data["rules"] = [{"id": "gentle-magic", "text": "magic is gentle"}]
    st = _story(factories, affirms_rules=["gentle-magic"])
    check_world_rules(rep, w, st)
    assert rep.fails == []


# ----------------------------------------------------------------- B2 interaction feedback
def test_skill_practice_interaction_without_feedback_warns(factories):
    rep = Report()
    w = _world(factories)
    st = _story(factories)
    st.data["pages"][1]["interaction"] = {
        "type": "rhyme-complete", "prompt": "finish it", "skill": "phonics",
        "data": {"answer": "cat"},
    }
    check_interactivity(rep, w, st)
    assert any("no feedback" in warn for warn in rep.warns)


def test_skill_practice_interaction_with_feedback_is_quiet_about_feedback(factories):
    rep = Report()
    w = _world(factories)
    st = _story(factories)
    st.data["pages"][1]["interaction"] = {
        "type": "rhyme-complete", "prompt": "finish it", "skill": "phonics",
        "data": {"answer": "cat"}, "feedback": {"correct": "Yes!", "try_again": "Try again"},
    }
    check_interactivity(rep, w, st)
    assert not any("no feedback" in warn for warn in rep.warns)


# ----------------------------------------------------------------- B2 decodable focus
def test_decodable_without_focus_warns(factories):
    rep = Report()
    w = _world(factories)
    st = _story(factories)
    st.data["reading_level"]["decodable"] = True
    st.data["reading_level"]["decoding_focus"] = ""
    check_reading(rep, w, st)
    assert any("decoding_focus is empty" in warn for warn in rep.warns)


# ----------------------------------------------------------------- A4 render readiness
def test_recurring_character_without_reference_images_warns(factories):
    rep = Report()
    c = factories.character(slug="hero", world="ww")
    c["reference_images"] = []
    w = _world(factories, characters=[c])
    st = _story(factories)  # hero appears on pages 1 and 2
    check_render_readiness(rep, w, st)
    assert any("no reference_images" in warn for warn in rep.warns)


def test_recurring_character_without_seed_warns(factories):
    rep = Report()
    c = factories.character(slug="hero", world="ww")
    c["reference_images"] = ["hero.refs/sheet.png"]
    c["seed"] = None
    w = _world(factories, characters=[c])
    st = _story(factories)
    check_render_readiness(rep, w, st)
    assert any("no locked seed" in warn for warn in rep.warns)


def test_one_off_character_does_not_trigger_readiness_warning(factories):
    rep = Report()
    c = factories.character(slug="hero", world="ww")
    c["reference_images"] = []
    c["seed"] = None
    w = _world(factories, characters=[c])
    st = _story(factories)
    # hero appears on only ONE page → a cameo, not a recurring identity
    st.data["pages"][2]["image"]["characters_present"] = []
    check_render_readiness(rep, w, st)
    assert rep.warns == []


# ----------------------------------------------------------------- publish gate scoping
def test_publish_gate_scopes_failures_to_this_story(factories):
    """A failure belonging to a *different* book must not trip this story's publish gate."""
    rep = Report()
    rep.fail("[illustration] other-world/other-story p3: image file 'x.png' not found")
    w = _world(factories)
    st = _story(factories, status="published", cover={"image": "images/cover.png"})
    check_publish_gate(rep, w, st)
    assert not any("[publish]" in f for f in rep.fails)


def test_publish_gate_fires_on_own_failure(factories):
    rep = Report()
    rep.fail("[consistency] ww/s1: references missing character 'ghost'")
    w = _world(factories)
    st = _story(factories, status="published", cover={"image": "images/cover.png"})
    check_publish_gate(rep, w, st)
    assert any("[publish]" in f for f in rep.fails)


def test_published_without_cover_warns_not_fails(factories):
    rep = Report()
    w = _world(factories)
    st = _story(factories, status="published", cover={"image": ""})
    check_publish_gate(rep, w, st)
    assert any("no cover image" in warn for warn in rep.warns)
    assert not any("[publish]" in f for f in rep.fails)
