"""Best-of-N render + visual QC — the per-page candidate loop.

For each page we render one or more candidates (varying the seed per retry), score each against
the page spec with a LOCAL Ollama vision model, keep the highest scorer, and move the winner to
the canonical ``page-NN.png`` (recording every attempt in ``page-NN.qc.json``). All QC is
best-effort: if Ollama is unreachable the first render wins. Providers/placeholders live in
sibling modules; this module is the orchestration that picks the best frame.
"""

from __future__ import annotations

import os
import random
from pathlib import Path

from .colors import palette_hexes
from .image_placeholder import write_placeholder_svg
from .image_providers import _cap_image_bytes, try_real_provider
from .model import World, character_with_stage as _char_with_stage
from .prompt_assembly import AssembledPrompt, assemble_page_prompt  # noqa: F401 — re-exported
from .vision_qc import score_image as _qc_score

# QC flags an edit pass can plausibly repair in place (vs. structural problems like duplicated
# characters or melted anatomy, which are re-rolled with a fresh seed instead).
_EDIT_FIXABLE_FLAGS = {
    "scene_mismatch",
    "wrong_characters",
    "missing_characters",
    "text_zone_cluttered",
    "style_inconsistent",
    "too_dark",
    "low_detail",
}

# Grid mode (one big sheet cut into per-page tiles) needs tiles big enough for a full-bleed
# page. This is the longest edge a grid tile is allowed to keep after slicing.
GRID_TILE_MAX_EDGE = 1184


def _write_prompt_sidecar(image_path: Path, ap: AssembledPrompt) -> None:
    """Record the EXACT assembled prompt next to the image (page-NN.prompt.txt).

    This makes every render auditable and reproducible: you can see precisely which
    style block + appearance_tokens + palette + seed produced a frame, diff it when a
    character drifts, and regenerate deterministically. Written for real renders AND
    placeholders so the audit trail is always present."""
    side = image_path.with_suffix(".prompt.txt")
    side.parent.mkdir(parents=True, exist_ok=True)
    side.write_text(
        f"PROMPT:\n{ap.prompt}\n\n"
        f"NEGATIVE:\n{ap.negative}\n\n"
        f"SEED: {ap.seed}\n"
        f"ASPECT: {ap.aspect_ratio}\n"
        f"CHARACTERS: {', '.join(ap.characters) or '—'}\n"
        f"REFERENCES: {', '.join(ap.reference_images) or '—'}\n",
        encoding="utf-8",
    )


def _generate_one_candidate(
    ap: AssembledPrompt,
    images_dir: Path,
    world: World,
    ref_base: Path,
    provider: str,
    num: int,
    title: str,
) -> Path | None:
    """Render exactly one candidate image. Returns the on-disk path of the real PNG (with the
    final ``page-NN-K.png`` suffix) or None if the provider failed. The image prompt sidecar
    is written next to it either way so each candidate is auditable."""
    suffix = ap.seed if ap.seed is not None else 0
    cand_png = images_dir / f"page-{num:02d}-{suffix}.png"
    if provider != "placeholder" and try_real_provider(provider, ap, cand_png, ref_base=ref_base):
        _write_prompt_sidecar(cand_png, ap)
        return cand_png
    if provider != "placeholder":
        # Real provider was requested but failed (e.g. rate limit); do NOT silently fall back
        # to a placeholder — the skill is explicit that placeholders aren't acceptable output.
        # We surface a placeholder only when the provider itself is the placeholder pipeline.
        return None
    out_svg = cand_png.with_suffix(".svg")
    write_placeholder_svg(out_svg, title, ap, world)
    _write_prompt_sidecar(out_svg, ap)
    return out_svg


def _qc_candidate(
    cand_path: Path, *, world: World, story: dict, page: dict, qc_model: str | None, verbose: bool
) -> dict:
    """Score one rendered candidate against the page spec via local Ollama vision. Returns
    a JSON-serialisable record. ``qc_score`` degrades to a permissive verdict if the local
    model is unreachable, so the rest of the loop can still pick a winner."""
    art = world.data.get("art_style", {}) or {}
    img = page.get("image", {}) or {}
    palette = palette_hexes(art)[:6]
    res = _qc_score(
        cand_path,
        page_text=page.get("text", ""),
        characters=img.get("characters_present", []) or [],
        tokens=[
            world.characters.get(s, {}).get("appearance_token", "")
            for s in (img.get("characters_present") or [])
            if world.characters.get(s)
        ],
        art_style_block=art.get("prompt_style_block", ""),
        palette=palette,
        text_zone=(page.get("layout") or {}).get("text_position")
        or (art.get("text_treatment", {}) or {}).get("placement", "lower-third"),
        model=qc_model,
        verbose=verbose,
    )
    return res.to_dict()


