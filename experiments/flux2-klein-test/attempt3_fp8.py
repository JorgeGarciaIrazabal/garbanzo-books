"""
Attempt 3: FLUX.2 [klein] 4B fp8 variant on CPU. fp8 should halve the
weight footprint of the transformer (from 3.9B*2=7.8GB to 3.9GB) and
cut activations. Lets us compare quality/cost vs bf16.
"""
import os
import resource
import time

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HOME", "/home/jgarcairaza/.cache/huggingface")

import torch
from diffusers import Flux2KleinPipeline

OUT = "/tmp/opencode/flux2-klein-test/outputs/attempt3_cpu_fp8_1024.png"
PROMPT = ("A tiny red panda wearing a yellow raincoat, standing on a mossy "
          "log in a soft misty forest, picture book illustration, "
          "warm golden light, painterly")

def rss_gb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024

t0 = time.time()
print(f"[{time.time()-t0:6.1f}s] loading FLUX.2-klein-4B-fp8 ...", flush=True)
pipe = Flux2KleinPipeline.from_pretrained(
    "black-forest-labs/FLUX.2-klein-4b-fp8",
    torch_dtype=torch.bfloat16,  # diffusers fp8 checkpoints load with bf16 as the runtime dtype
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
