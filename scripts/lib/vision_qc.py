"""Visual QC for generated illustrations: ask a local Ollama vision model whether the image
makes sense, then return a structured score that the generation loop can use to keep, retry,
or fall back to programmatic checks.

Why a vision model: the cheapest, most informative check on a freshly generated page is "does
it actually show what the page text says, with the right characters, with no duplicated
characters, with the text-zone clear?" A vision LLM can answer that; a perceptual hash
cannot. We use a local Ollama model so the whole pipeline still works **with no API key**
(matches the rest of this repo's "Ollama-first" stance — see CLAUDE.md).

Graceful degradation: if Ollama is unreachable, or the model doesn't accept images, or the
call times out, we return an "unavailable" verdict and the caller can keep the first render
rather than blocking the whole pipeline on QC.

The score is a 0–10 float with a one-line reason, plus a few boolean flags. The caller's
threshold decides what counts as "good enough". A page with `score >= threshold` and no hard
flags (e.g. duplicate characters) ships; everything else triggers a retry.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Default Ollama endpoint. Matches the Makefile (OLLAMA_HOST=http://localhost:11434) and
# opencode.json (baseURL http://localhost:11434/v1). Override with OLLAMA_HOST env.
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
# Default evaluator: MiniMax-M3 — a strong multimodal model, reached through Ollama's cloud
# tier (the ":cloud" tag). It reads embedded text and judges character/scene consistency far
# better than the small local vision models, so it's the preferred reviewer for the
# generate→evaluate→edit loop. Override with VISION_QC_MODEL. Auto-detected at runtime
# (_pick_vision_model) against what's actually pulled, with local models as the offline fallback.
DEFAULT_VISION_MODEL = os.environ.get("VISION_QC_MODEL", "minimax-m3:cloud")
# Vision-capable models in preference order. We pick the first one that's already pulled so we
# never auto-pull a multi-GB model behind the user's back. MiniMax-M3 leads; small local
# gemma/llava models are the no-network fallback.
_KNOWN_VISION_MODELS = [
    "minimax-m3:cloud", "minimax-m3",
    "gemma3:4b", "gemma3:12b", "gemma3:27b",
    "gemma4:e2b", "gemma4:9b",
    "llama3.2-vision:11b", "llama3.2-vision:90b",
    "llava:7b", "llava:13b", "llava:34b",
    "minicpm-v", "minicpm-v:8b",
]

# Hard timeout per call. Vision on a 1K PNG is usually a few seconds on CPU; we leave
# generous headroom for first-time model load.
_TIMEOUT = 120.0
# Token budget for the verdict. Reasoning models emit a long <think> block before the JSON,
# so this must be large enough to cover the reasoning + the JSON. Override with VISION_QC_TOKENS.
_NUM_PREDICT = int(os.environ.get("VISION_QC_TOKENS", "3000"))


@dataclass
class QCR:
    """The result of one QC pass. `ok` is the high-bit verdict the caller cares about;
    `score` and `flags` give the reasoning; `reason` is a human one-liner."""
    ok: bool
    score: float           # 0..10; treat as a soft "goodness" rating
    reason: str            # one short sentence
    flags: list[str] = field(default_factory=list)  # e.g. ["duplicate_characters", "scene_mismatch"]
    model: str = ""        # model that produced this score (for audit)
    raw: str = ""          # raw model output (debugging)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "score": self.score, "reason": self.reason,
                "flags": self.flags, "model": self.model}


def _list_pulled_models(host: str) -> list[str]:
    """Return the names of all models currently pulled on this Ollama host."""
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=3) as r:
            data = json.loads(r.read())
        return [m["name"] for m in data.get("models", [])]
    except Exception:  # noqa: BLE001 — host offline / DNS / refused
        return []


def _pick_vision_model(host: str = DEFAULT_OLLAMA_HOST) -> str | None:
    """Pick the best vision-capable model to evaluate with. An explicit ``VISION_QC_MODEL`` env
    wins outright (the user knows what they want, even a cloud model not in /api/tags). Otherwise
    pick the first preferred model that's actually pulled. Returns None if Ollama is unreachable
    and nothing is forced (so the caller can skip QC)."""
    forced = os.environ.get("VISION_QC_MODEL")
    if forced:
        return forced
    pulled = _list_pulled_models(host)
    if not pulled:
        return None
    pulled_lower = {p.lower(): p for p in pulled}
    for cand in _KNOWN_VISION_MODELS:
        if cand.lower() in pulled_lower:
            return pulled_lower[cand.lower()]
    # Last-resort heuristic: if a model name mentions a known vision family, use it.
    for p in pulled:
        lp = p.lower()
        if any(t in lp for t in ("minimax", "gemma", "llava", "llama3.2-vision", "vision", "minicpm-v")):
            return p
    return None


def _local_fallback_model(host: str, *, exclude: str | None = None) -> str | None:
    """The first LOCAL (non-cloud) vision model pulled on this host, for when the preferred
    reviewer is a flaky cloud model. ':cloud' models are skipped so the fallback always runs
    on-box. Returns None if no local vision model is available."""
    pulled = [p for p in _list_pulled_models(host) if not p.lower().endswith(":cloud")]
    pulled_lower = {p.lower(): p for p in pulled}
    for cand in _KNOWN_VISION_MODELS:
        if cand.endswith(":cloud"):
            continue
        m = pulled_lower.get(cand.lower())
        if m and m != exclude:
            return m
    for p in pulled:
        if p != exclude and any(t in p.lower() for t in ("gemma", "llava", "vision", "minicpm-v")):
            return p
    return None


def _flatten_palette(palette: list[Any]) -> list[str]:
    """Palette entries can be hex strings OR dicts with {name, role, hex}. Normalize."""
    out: list[str] = []
    for p in palette or []:
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, dict):
            label = p.get("name") or p.get("role") or "color"
            h = p.get("hex") or ""
            out.append(f"{label} {h}".strip())
    return out


def _build_prompt(page_text: str, characters: list[str], tokens: list[str],
                  art_style_block: str, palette: list[str], text_zone: str) -> str:
    """The instruction we send to the vision model. Kept small + structured so the
    output is easy to parse and the model doesn't drift into prose."""
    char_lines = "\n".join(f"  - {c}" for c in characters) or "  - (none)"
    token_lines = "\n".join(f"  - {t}" for t in tokens) or "  - (none)"
    flat = _flatten_palette(palette)
    pal_lines = ", ".join(flat) if flat else "(no palette)"
    return textwrap_dedent(f"""\
        You are a strict visual-QC reviewer for a children's picture book illustration.

        Page text (what the picture should show):
        \"\"\"{page_text.strip()}\"\"\"

        Characters expected in this picture (by slug):
        {char_lines}

        Locked character appearance tokens (the model must match these):
        {token_lines}

        Locked art style for the whole book:
        \"\"\"{(art_style_block or '').strip()}\"\"\"

        Locked palette: {pal_lines}
        Reserved text zone (must stay calm / low-detail for caption text): {text_zone}

        Look at the attached image. Then return ONLY a single JSON object with these fields:
        - "score": float 0..10 (10 = perfect).
        - "ok": boolean, true if score >= 7 AND no hard problems below.
        - "reason": one short sentence, plain English.
        - "flags": list of zero or more of:
            "duplicate_characters"   — same character drawn more than once in the frame
            "wrong_characters"       — characters look different from their tokens
            "missing_characters"     — an expected character is absent
            "scene_mismatch"         — picture does NOT match the page text
            "style_inconsistent"     — art style breaks from the locked style block
            "text_zone_cluttered"    — the reserved text area is too busy for legible captions
            "anatomy_issue"          — clear distortion (extra limbs, melted face, etc.)
            "too_dark" / "too_blurry" / "low_detail"
            "good"                   — none of the above; ship it
        The FIRST flag MUST be the most serious problem. Keep the list short (1-4 items).

        JSON only. No prose, no markdown fences.
    """)


