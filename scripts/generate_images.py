#!/usr/bin/env python3
"""Generate on-model illustrations by ASSEMBLING prompts (never hand-writing them).

Prompt = page scene + each present character's appearance_token + world prompt_style_block
       + palette + negative prompt + seed + reference images   (see lib/prompt_assembly.py)

Usage:
    uv run python scripts/generate_images.py worlds/<world>/stories/<story>   # all pages
    uv run python scripts/generate_images.py <world>/<story> --page 3         # one page
    uv run python scripts/generate_images.py --character <world>/<char>       # model sheet
    uv run python scripts/generate_images.py <world>/<story> --print-prompts   # dry run

Providers:
  - "nano-banana" (default) — Google Gemini's "Nano Banana" image model
    (gemini-2.5-flash-image). Free to start: get a key at https://aistudio.google.com/apikey
    and set GEMINI_API_KEY (or GOOGLE_API_KEY). Crucially, Nano Banana accepts the character's
    reference images as INPUT, which anchors character consistency far better than text alone.
  - "openai" — OpenAI Images (gpt-image-1), set OPENAI_API_KEY.
  - "placeholder" — no network: writes labeled SVG placeholders showing the assembled prompt +
    characters + seed over the world palette, so the whole pipeline runs/validates/builds
    offline. Automatically used as a fallback whenever the chosen provider has no API key.

Visual QC (best-of-N):
  After each render, the image is scored against the page's spec by a LOCAL Ollama vision
  model (gemma3 / gemma4 / llama3.2-vision / llava / …). If the score is below the threshold
  the render is rejected, the seed is varied, and a new candidate is generated. Up to
  ``--qc-retries+1`` candidates per page; the winner is renamed to the canonical
  ``page-NN.png`` and a per-page ``page-NN.qc.json`` sidecar records every attempt's score
  + flags + reason so the decision is auditable. Set ``--qc-off`` to disable (single render,
  no Ollama call). All QC is best-effort: if Ollama is unreachable the first render wins.

Env:
  GEMINI_API_KEY / GOOGLE_API_KEY   key for Nano Banana (free tier from Google AI Studio)
  GEMINI_IMAGE_MODEL                 override model (default gemini-2.5-flash-image; e.g.
                                     gemini-3-pro-image = "Nano Banana Pro", gemini-3.1-flash-image)
  IMAGE_PROVIDER                     default provider (default: nano-banana)
  OLLAMA_HOST                        Ollama endpoint (default http://localhost:11434)
  VISION_QC_MODEL                    override the auto-picked vision model
                                     (default: first vision-capable model pulled)
Note: Gemini-generated images carry an invisible SynthID watermark.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import random
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.colors import palette_hexes  # noqa: E402
from lib.model import (ROOT, World, dump_yaml, load_dotenv, load_world, load_yaml)  # noqa: E402
from lib.prompt_assembly import (AssembledPrompt, assemble_character_sheet_prompt,  # noqa: E402
                                 assemble_page_prompt)
from lib.vision_qc import score_image as _qc_score  # noqa: E402

PLACEHOLDER_W, PLACEHOLDER_H = 1024, 768

# Google "Nano Banana". gemini-2.5-flash-image is the original; gemini-3-pro-image is
# "Nano Banana Pro"; gemini-3.1-flash-image is the newer flash. Override via GEMINI_IMAGE_MODEL.
DEFAULT_NANO_BANANA_MODEL = "gemini-2.5-flash-image"
# Longest-edge cap for generated images. Nano Banana's native 1K 4:3 output is 1184x864, so
# this keeps the full 4:3 frame (a little past 1024 by design) while blocking 2K/4K. Anything
# larger is downscaled, preserving aspect ratio. Override with GEMINI_MAX_EDGE.
DEFAULT_MAX_EDGE = 1184
_RASTER_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
_warned_nokey: set[str] = set()


def _cap_image_bytes(data: bytes, max_edge: int) -> bytes:
    """Downscale (preserving aspect ratio) so the longest edge is <= max_edge. No-op if it
    already fits or Pillow is unavailable."""
    try:
        from io import BytesIO
        from PIL import Image
    except ImportError:
        print("  ! Pillow not installed — cannot enforce max image size "
              "(uv add pillow).", file=sys.stderr)
        return data
    img = Image.open(BytesIO(data))
    if max(img.size) <= max_edge:
        return data
    img.thumbnail((max_edge, max_edge))  # in-place, keeps aspect ratio, only shrinks
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _palette_hexes(world: World) -> list[str]:
    """The world palette as ``#rrggbb`` strings, with a sensible fallback so a
    placeholder still draws colour bands. Thin wrapper over the shared helper."""
    return palette_hexes(world.data.get("art_style"), fallback=True)


def write_placeholder_svg(path: Path, title: str, ap: AssembledPrompt, world: World) -> None:
    """A self-describing placeholder: palette bands + the assembled prompt text + seed."""
    pal = _palette_hexes(world)
    bands = ""
    bw = PLACEHOLDER_W / max(1, len(pal))
    for i, c in enumerate(pal):
        bands += f'<rect x="{i*bw:.0f}" y="0" width="{bw:.0f}" height="{PLACEHOLDER_H}" fill="{c}"/>'
    wrapped = textwrap.wrap(ap.prompt, width=64)[:14]
    lines = ""
    for i, ln in enumerate(wrapped):
        lines += f'<tspan x="48" dy="{0 if i==0 else 26}">{html.escape(ln)}</tspan>'
    chars = ", ".join(ap.characters) or "—"
    path.parent.mkdir(parents=True, exist_ok=True)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{PLACEHOLDER_W}" height="{PLACEHOLDER_H}" viewBox="0 0 {PLACEHOLDER_W} {PLACEHOLDER_H}">
  {bands}
  <rect x="32" y="120" width="{PLACEHOLDER_W-64}" height="{PLACEHOLDER_H-220}" rx="24" fill="#fffdf7" opacity="0.92"/>
  <text x="48" y="80" font-family="Georgia, serif" font-size="40" fill="#2d2a26">{html.escape(title)}</text>
  <text x="48" y="108" font-family="monospace" font-size="18" fill="#5b554d">PLACEHOLDER · characters: {html.escape(chars)} · seed: {ap.seed}</text>
  <text x="48" y="170" font-family="monospace" font-size="18" fill="#3a352f">{lines}</text>
  <rect x="0" y="{PLACEHOLDER_H-70}" width="{PLACEHOLDER_W}" height="70" fill="#2d2a26" opacity="0.08"/>
  <text x="48" y="{PLACEHOLDER_H-28}" font-family="sans-serif" font-size="20" fill="#2d2a26" opacity="0.6">text zone reserved here</text>
</svg>"""
    path.write_text(svg, encoding="utf-8")


