#!/usr/bin/env python3
"""Emit the whole workspace (worlds -> characters -> stories) as JSON, for the UI to render.

Usage: python scripts/library.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.model import load_all_worlds  # noqa: E402


def main() -> int:
    out = []
    for w in load_all_worlds(with_stories=True):
        art = w.data.get("art_style", {}) or {}
        out.append({
            "slug": w.slug,
            "title": w.data.get("title"),
            "tagline": w.data.get("tagline"),
            "premise": w.data.get("premise"),
            "age_bands": w.data.get("target_age_bands", []),
            "themes": w.data.get("themes", []),
            "palette": [
                {"name": s.get("name"), "hex": "#" + str(s.get("hex", "")).lstrip("#")}
                for s in art.get("palette", []) or []
            ],
            "characters": [
                {
                    "slug": c.get("slug"),
                    "name": c.get("name"),
                    "role": c.get("role"),
                    "one_liner": c.get("one_liner"),
                    "stages": [st.get("stage") for st in c.get("evolution", []) or []],
                    "has_reference": bool(c.get("reference_images")),
                }
                for c in w.characters.values()
            ],
            "stories": [
                {
                    "slug": s.slug,
                    "title": s.data.get("title"),
                    "logline": s.data.get("logline"),
                    "age_band": s.data.get("age_band"),
                    "status": s.data.get("status", "draft"),
                    "tags": s.data.get("tags", []),
                    "pages": len(s.data.get("pages", []) or []),
                    "interactions": len([p for p in s.data.get("pages", []) or [] if p.get("interaction")]),
                }
                for s in w.stories
            ],
        })
    print(json.dumps({"worlds": out}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
