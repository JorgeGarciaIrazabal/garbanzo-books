"""
Attempt 5: Amortize the 4B model load by running a small batch of
different prompts back-to-back. Measures per-image steady-state cost
(after the 1-time load), and confirms the box can do 2-3 images in
a single Python process without OOM.
"""
import os
import resource
import time

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HOME", "/home/jgarcairaza/.cache/huggingface")

import torch
from diffusers import Flux2KleinPipeline

OUT_DIR = "/tmp/opencode/flux2-klein-test/outputs/batch"
os.makedirs(OUT_DIR, exist_ok=True)

PROMPTS = [
    "A tiny red panda wearing a yellow raincoat in a mossy forest, picture book illustration",
    "A small fox cub curled up in a teacup, soft pastel colors, picture book illustration",
    "A friendly robot watering glowing flowers on a moonlit balcony, picture book illustration",
    "A baby owl wearing spectacles reading a tiny book by candlelight, picture book illustration",
]

def rss_gb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024

t_load = time.time()
pipe = Flux2KleinPipeline.from_pretrained(
    "black-forest-labs/FLUX.2-klein-4B",
    torch_dtype=torch.bfloat16,
)
pipe.set_progress_bar_config(disable=True)
print(f"LOAD time = {time.time()-t_load:.1f}s  RSS after load = {rss_gb():.2f} GB", flush=True)

t_first = None
for i, prompt in enumerate(PROMPTS):
    t0 = time.time()
    gen = torch.Generator(device="cpu").manual_seed(i)
    img = pipe(
        prompt=prompt,
        height=768, width=768,    # middle size for picture books
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
