"""Composable QA checkers for worlds and stories.

Each module holds one focused invariant and exposes ``check_*(rep, …)`` functions
that append findings to a shared :class:`~lib.checks.report.Report`. The runner
(``scripts/validate.py``) and the quality scorecard compose them; tests exercise
each in isolation with a fresh ``Report``.
"""
from __future__ import annotations

from .accessibility import check_accessibility
from .color import check_color_consistency
from .consistency import (check_character_tokens, check_relationships,
                          check_story_roster, check_world_style)
from .illustration import check_illustration, check_render_readiness
from .interactivity import INTERACTION_DATA_KEYS, PILLARS, check_interactivity
from .publish import check_publish_gate
from .reading import check_reading
from .report import Report
from .schema import load_schema, schema_check
from .tokens import check_appearance_token
from .voice import check_voice
from .world_rules import check_world_rules

__all__ = [
    "Report",
    "INTERACTION_DATA_KEYS",
    "PILLARS",
    "load_schema",
    "schema_check",
    "check_world_style",
    "check_character_tokens",
    "check_relationships",
    "check_color_consistency",
    "check_appearance_token",
    "check_story_roster",
    "check_reading",
    "check_interactivity",
    "check_accessibility",
    "check_illustration",
    "check_render_readiness",
    "check_voice",
    "check_world_rules",
    "check_publish_gate",
]
