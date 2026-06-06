"""
Attempt 1: Load FLUX.2 [klein] 4B locally on CPU in bf16, generate one image.

This is expected to OOM or take a very long time. The point is to
*measure* the constraint, not to produce a polished picture.
"""
import gc
import os
import sys
import time
import traceback

import torch
from PIL import Image

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
# Use the user-level cache (under /home) since /tmp is a small tmpfs.
os.environ.setdefault("HF_HOME", "/home/jgarcairaza/.cache/huggingface")

MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
OUT_DIR = "/tmp/opencode/flux2-klein-test/outputs"
os.makedirs(OUT_DIR, exist_ok=True)

PROMPT = "A tiny red panda wearing a yellow raincoat, standing in a soft mossy forest, picture book illustration"
NEG_PROMPT = "blurry, deformed, watermark, text"

# Try to keep memory pressure low enough that the host stays responsive.
# We will NOT use model_cpu_offload (it's a GPU helper). Instead we just
# load to CPU and run everything there.

t0 = time.time()
print(f"[{time.time()-t0:6.1f}s] importing Flux2KleinPipeline ...", flush=True)
from diffusers import Flux2KleinPipeline  # noqa: E402

print(f"[{time.time()-t0:6.1f}s] downloading/loading pipeline ({MODEL_ID}) ...", flush=True)
try:
    pipe = Flux2KleinPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        variant=None,           # we want the default fp32/bf16 weights
    )
    print(f"[{time.time()-t0:6.1f}s] loaded. moving to CPU (already on CPU) ...", flush=True)
    pipe.set_progress_bar_config(disable=True)
    print(f"[{time.time()-t0:6.1f}s] pipe components: {list(pipe.components.keys())}", flush=True)

    # Measure resident model memory on CPU.
    total_params = 0
    for name, comp in pipe.components.items():
        if hasattr(comp, "parameters"):
            n = sum(p.numel() for p in comp.parameters())
            total_params += n
            print(f"[{time.time()-t0:6.1f}s]   {name:14s} params={n/1e9:.3f} B", flush=True)
    print(f"[{time.time()-t0:6.1f}s] TOTAL params = {total_params/1e9:.3f} B "
          f"(~{total_params*2/1e9:.1f} GB in bf16)", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:6.1f}s] LOAD FAILED: {type(e).__name__}: {e}", flush=True)
    traceback.print_exc()
    sys.exit(2)

print(f"[{time.time()-t0:6.1f}s] starting generation (512x512, 4 steps, guidance 1.0) ...", flush=True)
try:
    gen = torch.Generator(device="cpu").manual_seed(0)
    image = pipe(
        prompt=PROMPT,
        height=512,
        width=512,
        guidance_scale=1.0,
        num_inference_steps=4,
        generator=gen,
    ).images[0]
except Exception as e:
    print(f"[{time.time()-t0:6.1f}s] GENERATION FAILED: {type(e).__name__}: {e}", flush=True)
    traceback.print_exc()
    sys.exit(3)

out = os.path.join(OUT_DIR, "attempt1_cpu_bf16_512.png")
image.save(out)
print(f"[{time.time()-t0:6.1f}s] saved {out} ({image.size})", flush=True)
