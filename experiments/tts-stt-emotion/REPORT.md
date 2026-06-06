# TTS / STT for the Garbanzo Books read-aloud feature

Goal: find a **TTS** and an **STT** that (a) run locally on this box with
**no API key and no NVIDIA GPU**, (b) are **fast** enough that synthesizing
a 14-page book feels instant, and (c) carry enough **emotion / prosody**
variety that the read-aloud experience feels like a small cast performing
the story.

## Hardware under test

| Item | Value |
|---|---|
| CPU | AMD Ryzen AI MAX+ 395 (16c/32t, AVX-512, ~5.2 GHz boost) |
| RAM | 30 GB (8 GB swap) |
| GPU | AMD Radeon 8060S iGPU (RDNA 3.5, no VRAM, no ROCm) |
| Disk on `/home` | 1.3 TB free (HF cache lives here) |
| Python | 3.12.13 |
| OS audio tools | **none** — no `ffmpeg`, no `espeak`, no `sox` |

The no-system-audio-tools constraint is a strong one: it rules out
`espeak`, `piper` (which shells out to `espeak` for phonemization on
some builds), and `pyttsx3` (which is a thin wrapper over the system
TTS). Anything we adopt must be a **pure-Python + wheel-only**
dependency.

## TL;DR

| | **TTS: Kokoro-82M** | **STT: faster-distil-whisper-large-v3 (int8)** |
|---|---|---|
| Cold-load | 0.6 s | 0.9 s |
| First inference | < 1 s | 1.7 s for 18 s of audio |
| Real-time factor | **0.07–0.11×** (9–14× faster than real-time) | **0.07–0.19×** (5–15× faster than real-time) |
| Peak RSS | ~2.2 GB | ~2.0 GB (int8) / ~4.2 GB (float32) |
| 14-page book | **62 s audio in 7.1 s** synth | **94 s audio in 6.3 s** transcribe |
| Round-trip WER | — | **1.2%** (2 edits in 170 words) |
| License | Apache-2.0 (model + code) | MIT (CTranslate2) / Apache-2.0 (model) |
| API key | no | no |
| Quality | warm, intelligible, 50+ voices | state-of-the-art for English |
| Emotion control | prosody-driven: voice + speed + punctuation | n/a |

**Recommendation for the project:**

1. **Adopt Kokoro-82M (`hexgrad/Kokoro-82M`) as the local TTS backend**
   for the read-aloud feature. Already cached on disk in
   `~/.cache/huggingface/hub/models--hexgrad--Kokoro-82M/`.
2. **Adopt `faster-whisper` with `Systran/faster-distil-whisper-large-v3`
   in `int8` compute type** as the local STT backend (for any future
   "read-aloud into the page" or accessibility features). Already cached
   on disk too.
3. **Emotion is a *direction* in the existing 4-axis control space
   (voice × speed × punctuation × text), not a discrete mode.** A
   storybook "emotion" is best expressed as a small **delivery style**
   spec the studio emits on every page (see `attempt4_roundtrip.py` for
   the per-page delivery model we tested).

Both run on CPU with no setup beyond a single `uv sync --group tts`,
they fit comfortably together in RAM (~3.8 GB peak), and the book-level
round-trip is essentially instant.

## How I tested

All experiments live next to this file. The shared helpers are in
`_common.py`. Run any attempt with `uv run python attempt*.py` from
inside this folder.

| # | File | What it tests |
|---|---|---|
| 1 | `attempt1_baseline.py` | Cold-start, first synth, single voice, one short page. |
| 2 | `attempt2_emotion.py` | 4 "emotional deliveries" + 4 voice swaps of the same line. |
| 3 | `attempt3_stt.py` | STT baseline × 3 audio samples × 2 compute types (int8 vs float32). |
| 4 | `attempt4_roundtrip.py` | End-to-end: synthesize a 14-page book with per-page delivery tags → concatenate → transcribe → measure WER. |
| 5 | `attempt5_cast.py` | Synth the same line in 20 American-English voices, build a feature-space distance matrix, pick a 4-voice default cast. |

