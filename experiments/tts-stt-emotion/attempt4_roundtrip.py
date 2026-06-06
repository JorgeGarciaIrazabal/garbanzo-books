"""
Attempt 4 — full-book round trip.

End-to-end test that mirrors the storybook read-aloud use case:
  1. Take a 14-page picture book (we hardcode one based on attempt1's text).
  2. Synthesize each page with a *different* emotional delivery (so the
     whole book has a character-arc feel).
  3. Concatenate the per-page WAVs into one book-length audio file.
  4. Run the whole book through STT and measure round-trip fidelity.

This is the single most important benchmark for the read-aloud feature,
because it shows the worst-case (longest) synthesis + longest transcript
time on this box.
"""
import json
import os

import numpy as np
import soundfile as sf

from _common import audio_stats, measure, rss_mb, save_wav

OUT_DIR = "experiments/tts-stt-emotion/outputs/attempt4_roundtrip"
os.makedirs(OUT_DIR, exist_ok=True)

# 14 short pages. Each one tagged with a delivery that matches the
# emotional beat. This is exactly what the storybook studio would do.
PAGES = [
    # (page_num, voice, speed, text, emotion_intent)
    (1,  "af_heart", 1.0,  "Once upon a time, in a tiny cottage at the edge of a mossy forest, there lived a small red panda named Pip.", "neutral"),
    (2,  "af_heart", 1.0,  "Every morning, Pip put on a yellow raincoat and set out to find a new friend.", "neutral"),
    (3,  "af_heart", 1.1,  "One day, Pip found a blue feather on the mossy path!", "excited"),
    (4,  "af_heart", 0.95, "It was longer than Pip's paw, and it shimmered in the morning light.", "wonder"),
    (5,  "af_heart", 1.0,  "Pip wondered, who does this feather belong to?", "curious"),
    (6,  "af_heart", 0.85, "Deep in the forest, an old owl watched from a hollow tree.", "calm"),
    (7,  "af_heart", 0.9,  "Hoo, said the owl. I have been waiting for you, little one.", "gentle"),
    (8,  "af_heart", 1.15, "Pip and the owl became friends at once!", "joyful"),
    (9,  "af_heart", 0.9,  "They shared acorn-cakes, and told stories of the wind.", "warm"),
    (10, "af_heart", 0.85, "But soon, the sun began to set, and Pip felt a little afraid.", "soft"),
    (11, "af_heart", 0.95, "Do not worry, said the owl. I will fly you home.", "reassuring"),
    (12, "af_heart", 1.0,  "They flew above the trees, and the world looked very small.", "wonder"),
    (13, "af_heart", 1.0,  "Good night, little panda, said the owl, until tomorrow.", "tender"),
    (14, "af_heart", 1.0,  "And Pip fell asleep, smiling, with the blue feather tucked under one ear.", "peaceful"),
]

print(f"[start] peak_rss={rss_mb():.1f} MB  pages={len(PAGES)}", flush=True)

with measure("import kokoro") as _:
    from kokoro import KModel, KPipeline

with measure("load KModel") as t_load:
    model = KModel().to("cpu")

with measure("KPipeline('a')") as _:
    pipe = KPipeline(lang_code="a", model=model)

# 1) Synthesize per-page, timing each
print("\n[1] SYNTHESIZE PAGES")
page_audio: list[np.ndarray] = []
page_meta: list[dict] = []
with measure("synthesize all 14 pages") as t_synth:
    for num, voice, speed, text, intent in PAGES:
        with measure(f"  page {num:02d} '{intent}'") as t_p:
            chunks = []
            for i, result in enumerate(pipe(text, voice=voice, speed=speed)):
                _, _, audio = result
                if audio is None:
                    continue
                chunks.append(audio.detach().cpu().numpy().astype(np.float32))
            audio = np.concatenate(chunks)
            page_audio.append(audio)
            save_wav(os.path.join(OUT_DIR, f"page{num:02d}.wav"), audio, 24000)
            stats = audio_stats(audio, 24000)
            stats["page"] = num
            stats["voice"] = voice
            stats["speed"] = speed
            stats["intent"] = intent
            stats["text"] = text
            stats["wall_time_s"] = round(t_p.elapsed, 3)
            page_meta.append(stats)
            print(
                f"    page {num:02d}  dur={stats['duration_s']:5.2f}s  wall={t_p.elapsed:.3f}s  "
                f"intent={intent:12s} rms={stats['rms']:.4f}",
                flush=True,
            )

