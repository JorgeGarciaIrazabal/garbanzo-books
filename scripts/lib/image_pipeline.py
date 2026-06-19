"""Best-of-N render + visual QC — the per-page candidate loop.

For each page we render one or more candidates (varying the seed per retry), score each against
the page spec with a LOCAL Ollama vision model, keep the highest scorer, and move the winner to
the canonical ``page-NN.png`` (recording every attempt in ``page-NN.qc.json``). All QC is
best-effort: if Ollama is unreachable the first render wins. Providers/placeholders live in
sibling modules; this module is the orchestration that picks the best frame.
"""
from __future__ import annotations

import random
from pathlib import Path

from .colors import palette_hexes
from .image_placeholder import write_placeholder_svg
from .image_providers import try_real_provider
from .model import World
from .prompt_assembly import AssembledPrompt
from .vision_qc import score_image as _qc_score


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


def _generate_one_candidate(ap: AssembledPrompt, images_dir: Path, world: World, ref_base: Path,
                            provider: str, num: int, title: str) -> Path | None:
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


def _qc_candidate(cand_path: Path, *, world: World, story: dict, page: dict, qc_model: str | None,
                  verbose: bool) -> dict:
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
        tokens=[world.characters.get(s, {}).get("appearance_token", "") for s in (img.get("characters_present") or []) if world.characters.get(s)],
        art_style_block=art.get("prompt_style_block", ""),
        palette=palette,
        text_zone=(page.get("layout") or {}).get("text_position")
            or (art.get("text_treatment", {}) or {}).get("placement", "lower-third"),
        model=qc_model,
        verbose=verbose,
    )
    return res.to_dict()


def _run_best_of_n(ap: AssembledPrompt, images_dir: Path, world: World, ref_base: Path,
                   story: dict, page: dict, provider: str, num: int, title: str,
                   *, qc_retries: int, qc_threshold: float, qc_model: str | None,
                   qc_off: bool, verbose: bool) -> tuple[Path, list[dict]]:
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
        qc_log.append({"attempt": 0, "path": cand.name, "ok": True, "score": 10.0,
                        "reason": "qc disabled", "flags": ["qc_disabled"]})
        return cand, qc_log

    best_path: Path | None = None
    best_score: float = -1.0
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
            qc_log.append({"attempt": attempt, "path": None, "ok": False, "score": 0.0,
                            "reason": "provider failed", "flags": ["provider_failed"]})
            continue
        verdict = _qc_candidate(cand, world=world, story=story, page=page,
                                qc_model=qc_model, verbose=verbose)
        verdict["attempt"] = attempt
        verdict["path"] = cand.name
        qc_log.append(verdict)
        score = verdict.get("score", 0.0) or 0.0
        print(f"    qc attempt {attempt + 1}/{max_attempts}: score={score:.1f} "
              f"ok={verdict.get('ok')} flags={verdict.get('flags', [])} — {verdict.get('reason','')[:80]}")
        if score > best_score:
            best_score = score
            best_path = cand
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
