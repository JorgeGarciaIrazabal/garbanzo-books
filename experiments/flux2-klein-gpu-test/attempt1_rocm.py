"""
Attempt 1: FLUX.2 [klein] 4B on the Strix Halo iGPU via ROCm 6.4.

Mirrors the structure of the original CPU attempt (flux2-klein-test/attempt1_local_cpu.py)
but uses device='cuda' (which on the ROCm PyTorch build maps to the AMD GPU).

If the GPU is not visible (is_available() == False), we fall back to
CPU and report a "GPU not available" result so the comparison is fair.
"""
import gc
import os
import sys
import time
import traceback

import torch
from PIL import Image

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HOME", "/home/jgarcairaza/.cache/huggingface")

# Try to convince ROCm to load on Strix Halo.
# Strix Halo is gfx1151, which is not yet in upstream PYTORCH_HIP_ARCHITECTURES.
# The standard workaround is to spoof as gfx1100 (RDNA 3) which is the closest
# supported family. gfx1100 covers RDNA 3 desktop, gfx1101 covers some laptops,
# gfx1102 covers some APUs — for Strix Halo the safest spoof is gfx1100.
os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", "11.0.0")

MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
OUT_DIR = "experiments/flux2-klein-gpu-test/outputs"
os.makedirs(OUT_DIR, exist_ok=True)

PROMPT = "A tiny red panda wearing a yellow raincoat, standing in a soft mossy forest, picture book illustration"
NEG_PROMPT = "blurry, deformed, watermark, text"


def rss_gb() -> float:
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024


def try_device() -> tuple[str, str]:
    """Return (device, reason). device is 'cuda' or 'cpu'."""
    if torch.cuda.is_available():
        try:
            name = torch.cuda.get_device_name(0)
            return "cuda", f"available ({name})"
        except Exception as e:
            return "cpu", f"is_available=True but init failed: {e}"
    return "cpu", "is_available=False"


device, why = try_device()
print(f"[probe] device={device!r}  reason={why}", flush=True)
print(f"[probe] hip_runtime={torch.version.hip}  cuda_arch_list={torch.cuda.get_arch_list()}", flush=True)
print(f"[probe] torch={torch.__version__}  rss={rss_gb():.2f} GB", flush=True)

t0 = time.time()
print(f"[{time.time()-t0:6.1f}s] importing Flux2KleinPipeline ...", flush=True)
from diffusers import Flux2KleinPipeline  # noqa: E402

print(f"[{time.time()-t0:6.1f}s] downloading/loading pipeline ({MODEL_ID}) ...", flush=True)
try:
    pipe = Flux2KleinPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        variant=None,
    )
    print(f"[{time.time()-t0:6.1f}s] loaded.", flush=True)
    pipe.set_progress_bar_config(disable=True)
    print(f"[{time.time()-t0:6.1f}s] pipe components: {list(pipe.components.keys())}", flush=True)
except Exception as e:
    print(f"[{time.time()-t0:6.1f}s] LOAD FAILED: {type(e).__name__}: {e}", flush=True)
    traceback.print_exc()
    sys.exit(2)

# Move the whole pipeline to the chosen device. For 'cuda' this hits the
# iGPU; for 'cpu' this is a no-op (the original attempt).
if device == "cuda":
    print(f"[{time.time()-t0:6.1f}s] moving pipeline to cuda ...", flush=True)
    try:
        pipe.to("cuda")
        print(f"[{time.time()-t0:6.1f}s] moved.  rss={rss_gb():.2f} GB", flush=True)
    except Exception as e:
        print(f"[{time.time()-t0:6.1f}s] MOVE TO CUDA FAILED: {type(e).__name__}: {e}", flush=True)
        print(f"[{time.time()-t0:6.1f}s] falling back to CPU ...", flush=True)
        device = "cpu"
        gc.collect()

print(f"[{time.time()-t0:6.1f}s] starting generation (512x512, 4 steps, guidance 1.0) on device={device} ...", flush=True)
try:
    gen = torch.Generator(device=device).manual_seed(0)
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

out = os.path.join(OUT_DIR, f"attempt1_{device}_bf16_512.png")
image.save(out)
print(f"[{time.time()-t0:6.1f}s] saved {out} ({image.size})  rss={rss_gb():.2f} GB", flush=True)
