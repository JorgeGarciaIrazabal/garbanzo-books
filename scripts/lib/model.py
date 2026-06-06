"""Loading, locating, and slugging worlds / characters / stories.

The whole toolchain agrees on this layout (see CLAUDE.md):

    worlds/<world>/world.yaml
    worlds/<world>/style-guide.md
    worlds/<world>/characters/<char>.yaml
    worlds/<world>/stories/<story>/story.yaml
    worlds/<world>/stories/<story>/images/
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Repo root = two levels up from this file (scripts/lib/model.py -> repo).
ROOT = Path(__file__).resolve().parents[2]
WORLDS = ROOT / "worlds"
SCHEMAS = ROOT / "schemas"


def load_dotenv(path: Path | None = None) -> None:
    """Minimal, dependency-free .env loader. Populates os.environ for keys not already set.
    Lines like KEY=value; ignores blanks and # comments. Quotes are stripped."""
    import os
    envp = path or (ROOT / ".env")
    if not envp.exists():
        return
    for line in envp.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def slugify(text: str) -> str:
    """Lower-case, kebab-case, ASCII-ish slug."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def dump_yaml(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True, width=100)


@dataclass
class Story:
    slug: str
    data: dict[str, Any]
    path: Path  # the story.yaml path

    @property
    def dir(self) -> Path:
        return self.path.parent

    @property
    def images_dir(self) -> Path:
        return self.dir / "images"


@dataclass
class World:
    slug: str
    data: dict[str, Any]
    path: Path  # the world.yaml path
    characters: dict[str, dict[str, Any]] = field(default_factory=dict)
    stories: list[Story] = field(default_factory=list)

    @property
    def dir(self) -> Path:
        return self.path.parent


def world_dir(slug: str) -> Path:
    return WORLDS / slug


def load_world(slug: str, *, with_stories: bool = True) -> World:
    wdir = world_dir(slug)
    wpath = wdir / "world.yaml"
    if not wpath.exists():
        raise FileNotFoundError(f"No world.yaml for world '{slug}' at {wpath}")
    world = World(slug=slug, data=load_yaml(wpath), path=wpath)

    cdir = wdir / "characters"
    if cdir.is_dir():
        for cpath in sorted(cdir.glob("*.yaml")):
            cdata = load_yaml(cpath)
            world.characters[cdata.get("slug", cpath.stem)] = cdata

    if with_stories:
        sdir = wdir / "stories"
        if sdir.is_dir():
            for spath in sorted(sdir.glob("*/story.yaml")):
                sdata = load_yaml(spath)
                world.stories.append(
                    Story(slug=sdata.get("slug", spath.parent.name), data=sdata, path=spath)
                )
    return world


def all_world_slugs() -> list[str]:
    if not WORLDS.is_dir():
        return []
    return sorted(p.name for p in WORLDS.iterdir() if (p / "world.yaml").exists())


def load_all_worlds(*, with_stories: bool = True) -> list[World]:
    return [load_world(s, with_stories=with_stories) for s in all_world_slugs()]


def find_story(world_slug: str, story_slug: str) -> Story:
    spath = WORLDS / world_slug / "stories" / story_slug / "story.yaml"
    if not spath.exists():
        raise FileNotFoundError(f"No story.yaml at {spath}")
    data = load_yaml(spath)
    return Story(slug=data.get("slug", story_slug), data=data, path=spath)


def character_with_stage(character: dict[str, Any], stage_id: str | None) -> dict[str, Any]:
    """Return a shallow view of a character with the given evolution stage applied:
    the stage's appearance_delta is appended to the appearance_token. Core identity is
    preserved; only the active stage extends it."""
    if not stage_id:
        return character
    for stage in character.get("evolution", []) or []:
        if stage.get("stage") == stage_id:
            view = dict(character)
            delta = stage.get("appearance_delta")
            if delta:
                view["appearance_token"] = (
                    f"{character.get('appearance_token', '')} [{stage_id}: {delta}]"
                )
            return view
    return character
