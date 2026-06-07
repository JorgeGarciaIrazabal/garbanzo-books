"""Tests for ``scripts/lib/colors.py`` — the shared hex-colour helpers that back
prompt assembly, the site build, placeholders, and the colour-consistency check.
"""
from __future__ import annotations

from lib.colors import (DEFAULT_PALETTE, character_hexes, hexes_in_text, norm_hex,
                        palette_hexes)


def test_norm_hex_normalises_case_and_hash():
    assert norm_hex("#C0392B") == "#c0392b"
    assert norm_hex("c0392b") == "#c0392b"


def test_norm_hex_rejects_bad_values():
    assert norm_hex("") is None
    assert norm_hex(None) is None
    assert norm_hex("#fff") is None  # 3-digit not accepted
    assert norm_hex("nothex!") is None


def test_palette_hexes_extracts_in_order():
    art = {"palette": [{"hex": "#f4e1c1"}, {"hex": "6b8f71"}, {"hex": "bad"}]}
    assert palette_hexes(art) == ["#f4e1c1", "#6b8f71"]


def test_palette_hexes_fallback_only_when_requested():
    assert palette_hexes({"palette": []}) == []
    assert palette_hexes(None, fallback=True) == DEFAULT_PALETTE


def test_hexes_in_text_pulls_all_mentions_lowercased():
    token = "HERO: red coat (#C0392B), yellow boots (#F1C40F), no third colour here"
    assert hexes_in_text(token) == {"#c0392b", "#f1c40f"}


def test_character_hexes_reads_color_palette():
    ch = {"appearance": {"color_palette": [{"part": "coat", "hex": "#c0392b"},
                                           {"part": "boots", "hex": "#F1C40F"}]}}
    assert character_hexes(ch) == {"#c0392b", "#f1c40f"}
