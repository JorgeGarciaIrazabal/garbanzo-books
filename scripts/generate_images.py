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

Env:
  GEMINI_API_KEY / GOOGLE_API_KEY   key for Nano Banana (free tier from Google AI Studio)
  GEMINI_IMAGE_MODEL                 override model (default gemini-2.5-flash-image; e.g.
                                     gemini-3-pro-image = "Nano Banana Pro", gemini-3.1-flash-image)
  IMAGE_PROVIDER                     default provider (default: nano-banana)
Note: Gemini-generated images carry an invisible SynthID watermark.
"""
from __future__ import annotations

import argparse
import html
import os
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.model import (ROOT, World, dump_yaml, load_dotenv, load_world, load_yaml)  # noqa: E402
from lib.prompt_assembly import (AssembledPrompt, assemble_character_sheet_prompt,  # noqa: E402
                                 assemble_page_prompt)

PLACEHOLDER_W, PLACEHOLDER_H = 1024, 768

# Google "Nano Banana". gemini-2.5-flash-image is the original; gemini-3-pro-image is
# "Nano Banana Pro"; gemini-3.1-flash-image is the newer flash. Override via GEMINI_IMAGE_MODEL.
DEFAULT_NANO_BANANA_MODEL = "gemini-2.5-flash-image"
# Longest-edge cap for generated images. Nano Banana's native 1K 4:3 output is 1184x864, so
# this keeps the full 4:3 frame (a little past 1024 by design) while blocking 2K/4K. Anything
# larger is downscaled, preserving aspect ratio. Override with GEMINI_MAX_EDGE.
DEFAULT_MAX_EDGE = 1184
_RASTER_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
_warned_nokey = set()


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
    out = []
    for s in (world.data.get("art_style", {}) or {}).get("palette", []) or []:
        h = str(s.get("hex", "")).lstrip("#")
        if len(h) == 6:
            out.append("#" + h)
    return out or ["#f4e1c1", "#6b8f71", "#d98a5b", "#3d5a73"]


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


def gen_story(ref: str, provider: str, only_page: int | None, seed_override: int | None,
              print_only: bool) -> None:
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
        out_png = images_dir / f"page-{num:02d}.png"
        if provider != "placeholder" and try_real_provider(provider, ap, out_png, ref_base=world.dir):
            fname = out_png.name
        else:
            out_svg = images_dir / f"page-{num:02d}.svg"
            write_placeholder_svg(out_svg, title, ap, world)
            fname = out_svg.name
        page.setdefault("image", {})["file"] = f"images/{fname}"
        if not page["image"].get("alt"):
            page["image"]["alt"] = _auto_alt(page, ap)
        changed = True

    if changed and not print_only:
        dump_yaml(story, spath)
        print(f"+ updated {spath.relative_to(ROOT)} with image paths + alt text")


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
    args = ap.parse_args()

    if args.character:
        gen_character_sheet(args.character, args.provider, args.print_prompts)
        return 0
    if not args.target:
        ap.error("provide <world>/<story> or --character <world>/<char>")
    gen_story(args.target, args.provider, args.page, args.seed, args.print_prompts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