def _gemini_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def _raster_refs(ap: AssembledPrompt, ref_base: Path | None) -> list[Path]:
    """Resolve the character reference images that Nano Banana can actually use as input
    (raster only — SVG placeholders are skipped)."""
    out: list[Path] = []
    if not ref_base:
        return out
    for rel in ap.reference_images or []:
        p = (ref_base / rel)
        if p.exists() and p.suffix.lower() in _RASTER_EXT:
            out.append(p)
    return out


def _gen_nano_banana(ap: AssembledPrompt, out_png: Path, ref_base: Path | None) -> bool:
    """Generate with Google's Nano Banana (Gemini image model).

    Nano Banana has no separate negative-prompt or seed field, so we fold the negative into
    the prompt as 'Avoid: ...'. Reference images are passed as input image parts, which is the
    strongest lever for character consistency this model offers.
    """
    key = _gemini_key()
    if not key:
        if "gemini" not in _warned_nokey:
            _warned_nokey.add("gemini")
            print("  ! no GEMINI_API_KEY/GOOGLE_API_KEY set — using placeholders. "
                  "Get a free key at https://aistudio.google.com/apikey", file=sys.stderr)
        return False
    import base64
    import json
    import urllib.error
    import urllib.request

    text = ap.prompt
    if ap.negative:
        text += f"\nAvoid: {ap.negative}."
    parts: list[dict] = [{"text": text}]
    for ref in _raster_refs(ap, ref_base):
        parts.append({"inline_data": {
            "mime_type": _RASTER_EXT[ref.suffix.lower()],
            "data": base64.b64encode(ref.read_bytes()).decode(),
        }})

    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            # 1K = smallest tier (~1MP); 4:3 at 1K is 1184x864. Keeps files small + on-cap.
            "imageConfig": {"aspectRatio": ap.aspect_ratio or "4:3", "imageSize": "1K"},
        },
    }
    model = os.getenv("GEMINI_IMAGE_MODEL", DEFAULT_NANO_BANANA_MODEL)
    # Image generation + responseModalities require the v1beta endpoint (v1 rejects them).
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent")
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            payload = json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("error", {}).get("message", detail)
        except Exception:  # noqa: BLE001
            pass
        hint = ""
        if e.code == 429 and "limit: 0" in detail:
            hint = (f"  → '{model}' image generation isn't available on the Gemini FREE tier "
                    "(free quota is 0). Enable billing on your Google Cloud project, or try a "
                    "different model via GEMINI_IMAGE_MODEL.")
        elif e.code == 429:
            hint = "  → rate-limited; wait and retry, or enable billing for higher limits."
        raise RuntimeError(f"HTTP {e.code}: {detail.strip()[:300]}{(chr(10) + hint) if hint else ''}")
    for cand in payload.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            blob = part.get("inline_data") or part.get("inlineData")
            if blob and blob.get("data"):
                data = base64.b64decode(blob["data"])
                data = _cap_image_bytes(data, int(os.getenv("GEMINI_MAX_EDGE", DEFAULT_MAX_EDGE)))
                out_png.parent.mkdir(parents=True, exist_ok=True)
                out_png.write_bytes(data)
                return True
    raise RuntimeError("Nano Banana returned no image part (response was text-only)")


