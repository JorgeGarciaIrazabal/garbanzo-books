"""Interactivity invariants: each game is a known type with the right ``data``
payload, branching ``choice`` targets resolve to real pages, the book varies its
*kinds* of fun (not all the same mechanic), and games give the child warm feedback.

Fun is the point, not reading-skill coverage — see ``methodology/fun-first.md`` and
``methodology/interactivity.md`` for the type catalogue and age-band fit.
"""
from __future__ import annotations

from typing import Any

from .report import Report

# Allowed interaction types and the keys their `data` payload should carry.
INTERACTION_DATA_KEYS: dict[str, list[str]] = {
    "seek-and-find": ["items"],
    "spot-the-difference": ["count"],
    "counting": ["answer"],
    "rhyme-complete": ["answer"],
    "word-match": ["pairs"],
    "sound-hunt": ["sound", "words"],
    "riddle": ["answer"],
    "comprehension-question": ["question"],
    "choice": ["options"],
    "maze": [],
    "trace-letter": ["letter"],
    "memory": [],
    "drag-order": ["sequence"],
    "tap-to-reveal": [],
    "coloring": [],
    "sorting": ["bins", "items"],
    "pattern": ["answer"],
    "odd-one-out": ["answer", "items"],
    "melody": ["notes"],
    # --- rich on-the-art games (normalized coords over the page image) ---
    "hidden-object": ["items"],
    "find-in-scene": ["items"],
    "tap-on-art": ["target"],
    "hotspot-reveal": ["hotspots"],
    "place-on-scene": ["items", "slots"],
    # --- true drag-and-drop suite ---
    "drag-sort": ["bins", "items"],
    "drag-match": ["pairs"],
    "jigsaw": [],            # defaults to an auto-cut of the page art
    "dress-up": ["parts", "zones"],
    "feed-the-thing": ["good", "bad"],
    # --- draw / reveal ---
    "connect-dots": ["dots"],
    "scratch-reveal": ["reveal"],
    # --- spatial / logic ---
    "sliding-puzzle": [],   # defaults to a 3x3 of the page art
    "balance-scale": ["left", "right", "answer"],
    # --- word / phonics ---
    "word-build": ["letters", "answer"],
    "anagram": ["scrambled", "answer"],
    "fill-the-blank": ["sentence", "answer"],
    # --- music / rhythm ---
    "rhythm-tap": ["pattern"],
    "song-builder": ["palette"],
    # --- memory ---
    "sequence-recall": ["sequence"],
    # --- arcade: real-time engine games, fullscreen over the page art ---
    "arcade-catch": ["catch"],
    "arcade-flap": ["player"],
    "arcade-run": ["player", "collect"],
    "arcade-pop": ["pop"],
    "arcade-toss": ["projectile", "target"],
    "arcade-steer": ["player", "collect"],
    # --- generic declarative game (LLM-authored) ---
    "custom": ["elements", "win"],
}

# The arcade family (gx.arcade.js): real games with a game loop — movement, physics,
# steering. Every noun in their payloads is skinned from the story.
ARCADE_TYPES = {t for t in INTERACTION_DATA_KEYS if t.startswith("arcade-")}
PILLARS = {"phonemic-awareness", "phonics", "fluency", "vocabulary", "comprehension"}

# Beats that practise a discrete skill (vs. pure discovery / free play) read as flat without
# an encouraging response — feedback.correct / feedback.try_again.
SKILL_PRACTICE_TYPES = {
    "rhyme-complete", "comprehension-question", "maze", "choice", "sorting", "pattern",
    "word-match", "riddle", "odd-one-out", "counting",
    "drag-sort", "drag-match", "jigsaw", "feed-the-thing", "place-on-scene",
    "sliding-puzzle", "balance-scale", "word-build", "anagram", "fill-the-blank",
    "sequence-recall", "find-in-scene", "hidden-object", "connect-dots", "custom",
} | ARCADE_TYPES  # arcade games have a win moment too — warm feedback makes it land