def _page_tokens(world: World, page: dict) -> list[str]:
    """The locked appearance tokens for the characters expected on this page."""
    present = (page.get("image", {}) or {}).get("characters_present", []) or []
    return [
        world.characters[s].get("appearance_token", "") for s in present if world.characters.get(s)
    ]


def _build_edit_instruction(verdict: dict, page: dict, tokens: list[str]) -> str:
    """Turn a QC verdict into a concrete Qwen-Image-Edit instruction. We lead with the specific
    defect the reviewer named, then re-state what the page should show and the locked character
    look, so the edit corrects the inconsistency without redrawing the whole scene."""
    flags = verdict.get("flags") or []
    reason = (verdict.get("reason") or "").strip()
    page_text = (page.get("text") or "").strip()
    tok = "; ".join(t for t in tokens if t)
    parts = [f"Fix this illustration: {reason}" if reason else "Fix this illustration."]
    if "scene_mismatch" in flags and page_text:
        parts.append(f"It must clearly show: {page_text}")
    if {"wrong_characters", "missing_characters"} & set(flags) and tok:
        parts.append(f"Make the characters exactly match: {tok}")
    if "text_zone_cluttered" in flags:
        parts.append("Clear the caption zone into calm, low-detail space.")
    if "too_dark" in flags:
        parts.append("Brighten the image and lift the shadows.")
    parts.append("Keep the existing art style, palette, and composition.")
    return " ".join(parts)


def _try_qwen_edit_fix(
    winner: Path,
    best_verdict: dict,
    images_dir: Path,
    world: World,
    story: dict,
    page: dict,
    num: int,
    *,
    qc_model: str | None,
    verbose: bool,
) -> tuple[Path, list[dict]]:
    """If the kept frame still has a fixable inconsistency, run ONE Qwen-Image-Edit pass to
    repair it, re-QC, and keep the edit only if it scores at least as well. Returns the
    (possibly replaced) winner path plus any QC log entries to append. No-op (returns winner
    unchanged) when the frame is already ok, the flags aren't edit-fixable, or ComfyUI is down."""
    flags = set(best_verdict.get("flags") or [])
    if best_verdict.get("ok") or not (flags & _EDIT_FIXABLE_FLAGS):
        return winner, []
    from . import comfyui_client as cc

    if not cc.is_available():
        return winner, []

    tokens = _page_tokens(world, page)
    instruction = _build_edit_instruction(best_verdict, page, tokens)
    edited = images_dir / f"page-{num:02d}-edit{winner.suffix}"
    try:
        data = cc.edit(instruction, winner)
        edited.write_bytes(_cap_image_bytes(data, int(os.getenv("GEMINI_MAX_EDGE", "1184"))))
    except Exception as e:  # noqa: BLE001 — edit is best-effort; keep the original on failure
        if verbose:
            print(f"    edit-fix: qwen-edit failed ({type(e).__name__}: {e}); keeping original")
        return winner, []

    verdict = _qc_candidate(
        edited, world=world, story=story, page=page, qc_model=qc_model, verbose=verbose
    )
    verdict["attempt"] = "edit-fix"
    verdict["path"] = edited.name
    verdict["instruction"] = instruction
    before, after = best_verdict.get("score", 0.0) or 0.0, verdict.get("score", 0.0) or 0.0
    print(f"    edit-fix: {before:.1f} → {after:.1f}  ({', '.join(flags & _EDIT_FIXABLE_FLAGS)})")
    if after >= before:
        return edited, [verdict]
    edited.unlink(missing_ok=True)  # edit didn't help; keep the original, but log the attempt
    return winner, [verdict]


