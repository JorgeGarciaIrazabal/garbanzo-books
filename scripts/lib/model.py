"""Loading, locating, and slugging worlds / characters / stories.

The whole toolchain agrees on this layout (see CLAUDE.md):

    worlds/<world>/world.yaml
    worlds/<world>/style-guide.md
    worlds/<world>/characters/<char>.yaml
    worlds/<world>/stories/<story>/story.yaml
    worlds/<world>/stories/<story>/images/
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Repo root = two levels up from this file (scripts/lib/model.py -> repo).
ROOT = Path(__file__).resolve().parents[2]
WORLDS = ROOT / "worlds"
SCHEMAS = ROOT / "schemas"


class ContentError(Exception):
    """A world/character/story file is unreadable or malformed. Carries a human-readable,
    path-prefixed message so callers can skip the one bad file instead of crashing everything."""


def _rel(p: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except Exception:
        return str(p)


def load_dotenv(path: Path | None = None) -> None:
    """Minimal, dependency-free .env loader. Populates os.environ for keys that are unset OR
    present-but-blank. Lines like KEY=value; ignores blanks and # comments. Quotes are stripped.

    The blank-override matters: a parent process (e.g. the studio server / OpenCode) may export an
    EMPTY GEMINI_API_KEY, which would otherwise shadow the real value in .env and silently force
    placeholder art. A non-empty exported value still wins (real environment beats .env)."""
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
        if key and not os.environ.get(key):  # unset or empty → take it from .env
            os.environ[key] = val


# Auto-load .env the moment this module is imported, so EVERY script that uses the data model has
# credentials (GEMINI_API_KEY, IMAGE_PROVIDER, …) available without remembering to call it itself.
# Idempotent and cheap; a real exported value still wins (see load_dotenv).
load_dotenv()


def slugify(text: str) -> str:
    """Lower-case, kebab-case, ASCII-ish slug."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def load_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML mapping. Raises ContentError (not a raw traceback) on malformed YAML or a
    non-mapping top level, so callers can report/skip one bad file cleanly. Missing file still
    raises FileNotFoundError (a different, expected condition)."""
    p = Path(path)
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError:
        raise
    except (yaml.YAMLError, UnicodeDecodeError) as e:
        raise ContentError(f"{_rel(p)} is not valid YAML: {str(e).splitlines()[0] if str(e) else e}") from e
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ContentError(f"{_rel(p)} must be a YAML mapping, got {type(data).__name__}")
    return data


def dump_yaml(data: dict[str, Any], path: Path) -> None:
    """Write YAML *safely*: serialize, re-parse to guarantee it's well-formed, then write to a temp
    file in the same directory and atomically rename into place. This makes a half-written or
    unparseable file impossible — a reader either sees the previous good file or the new good one,
    never a truncated/corrupt one. This is the write-time guardrail for the whole workspace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
    try:
        yaml.safe_load(text)  # never commit something we can't read back
    except yaml.YAMLError as e:  # pragma: no cover - safe_dump output should always parse
        raise ContentError(f"refusing to write {_rel(path)}: produced invalid YAML ({e})") from e
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)  # atomic on POSIX
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def validate_content(kind: str, data: dict[str, Any]) -> None:
    """Best-effort schema guardrail used at write time. Raises ContentError if `data` violates
    schemas/<kind>.schema.json. No-op if jsonschema or the schema file is unavailable, so it never
    blocks offline use. kind in {world, character, story}."""
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return
    import json
    sp = SCHEMAS / f"{kind}.schema.json"
    if not sp.exists():
        return
    schema = json.loads(sp.read_text(encoding="utf-8"))
    errs = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
    if errs:
        e = errs[0]
        loc = "/".join(str(x) for x in e.path) or "(root)"
        raise ContentError(f"{kind} is not schema-valid at {loc}: {e.message}")


@dataclass
class Story:
    slug: str
    data: dict[str, Any]
    path: Path  # the story.yaml path
    included: bool = True  # set by build_site to mark stories in the current build (drafts toggle)

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
    errors: list[str] = field(default_factory=list)  # malformed characters/stories that were skipped

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
            try:
                cdata = load_yaml(cpath)
            except ContentError as e:  # one bad character must not sink the whole world
                world.errors.append(str(e))
                continue
            world.characters[cdata.get("slug", cpath.stem)] = cdata

    if with_stories:
        sdir = wdir / "stories"
        if sdir.is_dir():
            for spath in sorted(sdir.glob("*/story.yaml")):
                try:
                    sdata = load_yaml(spath)
                except ContentError as e:  # one half-written story must not sink the world
                    world.errors.append(str(e))
                    continue
                world.stories.append(
                    Story(slug=sdata.get("slug", spath.parent.name), data=sdata, path=spath)
                )
    return world


def all_world_slugs() -> list[str]:
    if not WORLDS.is_dir():
        return []
    return sorted(p.name for p in WORLDS.iterdir() if (p / "world.yaml").exists())


def load_all_worlds(*, with_stories: bool = True, errors: list[str] | None = None) -> list[World]:
    """Load every world, resiliently: a world whose world.yaml is unreadable is skipped (not
    fatal), and any malformed character/story inside a world is skipped too. Problems are appended
    to `errors` (if given) and echoed to stderr, so the caller can surface them while still showing
    every good world. One broken file can never blank out the whole library again."""
    worlds: list[World] = []
    for s in all_world_slugs():
        try:
            w = load_world(s, with_stories=with_stories)
        except (ContentError, FileNotFoundError) as e:
            msg = f"world '{s}': {e}"
            if errors is not None:
                errors.append(msg)
            print(f"  ! skipped {msg}", file=sys.stderr)
            continue
        for em in w.errors:
            if errors is not None:
                errors.append(em)
            print(f"  ! {em}", file=sys.stderr)
        worlds.append(w)
    return worlds


def find_story(world_slug: str, story_slug: str) -> Story:
    spath = WORLDS / world_slug / "stories" / story_slug / "story.yaml"
    if not spath.exists():
        raise FileNotFoundError(f"No story.yaml at {spath}")
    data = load_yaml(spath)
    return Story(slug=data.get("slug", story_slug), data=data, path=spath)


def normalize_rules(world_data: dict[str, Any]) -> list[dict[str, str]]:
    """Return the world's ``rules`` as a list of ``{"id", "text"}`` dicts.

    Rules may be authored two ways and both are supported so existing worlds keep
    working: a plain string (gets a positional id ``r1``, ``r2``, …) or a mapping
    ``{id?, text}`` (an explicit, stable id the author can reference from a story's
    ``affirms_rules``). This is the bridge that makes prose world-rules
    machine-affirmable without forcing anyone to rewrite them.
    """
    out: list[dict[str, str]] = []
    for i, rule in enumerate(world_data.get("rules", []) or [], start=1):
        if isinstance(rule, dict):
            text = str(rule.get("text", "")).strip()
            rid = str(rule.get("id") or f"r{i}").strip()
        else:
            text = str(rule).strip()
            rid = f"r{i}"
        out.append({"id": rid, "text": text})
    return out


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
