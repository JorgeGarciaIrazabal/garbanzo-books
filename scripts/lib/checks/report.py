"""The shared findings accumulator used by every checker.

A ``Report`` collects three kinds of finding:

* **pass**  — an invariant held (counted, not stored; keeps the summary honest).
* **fail**  — a hard violation that blocks publishing.
* **warn**  — an advisory: something to look at, but not a blocker.

Every checker under ``lib.checks`` takes a ``Report`` and appends to it, so the
runner (``scripts/validate.py``) can compose them in any order and print one
summary. Keeping this tiny and dependency-free means each checker is trivially
unit-testable: hand it a fresh ``Report`` and assert on ``.fails`` / ``.warns``.
"""
from __future__ import annotations


class Report:
    def __init__(self) -> None:
        self.passes = 0
        self.fails: list[str] = []
        self.warns: list[str] = []

    def ok(self, msg: str) -> None:
        self.passes += 1

    def fail(self, msg: str) -> None:
        self.fails.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)
