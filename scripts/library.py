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
from lib.readability import story_age_label, world_age_label  # noqa: E402


def main() -> int:
    out = []
    errors: list[str] = []
    for w in load_all_worlds(with_stories=True, errors=errors):
        art = w.data.get("art_style", {}) or {}
        out.append({
            "slug": w.slug,
            "title": w.data.get("title"),
            "tagline": w.data.get("tagline"),
            "premise": w.data.get("premise"),
            "years": w.data.get("target_years", []),
            "audience": world_age_label(w.data),
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
                    # Extra detail for the studio's character popup (all additive).
                    "species": c.get("species"),
                    "pronouns": c.get("pronouns"),
                    "traits": (c.get("personality") or {}).get("traits", []) or [],
                    "motivation": (c.get("personality") or {}).get("motivation"),
                    "flaws": (c.get("personality") or {}).get("flaws", []) or [],
                    "quirks": (c.get("personality") or {}).get("quirks", []) or [],
                    "speech_style": (c.get("voice") or {}).get("speech_style"),
                    "catchphrases": (c.get("voice") or {}).get("catchphrases", []) or [],
                    "evolution": [
                        {"stage": st.get("stage"), "summary": st.get("summary")}
                        for st in c.get("evolution", []) or []
                    ],
                    # First reference image's filename — the site build copies it to
                    # world/<wslug>/refs/<cslug>-<filename>, which the UI links to.
                    "reference": (
                        Path(str((c.get("reference_images") or [None])[0])).name
                        if c.get("reference_images") else None
                    ),
                }
                for c in w.characters.values()
            ],
            "stories": [
                {
                    "slug": s.slug,
                    "title": s.data.get("title"),
                    "logline": s.data.get("logline"),
                    "target_year": s.data.get("target_year"),
                    "age": story_age_label(s.data),
                    "status": s.data.get("status", "draft"),
                    "tags": s.data.get("tags", []),
                    "pages": len(s.data.get("pages", []) or []),
                    "interactions": len([p for p in s.data.get("pages", []) or [] if p.get("interaction")]),
                }
                for s in w.stories
            ],
        })
    print(json.dumps({"worlds": out, "errors": errors}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
