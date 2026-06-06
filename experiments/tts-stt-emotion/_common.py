"""
Shared helpers for the tts-stt-emotion experiment.

We use this to keep wall-time, peak-RSS, and audio stats consistent across
all attempts. Reads HF cache from the user-level path (mirroring the
flux2-klein-test experiment).
"""
import contextlib
import gc
import os
import resource
import time

import numpy as np
import soundfile as sf

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HOME", "/home/jgarcairaza/.cache/huggingface")
# CTranslate2 (faster-whisper) is multithreaded by default; cap to keep the
# machine responsive. The experiments still measure with the cap.
os.environ.setdefault("OMP_NUM_THREADS", "16")
os.environ.setdefault("MKL_NUM_THREADS", "16")


def rss_mb() -> float:
    """Peak resident-set size so far in MB (POSIX only)."""
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return ru.ru_maxrss / 1024.0  # Linux: ru_maxrss is in kilobytes


class Timer:
    def __init__(self, label: str = ""):
        self.label = label
        self.t0 = 0.0
        self.elapsed = 0.0

    def __enter__(self):
        gc.collect()
        self.t0 = time.time()
        return self

    def __exit__(self, *exc):
        self.elapsed = time.time() - self.t0

    def report(self) -> str:
        return f"{self.label}: {self.elapsed:.3f}s  peak_rss={rss_mb():.1f} MB"


@contextlib.contextmanager
def measure(label: str = ""):
    t = Timer(label)
    with t:
        yield t
    print(f"[{t.elapsed:7.3f}s] {label}  peak_rss={rss_mb():.1f} MB", flush=True)


def audio_stats(audio: np.ndarray, sr: int) -> dict:
    """Cheap summary stats for a mono float waveform."""
    if audio.ndim > 1:
        audio = audio.mean(axis=-1)
    duration_s = len(audio) / sr
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    peak = float(np.max(np.abs(audio)))
    # zero-crossing rate: cheap proxy for noisiness/excitement
    zc = float(np.mean(np.abs(np.diff(np.sign(audio))) > 0))
    return {
        "duration_s": round(duration_s, 3),
        "samples": int(audio.shape[0]),
        "sr": int(sr),
        "rms": round(rms, 5),
        "peak": round(peak, 5),
        "zcr": round(zc, 5),
    }


def save_wav(path: str, audio: np.ndarray, sr: int) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Kokoro returns float32 in [-1, 1]; soundfile will write 16-bit PCM by default.
    sf.write(path, audio, sr)
