"""Talk to a local ComfyUI server (the kyuz0 Strix-Halo container) to render and edit images.

This is the single place that knows how to drive ComfyUI. Everything else (the providers,
the QC/edit loop) goes through the small surface here:

  - ``is_available()``                  — is a ComfyUI server reachable?
  - ``generate(kind, prompt, ...)``     — text-to-image with "qwen" or "flux2"  -> PNG bytes
  - ``edit(instruction, input_png, ...)`` — Qwen-Image-Edit a PNG in place      -> PNG bytes

How it works: we ship the *validated* ComfyUI API-format workflows (the exact graphs that were
benchmarked on gfx1151) as JSON templates under ``comfy_workflows/``. Rather than hand-build
node graphs in Python (brittle), we LOAD a template and patch a few fields generically — by
node ``class_type``, never by hardcoded id — so a template can be re-exported from ComfyUI and
dropped in without code changes:
  * the positive text-encode node (the one whose prompt is non-empty in the template)
  * the negative text-encode node (the empty one)            — t2i only
  * the sampler seed (KSampler.seed / RandomNoise.noise_seed)
  * the latent dimensions (Empty*LatentImage width/height)
  * the LoadImage filename                                   — edit only

All model filenames live in the templates and can be overridden by env (see ``MODEL_ENV``) so a
re-quantized model is a one-line change, not a code edit.

Everything is best-effort and stdlib-only: if the server is down or a render fails, callers get
a clear exception and fall back (placeholders / keep-first), exactly like the other providers.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

# Where ComfyUI lives. The kyuz0 container publishes :8188. Override with COMFYUI_HOST.
HOST = os.environ.get("COMFYUI_HOST", "127.0.0.1:8188")
# Generation can be slow on an iGPU (FLUX.2 ~6 min). Generous ceiling; override per need.
GEN_TIMEOUT = float(os.environ.get("COMFYUI_TIMEOUT", "900"))

_TEMPLATES = Path(__file__).parent / "comfy_workflows"
_TEMPLATE_FILE = {"qwen": "qwen_t2i.json", "flux2": "flux2_t2i.json", "edit": "qwen_edit.json"}

# Optional env overrides for model filenames, applied to the matching loader node by class_type.
# Keeps re-quantized / renamed checkpoints a config change, not a code change.
MODEL_ENV = {
    "UnetLoaderGGUF": ("unet_name", {"qwen": "COMFYUI_QWEN_UNET", "flux2": "COMFYUI_FLUX2_UNET",
                                     "edit": "COMFYUI_QWEN_EDIT_UNET"}),
}

_TEXT_ENCODE_CLASSES = {"CLIPTextEncode", "TextEncodeQwenImageEditPlus", "TextEncodeQwenImageEdit"}
_LATENT_CLASSES = {"EmptySD3LatentImage", "EmptyFlux2LatentImage", "EmptyLatentImage"}


def _http_json(url: str, payload: dict | None = None, timeout: float = 30.0) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def is_available(host: str = HOST) -> bool:
    """True if a ComfyUI server answers on ``host``. Cheap; used for preflight + fallback."""
    try:
        _http_json(f"http://{host}/system_stats", timeout=4)
        return True
    except Exception:  # noqa: BLE001 — offline / refused / DNS
        return False


def _aspect_to_wh(aspect: str) -> tuple[int, int]:
    """Map an aspect ratio to a ~1MP render size that the models like (multiples of 16)."""
    table = {
        "1:1": (1024, 1024), "4:3": (1152, 864), "3:4": (864, 1152),
        "16:9": (1280, 720), "9:16": (720, 1280), "3:2": (1216, 832), "2:3": (832, 1216),
    }
    return table.get((aspect or "4:3").strip(), (1152, 864))


def _load_template(kind: str) -> dict:
    name = _TEMPLATE_FILE.get(kind)
    if not name:
        raise ValueError(f"unknown workflow kind {kind!r} (expected one of {list(_TEMPLATE_FILE)})")
    return json.loads((_TEMPLATES / name).read_text())


def _patch(wf: dict, kind: str, *, positive: str, negative: str | None, seed: int,
           width: int | None, height: int | None, image_name: str | None) -> dict:
    """Patch a loaded template in place (see module docstring for what/why). Returns wf."""
    # Text encoders: the node carrying a non-empty prompt in the template is the positive one.
    def _text_field(inp: dict) -> str | None:
        for f in ("text", "prompt"):
            if f in inp:
                return f
        return None

    for node in wf.values():
        ct = node.get("class_type")
        inp = node.get("inputs", {})
        if ct in _TEXT_ENCODE_CLASSES:
            field = _text_field(inp)
            if field is None:
                continue
            if (inp.get(field) or "").strip():       # non-empty in template -> positive
                inp[field] = positive
            elif negative is not None and ct == "CLIPTextEncode":  # empty -> negative (t2i)
                inp[field] = negative
        elif ct in ("KSampler",) and "seed" in inp:
            inp["seed"] = seed
        elif ct == "RandomNoise" and "noise_seed" in inp:
            inp["noise_seed"] = seed
        elif ct in _LATENT_CLASSES:
            if width:
                inp["width"] = width
            if height:
                inp["height"] = height
        elif ct == "LoadImage" and image_name is not None:
            inp["image"] = image_name
        # Model filename overrides from env.
        if ct in MODEL_ENV:
            key, env_by_kind = MODEL_ENV[ct]
            override = os.environ.get(env_by_kind.get(kind, ""))
            if override:
                inp[key] = override
    return wf


def upload_image(path: Path, host: str = HOST) -> str:
    """Upload a PNG to ComfyUI's input dir (multipart) and return the stored filename to
    reference from a LoadImage node. Stdlib-only multipart so we keep zero deps."""
    boundary = f"----comfy{uuid.uuid4().hex}"
    body = bytearray()
    body += f"--{boundary}\r\n".encode()
    body += (f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\n'
             f"Content-Type: image/png\r\n\r\n").encode()
    body += path.read_bytes()
    body += f"\r\n--{boundary}\r\n".encode()
    body += 'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'.encode()
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"http://{host}/upload/image", data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        info = json.loads(r.read())
    name = info.get("name") or path.name
    return f"{info['subfolder']}/{name}" if info.get("subfolder") else name


def _run(wf: dict, host: str, timeout: float) -> bytes:
    """Queue a workflow, wait for it, and return the first output image's PNG bytes."""
    cid = uuid.uuid4().hex
    pid = _http_json(f"http://{host}/prompt", {"prompt": wf, "client_id": cid})["prompt_id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        hist = _http_json(f"http://{host}/history/{pid}", timeout=30)
        entry = hist.get(pid)
        if not entry:
            continue
        status = entry.get("status", {})
        if status.get("status_str") == "error":
            raise RuntimeError(f"ComfyUI execution error: {json.dumps(status)[:400]}")
        for node in entry.get("outputs", {}).values():
            for im in node.get("images", []):
                q = urllib.parse.urlencode({"filename": im["filename"],
                                            "subfolder": im.get("subfolder", ""),
                                            "type": im.get("type", "output")})
                with urllib.request.urlopen(f"http://{host}/view?{q}", timeout=60) as r:
                    return r.read()
    raise TimeoutError(f"ComfyUI render exceeded {timeout:.0f}s")


def generate(kind: str, prompt: str, *, negative: str = "", seed: int | None = None,
             aspect_ratio: str = "4:3", host: str = HOST, timeout: float = GEN_TIMEOUT) -> bytes:
    """Text-to-image with ``kind`` in {"qwen", "flux2"}. Returns PNG bytes."""
    w, h = _aspect_to_wh(aspect_ratio)
    wf = _patch(_load_template(kind), kind, positive=prompt, negative=negative,
                seed=seed if seed is not None else uuid.uuid4().int % 2_000_000_000,
                width=w, height=h, image_name=None)
    return _run(wf, host, timeout)


def edit(instruction: str, input_png: Path, *, seed: int | None = None,
         host: str = HOST, timeout: float = GEN_TIMEOUT) -> bytes:
    """Qwen-Image-Edit ``input_png`` per ``instruction``. Returns the edited PNG bytes."""
    name = upload_image(input_png, host)
    wf = _patch(_load_template("edit"), "edit", positive=instruction, negative=None,
                seed=seed if seed is not None else uuid.uuid4().int % 2_000_000_000,
                width=None, height=None, image_name=name)
    return _run(wf, host, timeout)