def _run_best_of_n(
    ap: AssembledPrompt,
    images_dir: Path,
    world: World,
    ref_base: Path,
    story: dict,
    page: dict,
    provider: str,
    num: int,
    title: str,
    *,
    qc_retries: int,
    qc_threshold: float,
    qc_model: str | None,
    qc_off: bool,
    qc_edit_fix: bool,
    verbose: bool,
) -> tuple[Path, list[dict]]:
    """Generate one or more candidates, QC them with local Ollama vision, and pick the best.

    Returns ``(winner_path, qc_log)`` where ``qc_log`` is the per-attempt record (one entry
    per candidate, with score/flags/path) that gets written to ``page-NN.qc.json`` so the
    render history is auditable. If QC is off, or no local vision model is available, the
    first (and only) attempt wins and ``qc_log`` records that fact transparently."""
    qc_log: list[dict] = []
    if qc_off or provider == "placeholder" or qc_retries <= 0:
        cand = _generate_one_candidate(ap, images_dir, world, ref_base, provider, num, title)
        if cand is None:
            raise RuntimeError(f"p{num}: image provider failed (no candidate rendered)")
        qc_log.append(
            {
                "attempt": 0,
                "path": cand.name,
                "ok": True,
                "score": 10.0,
                "reason": "qc disabled",
                "flags": ["qc_disabled"],
            }
        )
        return cand, qc_log

    best_path: Path | None = None
    best_score: float = -1.0
    best_verdict: dict = {}
    max_attempts = max(1, qc_retries + 1)  # qc_retries=2 → up to 3 candidates

    for attempt in range(max_attempts):
        # Vary the seed per attempt so retries aren't identical re-rolls. We mutate ap.seed
        # (it's per-attempt, not the story's stable seed).
        if attempt == 0 and ap.seed is not None:
            attempt_seed = ap.seed
        else:
            attempt_seed = random.randint(1, 2_000_000_000)
        ap.seed = attempt_seed
        cand = _generate_one_candidate(ap, images_dir, world, ref_base, provider, num, title)
        if cand is None:
            qc_log.append(
                {
                    "attempt": attempt,
                    "path": None,
                    "ok": False,
                    "score": 0.0,
                    "reason": "provider failed",
                    "flags": ["provider_failed"],
                }
            )
            continue
        verdict = _qc_candidate(
            cand, world=world, story=story, page=page, qc_model=qc_model, verbose=verbose
        )
        verdict["attempt"] = attempt
        verdict["path"] = cand.name
        qc_log.append(verdict)
        score = verdict.get("score", 0.0) or 0.0
        print(
            f"    qc attempt {attempt + 1}/{max_attempts}: score={score:.1f} "
            f"ok={verdict.get('ok')} flags={verdict.get('flags', [])} — {verdict.get('reason', '')[:80]}"
        )
        if score > best_score:
            best_score = score
            best_path = cand
            best_verdict = verdict
        # Hard stops: duplicate characters, anatomy, or empty/blank image are not salvageable
        # by trying again with a different seed — they reflect a prompt issue. We let the
        # outer loop continue (we don't waste another API call) but break the local loop.
        hard_flags = {"duplicate_characters", "anatomy_issue"}
        if hard_flags.intersection(verdict.get("flags") or []):
            break
        # Soft pass: meets the threshold — stop early so we don't burn API calls.
        if verdict.get("ok") and score >= qc_threshold:
            break

    if best_path is None:
        # Every attempt failed to even render. Re-raise so the caller surfaces it.
        raise RuntimeError(f"p{num}: no candidate rendered after {max_attempts} attempt(s)")

    # If the best frame still reads as inconsistent, try a single targeted Qwen-Image-Edit
    # repair (cheaper and more faithful than another full re-roll) and keep it if it's better.
    if qc_edit_fix:
        best_path, edit_log = _try_qwen_edit_fix(
            best_path,
            best_verdict,
            images_dir,
            world,
            story,
            page,
            num,
            qc_model=qc_model,
            verbose=verbose,
        )
        qc_log.extend(edit_log)
    return best_path, qc_log


def _finalize_winner(winner: Path, images_dir: Path, num: int) -> Path:
    """Move the winning candidate to the canonical ``page-NN.<ext>`` (and its .prompt.txt
    sidecar) and clean up the rejected siblings. The QC log in page-NN.qc.json preserves
    the audit trail."""
    canonical = images_dir / f"page-{num:02d}{winner.suffix}"
    if winner.resolve() != canonical.resolve():
        if canonical.exists():
            canonical.unlink()
        winner.rename(canonical)
        # Move the .prompt.txt sidecar with it so the canonical artifact stays self-contained.
        sidecar = winner.with_suffix(".prompt.txt")
        if sidecar.exists():
            new_sidecar = canonical.with_suffix(".prompt.txt")
            if new_sidecar.exists():
                new_sidecar.unlink()
            sidecar.rename(new_sidecar)
    # Remove other candidates (and their sidecars) for this page — they're the rejected
    # siblings, and the QC log in page-NN.qc.json is now the only audit trail for them.
    for sibling in images_dir.glob(f"page-{num:02d}-*.{winner.suffix.lstrip('.')}"):
        if sibling.resolve() != canonical.resolve():
            sibling.unlink()
            sibling.with_suffix(".prompt.txt").unlink(missing_ok=True)
    return canonical


def slice_grid_sheet(
    sheet_png: Path, images_dir: Path, page_nums: list[int], max_edge: int = GRID_TILE_MAX_EDGE
) -> list[Path]:
    """Cut a 3x3 grid sheet into per-page tiles, in reading order (row-major).

    Tile i (0-based) lands at ``page-<page_nums[i]>.png`` in ``images_dir``. The canvas is
    divided by exact thirds (no margins assumed). Returns the list of written tile paths.
    Raises ValueError if the sheet isn't a raster Pillow can open.
    """
    from PIL import Image

    sheet: Image.Image = Image.open(sheet_png)
    if sheet.mode not in ("RGB", "RGBA"):
        sheet = sheet.convert("RGB")
    w, h = sheet.size
    cols, rows = 3, 3
    tw, th = w / cols, h / rows
    tiles: list[Path] = []
    for i, num in enumerate(page_nums):
        r, c = divmod(i, cols)
        box = (round(c * tw), round(r * th), round((c + 1) * tw), round((r + 1) * th))
        tile = sheet.crop(box)
        if max(tile.size) > max_edge:
            tile.thumbnail((max_edge, max_edge))
        out = images_dir / f"page-{num:02d}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        tile.save(out, format="PNG")
        tiles.append(out)
    return tiles