# "Rich" games — the ones that make a book feel like a toy, not a worksheet: play ON the art,
# true dragging, drawing, spatial puzzles, music, or an LLM-authored custom game. The quality
# gate wants at least one of these per book (kids want to DO, not just pick an answer).
RICH_TYPES = {
    "hidden-object", "find-in-scene", "tap-on-art", "hotspot-reveal", "place-on-scene",
    "spot-the-difference", "drag-sort", "drag-match", "jigsaw", "dress-up", "feed-the-thing",
    "connect-dots", "scratch-reveal", "sliding-puzzle", "balance-scale", "maze",
    "rhythm-tap", "song-builder", "sequence-recall", "melody", "trace-letter", "custom",
} | ARCADE_TYPES  # arcade games are the richest of all — a real game loop

# Types whose `data` carries on-art coordinates that must sit inside the frame.
_COORD_TYPES = {
    "hidden-object", "find-in-scene", "tap-on-art", "hotspot-reveal", "place-on-scene",
    "connect-dots", "dress-up",
}


def _coord_ok(c: Any) -> bool:
    """A coord is {x, y} with both numeric and inside the frame (0..100 covers both the
    normalized 0..1 and legacy percent 0..100 conventions)."""
    if not isinstance(c, dict):
        return False
    try:
        x, y = float(c.get("x")), float(c.get("y"))
    except (TypeError, ValueError):
        return False
    return 0 <= x <= 100 and 0 <= y <= 100


def _check_coords(rep: Report, where: str, pnum: Any, t: str, data: dict) -> None:
    """On-art games place things by coordinate; an off-frame coord would render off-screen."""
    pts: list[Any] = []
    for it in data.get("items", []) or []:
        pts.append(it.get("at") if isinstance(it, dict) else None)
    for sp in data.get("hotspots", []) or []:
        pts.append(sp.get("at") if isinstance(sp, dict) else None)
    for sl in data.get("slots", []) or []:
        pts.append(sl.get("at") if isinstance(sl, dict) else None)
    for dt in data.get("dots", []) or []:
        pts.append(dt.get("at") if isinstance(dt, dict) else None)
    for zn in data.get("zones", []) or []:
        pts.append(zn.get("at") if isinstance(zn, dict) else None)
    if isinstance(data.get("target"), dict):
        pts.append(data["target"].get("at"))
    bad = [p for p in pts if p is not None and not _coord_ok(p)]
    if bad:
        rep.fail(f"[interaction] {where} p{pnum} ({t}): coordinate(s) off-frame or non-numeric "
                 f"{bad} — on-art coords are {{x,y}} in 0..1")


def _check_custom_spec(rep: Report, where: str, pnum: Any, data: dict) -> None:
    """A `custom` game is winnable by construction (no fail state), but its win condition
    must REFERENCE only declared elements and an `all-placed` win must be REACHABLE."""
    elements = data.get("elements") or []
    if not isinstance(elements, list) or not elements:
        rep.fail(f"[interaction] {where} p{pnum} (custom): needs at least one element")
        return
    ids: list[str] = []
    for e in elements:
        if not isinstance(e, dict) or not e.get("id"):
            rep.fail(f"[interaction] {where} p{pnum} (custom): every element needs an id")
            return
        ids.append(e["id"])
        if e.get("at") is not None and not _coord_ok(e["at"]):
            rep.fail(f"[interaction] {where} p{pnum} (custom): element '{e['id']}' has an off-frame `at`")
    if len(set(ids)) != len(ids):
        rep.fail(f"[interaction] {where} p{pnum} (custom): element ids must be unique {ids}")
    id_set = set(ids)

    def check_win(win: Any) -> None:
        if not isinstance(win, dict):
            rep.fail(f"[interaction] {where} p{pnum} (custom): win must be an object")
            return
        for sub_key in ("all", "any"):
            for sub in win.get(sub_key, []) or []:
                check_win(sub)
        if isinstance(win.get("not"), dict):
            check_win(win["not"])
        mode = win.get("mode")
        # collect referenced ids per mode
        refs: list[str] = []
        for pr in win.get("pairs", []) or []:
            refs += [x for x in (pr or []) if isinstance(x, str)]
        refs += [x for x in win.get("order", []) or [] if isinstance(x, str)]
        refs += [x for x in win.get("steps", []) or [] if isinstance(x, str)]
        refs += [x for x in win.get("targets", []) or [] if isinstance(x, str)]
        refs += [x for x in (win.get("state") or {}).keys()]
        dangling = [r for r in refs if r not in id_set]
        if dangling:
            rep.fail(f"[interaction] {where} p{pnum} (custom): win references unknown element(s) {dangling}")
        if mode == "all-placed":
            draggables = [e for e in elements if e.get("kind") == "draggable"]
            zones = [e for e in elements if e.get("kind") in ("dropzone", "target")]
            if not draggables:
                rep.warn(f"{where} p{pnum} (custom): all-placed win but no draggables to place")

            def _placeable(d):
                grp, did = d.get("group"), d.get("id")
                return any(
                    (not z.get("accepts")) or (grp in (z.get("accepts") or [])) or (did in (z.get("accepts") or []))
                    for z in zones
                )
            # Decoys (draggables with no accepting zone) are allowed — the kid must NOT place
            # them. The win only needs every PLACEABLE draggable placed, so it's reachable as
            # long as at least one draggable has a home.
            if draggables and not any(_placeable(d) for d in draggables):
                rep.fail(f"[interaction] {where} p{pnum} (custom): no draggable has a dropzone "
                         "that accepts it — the all-placed game can't be won")

    check_win(data.get("win"))


