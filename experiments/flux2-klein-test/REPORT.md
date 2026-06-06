# FLUX.2 [klein] — local feasibility test

This folder is an isolated sandbox. **It does not touch anything in the
parent `garbanzo-books` project** — no files were added or modified outside
`/tmp/opencode/flux2-klein-test/`.

## Hardware under test

| Item | Value |
|---|---|
| CPU | 32 threads |
| RAM | 30 GB (8 GB swap) |
| GPU | AMD Strix Halo (Radeon 8060S) — **iGPU, RDNA 3.5, shares system RAM** |
| CUDA / ROCm | None installed; no NVIDIA |
| Disk on `/home` | 1.3 TB free (used for HF cache) |
| Python | 3.13.7, diffusers 0.37.1 |

## Conclusion (short version)

**Yes, FLUX.2 [klein] 4B works locally on this machine on CPU.**
No GPU is required. Cost is modest: **~38 s / 768×768 image, ~62 s / 1024×1024,
peak RSS ~17 GB**. A full 14-page picture book is roughly 9 minutes of
generation, dominated by 4-step denoising.

## Attempt results

| # | Model | Size | Steps | Resolution | Wall time | Peak RSS | Result |
|---|---|---|---|---|---|---|---|
| 1 | `FLUX.2-klein-4B` (bf16) | 7.98 B params | 4 | 512×512 | **17 s** | – | ✅ |
| 2 | `FLUX.2-klein-4B` (bf16) | 7.98 B params | 4 | 1024×1024 | **62 s** | 17.97 GB | ✅ |
| 3 | `FLUX.2-klein-4b-fp8` | 3.9 B-equivalent weights | – | – | – | – | ⏭️ skipped (no `model_index.json`, would need a custom loader) |
| 4 | `FLUX.2-klein-9b-kv` | ~9 B params | – | – | – | – | ⏭️ skipped (gated — non-commercial license + auth required) |
| 5 | `FLUX.2-klein-4B` (bf16), batch×4 | – | 4 | 768×768 | **36 s, 38 s, 39 s, 39 s** (steady-state ~38 s) | 16.97 GB | ✅ |

The model fits in memory comfortably; 30 GB RAM is enough. CPU is the only
bottleneck. With 32 threads the per-image time is ~38 s for 768² and ~62 s
for 1024² — both **faster than typical first-token latency for cloud
inference providers** once you account for network round-trips.

## What I deliberately did *not* try

* **9B kv (gated, non-commercial)** — would need license acceptance, but the
  4B is Apache-2.0 and is what the project should use anyway.
* **`4B-fp8` via diffusers** — that repo ships only a single
  `flux-2-klein-4b-fp8.safetensors` with no `model_index.json`, so it would
  need a hand-written `Flux2KleinPipeline` load. fp8 would halve the
  transformer weight (3.9 GB instead of 7.8 GB) and likely cut RSS to ~10 GB,
  but the bf16 path already fits in RAM, so the win is mostly for parallelism.
* **AMD ROCm GPU path** — PyTorch on Strix Halo requires the unofficial
  `torch+rocm` wheel plus a `HSA_OVERRIDE_GFX_VERSION` and would still run
  through system RAM (the iGPU has no VRAM of its own). The CPU path is
  competitive and the code stays portable.

## What the storybook project should do

The repo's current `scripts/generate_images.py` defaults to **Gemini
"nano-banana"** because that's the only path that works *out of the box*
on a dev box without a real GPU. With the results above, we can add a
**local FLUX.2 [klein] backend** that has several real advantages for this
project:

| Property | Gemini nano-banana | FLUX.2 [klein] 4B local |
|---|---|---|
| Cost | Free tier OK, then metered | Free (electricity only) |
| Latency | network + queue | **38 s / 768², no network** |
| Style / character control | weak (text-prompt only) | strong (seed + ref images + LoRA) |
| Privacy | prompt goes to Google | stays on disk |
| Privacy of children's prompts | **concerning** | none |
| Apache-2.0 | depends on Google's terms | ✅ |
| Diffusers integration | none | ✅ first-class |

A 14-page book at 768² is about **9 minutes wall** on this box, with all
seeds, references, and style tokens fully under the project's control.
For a workflow where you iterate on a single page (the typical case during
character design), it's **interactive** — 30 s is fast enough to try 5
prompts in 3 minutes.

## Sketch: how to add a `backend: local-flux` mode to the project

(Not yet implemented in the project — this is just the design so you
can decide whether to wire it in.)

```python
# in scripts/generate_images.py, a new branch:
elif backend == "local-flux":
    from diffusers import Flux2KleinPipeline
    import torch
    pipe = Flux2KleinPipeline.from_pretrained(
        "black-forest-labs/FLUX.2-klein-4B",
        torch_dtype=torch.bfloat16,
    )
    # The scene prompt is the page's `image.scene`; the world style +
    # character appearance tokens are appended here automatically.
    full_prompt = f"{scene}, {style_block}, {', '.join(appearance_tokens)}"
    negative = palette_negative_prompt  # optional, may not be supported
    image = pipe(
        prompt=full_prompt,
        height=h, width=w,
        num_inference_steps=4,
        guidance_scale=1.0,
        generator=torch.Generator(device="cpu").manual_seed(seed),
    ).images[0]
```

The world `prompt_style_block` + `palette` + character `appearance_token`s
get assembled exactly the way the project already does for Gemini — only
the call site changes.

## Files in this sandbox

```
/tmp/opencode/flux2-klein-test/
├── .venv/                     # isolated Python 3.13 env
├── attempt1_local_cpu.py      # 4B, 512x512 — 17 s
├── attempt2_1024.py           # 4B, 1024x1024 — 62 s, 17.97 GB peak
├── attempt3_fp8.py            # skipped (no diffusers index)
├── attempt4_9bkv.py           # skipped (gated)
├── attempt5_batch.py          # 4B, batch of 4 at 768x768 — 38 s each
├── outputs/
│   ├── attempt1_cpu_bf16_512.png
│   ├── attempt2_cpu_bf16_1024.png
│   └── batch/
│       ├── page_00.png        # red panda in mossy forest
│       ├── page_01.png        # fox cub in teacup
│       ├── page_02.png        # robot watering flowers
│       └── page_03.png        # owl reading a book
└── REPORT.md                  # this file
```
