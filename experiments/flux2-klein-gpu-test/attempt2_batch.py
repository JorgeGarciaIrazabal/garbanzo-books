"""
Attempt 2: GPU batch of 4 — does the iGPU keep up under load?

Mirrors flux2-klein-test/attempt5_batch.py but on the iGPU.
"""
import os
import resource
import time

import torch
from diffusers import Flux2KleinPipeline

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HOME", "/home/jgarcairaza/.cache/huggingface")
os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", "11.0.0")

OUT_DIR = "experiments/flux2-klein-gpu-test/outputs/batch"
os.makedirs(OUT_DIR, exist_ok=True)

PROMPTS = [
    "A tiny red panda wearing a yellow raincoat in a mossy forest, picture book illustration",
    "A small fox cub curled up in a teacup, soft pastel colors, picture book illustration",
    "A friendly robot watering glowing flowers on a moonlit balcony, picture book illustration",
    "A baby owl wearing spectacles reading a tiny book by candlelight, picture book illustration",
]


def rss_gb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024


def device():
    if torch.cuda.is_available():
        try:
            torch.cuda.init()
            return "cuda", torch.cuda.get_device_name(0)
        except Exception as e:
            return "cpu", f"init failed: {e}"
    return "cpu", "is_available=False"


dev, name = device()
print(f"[probe] device={dev!r}  ({name})", flush=True)

t_load = time.time()
pipe = Flux2KleinPipeline.from_pretrained(
    "black-forest-labs/FLUX.2-klein-4B",
    torch_dtype=torch.bfloat16,
)
pipe.set_progress_bar_config(disable=True)
print(f"LOAD time = {time.time()-t_load:.1f}s  RSS after load = {rss_gb():.2f} GB", flush=True)

if dev == "cuda":
    print(f"moving pipeline to cuda ...", flush=True)
    try:
        pipe.to("cuda")
        print(f"  moved, RSS = {rss_gb():.2f} GB", flush=True)
    except Exception as e:
        print(f"  FAILED: {e}; falling back to CPU", flush=True)
        dev = "cpu"

t_first = None
for i, prompt in enumerate(PROMPTS):
    t0 = time.time()
    gen = torch.Generator(device=dev).manual_seed(i)
    img = pipe(
        prompt=prompt,
        height=768, width=768,
        guidance_scale=1.0,
        num_inference_steps=4,
        generator=gen,
    ).images[0]
    dt = time.time() - t0
    if t_first is None:
        t_first = dt
    out = os.path.join(OUT_DIR, f"page_{i:02d}.png")
    img.save(out)
    print(f"  image {i+1}/{len(PROMPTS)}  {dt:5.1f}s  peak_RSS={rss_gb():.2f} GB  -> {out}", flush=True)

print(f"\nfirst-image time = {t_first:.1f}s (includes warmup/compile)", flush=True)