def _check_one(rep: Report, where: str, pnum: Any, it: dict, page_nums: set, depth: int = 0) -> None:
    """Validate a single interaction (or a step within one)."""
    t = it.get("type")
    need = INTERACTION_DATA_KEYS.get(t)
    if need is None:
        rep.fail(f"[interaction] {where} p{pnum}: unknown type '{t}'")
        return
    data = it.get("data", {}) or {}
    missing = [k for k in need if k not in data]
    if missing:
        rep.fail(f"[interaction] {where} p{pnum} ({t}): data missing {missing}")
    if t in _COORD_TYPES:
        _check_coords(rep, where, pnum, t, data)
    if t == "custom":
        _check_custom_spec(rep, where, pnum, data)
    if t in SKILL_PRACTICE_TYPES and not (it.get("feedback") or {}):
        rep.warn(f"{where} p{pnum}: {t} has no feedback (correct/try_again) — "
                 "add encouragement so the beat lands")
    if t == "choice":
        for opt in data.get("options", []) or []:
            if opt.get("goto") not in page_nums:
                rep.fail(f"[interaction] {where} p{pnum}: choice goto "
                         f"{opt.get('goto')} is not a real page")
    steps = it.get("steps")
    if steps:
        if depth > 0:
            rep.fail(f"[interaction] {where} p{pnum}: steps may not nest steps")
        else:
            for st in steps:
                _check_one(rep, where, pnum, st, page_nums, depth + 1)


def check_interactivity(rep: Report, world: Any, story: Any) -> None:
    s = story.data
    where = f"{world.slug}/{story.slug}"
    pages = s.get("pages", []) or []
    page_nums = {p.get("number") for p in pages}

    types_seen: set[str] = set()
    has_interaction = False
    for p in pages:
        it = p.get("interaction")
        if not it:
            continue
        has_interaction = True
        if it.get("type"):
            types_seen.add(it["type"])
        _check_one(rep, where, p.get("number"), it, page_nums)
    if has_interaction:
        rep.ok(f"interactions {where}")
        n_games = len([p for p in pages if p.get("interaction")])
        # Fun comes from variety, not skill coverage — nudge if every game is the same kind.
        if len(types_seen) < 3 and len(types_seen) < n_games:
            rep.warn(f"{where}: games use only {len(types_seen)} kind(s) — vary the fun "
                     "(mix a search, a maze, a music beat, a branch; don't ship all quizzes)")
        # Kids want to DO, not just pick — nudge if nothing rich (on-art / drag / puzzle / music).
        if n_games >= 2 and not (types_seen & RICH_TYPES):
            rep.warn(f"{where}: every game is a quiz/tap — add at least one rich game "
                     "(in-scene, drag-and-drop, a puzzle, or a custom game)")
    else:
        rep.warn(f"{where}: no interactions yet")