def textwrap_dedent(s: str) -> str:
    """Tiny stdlib-free stand-in for textwrap.dedent (keeps this module dependency-free)."""
    lines = s.splitlines()
    if not lines:
        return s
    indents = [len(ln) - len(ln.lstrip(" ")) for ln in lines if ln.strip()]
    pad = min(indents) if indents else 0
    return "\n".join(ln[pad:] if len(ln) >= pad else ln for ln in lines)


def _parse_model_json(text: str) -> dict[str, Any] | None:
    """Robustly pull a JSON object out of a model response. Models sometimes wrap it in
    markdown fences, prefix it with 'Sure!', or add a trailing '}'. This handles the
    realistic shapes we see in the wild."""
    if not text:
        return None
    s = text.strip()
    # Reasoning models (minimax-m3, kimi, …) emit a <think>…</think> block before the answer.
    # Drop it so the JSON underneath is what we parse (and so a long chain-of-thought doesn't
    # look like "no JSON"). Tolerate an unclosed tag from a truncated response.
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL)
    s = re.sub(r"<think>.*$", "", s, flags=re.DOTALL).strip()
    # Strip ```json ... ``` fences if present.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL)
    if fence:
        s = fence.group(1)
    # Find the outermost {...} on its own — covers leading "Sure! {" or trailing "}".
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        # One last try: replace single quotes and Python booleans, then parse.
        cleaned = m.group(0).replace("'", '"').replace("True", "true").replace("False", "false")
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None


