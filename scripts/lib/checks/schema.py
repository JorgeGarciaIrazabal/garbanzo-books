"""JSON-Schema validation against schemas/<kind>.schema.json.

Reads the schema directory dynamically from ``lib.model.SCHEMAS`` (rather than
binding it at import time) so tests that repoint ``model.SCHEMAS`` at an isolated
workspace are honoured. Degrades gracefully — a missing ``jsonschema`` or schema
file becomes a warning, never a crash, so the toolchain still runs offline.
"""
from __future__ import annotations

import json
from typing import Any

from .. import model
from .report import Report

try:
    from jsonschema import Draft202012Validator
    HAVE_JSONSCHEMA = True
except Exception:  # noqa: BLE001
    HAVE_JSONSCHEMA = False


def load_schema(name: str) -> dict | None:
    p = model.SCHEMAS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def schema_check(rep: Report, data: dict[str, Any], schema_name: str, where: str) -> None:
    if not HAVE_JSONSCHEMA:
        rep.warn(f"jsonschema not installed — skipped schema check for {where} (pip install jsonschema)")
        return
    schema = load_schema(schema_name)
    if not schema:
        rep.warn(f"schema {schema_name} missing")
        return
    errs = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
    if errs:
        for e in errs[:10]:
            loc = "/".join(str(p) for p in e.path) or "(root)"
            rep.fail(f"[schema] {where}: {loc}: {e.message}")
    else:
        rep.ok(f"schema {where}")