def _gen_openai(ap: AssembledPrompt, out_png: Path) -> bool:
    if not os.getenv("OPENAI_API_KEY"):
        return False
    import base64
    import json
    import urllib.request
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps({
            "model": os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
            "prompt": ap.prompt + "\nAvoid: " + ap.negative,
            "size": "1024x768" if ap.aspect_ratio == "4:3" else "1024x1024",
            "n": 1,
        }).encode(),
        headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        payload = json.loads(r.read())
    b64 = payload["data"][0]["b64_json"]
    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_png.write_bytes(base64.b64decode(b64))
    return True


def try_real_provider(provider: str, ap: AssembledPrompt, out_png: Path,
                      ref_base: Path | None = None) -> bool:
    """Generate a real image with the chosen provider. Returns True on success, False to fall
    back to a placeholder. Guarded so the toolchain never hard-depends on a network/API."""
    try:
        if provider in ("gemini", "nano-banana"):
            return _gen_nano_banana(ap, out_png, ref_base)
        if provider == "openai":
            return _gen_openai(ap, out_png)
    except Exception as e:  # noqa: BLE001 — never let image gen break the pipeline
        print(f"  ! provider '{provider}' failed ({e}); using placeholder.", file=sys.stderr)
    return False


def split_ref(ref: str) -> tuple[str, str]:
    if "/" not in ref:
        raise SystemExit(f"expected <world>/<name>, got '{ref}'")
    world, name = ref.split("/", 1)
    return world, name