def _score_to_qcr(parsed: dict[str, Any], model: str, raw: str) -> QCR:
    score = float(parsed.get("score", 0) or 0)
    score = max(0.0, min(10.0, score))
    flags = [str(f).strip() for f in (parsed.get("flags") or []) if str(f).strip()]
    reason = str(parsed.get("reason") or "").strip() or "no reason given"
    explicit_ok = parsed.get("ok")
    if explicit_ok is None:
        ok = score >= 7.0 and "good" in flags
    else:
        ok = bool(explicit_ok) and score >= 7.0
    return QCR(ok=ok, score=score, reason=reason, flags=flags, model=model, raw=raw)


def _unavailable(reason: str) -> QCR:
    return QCR(ok=True, score=10.0, reason=f"qc unavailable: {reason}", flags=["qc_unavailable"])


def _mime_for(p: Path) -> str:
    mime, _ = mimetypes.guess_type(p.name)
    return mime or "image/png"


def score_image(image_path: Path, *, page_text: str, characters: list[str],
                tokens: list[str], art_style_block: str = "", palette: list[str] | None = None,
                text_zone: str = "lower third", host: str = DEFAULT_OLLAMA_HOST,
                model: str | None = None, verbose: bool = False) -> QCR:
    """Send one image to a local Ollama vision model and return a structured QC verdict.

    All four art-locking inputs (page text, characters, tokens, palette, style block) are
    passed in so the model can grade against THIS page's actual spec — not generic vibes.

    Returns a QCR. If Ollama is unreachable, the model isn't pulled, the call times out, or
    the model returns unparseable text, returns a permissive `_unavailable` verdict so the
    pipeline keeps moving (we never block illustration on a flaky local service)."""
    if not image_path.exists() or image_path.stat().st_size == 0:
        return _unavailable("image missing or empty")

    chosen_model = model or _pick_vision_model(host)
    if not chosen_model:
        return _unavailable("no vision-capable Ollama model pulled on this host")

    prompt = _build_prompt(page_text, characters, tokens, art_style_block, palette or [], text_zone)
    img_b64 = base64.b64encode(image_path.read_bytes()).decode()

    def _ask(model_name: str) -> tuple[QCR | None, str]:
        """Up to two attempts at one model. Returns (QCR, "") on success, else (None, reason).
        Cloud models (minimax-m3:cloud) sometimes return an empty body on a cold call, so we
        re-ask once with a short pause before giving up on this model."""
        # num_predict is generous: reasoning models (minimax-m3, kimi) spend most tokens in a
        # <think> block before the JSON, and a tight cap truncates them to an empty verdict.
        body = {"model": model_name, "prompt": prompt, "images": [img_b64], "stream": False,
                "options": {"temperature": 0.0, "num_predict": _NUM_PREDICT}}
        reason = ""
        for attempt in range(2):
            req = urllib.request.Request(f"{host}/api/generate", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
                    payload = json.loads(r.read())
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                reason = f"ollama {e.__class__.__name__}"
                if verbose:
                    print(f"  · qc[{model_name}]: call failed ({e})", file=sys.stderr)
            else:
                raw = (payload.get("response") or "").strip()
                parsed = _parse_model_json(raw)
                if parsed:
                    return _score_to_qcr(parsed, model=model_name, raw=raw), ""
                reason = "empty response" if not raw else "non-JSON response"
                if verbose:
                    print(f"  · qc[{model_name}]: {reason} (try {attempt+1}/2, {raw[:60]!r})",
                          file=sys.stderr)
            time.sleep(1.0)
        return None, reason

    # Try the preferred model; if it can't produce a usable verdict (e.g. a flaky cloud model),
    # fall back to a reliable LOCAL vision model so QC — and the edit-fix it gates — still runs.
    last_err = ""
    tried: list[str] = []
    for cand in [chosen_model, _local_fallback_model(host, exclude=chosen_model)]:
        if not cand or cand in tried:
            continue
        tried.append(cand)
        qcr, err = _ask(cand)
        if qcr is not None:
            return qcr
        last_err = f"{cand}: {err}"
    return _unavailable(last_err or "no usable QC response")
