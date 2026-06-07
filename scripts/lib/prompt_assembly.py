"""Assemble a final illustration prompt from the locked world art style + each present
character's appearance_token + palette + negative prompt + seed + reference images.

This is THE consistency lever (methodology/consistency.md). Page image prompts are scene-only;
this module injects identity + style so every image matches. Never hand-write a full prompt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .colors import norm_hex
from .model import World, character_with_stage


@dataclass
class AssembledPrompt:
    prompt: str
    negative: str
    seed: int | None
    aspect_ratio: str
    reference_images: list[str] = field(default_factory=list)
    characters: list[str] = field(default_factory=list)


def _palette_phrase(art_style: dict[str, Any]) -> str:
    swatches = art_style.get("palette", []) or []
    parts = []
    for s in swatches:
        h = norm_hex(s.get("hex"))
        if h:
            parts.append(f"{s.get('name', s.get('role', 'color'))} {h}")
    return ", ".join(parts)


def _story_stage_map(story: dict[str, Any]) -> dict[str, str | None]:
    return {c.get("slug"): c.get("stage") for c in story.get("characters", []) or []}


def assemble_page_prompt(world: World, story: dict[str, Any], page: dict[str, Any]) -> AssembledPrompt:
    art = world.data.get("art_style", {}) or {}
    image = page.get("image", {}) or {}
    scene = image.get("prompt", "").strip()

    stage_map = _story_stage_map(story)
    present = image.get("characters_present", []) or []

    tokens: list[str] = []
    char_palettes: list[str] = []
    refs: list[str] = []
    seed = image.get("seed")
    used_chars: list[str] = []

    for slug in present:
        char = world.characters.get(slug)
        if not char:
            continue
        view = character_with_stage(char, stage_map.get(slug))
        token = view.get("appearance_token")
        if token:
            tokens.append(token)
        used_chars.append(slug)
        for cp in char.get("appearance", {}).get("color_palette", []) or []:
            h = norm_hex(cp.get("hex"))
            if h:
                char_palettes.append(f"{slug} {cp.get('part','')} {h}")
        refs.extend(char.get("reference_images", []) or [])
        if seed is None and char.get("seed") is not None and len(present) == 1:
            seed = char.get("seed")

    # Composition / text-zone note keeps the page's text area low-detail and legible.
    text_zone = image.get("text_zone") or (art.get("text_treatment", {}) or {}).get(
        "placement", "lower third"
    )
    comp_note = (
        f"leave the {text_zone} as calm, low-detail negative space for caption text; "
        "keep characters clear of that zone"
    )

    palette_phrase = _palette_phrase(art)

    segments = [scene]
    if tokens:
        segments.append("Characters: " + " | ".join(tokens))
    if art.get("prompt_style_block"):
        segments.append(art["prompt_style_block"])
    if palette_phrase:
        segments.append("palette: " + palette_phrase)
    if char_palettes:
        segments.append("character colors: " + ", ".join(char_palettes))
    segments.append(comp_note)

    prompt = ". ".join(s.strip().rstrip(".") for s in segments if s and s.strip()) + "."

    return AssembledPrompt(
        prompt=prompt,
        negative=art.get("negative_prompt", "") or "",
        seed=seed,
        aspect_ratio=art.get("aspect_ratio", "4:3"),
        reference_images=refs,
        characters=used_chars,
    )


def assemble_character_sheet_prompt(world: World, char: dict[str, Any]) -> AssembledPrompt:
    """Prompt for a character model/turnaround sheet — locked first, then reused as the
    reference for every page."""
    art = world.data.get("art_style", {}) or {}
    token = char.get("appearance_token", "")
    scene = (
        f"Character model sheet / turnaround of {char.get('name','the character')}: "
        "front, three-quarter, side, and back views at consistent height, plus three facial "
        "expressions, neutral plain background"
    )
    palette_phrase = _palette_phrase(art)
    segments = [scene, f"Character: {token}"]
    if art.get("prompt_style_block"):
        segments.append(art["prompt_style_block"])
    if palette_phrase:
        segments.append("palette: " + palette_phrase)
    prompt = ". ".join(s.strip().rstrip(".") for s in segments if s and s.strip()) + "."
    return AssembledPrompt(
        prompt=prompt,
        negative=art.get("negative_prompt", "") or "",
        seed=char.get("seed"),
        aspect_ratio="3:2",
        reference_images=char.get("reference_images", []) or [],
        characters=[char.get("slug", "")],
    )