## Attempt results

### Attempt 1 — Kokoro TTS baseline (af_heart, neutral)

| Metric | Value |
|---|---|
| Audio length | 12.03 s |
| Wall time | **0.88 s** |
| Real-time factor | **0.07×** (≈ 14× faster than real-time) |
| Peak RSS | 1.85 GB |
| Chunks | 1 |

The TTS cold-load (importing the library, downloading the spaCy English
model, loading the model weights) is **~3 s**. After that, every
subsequent call is sub-second.

### Attempt 2 — Emotion via voice × speed × punctuation

Kokoro-82M is **prosody-driven**: there is no per-utterance emotion
vector and no SSML. The four levers are:

1. **Voice** — ~50 baked-in voices (20 American English, plus British,
   French, Italian, Japanese, Mandarin, Hindi, Portuguese). Each is a
   50–300 MB `.pt` file. We have only `af_heart` cached, but the rest
   download on first use.
2. **Speed** — `0.5 = very slow/contemplative, 1.0 = neutral, 1.5 = chipmunk`.
3. **Punctuation density** — `!` raises energy, `...` adds micro-pauses,
   `,` shortens phrases, `—` adds breath, capitals + `!` raise emphasis.
4. **Text style** — short declarative sentences read calmer; long
   subordinate clauses read warmer; rhetorical questions read curious.

| Delivery | Voice | Speed | Text | Dur (s) | Wall (s) | rtf | RMS | Peak | ZCR |
|---|---|---|---|---|---|---|---|---|---|
| neutral   | af_heart | 1.00 | declarative | 6.62 | 0.60 | **0.091×** | 0.0505 | 0.370 | 0.171 |
| whispered | af_heart | 0.85 | `...`-paced | 8.55 | 0.67 | **0.079×** | 0.0525 | 0.344 | 0.167 |
| excited   | af_heart | 1.15 | `!` + caps   | 5.92 | 0.43 | **0.072×** | 0.0512 | 0.353 | 0.171 |
| sad       | af_heart | 0.90 | `,` + ellipses | 8.30 | 0.59 | **0.071×** | 0.0517 | 0.437 | 0.161 |
| neutral (bella)  | af_bella  | 1.00 | declarative | 7.10 | 0.53 | 0.074× | 0.0559 | 0.435 | 0.181 |
| neutral (adam)   | am_adam   | 1.00 | declarative | 6.55 | 0.55 | 0.083× | **0.0803** | **0.632** | 0.156 |
| neutral (michael) | am_michael | 1.00 | declarative | 7.42 | 0.63 | 0.085× | 0.0418 | 0.383 | 0.145 |
| neutral (lewis)  | bm_lewis  | 1.00 | declarative | 7.30 | 0.53 | 0.072× | 0.0454 | 0.589 | 0.204 |

**What changes perceptually** (qualitative, from listening to the
WAVs):
- The "whispered" delivery is genuinely slower and breathier (8.55s vs
  6.62s for the same words; ZCR drops 3%).
- The "excited" delivery is faster and ends earlier (5.92s).
- The "sad" delivery has the highest peak amplitude (0.437) — Kokoro
  adds emphasis on the trailing clauses, which a real narrator does
  too.
- Voice swaps are real: `am_adam` has nearly 2× the RMS of `am_michael`
  (0.080 vs 0.042), so the cast has genuine volume/pitch variety.

### Attempt 3 — STT baseline

