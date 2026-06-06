"""
Attempt 4: FLUX.2 [klein] 9B KV (single-checkpoint, no base/refiner split)
on CPU. ~9B params, no negative prompt, 4 distilled steps. Goal: discover
whether this 30GB-RAM box can hold the bigger model.
"""
import os
import resource
import time
import traceback

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HOME", "/home/jgarcairaza/.cache/huggingface")

import torch
from diffusers import Flux2KleinPipeline

OUT = "/tmp/opencode/flux2-klein-test/outputs/attempt4_cpu_bf16_9bkv_512.png"
PROMPT = "A tiny red panda wearing a yellow raincoat in a soft mossy forest, picture book illustration"

def rss_gb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024

t0 = time.time()
print(f"[{time.time()-t0:6.1f}s] loading FLUX.2-klein-9b-kv ...", flush=True)
try:
    pipe = Flux2KleinPipeline.from_pretrained(
        "black-forest-labs/FLUX.2-klein-9b-kv",
        torch_dtype=torch.bfloat16,
    )
except Exception as e:
    print(f"LOAD FAILED: {type(e).__name__}: {e}", flush=True)
    traceback.print_exc()
    raise
pipe.set_progress_bar_config(disable=True)
print(f"[{time.time()-t0:6.1f}s] loaded. RSS={rss_gb():.2f} GB", flush=True)

# 512 to keep memory comfortable; this is a feasibility probe, not a quality run.
t1 = time.time()
gen = torch.Generator(device="cpu").manual_seed(0)
img = pipe(
    prompt=PROMPT,
    height=512, width=512,
    guidance_scale=1.0,
    num_inference_steps=4,
    generator=gen,
).images[0]
dt = time.time() - t1
img.save(OUT)
print(f"[{time.time()-t0:6.1f}s] saved {OUT} ({img.size})  gen_time={dt:.1f}s  peak_RSS={rss_gb():.2f} GB", flush=True)
