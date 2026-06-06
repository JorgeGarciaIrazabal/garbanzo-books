"""
Attempt 2 — emotion exploration.

Kokoro-82M is *prosody-driven* — it has no per-utterance emotion vector
and no SSML. "Emotion" comes from:

  1. Voice choice (Kokoro ships ~50 voices with different warmth/breathiness).
  2. Punctuation and punctuation density (`!`, `?`, ellipses `...`, em-dash `—`).
  3. Speed (faster = more excited; slower = more contemplative/gentle).

We synthesize a single picture-book scene — "Pip the red panda finds a
mysterious blue feather" — in 6 deliveries that a story director might
realistically call for, on 3 voices, and measure both the audio
characteristics and the time cost.

Outputs:
  outputs/attempt2_emotion/
    af_heart__neutral.wav
    af_heart__whispered.wav
    af_heart__excited.wav
    af_heart__sad.wav
    af_bella__neutral.wav
    am_adam__neutral.wav
    am_michael__neutral.wav
    bm_lewis__neutral.wav
    summary.json
"""
import json
import os
import sys
import time

import numpy as np

from _common import audio_stats, measure, rss_mb, save_wav

OUT_DIR = "experiments/tts-stt-emotion/outputs/attempt2_emotion"
os.makedirs(OUT_DIR, exist_ok=True)

# Different "deliveries" of the SAME scene. The story director would
# request these by name; the TTS system has to coax them out of the model
# with text + voice + speed.
SCENES = {
    "neutral": {
        "voice": "af_heart",
        "speed": 1.0,
        "text": (
            "Pip found a blue feather on the mossy path. "
            "It was longer than Pip's paw, and it shimmered in the morning light."
        ),
    },
    "whispered": {
        "voice": "af_heart",
        "speed": 0.85,
        "text": (
            "Pip found a blue feather... on the mossy path. "
            "It was... longer than Pip's paw, and it... shimmered, in the morning light."
        ),
    },
    "excited": {
        "voice": "af_heart",
        "speed": 1.15,
        "text": (
            "Pip found a BLUE feather! On the mossy path! "
            "It was longer than Pip's paw, and it SHIMMERED in the morning light!"
        ),
    },
    "sad": {
        "voice": "af_heart",
        "speed": 0.9,
        "text": (
            "Pip found a blue feather, on the mossy path, all alone. "
            "It was longer than Pip's paw, and... it reminded Pip of home."
        ),
    },
}

# Same text, but different voice. Shows the *character-voice* axis.
VOICE_COMPARISON_TEXT = SCENES["neutral"]["text"]
VOICE_LIST = ["af_bella", "am_adam", "am_michael", "bm_lewis"]

print(f"[start] python={sys.version.split()[0]} peak_rss={rss_mb():.1f} MB", flush=True)

with measure("import kokoro") as _:
    from kokoro import KModel, KPipeline

with measure("load KModel") as _:
    model = KModel().to("cpu")

with measure("KPipeline('a')") as _:
    pipe = KPipeline(lang_code="a", model=model)


def synth(name: str, voice: str, speed: float, text: str) -> dict:
    chunks: list = []
    stats: dict = {}
    with measure(f"synth {name} voice={voice} speed={speed}") as t:
        for i, result in enumerate(pipe(text, voice=voice, speed=speed)):
            graphemes, phonemes, audio = result
            if audio is None:
                continue
            a = audio.detach().cpu().numpy().astype(np.float32)
            chunks.append(a)
    if not chunks:
        raise RuntimeError(f"no audio for {name}")
    full = np.concatenate(chunks)
    save_wav(os.path.join(OUT_DIR, f"{name}.wav"), full, 24000)
    stats = audio_stats(full, 24000)
    stats["name"] = name
    stats["voice"] = voice
    stats["speed"] = speed
    stats["text"] = text
    stats["wall_time_s"] = round(t.elapsed, 3)
    stats["realtime_factor"] = round(t.elapsed / max(stats["duration_s"], 1e-3), 4)
    return stats


results: list[dict] = []
for name, spec in SCENES.items():
    results.append(synth(name, spec["voice"], spec["speed"], spec["text"]))

for voice in VOICE_LIST:
    name = f"voice__{voice}__neutral"
    try:
        results.append(synth(name, voice, 1.0, VOICE_COMPARISON_TEXT))
    except Exception as e:
        print(f"  [skip] {voice}: {e}", flush=True)

with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
    json.dump(
        {
            "model": "Kokoro-82M (v1.0)",
            "device": "cpu",
            "results": results,
            "peak_rss_mb_at_end": round(rss_mb(), 1),
        },
        f,
        indent=2,
    )

print("\n[summary]")
for r in results:
    print(
        f"  {r['name']:32s} voice={r['voice']:10s} speed={r['speed']:.2f}  "
        f"dur={r['duration_s']:5.2f}s  wall={r['wall_time_s']:.2f}s  "
        f"rtf={r['realtime_factor']:.3f}x  rms={r['rms']:.4f}  peak={r['peak']:.3f}  zcr={r['zcr']:.4f}",
        flush=True,
    )
# also keep the live per-attempt report from the with-block above by re-emitting from the stored list
print("\n[live per-attempt wall times]")
for r in results:
    print(f"  {r['name']:32s} wall_time_s={r['wall_time_s']:.3f}", flush=True)
