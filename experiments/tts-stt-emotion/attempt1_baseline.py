"""
Attempt 1 — Kokoro-82M TTS baseline.

Goal: can we get a usable TTS on this box, and how fast is the *first*
synthesis? We use the only voice that's already on disk (`af_heart`).
This gives us the cold-start cost (model load + first chunk) and the
steady-state cost (chunks 2..N) for a typical ~14-page read-aloud.

Output: outputs/attempt1_baseline/<N>.wav for each chunk, plus a JSON of
audio stats.
"""
import json
import os
import sys

import numpy as np

from _common import audio_stats, measure, rss_mb, save_wav

OUT_DIR = "experiments/tts-stt-emotion/outputs/attempt1_baseline"
os.makedirs(OUT_DIR, exist_ok=True)

TEXT = (
    "Once upon a time, in a tiny cottage at the edge of a mossy forest, "
    "there lived a small red panda named Pip. Every morning, Pip put on a "
    "yellow raincoat and set out to find a new friend."
)

print(f"[start] python={sys.version.split()[0]} peak_rss={rss_mb():.1f} MB", flush=True)

with measure("import kokoro") as _:
    from kokoro import KModel, KPipeline

with measure("load KModel (downloads config.json + kokoro-v1_0.pth if needed)") as _:
    model = KModel().to("cpu")  # default repo_id, default config

# 'a' = American English. af_heart is the only voice we already have on disk.
with measure("KPipeline(lang_code='a')") as _:
    pipe = KPipeline(lang_code="a", model=model)

with measure("synthesize TEXT (af_heart, speed=1.0)") as t:
    chunks = []
    for i, result in enumerate(pipe(TEXT, voice="af_heart", speed=1.0)):
        graphemes, phonemes, audio = result
        if audio is None:
            continue
        a = audio.detach().cpu().numpy().astype(np.float32)
        chunks.append((i, graphemes, phonemes, a))
        print(
            f"   chunk {i}: text={graphemes!r:60s}  phonemes={phonemes[:30]!r}  "
            f"audio={audio_stats(a, 24000)}",
            flush=True,
        )

print(t.report(), flush=True)

# Persist.
for i, g, p, a in chunks:
    save_wav(os.path.join(OUT_DIR, f"chunk{i:02d}.wav"), a, 24000)
    with open(os.path.join(OUT_DIR, f"chunk{i:02d}.json"), "w") as f:
        json.dump({"graphemes": g, "phonemes": p, "audio": audio_stats(a, 24000)}, f, indent=2)

# Concatenated full clip
full = np.concatenate([a for _, _, _, a in chunks])
save_wav(os.path.join(OUT_DIR, "full.wav"), full, 24000)
with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
    json.dump(
        {
            "voice": "af_heart",
            "speed": 1.0,
            "n_chunks": len(chunks),
            "total_duration_s": audio_stats(full, 24000)["duration_s"],
            "wall_time_s": t.elapsed,
            "peak_rss_mb": rss_mb(),
            "realtime_factor": t.elapsed / max(audio_stats(full, 24000)["duration_s"], 1e-6),
        },
        f,
        indent=2,
    )

print(
    f"[done] wrote {len(chunks)} chunks + full.wav to {OUT_DIR}\n"
    f"  wall_time={t.elapsed:.2f}s  audio={audio_stats(full, 24000)['duration_s']:.2f}s  "
    f"rtf={t.elapsed / max(audio_stats(full, 24000)['duration_s'], 1e-6):.2f}x  "
    f"peak_rss={rss_mb():.1f} MB",
    flush=True,
)