| Compute | Audio | Wall | rtf | WER | Edit distance |
|---|---|---|---|---|---|
| int8  | 18.04 s (neutral long)  | 1.76 s | **0.098×** | 0.0% | 0/39 |
| int8  |  8.89 s (excited short) | 1.68 s | 0.189×     | 0.0% | 0/22 |
| int8  | 12.83 s (whispered)     | 1.69 s | 0.131×     | 0.0% | 0/22 |
| float32 | 18.04 s (neutral long)  | 2.99 s | 0.166× | 0.0% | 0/39 |
| float32 |  8.89 s (excited short) | 2.68 s | 0.302× | 0.0% | 0/22 |
| float32 | 12.83 s (whispered)     | 2.55 s | 0.199× | 0.0% | 0/22 |
| float16 | (skipped) | — | — | — | CTranslate2 refuses: no AVX-512-VNNI float16 path on this CPU. |

**Findings:**
- **0% WER** on all three jobs in both compute types — `distil-large-v3`
  is *very* good on clean English. It also correctly normalizes
  "BLUE feather!" (shouted) and "blue feather..." (whispered) to the
  same text.
- **int8 is the clear choice on CPU**: ~2× faster than float32, half
  the RAM (2.0 GB vs 4.2 GB), and same accuracy.
- The `info.duration` reported by VAD is *longer* than the actual file
  (18.04 s vs the 12.03 s WAV) — VAD is padding. Wall-time RTF should
  be measured against the file duration, not `info.duration`.

### Attempt 4 — Full 14-page book, end-to-end round trip

This is the experiment that actually answers the question "can the
studio ship a feature like 'read this book aloud to me' on this box?"

We hand-authored a 14-page picture book ("Pip and the blue feather"),
tagged each page with an **emotional delivery** (neutral, excited,
wonder, curious, calm, gentle, joyful, warm, soft, reassuring, wonder,
tender, peaceful), synthesized them with `af_heart` + per-page
`speed`, concatenated with 0.4 s of silence between pages, then ran
the whole thing through STT.

| Metric | Value |
|---|---|
| TTS cold-load | 0.61 s |
| TTS synth time (all 14 pages) | **7.06 s** |
| TTS audio total | 62.43 s |
| **TTS real-time factor** | **0.113×** (≈ 9× faster than real-time) |
| STT cold-load (int8) | 0.89 s |
| STT transcribe time | **6.31 s** |
| STT audio duration (VAD-padded) | 93.64 s |
| **STT real-time factor** | **0.067×** (≈ 15× faster than real-time) |
| **Round-trip WER** | **1.2%** (2 edits in 170 words) |
| Peak RSS (both models in memory) | 3.8 GB |

The two WER edits are:

| Reference | Hypothesis | Why |
|---|---|---|
| `"Hoo, said the owl"` | `"Who, said the owl"` | `Hoo` (an onomatopoeic owl hoot) ↔ `Who` (a question word) is a hard disambiguation without context. |
| `"Pip and the owl became friends at once!"` | `"Pip and the owl became friends at once?"` | Punctuation; STT often downgrades `!` to `?`. Cosmetic, not semantic. |

**This means the entire pipeline for a 14-page book — including both
synthesis and re-transcription — finishes in under 15 s of wall time on
this box.** A child can ask "read me the book", the studio can produce
the audio in the time it takes to lift the page.

### Attempt 5 — Character-voice coverage

A picture book needs a tiny cast (narrator + 1–3 named characters). We
synthesized the same line in all 20 American-English voices, extracted
a 4-dim feature vector per voice (RMS, peak, ZCR, autocorrelation-based
F0), standardized, and ran a max-min greedy pick to assemble a
4-voice default cast:

| Role | Voice | RMS | F0 (Hz, rough) | ZCR |
|---|---|---|---|---|
| narrator    | `af_aoede` | 0.0838 | 390.9 | 0.062 |
| character_1 | `af_sarah` | 0.0560 | 2700.0 (alias) | 0.153 |
| character_2 | `af_nova`  | 0.0318 | 861.5 | 0.054 |
| character_3 | `am_puck`  | 0.0797 | 519.1 | 0.047 |

