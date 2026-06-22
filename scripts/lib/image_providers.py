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
# Run-scoped flags. Once antigravity's image quota is exhausted (429) we stop calling it and
# route the rest of the run's images through the nano-banana fallback — one wasted 429 per page
# adds up across a book.
_antigravity_state: set[str] = set()


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
    import hashlib
    import re
    import subprocess
    import time

    agy = Path.home() / ".local" / "bin" / "agy"
    if not agy.exists():
        agy = Path("agy")
    cmd = [str(agy), "--dangerously-skip-permissions"]
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
    cmd += ["--print", agent_prompt]

    out_png.parent.mkdir(parents=True, exist_ok=True)
    # Run agy from a scratch directory so the project repo is not its workspace context.
    scratch_dir = Path("/tmp/opencode/agy-scratch")
    scratch_dir.mkdir(parents=True, exist_ok=True)

    brain = Path.home() / ".gemini" / "antigravity-cli" / "brain"

    def _md5_file(p: Path) -> str | None:
        try:
            return hashlib.md5(p.read_bytes()).hexdigest()
        except OSError:
            return None

    # Snapshot what exists BEFORE the run so we can tell a freshly-generated image apart from
    # the recurring sample/temp art that already litters agy's brain/ tree (every session drops
    # identical copies of a few stock pictures into .tempmediaStorage). Index pre-existing
    # rasters by byte-size — a cheap stat — and only hash on a size collision, so this stays fast.
    before_by_size: dict[int, list[Path]] = {}
    if brain.exists():
        for p in brain.rglob("*"):
            if p.is_file() and p.suffix.lower() in _RASTER_EXT:
                try:
                    before_by_size.setdefault(p.stat().st_size, []).append(p)
                except OSError:
                    pass
    before = {p for grp in before_by_size.values() for p in grp}

    # Reference images we attach must never be mistaken for generated output either.
    ref_hashes = {h for h in (_md5_file(r) for r in _raster_refs(ap, ref_base)) if h}
    _pre_hashes_by_size: dict[int, set[str]] = {}

    def _is_recycled(candidate: Path) -> bool:
        """True if this file is a reference image, or content that already existed before the
        run (agy's recurring sample art) — i.e. NOT a fresh, prompt-driven render. This is the
        guard against every page being saved as the same stale stock image."""
        ch = _md5_file(candidate)
        if ch is None or ch in ref_hashes:
            return True
        try:
            size = candidate.stat().st_size
        except OSError:
            return True
        if size not in _pre_hashes_by_size:
            _pre_hashes_by_size[size] = {
                h for h in (_md5_file(q) for q in before_by_size.get(size, [])) if h}
        return ch in _pre_hashes_by_size[size]

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

    # The agent reports what it wrote as markdown links. Those paths live under THIS
    # invocation's own brain/<session>/ tree, so they are the only race-safe signal: when
    # several pages render concurrently they share the brain/ root, and scanning it wholesale
    # lets one page pick up another's fresh output (that cross-talk collapsed many pages onto a
    # single image). So we trust the links, and otherwise scan only this run's session dir.
    linked: list[Path] = []
    for pattern in (r'\]\(file://([^)]+)\)', r'!\[[^\]]*\]\(([^)]+)\)'):
        for url in re.findall(pattern, stdout):
            linked.append(Path(url.replace("file://", "")))

    # 1) Prefer a raster the agent explicitly says it saved (and that is a genuine fresh render,
    #    not a reference image or the recurring stock art that already litters brain/).
    for candidate in linked:
        if (candidate.exists() and candidate.suffix.lower() in _RASTER_EXT
                and not _is_recycled(candidate)):
            out_png.write_bytes(_cap_image_bytes(candidate.read_bytes(), cap_edge))
            return True

    # 2) Otherwise scan ONLY this invocation's own session dir(s) — never the shared brain/ root.
    #    The session id appears in any path the agent mentioned.
    for sid in set(re.findall(r'/brain/([0-9a-fA-F-]{36})\b', stdout)):
        sess = brain / sid
        if not sess.exists():
            continue
        cands = [p for p in sess.rglob("*")
                 if p.is_file() and p.suffix.lower() in _RASTER_EXT and p not in before]
        for candidate in sorted(cands, key=lambda p: p.stat().st_mtime, reverse=True):
            if _is_recycled(candidate):
                continue
            out_png.write_bytes(_cap_image_bytes(candidate.read_bytes(), cap_edge))
            return True

    # 3) Last resort: an embedded base64 image in the text output.
    b64_match = re.search(r'data:image/(?:png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=]+)', stdout)
    if b64_match:
        raw = base64.b64decode(b64_match.group(1))
        if hashlib.md5(raw).hexdigest() not in ref_hashes:
            out_png.write_bytes(_cap_image_bytes(raw, cap_edge))
            return True

    if re.search(r'\b429\b|RESOURCE_EXHAUSTED|quota', stdout + stderr, re.I):
        _antigravity_state.add("exhausted")
        print("  ! antigravity image quota exhausted (HTTP 429 RESOURCE_EXHAUSTED) — no image "
              "generated.", file=sys.stderr)
    else:
        print("  ! antigravity returned no fresh, prompt-driven image; treating as a failed "
              "render.", file=sys.stderr)
    return False


