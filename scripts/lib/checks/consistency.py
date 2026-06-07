"""Cross-reference and identity consistency: the locked style block, every
referenced character existing and carrying its appearance_token, evolution stages
resolving, and character relationships pointing at real castmates.

These are the invariants behind Core Principle #1/#2 (consistency is assembled,
personality is a contract): if a story names a character the world doesn't have,
or pins them to a stage that was never defined, the book can't render on-model.
"""
from __future__ import annotations

from typing import Any

from .report import Report


def check_world_style(rep: Report, world: Any) -> None:
    """The world's locked art-style levers must be present (style won't lock without them)."""
    art = world.data.get("art_style", {}) or {}
    if not art.get("prompt_style_block"):
        rep.fail(f"[consistency] world {world.slug}: art_style.prompt_style_block missing (style won't lock)")
    else:
        rep.ok("style block")
    if not art.get("palette"):
        rep.fail(f"[consistency] world {world.slug}: art_style.palette empty")


def check_character_tokens(rep: Report, world: Any) -> None:
    """Every character in the world must carry a non-placeholder appearance_token."""
    for cslug, c in world.characters.items():
        if not c.get("appearance_token"):
            rep.fail(f"[consistency] character {cslug}: appearance_token missing (visual consistency lever)")
        elif "TODO" in c.get("appearance_token", ""):
            rep.warn(f"character {cslug}: appearance_token still has TODO")
        else:
            rep.ok(f"appearance_token {cslug}")


def check_relationships(rep: Report, world: Any) -> None:
    """Character relationships must point at characters that exist in the world."""
    for cslug, c in world.characters.items():
        for rel in c.get("relationships", []) or []:
            target = rel.get("character")
            if target and target not in world.characters:
                rep.fail(f"[consistency] character {cslug}: relationship target '{target}' "
                         "is not a character in this world")


def check_story_roster(rep: Report, world: Any, story: Any) -> None:
    """Story roster + per-page image characters resolve to real, tokened characters
    at valid evolution stages."""
    s = story.data
    where = f"{world.slug}/{story.slug}"
    pages = s.get("pages", []) or []

    roster = {c.get("slug"): c for c in s.get("characters", []) or []}
    for slug, entry in roster.items():
        ch = world.characters.get(slug)
        if not ch:
            rep.fail(f"[consistency] {where}: references missing character '{slug}'")
            continue
        if not ch.get("appearance_token"):
            rep.fail(f"[consistency] {where}: character '{slug}' has no appearance_token")
        stage = entry.get("stage")
        if stage:
            stages = {st.get("stage") for st in ch.get("evolution", []) or []}
            if stage not in stages and stage != "base":
                rep.fail(f"[consistency] {where}: character '{slug}' pinned to unknown stage '{stage}'")

    for p in pages:
        for cp in (p.get("image", {}) or {}).get("characters_present", []) or []:
            if cp not in world.characters:
                rep.fail(f"[consistency] {where} p{p.get('number')}: image character '{cp}' not in world")
    if roster:
        rep.ok(f"character roster {where}")