def gen_character_sheet(ref: str, provider: str, print_only: bool) -> None:
    world_slug, char_slug = split_ref(ref)
    world = load_world(world_slug, with_stories=False)
    char = world.characters.get(char_slug)
    if not char:
        raise SystemExit(f"no character '{char_slug}' in world '{world_slug}'")
    ap = assemble_character_sheet_prompt(world, char)
    print(f"--- character sheet: {char_slug} ---\n{ap.prompt}\nNEGATIVE: {ap.negative}\nSEED: {ap.seed}\n")
    if print_only:
        return
    refs_dir = world.dir / "characters" / f"{char_slug}.refs"
    out_png = refs_dir / "model-sheet.png"
    if provider != "placeholder" and try_real_provider(provider, ap, out_png, ref_base=world.dir):
        rel = out_png.relative_to(world.dir)
    else:
        out_svg = refs_dir / "model-sheet.svg"
        write_placeholder_svg(out_svg, f"{char.get('name')} — model sheet", ap, world)
        rel = out_svg.relative_to(world.dir)
    # Record as a reference image (path relative to the world dir).
    rel_str = str(rel)
    refs = char.setdefault("reference_images", [])
    if rel_str not in refs:
        refs.insert(0, rel_str)
    dump_yaml(char, world.dir / "characters" / f"{char_slug}.yaml")
    print(f"+ wrote {rel_str} and recorded it in reference_images")


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
        text_zone=img.get("text_zone") or (art.get("text_treatment", {}) or {}).get("placement", "lower third"),
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


def gen_story(ref: str, provider: str, only_page: int | None, seed_override: int | None,
              print_only: bool, *, qc_retries: int, qc_threshold: float,
              qc_model: str | None, qc_off: bool, verbose: bool = False) -> None:
    world_slug, story_slug = _resolve_story(ref)
    world = load_world(world_slug, with_stories=False)
    spath = ROOT / "worlds" / world_slug / "stories" / story_slug / "story.yaml"
    story = load_yaml(spath)
    images_dir = spath.parent / "images"
    changed = False

    for page in story.get("pages", []) or []:
        num = page.get("number", 0)
        if only_page is not None and num != only_page:
            continue
        ap = assemble_page_prompt(world, story, page)
        if seed_override is not None:
            ap.seed = seed_override
        print(f"--- page {num:02d} ---\n{ap.prompt}\nNEGATIVE: {ap.negative}  SEED: {ap.seed}\n")
        if print_only:
            continue
        title = f"{story.get('title','')} — p{num}"
        winner, qc_log = _run_best_of_n(
            ap, images_dir, world, world.dir, story, page, provider, num, title,
            qc_retries=qc_retries, qc_threshold=qc_threshold, qc_model=qc_model,
            qc_off=qc_off, verbose=verbose,
        )
        canonical = _finalize_winner(winner, images_dir, num)
        # Persist the QC log sidecar.
        qc_sidecar = images_dir / f"page-{num:02d}.qc.json"
        qc_sidecar.write_text(
            json.dumps({"page": num, "prompt_seed": ap.seed, "threshold": qc_threshold,
                          "attempts": qc_log, "winner": canonical.name}, indent=2),
            encoding="utf-8",
        )
        page.setdefault("image", {})["file"] = f"images/{canonical.name}"
        if not page["image"].get("alt"):
            page["image"]["alt"] = _auto_alt(page, ap)
        changed = True

    if changed and not print_only:
        dump_yaml(story, spath)
        print(f"+ updated {spath.relative_to(ROOT)} with image paths + alt text")


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