def _gen_comfyui(ap: AssembledPrompt, out_png: Path, kind: str) -> bool:
    """Generate locally via a ComfyUI server (the Strix-Halo container), with ``kind`` in
    {"qwen", "flux2"}. No API key, no network — runs on the local iGPU. Reference images are
    not forwarded (these t2i graphs have no image input); character consistency rides on the
    dense appearance_token text already in ``ap.prompt``, same as the antigravity path."""
    from . import comfyui_client as cc
    if not cc.is_available():
        if "comfyui" not in _warned_nokey:
            _warned_nokey.add("comfyui")
            print(f"  ! no ComfyUI server at {cc.HOST} — start the toolbox container "
                  "(experiments/qwen-image-edit/docker_comfyui.sh) or set COMFYUI_HOST.",
                  file=sys.stderr)
        return False
    data = cc.generate(kind, ap.prompt, negative=ap.negative or "", seed=ap.seed,
                       aspect_ratio=ap.aspect_ratio or "4:3")
    data = _cap_image_bytes(data, int(os.getenv("GEMINI_MAX_EDGE", DEFAULT_MAX_EDGE)))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_png.write_bytes(data)
    return True


def try_real_provider(provider: str, ap: AssembledPrompt, out_png: Path,
                      ref_base: Path | None = None) -> bool:
    """Generate a real image with the chosen provider. Returns True on success, False to fall
    back to a placeholder. Guarded so the toolchain never hard-depends on a network/API."""
    try:
        if provider in ("local", "qwen", "qwen-image"):
            return _gen_comfyui(ap, out_png, "qwen")
        if provider == "flux2":
            return _gen_comfyui(ap, out_png, "flux2")
        if provider in ("gemini", "nano-banana"):
            return _gen_nano_banana(ap, out_png, ref_base)
        if provider == "openai":
            return _gen_openai(ap, out_png)
        if provider == "antigravity":
            return _gen_antigravity_or_fallback(ap, out_png, ref_base)
    except Exception as e:  # noqa: BLE001 — never let image gen break the pipeline
        print(f"  ! provider '{provider}' failed ({e}); using placeholder.", file=sys.stderr)
    return False


def _gen_antigravity_or_fallback(ap: AssembledPrompt, out_png: Path,
                                 ref_base: Path | None) -> bool:
    """Try antigravity; if its image quota is exhausted (or it otherwise can't produce) and a
    GEMINI_API_KEY is available, fall back to nano-banana so a book still renders end-to-end.
    Once exhausted in this run, skip antigravity entirely to avoid a wasted 429 per page."""
    if "exhausted" not in _antigravity_state:
        if _gen_antigravity(ap, out_png, ref_base):
            return True

    # Antigravity couldn't deliver. Fall back to the nano-banana API if a key is configured.
    if not _gemini_key():
        return False
    if "exhausted" in _antigravity_state and "fellback" not in _antigravity_state:
        _antigravity_state.add("fellback")
        print("  → antigravity quota exhausted; rendering remaining images with nano-banana "
              "(Gemini API).", file=sys.stderr)
    try:
        return _gen_nano_banana(ap, out_png, ref_base)
    except Exception as e:  # noqa: BLE001
        print(f"  ! nano-banana fallback failed ({e}); using placeholder.", file=sys.stderr)
        return False