def build_grid_prompt(world: World, story: dict, pages: list[dict]) -> AssembledPrompt:
    """Assemble ONE prompt for a 3x3 story contact sheet covering the given pages.

    Each panel gets: the scene + that page's character tokens (with evolution deltas), so
    every cell is a complete self-contained illustration. The world style block / palette /
    negative are shared by all panels of a book, so they're stated once. The sheet is 1:1
    (3x3 grid of square panels); per-page seeds are averaged out — one seed (the first
    character's) anchors the sheet, and all reference images are forwarded so providers
    that accept them (nano-banana) still get the anchors.
    """
    if not pages:
        raise ValueError("no pages to put on the grid")
    art = world.data.get("art_style", {}) or {}
    stage_map = {c.get("slug"): c.get("stage") for c in story.get("characters", []) or []}
    cells: list[str] = []
    tokens: list[str] = []
    refs: list[str] = []
    chars: list[str] = []
    seed: int | None = None
    for page in pages:
        ap = assemble_page_prompt(world, story, page)
        scene = ((page.get("image", {}) or {}).get("prompt") or "").strip().rstrip(".")
        num = page.get("number", 0)
        cells.append(f"Panel for page {num}: {scene}")
        for slug in ap.characters:
            if slug not in chars:
                chars.append(slug)
                char = world.characters.get(slug, {})
                view = _char_with_stage(char, stage_map.get(slug))
                tok = view.get("appearance_token") or ""
                if tok:
                    tokens.append(f"{slug}: {tok}")
                for r in char.get("reference_images", []) or []:
                    if r not in refs:
                        refs.append(r)
                if seed is None and char.get("seed") is not None:
                    seed = char["seed"]
    style = art.get("prompt_style_block", "") or ""
    neg = art.get("negative_prompt", "") or ""
    from .colors import palette_hexes

    palette = ", ".join(palette_hexes(art)[:8])
    # Panels are described by GRID POSITION (row-major) so the model can place them even if
    # it ignores the exact count, and a PARTIAL batch (fewer than 9 pages) names its true
    # shape. Empty cells are explicitly filled with decorative art — a blank cell invites
    # the model to bleed a neighbouring scene into it, which corrupts the tile slicing.
    n = len(pages)
    rows_used = (n + 2) // 3
    if n == 9:
        shape = "nine equal square panels arranged in three rows of three"
    else:
        last = "one panel in the final row" if n % 3 == 1 else (
            "two panels in the final row" if n % 3 == 2 else "three panels in the final row")
        shape = f"a {rows_used}-row grid of equal square panels, three per row, with {n} " \
                f"story panels ({last}) and {9 - n} filler panels"
    filled = [f"row {i // 3 + 1}, column {i % 3 + 1}" for i in range(len(cells))]
    placed = [f"{pos} — {cell}" for pos, cell in zip(filled, cells)]
    filler = (
        f"\nThe remaining {9 - n} panel(s) (row-major after the {n} story panels) are "
        "DECORATIVE FILLER in the same style: small standalone vignettes of the book's "
        "world (scenery, tiny background props, no characters, no story action) — they are "
        "never used as book pages, so keep them simple and uncluttered."
        if n < 9 else ""
    )
    prompt = (
        f"A 3x3 grid contact sheet for the children's picture book "
        f"'{story.get('title', 'the book')}': {shape} with clean thin white gutters, each "
        "story panel a complete self-contained full-bleed storybook illustration. ABSOLUTELY "
        "NO text, letters, numbers, labels, watermarks, captions, or page numbers anywhere "
        "in the image.\n\n"
        + "\n".join(placed)
        + filler
        + (
            "\n\nCharacters — each character must look IDENTICAL in every panel they appear "
            "in (same face, same outfit, same proportions):\n" + "\n".join(tokens)
            if tokens
            else ""
        )
        + (f"\n\nStyle for every panel: {style}." if style else "")
        + (f"\nPalette: {palette}." if palette else "")
        + "\nLeave the lower third of every panel as calm, low-detail negative space."
    )
    return AssembledPrompt(
        prompt=prompt,
        negative=neg,
        seed=seed,
        aspect_ratio="1:1",
        reference_images=refs,
        characters=chars,
    )
