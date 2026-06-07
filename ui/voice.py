"""Local, key-free speech for the studio — natural read-aloud + voice input.

The models here were chosen by the experiments in experiments/tts-stt-emotion/REPORT.md:

  * TTS — **Kokoro-82M** (`hexgrad/Kokoro-82M`): warm, natural, 50+ voices, ~14× faster than
    real-time on CPU. Prosody is controlled by voice + speed.
  * STT — **faster-whisper / `Systran/faster-distil-whisper-large-v3`** (int8): state-of-the-art
    English, ~15× faster than real-time on CPU, ~1% round-trip WER.

Both run on CPU with no API key and no GPU, and their weights are already cached under
~/.cache/huggingface. Models load lazily on first use (~3 s cold) and are then reused; the actual
synth/transcribe calls are blocking, so the server runs them via ``asyncio.to_thread`` and
serializes each model behind a lock (the model objects are not re-entrant).
"""
from __future__ import annotations

import importlib.util
import io
import os
import threading
from pathlib import Path

# Point HF at the user cache where the experiments already downloaded the weights, silence its
# progress bars, and keep CPU thread use reasonable. setdefault so an explicit env still wins.
os.environ.setdefault("HF_HOME", str(Path.home() / ".cache" / "huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
# These models are open and already cached — there's no token and nothing to download at runtime.
# Run cache-only so HF never makes the (unauthenticated) network revision-check that prints the
# "set a HF_TOKEN" warning; it also makes startup faster and works fully offline. To add a NEW
# Kokoro voice that isn't cached yet, run once with HF_HUB_OFFLINE=0 to let it download.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

SAMPLE_RATE = 24000           # Kokoro's native output rate
DEFAULT_VOICE = "af_heart"    # warm narrator voice that ships cached
STT_MODEL = "Systran/faster-distil-whisper-large-v3"

# A small, child-distinguishable cast (the default cast picked in attempt5_cast). af_heart is the
# only one cached up front; the rest download on first use.
VOICES = ["af_heart", "af_aoede", "af_bella", "af_nova", "af_sarah", "am_adam", "am_puck", "bm_lewis"]


def available() -> dict:
    """Which backends *could* run (their deps import). Models still load lazily on first call."""
    return {
        "tts": importlib.util.find_spec("kokoro") is not None
        and importlib.util.find_spec("soundfile") is not None,
        "stt": importlib.util.find_spec("faster_whisper") is not None,
        "voices": VOICES,
        "default_voice": DEFAULT_VOICE,
    }


# ---- lazy singletons (one lock per model: guards the load AND serializes inference) -------------
_tts_lock = threading.Lock()
_stt_lock = threading.Lock()
_tts_pipe = None
_stt_model = None


def _ensure_tts():
    """Load Kokoro once. Caller must hold _tts_lock."""
    global _tts_pipe
    if _tts_pipe is None:
        from kokoro import KModel, KPipeline
        model = KModel().to("cpu")
        _tts_pipe = KPipeline(lang_code="a", model=model)  # 'a' = American English
    return _tts_pipe


def _ensure_stt():
    """Load faster-whisper once. Caller must hold _stt_lock."""
    global _stt_model
    if _stt_model is None:
        from faster_whisper import WhisperModel
        # int8 on CPU: ~2× faster than float32, half the RAM, same accuracy (see REPORT Attempt 3).
        _stt_model = WhisperModel(STT_MODEL, device="cpu", compute_type="int8")
    return _stt_model


def synthesize(text: str, voice: str = DEFAULT_VOICE, speed: float = 1.0) -> bytes:
    """text → 24 kHz mono 16-bit WAV bytes. Blocking — call via ``asyncio.to_thread``."""
    import numpy as np
    import soundfile as sf

    text = (text or "").strip()
    if not text:
        raise ValueError("empty text")
    if voice not in VOICES:
        voice = DEFAULT_VOICE
    speed = max(0.5, min(2.0, float(speed)))
    with _tts_lock:
        pipe = _ensure_tts()
        chunks = []
        for _, _, audio in pipe(text, voice=voice, speed=speed):
            if audio is None:
                continue
            chunks.append(audio.detach().cpu().numpy().astype("float32"))
    full = np.concatenate(chunks) if chunks else np.zeros(1, dtype="float32")
    buf = io.BytesIO()
    sf.write(buf, full, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def transcribe(audio_bytes: bytes) -> str:
    """Any browser audio blob (webm/opus, ogg, wav, …) → text. PyAV (bundled with faster-whisper)
    decodes it in-process, so no system ffmpeg is needed. Blocking — call via ``asyncio.to_thread``."""
    if not audio_bytes:
        return ""
    with _stt_lock:
        model = _ensure_stt()
        segments, _ = model.transcribe(
            io.BytesIO(audio_bytes), language="en", beam_size=5, vad_filter=True
        )
        return "".join(seg.text for seg in segments).strip()


def warm() -> None:
    """Eagerly load both models (used by a background warm-up so the first click is instant)."""
    caps = available()
    if caps["tts"]:
        try:
            with _tts_lock:
                _ensure_tts()
        except Exception:
            pass
    if caps["stt"]:
        try:
            with _stt_lock:
                _ensure_stt()
        except Exception:
            pass
