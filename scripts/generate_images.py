#!/usr/bin/env python3
"""Generate on-model illustrations by ASSEMBLING prompts (never hand-writing them).

Prompt = page scene + each present character's appearance_token + world prompt_style_block
       + palette + negative prompt + seed + reference images   (see lib/prompt_assembly.py)

Usage:
    uv run python scripts/generate_images.py worlds/<world>/stories/<story>   # all pages
    uv run python scripts/generate_images.py <world>/<story> --page 3         # one page
    uv run python scripts/generate_images.py --character <world>/<char>       # model sheet
    uv run python scripts/generate_images.py <world>/<story> --print-prompts   # dry run

This module is the CLI + the story/character drivers; the moving parts live in lib/:
  lib/prompt_assembly.py  — assembles the prompt (scene + tokens + style + palette + seed + refs)
  lib/image_providers.py  — the real providers (nano-banana / openai / antigravity) + dispatch
  lib/image_placeholder.py— the offline self-describing SVG fallback
  lib/image_pipeline.py   — best-of-N render + local-vision QC + winner finalisation

Providers:
  - "antigravity" (default) — Google Gemini image generation via the local Antigravity CLI
    (agy) and its generate_image tool. Uses your existing Google OAuth session; no API key
    required. Set ANTIGRAVITY_MODEL to override the default image model.
  - "nano-banana" — Google Gemini's "Nano Banana" image model (gemini-2.5-flash-image).
    Free to start: get a key at https://aistudio.google.com/apikey and set GEMINI_API_KEY (or
    GOOGLE_API_KEY). Crucially, Nano Banana accepts the character's reference images as INPUT,
    which anchors character consistency far better than text alone.
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
  IMAGE_PROVIDER                     default provider (default: antigravity)
  OLLAMA_HOST                        Ollama endpoint (default http://localhost:11434)
  VISION_QC_MODEL                    override the auto-picked vision model
                                     (default: first vision-capable model pulled)
Note: Gemini-generated images carry an invisible SynthID watermark.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.model import (ROOT, dump_yaml, load_dotenv, load_world, load_yaml)  # noqa: E402
from lib.progress import finish as _progress_finish  # noqa: E402
from lib.progress import report as _progress_report  # noqa: E402
from lib.prompt_assembly import (AssembledPrompt, assemble_character_sheet_prompt,  # noqa: E402
                                 assemble_page_prompt)
# Re-exported so callers (and the test-suite) can keep reaching these through generate_images.
from lib.image_placeholder import (PLACEHOLDER_H, PLACEHOLDER_W, _palette_hexes,  # noqa: E402,F401
                                   write_placeholder_svg)
from lib.image_providers import (_cap_image_bytes, _gemini_key, _gen_antigravity,  # noqa: E402,F401
                                 _gen_nano_banana, _gen_openai, _raster_refs, try_real_provider)
from lib.image_pipeline import (_finalize_winner, _generate_one_candidate,  # noqa: E402,F401
                                _qc_candidate, _run_best_of_n, _write_prompt_sidecar)


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


def gen_story(ref: str, provider: str, only_page: int | None, seed_override: int | None,
              print_only: bool, *, qc_retries: int, qc_threshold: float,
              qc_model: str | None, qc_off: bool, verbose: bool = False,
              jobs: int = 1) -> None:
    world_slug, story_slug = _resolve_story(ref)
    world = load_world(world_slug, with_stories=False)
    spath = ROOT / "worlds" / world_slug / "stories" / story_slug / "story.yaml"
    story = load_yaml(spath)
    images_dir = spath.parent / "images"

    # Assemble every prompt up front (cheap, deterministic, and the dry-run output stays
    # ordered), then render. Each page's render is fully self-contained — its own prompt,
    # its own page-NN-* candidate files, its own page dict and qc sidecar — so pages can
    # render CONCURRENTLY. A 16-page book at ~30s/page is ~8 min sequential; with --jobs 4
    # it's ~2 min, which is most of the wall-clock cost of making a book.
    work: list[tuple[dict, AssembledPrompt, int]] = []
    for page in story.get("pages", []) or []:
        num = page.get("number", 0)
        if only_page is not None and num != only_page:
            continue
        ap = assemble_page_prompt(world, story, page)
        if seed_override is not None:
            ap.seed = seed_override
        print(f"--- page {num:02d} ---\n{ap.prompt}\nNEGATIVE: {ap.negative}  SEED: {ap.seed}\n")
        if not print_only:
            work.append((page, ap, num))

    def _render_page(item: tuple[dict, AssembledPrompt, int]) -> None:
        page, ap, num = item
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
        print(f"  ✓ page {num:02d} done → {canonical.name}")
        # Live progress for the studio's activity strip (best-effort side-channel —
        # stdout from this script only reaches the UI when the whole run finishes).
        with done_lock:
            done_count[0] += 1
            _progress_report("illustrating", done_count[0], len(work), f"page {num:02d}")

    done_lock = threading.Lock()
    done_count = [0]
    if work:
        _progress_report("illustrating", 0, len(work), story.get("title", ""))
    try:
        if jobs > 1 and len(work) > 1 and provider != "placeholder":
            from concurrent.futures import ThreadPoolExecutor
            print(f"rendering {len(work)} page(s) with {jobs} parallel jobs…")
            with ThreadPoolExecutor(max_workers=jobs) as ex:
                # list() drains the iterator so the first worker exception propagates.
                list(ex.map(_render_page, work))
        else:
            for item in work:
                _render_page(item)
    finally:
        if work:
            _progress_finish()

    if work:
        dump_yaml(story, spath)
        print(f"+ updated {spath.relative_to(ROOT)} with image paths + alt text")


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
    ap.add_argument("--provider", default=os.getenv("IMAGE_PROVIDER", "antigravity"),
                    choices=["nano-banana", "gemini", "openai", "antigravity", "placeholder"],
                    help="default: antigravity (local agy CLI via Google OAuth, no API key); "
                         "nano-banana/gemini use GEMINI_API_KEY and fall back to placeholders "
                         "if no key is set")
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
    ap.add_argument("--jobs", type=int, default=int(os.getenv("IMAGE_JOBS", "4")),
                    help="render this many pages concurrently (default 4, env IMAGE_JOBS; "
                         "ignored for the placeholder provider)")
    ap.add_argument("--print-timeout", default=os.getenv("ANTIGRAVITY_TIMEOUT", "240s"),
                    help="timeout for the Antigravity CLI in print mode (default: 240s, or ANTIGRAVITY_TIMEOUT)")
    args = ap.parse_args()

    if args.print_timeout:
        os.environ["ANTIGRAVITY_TIMEOUT"] = args.print_timeout

    if args.character:
        gen_character_sheet(args.character, args.provider, args.print_prompts)
        return 0
    if not args.target:
        ap.error("provide <world>/<story> or --character <world>/<char>")
    if args.verify:
        return verify_story(args.target)
    gen_story(args.target, args.provider, args.page, args.seed, args.print_prompts,
              qc_retries=args.qc_retries, qc_threshold=args.qc_threshold,
              qc_model=args.qc_model, qc_off=args.qc_off, verbose=args.qc_verbose,
              jobs=max(1, args.jobs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
