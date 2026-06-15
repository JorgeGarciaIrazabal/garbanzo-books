"""The real image providers — and the guarded dispatch that never breaks the pipeline.

Each ``_gen_*`` returns True after writing ``out_png``, or False to fall back to a placeholder.
``try_real_provider`` picks the provider and swallows any exception (network/API/CLI), so the
toolchain has no hard dependency on a key being present or a service being up. Providers:
  - nano-banana / gemini : Google Gemini image model (GEMINI_API_KEY / GOOGLE_API_KEY)
  - openai               : OpenAI Images, gpt-image-1 (OPENAI_API_KEY)
  - antigravity          : the local agy CLI's generate_image tool, via Google OAuth (no key)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .prompt_assembly import AssembledPrompt

# Google "Nano Banana". gemini-2.5-flash-image is the original; gemini-3-pro-image is
# "Nano Banana Pro"; gemini-3.1-flash-image is the newer flash. Override via GEMINI_IMAGE_MODEL.
DEFAULT_NANO_BANANA_MODEL = "gemini-2.5-flash-image"
# Longest-edge cap for generated images. Nano Banana's native 1K 4:3 output is 1184x864, so
# this keeps the full 4:3 frame (a little past 1024 by design) while blocking 2K/4K. Anything
# larger is downscaled, preserving aspect ratio. Override with GEMINI_MAX_EDGE.
DEFAULT_MAX_EDGE = 1184
_RASTER_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
_warned_nokey: set[str] = set()
_warned_antigravity: set[str] = set()


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
            "model": os.getenv("OPENAI_API_MODEL", "gpt-image-1"),
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


def _gen_antigravity(ap: AssembledPrompt, out_png: Path, ref_base: Path | None = None) -> bool:
    """Generate a real image via the Antigravity CLI (agy) agent and its generate_image tool.

    This uses the user's existing Google OAuth session, so no GEMINI_API_KEY is required.
    We prompt the agent non-interactively; it writes the generated image into its own
    ``brain/`` artifact tree. We then locate the newest raster artifact it produced and copy
    it into the canonical pipeline path. Reference images are not forwarded automatically
    because agy's tool interface doesn't accept arbitrary inline image bytes; on-model
    consistency therefore depends on the dense appearance_token text in the assembled prompt.
    """
    import base64
    import re
    import subprocess
    import time

    agy = Path.home() / ".local" / "bin" / "agy"
    if not agy.exists():
        agy = Path("agy")
    cmd = [str(agy), "--print", "--dangerously-skip-permissions"]
    timeout_s = os.getenv("ANTIGRAVITY_TIMEOUT", "240s")
    cmd += ["--print-timeout", timeout_s]

    if "antigravity" not in _warned_antigravity:
        _warned_antigravity.add("antigravity")
        print("  → using Antigravity CLI (agy) generate_image tool via OAuth", file=sys.stderr)

    text = ap.prompt
    if ap.negative:
        text += f"\nAvoid: {ap.negative}."
    size = "1024x768" if ap.aspect_ratio == "4:3" else "1024x1024"

    agent_prompt = (
        "You are an image-generation assistant. Do NOT edit files, write code, or run tests. "
        "Your ONLY job is to use the generate_image tool to create an image and save it.\n\n"
        f"Use the generate_image tool to create the following image. "
        f"Size {size}, PNG format. Save the final PNG file.\n\n{text}"
    )
    cmd.append(agent_prompt)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    # Run agy from a scratch directory so the project repo is not its workspace context.
    scratch_dir = Path("/tmp/opencode/agy-scratch")
    scratch_dir.mkdir(parents=True, exist_ok=True)

    brain = Path.home() / ".gemini" / "antigravity-cli" / "brain"
    before = {p for p in brain.rglob("*") if p.is_file()} if brain.exists() else set()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=360, cwd=scratch_dir,
                                env={**os.environ, "ANTIGRAVITY_MODEL":
                                     os.getenv("ANTIGRAVITY_MODEL", "gemini-3.1-flash-image")})
    except FileNotFoundError:
        print("  ! antigravity CLI (agy) not found at ~/.local/bin/agy", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print("  ! antigravity CLI timed out", file=sys.stderr)
        return False

    stdout = result.stdout or ""
    stderr = result.stderr or ""

    if result.returncode != 0:
        print(f"  ! antigravity CLI failed (exit {result.returncode}): {stderr[:400]}",
              file=sys.stderr)
        return False

    cap_edge = int(os.getenv("GEMINI_MAX_EDGE", DEFAULT_MAX_EDGE))

    # Wait briefly for the agent to flush the artifact to disk.
    time.sleep(0.5)

    # The agent may write the file to a path it mentions in stdout; prefer that.
    for pattern in (r'\[([^\]]+)\]\(file://([^)]+)\)', r'!\[([^\]]*)\]\(([^)]+)\)'):
        for _label, file_url in re.findall(pattern, stdout):
            candidate = Path(file_url.replace("file://", ""))
            if candidate.exists() and candidate.suffix.lower() in _RASTER_EXT:
                out_png.write_bytes(_cap_image_bytes(candidate.read_bytes(), cap_edge))
                return True

    # Fall back: pick the newest raster artifact created under ~/.gemini/antigravity-cli/brain.
    after = {p for p in brain.rglob("*") if p.is_file()}
    new_files = after - before
    raster = [p for p in new_files if p.suffix.lower() in _RASTER_EXT]
    if raster:
        newest = max(raster, key=lambda p: p.stat().st_mtime)
        out_png.write_bytes(_cap_image_bytes(newest.read_bytes(), cap_edge))
        return True

    # Last resort: embedded base64 image in the text output.
    b64_match = re.search(r'data:image/(?:png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=]+)', stdout)
    if b64_match:
        out_png.write_bytes(_cap_image_bytes(base64.b64decode(b64_match.group(1)), cap_edge))
        return True

    print("  ! antigravity did not return or save a usable image", file=sys.stderr)
    return False


def try_real_provider(provider: str, ap: AssembledPrompt, out_png: Path,
                      ref_base: Path | None = None) -> bool:
    """Generate a real image with the chosen provider. Returns True on success, False to fall
    back to a placeholder. Guarded so the toolchain never hard-depends on a network/API."""
    try:
        if provider in ("gemini", "nano-banana"):
            return _gen_nano_banana(ap, out_png, ref_base)
        if provider == "openai":
            return _gen_openai(ap, out_png)
        if provider == "antigravity":
            return _gen_antigravity(ap, out_png, ref_base)
    except Exception as e:  # noqa: BLE001 — never let image gen break the pipeline
        print(f"  ! provider '{provider}' failed ({e}); using placeholder.", file=sys.stderr)
    return False