def verify_story(ref: str) -> int:
    """Re-assert the visual-consistency invariants for every page WITHOUT calling any
    provider (A4): each character in frame resolves and carries an appearance_token, and
    recurring characters have a locked seed + a reference image to anchor renders.

    Returns a process exit code: 0 = ready to illustrate on-model, 1 = hard problems."""
    world_slug, story_slug = _resolve_story(ref)
    world = load_world(world_slug, with_stories=False)
    spath = ROOT / "worlds" / world_slug / "stories" / story_slug / "story.yaml"
    story = load_yaml(spath)
    pages = story.get("pages", []) or []

    errors: list[str] = []
    warnings: list[str] = []
    appearances: dict[str, int] = {}
    for page in pages:
        num = page.get("number", 0)
        present = (page.get("image", {}) or {}).get("characters_present", []) or []
        for slug in present:
            appearances[slug] = appearances.get(slug, 0) + 1
            char = world.characters.get(slug)
            if not char:
                errors.append(f"p{num}: character '{slug}' is not in world '{world_slug}'")
            elif not char.get("appearance_token"):
                errors.append(f"p{num}: character '{slug}' has no appearance_token to inject")
        # Assembling proves the prompt builds and shows what would be sent.
        assemble_page_prompt(world, story, page)

    for slug, count in appearances.items():
        char = world.characters.get(slug)
        if not char or count < 2:
            continue
        if not char.get("reference_images"):
            warnings.append(f"recurring '{slug}' has no reference_images (model sheet) to anchor renders")
        if char.get("seed") is None:
            warnings.append(f"recurring '{slug}' has no locked seed (renders won't be reproducible)")

    print(f"--- verify: {world_slug}/{story_slug} ({len(pages)} pages) ---")
    for w in warnings:
        print(f"  ⚠  {w}")
    for e in errors:
        print(f"  ✗  {e}")
    if errors:
        print(f"  => NOT READY ({len(errors)} blocker(s))")
        return 1
    print("  => READY to illustrate on-model" + (f" ({len(warnings)} warning(s))" if warnings else ""))
    return 0


def _auto_alt(page: dict, ap: AssembledPrompt) -> str:
    base = (page.get("image", {}) or {}).get("prompt", "").strip().rstrip(".")
    who = ", ".join(ap.characters)
    return (base + (f" — featuring {who}" if who else "")).strip() or "Illustration"


def _resolve_story(ref: str) -> tuple[str, str]:
    p = Path(ref)
    if p.is_dir() and (p / "story.yaml").exists():
        story = p.name
        world = p.parent.parent.name
        return world, story
    if "/" in ref:
        return tuple(ref.split("/", 1))  # type: ignore[return-value]
    raise SystemExit(f"expected <world>/<story> or a story dir, got '{ref}'")


def main() -> int:
    load_dotenv()  # read .env (GEMINI_API_KEY, IMAGE_PROVIDER, ...) before defaults are bound
    ap = argparse.ArgumentParser(description="Assemble prompts and generate illustrations.")
    ap.add_argument("target", nargs="?", help="<world>/<story> or a story dir")
    ap.add_argument("--character", help="<world>/<char> — generate a model sheet instead")
    ap.add_argument("--page", type=int, help="only this page number")
    ap.add_argument("--seed", type=int, help="override seed")
    ap.add_argument("--provider", default=os.getenv("IMAGE_PROVIDER", "nano-banana"),
                    choices=["nano-banana", "gemini", "openai", "placeholder"],
                    help="default: nano-banana (Google Gemini image model); falls back to "
                         "placeholders if no API key is set")
    ap.add_argument("--print-prompts", action="store_true", help="dry run: only print prompts")
    ap.add_argument("--verify", action="store_true",
                    help="check render-readiness invariants (tokens/seeds/refs) without "
                         "calling any provider; exit 1 if a character can't render on-model")
    ap.add_argument("--qc-off", action="store_true",
                    help="disable vision QC (single render per page, no Ollama call)")
    ap.add_argument("--qc-retries", type=int, default=2,
                    help="extra retries if QC rejects a render (default 2 → up to 3 candidates)")
    ap.add_argument("--qc-threshold", type=float, default=7.0,
                    help="minimum QC score (0-10) for a render to be accepted (default 7.0)")
    ap.add_argument("--qc-model", default=None,
                    help="Ollama vision model for QC (default: first vision-capable model pulled)")
    ap.add_argument("--qc-verbose", action="store_true",
                    help="print extra diagnostic info when QC calls fail")
    args = ap.parse_args()

    if args.character:
        gen_character_sheet(args.character, args.provider, args.print_prompts)
        return 0
    if not args.target:
        ap.error("provide <world>/<story> or --character <world>/<char>")
    if args.verify:
        return verify_story(args.target)
    gen_story(args.target, args.provider, args.page, args.seed, args.print_prompts,
              qc_retries=args.qc_retries, qc_threshold=args.qc_threshold,
              qc_model=args.qc_model, qc_off=args.qc_off, verbose=args.qc_verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
