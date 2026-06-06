"""
Attempt 5 — character-voice coverage for read-aloud cast.

A picture book has a tiny cast: typically a narrator + 1–3 named
characters. The read-aloud experience depends on those voices being
**distinct enough that a child can tell who is talking** without a
visual cue. The question we answer here:

    "Across the ~20 American English voices that ship with Kokoro,
     how many genuinely distinct character voices can we find for a
     4-character cast (narrator + 3 named animals)?"

We synthesise the same line in every American English voice, then
measure pairwise distance on a handful of cheap audio features (pitch
proxy via zero-crossing rate on band-passed signal, RMS, spectral
centroid estimated via autocorrelation). Voices that are far apart
in this space are perceptually distinct.

We also do a "small-cast" pick — one narrator + 3 characters — that
maximises inter-voice distance, so the storybook studio has a good
default.
"""
import json
import os

import numpy as np
import soundfile as sf

from _common import audio_stats, measure, rss_mb

OUT_DIR = "experiments/tts-stt-emotion/outputs/attempt5_cast"
os.makedirs(OUT_DIR, exist_ok=True)

LINE = "Hello, little one. I have been waiting for you."

# American English 'af_*' (female) and 'am_*' (male) — the most expressive
# for a picture-book cast. We skip the british and other langs because
# the storybook pipeline currently only has 'a' downloaded.
AMERICAN_VOICES = [
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica",
    "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
    "am_michael", "am_onyx", "am_puck", "am_santa",
]

print(f"[start] peak_rss={rss_mb():.1f} MB  voices={len(AMERICAN_VOICES)}", flush=True)

with measure("import kokoro") as _:
    from kokoro import KModel, KPipeline

with measure("load KModel") as _:
    model = KModel().to("cpu")

with measure("KPipeline('a')") as _:
    pipe = KPipeline(lang_code="a", model=model)


def voice_features(audio: np.ndarray, sr: int) -> dict:
    """Cheap perceptual features from a 24 kHz mono float waveform."""
    x = audio.astype(np.float64)
    x = x - x.mean()
    rms = float(np.sqrt(np.mean(x * x)))
    peak = float(np.max(np.abs(x)))
    # Zero-crossing rate as a *very* rough pitch proxy.
    zcr = float(np.mean(np.abs(np.diff(np.sign(x))) > 0))
    # Spectral centroid via autocorrelation peak: cheap pitch estimate.
    # Window: take 30 ms chunks, find first peak after zero-crossing.
    win = int(0.03 * sr)
    if len(x) < win * 4:
        f0 = 0.0
    else:
        starts = np.linspace(0, len(x) - win, 8, dtype=int)
        f0s = []
        for s in starts:
            seg = x[s : s + win]
            seg = seg * np.hanning(len(seg))
            ac = np.correlate(seg, seg, mode="full")[len(seg) - 1 :]
            # first local maximum after the central peak
            d = np.diff(ac)
            pos = np.where((d[:-1] > 0) & (d[1:] <= 0))[0]
            pos = pos[pos > 5]
            if len(pos) == 0:
                continue
            lag = pos[0]
            if lag == 0:
                continue
            f0s.append(sr / lag)
        f0 = float(np.median(f0s)) if f0s else 0.0
    return {"rms": rms, "peak": peak, "zcr": zcr, "f0_hz": f0}


print("\n[1] SYNTHESIZE ALL VOICES")
results: list[dict] = []
with measure("synth all voices (line=short)") as t_total:
    for v in AMERICAN_VOICES:
        try:
            with measure(f"  {v}") as t:
                chunks = []
                for i, result in enumerate(pipe(LINE, voice=v, speed=1.0)):
                    _, _, audio = result
                    if audio is None:
                        continue
                    chunks.append(audio.detach().cpu().numpy().astype(np.float32))
                audio = np.concatenate(chunks)
            save_path = os.path.join(OUT_DIR, f"{v}.wav")
            sf.write(save_path, audio, 24000)
            feats = voice_features(audio, 24000)
            feats["voice"] = v
            feats["duration_s"] = len(audio) / 24000
            feats["wall_time_s"] = round(t.elapsed, 3)
            results.append(feats)
        except Exception as e:
            print(f"    [skip {v}] {type(e).__name__}: {e}", flush=True)

# 2) Build a distance matrix
print("\n[2] BUILD DISTANCE MATRIX")
F = ["rms", "peak", "zcr", "f0_hz"]
M = np.array([[r[f] for f in F] for r in results], dtype=np.float64)
# Standardise each feature to unit variance so f0 doesn't dominate
mu = M.mean(axis=0)
sd = M.std(axis=0)
sd[sd == 0] = 1.0
Z = (M - mu) / sd
# Pairwise euclidean distance
D = np.sqrt(((Z[:, None, :] - Z[None, :, :]) ** 2).sum(axis=-1))
n = len(results)
print(f"  computed {n}x{n} distance matrix over features {F}")

# 3) Greedy pick: start with highest-energy, then greedily add the voice
#    that is *most distant* from the existing set. This is a tiny
#    max-min facility-location.
picked: list[int] = [int(np.argmax([r["rms"] for r in results]))]  # narrator = high rms
cast_names = ["narrator"]
for _ in range(3):
    last = picked[-1]
    dists_to_last = D[last]
    # Mask out already-picked
    for p in picked:
        dists_to_last[p] = -np.inf
    nxt = int(np.argmax(dists_to_last))
    picked.append(nxt)
    cast_names.append(f"character_{len(cast_names)}")

print(f"\n[3] DEFAULT 4-VOICE CAST (max-min greedy)")
for label, idx in zip(cast_names, picked):
    r = results[idx]
    print(f"  {label:12s} -> {r['voice']:12s}  rms={r['rms']:.4f}  "
          f"f0={r['f0_hz']:5.1f}Hz  zcr={r['zcr']:.4f}")

# 4) Persist
with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
    json.dump(
        {
            "model": "Kokoro-82M (v1.0)",
            "n_voices": len(results),
            "voices": results,
            "feature_columns": F,
            "distance_matrix": D.tolist(),
            "cast_suggestion": {
                "narrator": results[picked[0]]["voice"],
                "character_1": results[picked[1]]["voice"],
                "character_2": results[picked[2]]["voice"],
                "character_3": results[picked[3]]["voice"],
            },
            "cast_min_pairwise_distance": float(
                min(D[i, j] for i in picked for j in picked if i != j)
            ),
            "peak_rss_mb": round(rss_mb(), 1),
        },
        f,
        indent=2,
    )

print(f"\n[done] wrote {len(results)} voice samples + summary to {OUT_DIR}")
print(f"  total synth time: {t_total.elapsed:.2f}s")
