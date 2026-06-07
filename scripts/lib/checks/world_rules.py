"""World-rule consistency (Core Principle #2: the world's rules are inviolable).

World ``rules`` are prose ("magic is gentle and small"), so they can't be checked
literally. Instead we give them a traceable hook: a story may declare
``affirms_rules: [<rule-id>]`` to say "this book engages these laws of the world."
The checker then verifies the references resolve, and nudges a *published* book to
affirm at least one rule — so adherence becomes a reviewable, surfaced fact rather
than a hope. Rule ids come from ``model.normalize_rules`` (positional ``r1, r2…``
for plain-string rules, or an explicit ``id`` on mapping-form rules).
"""
from __future__ import annotations

from typing import Any

from ..model import normalize_rules
from .report import Report


def check_world_rules(rep: Report, world: Any, story: Any) -> None:
    s = story.data
    where = f"{world.slug}/{story.slug}"
    rule_ids = {r["id"] for r in normalize_rules(world.data)}
    affirmed = s.get("affirms_rules", []) or []

    for rid in affirmed:
        if rid not in rule_ids:
            rep.fail(f"[consistency] {where}: affirms_rules references unknown world rule '{rid}'")

    valid = [rid for rid in affirmed if rid in rule_ids]
    if s.get("status") == "published" and rule_ids and not valid:
        rep.warn(f"{where}: published but affirms no world rules — add affirms_rules so adherence "
                 "to the world's laws is traceable")
    elif valid:
        rep.ok(f"world-rule affirmation {where}")