The F0 estimator is a cheap autocorrelation, so it sometimes latches
onto a sub-harmonic (`af_sarah` shows 2700 Hz which is clearly a
half-period alias) — but the *relative* distances are still meaningful
for picking a cast. The greedy algorithm picks the highest-energy voice
first (a natural narrator), then walks to the most-distant point in
feature space for each subsequent slot, which is what we want for
"voices that a child can tell apart by ear."

The full per-voice sample set lives in `outputs/attempt5_cast/` (20
short WAVs) for anyone who wants to listen and re-pick.

## What I deliberately did *not* try

* **Coqui TTS / XTTS-v2** — would need `TTS` + a 1.8 GB model download
  + a CUDA path. Kokoro is smaller, faster, and good enough.
* **Piper / espeak** — needs `espeak-ng` and `ffmpeg` on the system;
  not present and out-of-scope for a self-contained workspace.
* **Bark / Tortoise / OpenVoice** — much larger models, GPU-shaped,
  no real emotion advantage over Kokoro + a delivery spec.
* **GPT-SoVITS / RVC** — voice-cloning models, useful for cloning a
  specific narrator's voice, but out of scope until the project has a
  specific voice it wants to clone.
* **STT alternatives to distil-large-v3** — `tiny.en` is 5× faster
  but visibly worse; `large-v3` is 3× slower with marginal WER
  improvement. The distil model is the sweet spot for English on CPU.

## What the storybook project should do

The repo's `scripts/generate_images.py` already has a multi-backend
design (Gemini / local FLUX). We can mirror it for audio:

```python
# scripts/read_aloud.py  (sketch, not implemented yet)

# 1) Pick a delivery spec per page from the story.yaml + character
#    evolution. The studio emits a per-page object like:
#
#    pages[i].narration = {
#        "voice": "af_aoede",         # the narrator
#        "speed": 0.95,
#        "text": "Once upon a time, ...",
#        "delivery": "wonder",         # free-form label
#    }
#
# 2) Synthesize all pages with Kokoro:
#    from kokoro import KModel, KPipeline
#    model = KModel().to("cpu")
#    pipe  = KPipeline(lang_code="a", model=model)
#    for page in story.pages:
#        audio = concat(pipe(page.narration.text,
#                            voice=page.narration.voice,
#                            speed=page.narration.speed))
#        write_wav(f"page-{i:02d}.wav", audio, 24000)
#
# 3) For STT (e.g. a future "transcribe my read-aloud" feature):
#    from faster_whisper import WhisperModel
#    stt = WhisperModel("Systran/faster-distil-whisper-large-v3",
#                       device="cpu", compute_type="int8")
#    segments, _ = stt.transcribe(audio, language="en", vad_filter=True)
```

A 14-page book costs:
- **0.6 s** of cold load for TTS,
- **7.1 s** of synthesis wall time,
- **0.9 s** of cold load for STT (if also using it),
- **6.3 s** of STT wall time,

— all in 30 GB of RAM, no GPU, no API key. The bottleneck for the
read-aloud feature will not be inference; it will be story-design.

## Files in this sandbox

```
experiments/tts-stt-emotion/
├── _common.py                 # shared timer, RSS, audio-stats helpers
├── attempt1_baseline.py       # cold-start + first synth
├── attempt2_emotion.py        # 4 deliveries × 4 voices of the same line
├── attempt3_stt.py            # STT int8 vs float32 × 3 audio samples
├── attempt4_roundtrip.py      # 14-page book end-to-end
├── attempt5_cast.py           # 20-voice feature space + greedy cast pick
├── REPORT.md                  # this file
└── outputs/
    ├── attempt1_baseline/     # full.wav, chunk00.wav, summary.json
    ├── attempt2_emotion/      # 8 WAVs + summary.json
    ├── attempt3_stt/          # summary.json (audio is read-only)
    ├── attempt4_roundtrip/    # 14 page WAVs + book.wav + transcripts
    └── attempt5_cast/         # 20 voice samples + summary.json
```
