"""
Attempt 3 — STT baseline with faster-whisper (CTranslate2).

We load Systran/faster-distil-whisper-large-v3 (already on disk in
HF_HOME) and transcribe:
  - attempt1_baseline/full.wav     (Kokoro's neutral "Once upon a time..." text)
  - attempt2_emotion/af_heart__excited.wav  (the loudest, fastest delivery)
  - attempt2_emotion/af_heart__whispered.wav (the softest, slowest delivery)

We measure wall time, peak RSS, and word error rate (WER) against the
known ground truth. We also try int8 vs float16 vs float32 to see what
fits our CPU box best.
"""
import json
import os
import time

import numpy as np
import soundfile as sf

from _common import audio_stats, measure, rss_mb, save_wav

OUT_DIR = "experiments/tts-stt-emotion/outputs/attempt3_stt"
os.makedirs(OUT_DIR, exist_ok=True)

JOBS = [
    {
        "name": "neutral_long",
        "audio": "experiments/tts-stt-emotion/outputs/attempt1_baseline/full.wav",
        "gt": (
            "Once upon a time, in a tiny cottage at the edge of a mossy forest, "
            "there lived a small red panda named Pip. Every morning, Pip put on a "
            "yellow raincoat and set out to find a new friend."
        ),
    },
    {
        "name": "excited_short",
        "audio": "experiments/tts-stt-emotion/outputs/attempt2_emotion/excited.wav",
        "gt": (
            "Pip found a BLUE feather! On the mossy path! "
            "It was longer than Pip's paw, and it SHIMMERED in the morning light!"
        ),
    },
    {
        "name": "whispered_short",
        "audio": "experiments/tts-stt-emotion/outputs/attempt2_emotion/whispered.wav",
        "gt": (
            "Pip found a blue feather... on the mossy path. "
            "It was... longer than Pip's paw, and it... shimmered, in the morning light."
        ),
    },
]


def normalize_for_wer(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace. Mirrors common WER recipes."""
    import re

    s = s.lower()
    s = re.sub(r"[^\w\s']", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def wer(ref: str, hyp: str) -> tuple[int, int, float]:
    """Standard Levenshtein-based WER (sub/ins/del). Returns (edits, ref_words, wer)."""
    ref_w = normalize_for_wer(ref).split()
    hyp_w = normalize_for_wer(hyp).split()
    n = len(ref_w)
    # DP
    dp = [[0] * (len(hyp_w) + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(len(hyp_w) + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, len(hyp_w) + 1):
            cost = 0 if ref_w[i - 1] == hyp_w[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,         # deletion
                dp[i][j - 1] + 1,         # insertion
                dp[i - 1][j - 1] + cost,  # sub/match
            )
    edits = dp[n][len(hyp_w)]
    return edits, n, edits / max(n, 1)


print(f"[start] peak_rss={rss_mb():.1f} MB", flush=True)

with measure("import faster_whisper") as _:
    from faster_whisper import WhisperModel

# 1) LOAD — try int8 first (lowest RAM on CPU, recommended by faster-whisper)
MODEL_ID = "Systran/faster-distil-whisper-large-v3"
COMPUTE_TYPES = ["int8", "float16", "float32"]

all_results = []
for ct in COMPUTE_TYPES:
    label = f"load model ({ct})"
    try:
        with measure(label) as t_load:
            model = WhisperModel(MODEL_ID, device="cpu", compute_type=ct)
    except Exception as e:
        print(f"  [skip {ct}] {type(e).__name__}: {e}", flush=True)
        continue

    for job in JOBS:
        with measure(f"transcribe {job['name']} ct={ct}") as t:
            audio, sr = sf.read(job["audio"], dtype="float32")
            if sr != 16000:
                # faster-whisper resamples internally, but we'll be explicit
                pass
            segments, info = model.transcribe(
                audio,
                language="en",
                beam_size=5,
                vad_filter=True,
            )
            hyp = "".join(seg.text for seg in segments).strip()
        edits, n_words, w = wer(job["gt"], hyp)
        all_results.append(
            {
                "compute_type": ct,
                "job": job["name"],
                "audio_dur_s": info.duration,
                "audio_sr": sr,
                "n_segments": info.language_probability if False else None,  # placeholder
                "hyp": hyp,
                "gt": job["gt"],
                "edits": edits,
                "ref_words": n_words,
                "wer": round(w, 4),
                "wall_time_s": round(t.elapsed, 3),
                "load_time_s": round(t_load.elapsed, 3),
                "realtime_factor": round(t.elapsed / max(info.duration, 1e-3), 4),
            }
        )
        print(
            f"  [{ct}] {job['name']:20s} dur={info.duration:5.2f}s  "
            f"wall={t.elapsed:.2f}s  rtf={t.elapsed / max(info.duration, 1e-3):.3f}x  "
            f"wer={w * 100:.1f}%  ({edits}/{n_words} edits)",
            flush=True,
        )

    del model

with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
    json.dump(
        {
            "model": MODEL_ID,
            "device": "cpu",
            "results": all_results,
            "peak_rss_mb_at_end": round(rss_mb(), 1),
        },
        f,
        indent=2,
    )

# Pretty print final
print("\n[STT results]")
for r in all_results:
    print(
        f"  ct={r['compute_type']:8s} job={r['job']:20s}  "
        f"wer={r['wer'] * 100:5.1f}%  rtf={r['realtime_factor']:.3f}x  "
        f"wall={r['wall_time_s']:.2f}s"
    )

print(f"\nHypothesis examples:")
for r in all_results[:3]:
    print(f"  [{r['compute_type']}] {r['job']}: {r['hyp']}")
