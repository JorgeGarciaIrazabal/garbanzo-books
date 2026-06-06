"""
Attempt 2: FLUX.2 [klein] 4B on CPU at the realistic picture-book page
size (1024x1024) and at 4 steps. Measure wall time and peak RSS.
"""
import os
import resource
import time
import traceback

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HOME", "/home/jgarcairaza/.cache/huggingface")

import torch
from PIL import Image

from diffusers import Flux2KleinPipeline

OUT = "/tmp/opencode/flux2-klein-test/outputs/attempt2_cpu_bf16_1024.png"
PROMPT = ("A tiny red panda wearing a yellow raincoat, standing on a mossy "
          "log in a soft misty forest, picture book illustration, "
          "warm golden light, painterly")

def rss_gb():
    # ru_maxrss is in KiB on Linux
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024

t0 = time.time()
print(f"[{t0:+.1f}] loading pipeline (FLUX.2-klein-4B, bf16, CPU) ...", flush=True)
pipe = Flux2KleinPipeline.from_pretrained(
    "black-forest-labs/FLUX.2-klein-4B",
    torch_dtype=torch.bfloat16,
)
pipe.set_progress_bar_config(disable=True)
print(f"[{time.time()-t0:6.1f}s] loaded. RSS={rss_gb():.2f} GB", flush=True)

t1 = time.time()
gen = torch.Generator(device="cpu").manual_seed(42)
img = pipe(
    prompt=PROMPT,
    height=1024, width=1024,
    guidance_scale=1.0,
    num_inference_steps=4,
    generator=gen,
).images[0]
dt = time.time() - t1
img.save(OUT)
print(f"[{time.time()-t0:6.1f}s] saved {OUT} ({img.size})  gen_time={dt:.1f}s  peak_RSS={rss_gb():.2f} GB", flush=True)