# 2) Concatenate the whole book
print("\n[2] CONCATENATE")
silence = np.zeros(int(0.4 * 24000), dtype=np.float32)  # 0.4s between pages
book = np.concatenate([a for tup in zip(page_audio, [silence] * len(page_audio)) for a in tup])
save_wav(os.path.join(OUT_DIR, "book.wav"), book, 24000)
book_stats = audio_stats(book, 24000)
print(f"    book total: {book_stats['duration_s']:.2f}s   file: book.wav")

# 3) STT round-trip
print("\n[3] STT ROUND TRIP")
with measure("import faster_whisper") as _:
    from faster_whisper import WhisperModel

with measure("load STT (int8)") as t_stt_load:
    stt = WhisperModel("Systran/faster-distil-whisper-large-v3", device="cpu", compute_type="int8")

with measure("transcribe full book (int8)") as t_stt:
    segments, info = stt.transcribe(book, language="en", beam_size=5, vad_filter=True)
    transcript = " ".join(seg.text.strip() for seg in segments).strip()

# Compare to ground truth
gt_full = " ".join(p[3] for p in PAGES)
# Token-level WER
import re


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s']", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def wer(ref: str, hyp: str) -> tuple[int, int, float]:
    ref_w = norm(ref).split()
    hyp_w = norm(hyp).split()
    n = len(ref_w)
    dp = [[0] * (len(hyp_w) + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(len(hyp_w) + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, len(hyp_w) + 1):
            cost = 0 if ref_w[i - 1] == hyp_w[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    edits = dp[n][len(hyp_w)]
    return edits, n, edits / max(n, 1)


edits, n, w = wer(gt_full, transcript)

with open(os.path.join(OUT_DIR, "book_transcript.txt"), "w") as f:
    f.write(transcript)
with open(os.path.join(OUT_DIR, "book_groundtruth.txt"), "w") as f:
    f.write(gt_full)

summary = {
    "model_tts": "Kokoro-82M (v1.0)",
    "model_stt": "Systran/faster-distil-whisper-large-v3 (int8)",
    "n_pages": len(PAGES),
    "tts_load_s": round(t_load.elapsed, 3),
    "tts_synth_total_s": round(t_synth.elapsed, 3),
    "tts_audio_total_s": round(book_stats["duration_s"], 3),
    "tts_realtime_factor": round(t_synth.elapsed / max(book_stats["duration_s"], 1e-3), 4),
    "stt_load_s": round(t_stt_load.elapsed, 3),
    "stt_transcribe_s": round(t_stt.elapsed, 3),
    "stt_audio_dur_s": round(info.duration, 3),
    "stt_realtime_factor": round(t_stt.elapsed / max(info.duration, 1e-3), 4),
    "round_trip_wer": round(w, 4),
    "round_trip_edits": edits,
    "round_trip_ref_words": n,
    "peak_rss_mb_at_end": round(rss_mb(), 1),
    "pages": page_meta,
}
with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
    json.dump(summary, f, indent=2)

print("\n[ROUND TRIP SUMMARY]")
print(f"  pages synthesized:    {len(PAGES)}")
print(f"  TTS load:             {t_load.elapsed:.2f}s")
print(f"  TTS synth (all):      {t_synth.elapsed:.2f}s for {book_stats['duration_s']:.2f}s of audio "
      f"(rtf={t_synth.elapsed / max(book_stats['duration_s'], 1e-3):.3f}x)")
print(f"  STT load (int8):      {t_stt_load.elapsed:.2f}s")
print(f"  STT transcribe:       {t_stt.elapsed:.2f}s for {info.duration:.2f}s of audio "
      f"(rtf={t_stt.elapsed / max(info.duration, 1e-3):.3f}x)")
print(f"  Round-trip WER:       {w * 100:.1f}%  ({edits}/{n} edits)")
print(f"  Peak RSS:             {rss_mb():.1f} MB")
print()
print("  --- transcript ---")
print("  " + transcript[:500] + ("..." if len(transcript) > 500 else ""))
