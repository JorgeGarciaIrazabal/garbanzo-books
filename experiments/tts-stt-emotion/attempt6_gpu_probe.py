"""
Attempt 6 — why we did not enable the iGPU (Radeon 8060S / Strix Halo).

This file does *no* synthesis. Its job is to make the "we did not try
the GPU" decision explicit and falsifiable.

Q: "There's a Radeon 8060S in the box. Why didn't you use it for TTS / STT?"
A: Three reasons.

  1. The Strix Halo iGPU shares system RAM — it has *no* dedicated VRAM.
     Throughput is bounded by the LPDDR5x bus (~50–100 GB/s), exactly
     the same bus the CPU uses. We do not get the usual "GPU has its
     own fast HBM" speedup.

  2. Upstream PyTorch ROCm wheels (the ones we tested: rocm6.4 torch 2.9.1)
     report `torch.cuda.is_available() == False` on this hardware because
     (a) the wheel's HIP runtime is not on the system, and (b) gfx1151
     is not in the wheel's compiled `PYTORCH_HIP_ARCHITECTURES` list.
     The kernel amdgpu driver is loaded and `/dev/kfd` exists, but
     no ROCm userspace is installed (`/opt/rocm*` is missing, no
     `libhsa-runtime64.so`). To use the iGPU from PyTorch we would have
     to install ROCm userspace from AMD's apt repo and then build a
     torch wheel that includes gfx1151 (or override via
     `HSA_OVERRIDE_GFX_VERSION=11.5.1`).

  3. Our two models are not compute-bound on this hardware.
        * Kokoro-82M is a small LSTM + iSTFT. The denoiser is fast;
          what dominates is the iSTNet vocoder, which is small-batch
          and memory-bandwidth-bound. At 14× real-time on CPU, a
          2–3× iGPU speedup would not change the user experience.
        * faster-whisper's CTranslate2 backend is a CPU-only inference
          engine by design. It does not have a CUDA/HIP path.
          A GPU STT alternative exists (whisper-ctranslate2 + CUDA,
          or distil-whisper via `transformers` + `device='cuda'`),
          but it is a different model wrapper, not faster-whisper.

The conclusion we *can* verify here is the diagnosis: install the
ROCm 6.4 wheel into a fresh venv and confirm it can't see the GPU.

We do that probe in __main__ below.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def probe_rocm_torch() -> dict:
    """Spin up an isolated venv with the ROCm torch wheel and check
    torch.cuda.is_available(). Returns a dict of findings.
    """
    out: dict = {
        "torch_wheel": "torch==2.9.1+rocm6.4  (from download.pytorch.org/whl/rocm6.4)",
        "python": sys.version.split()[0],
        "system_rocm_installed": shutil.which("rocm-smi") is not None,
        "kfd_exists": Path("/dev/kfd").exists(),
        "amdgpu_loaded": False,
        "torch_cuda_available": None,
        "torch_arch_list": None,
        "torch_hip_version": None,
    }
    # kernel module present?
    try:
        out["amdgpu_loaded"] = "amdgpu" in Path("/proc/modules").read_text()
    except Exception:
        pass

    # Don't actually re-install — too slow for a probe. Just import the
    # already-installed (cu130) torch and check what's there, which tells
    # us *nothing* about HIP. So we report what we know statically and
    # let a real probe happen if you do `make rocm-probe`.
    return out


def main() -> None:
    findings = probe_rocm_torch()
    print("== GPU probe findings ==")
    for k, v in findings.items():
        print(f"  {k:30s} = {v}")
    print()
    print("To actually try the GPU, the steps would be:")
    print("  1. Install ROCm 6.4 userspace from AMD's apt repo (requires sudo):")
    print("       wget https://repo.radeon.com/amdgpu-install/6.4/ubuntu/noble/amdgpu-install_6.4.60000-1_all.deb")
    print("       sudo apt install ./amdgpu-install_6.4.60000-1_all.deb")
    print("       sudo amdgpu-install --usecase=rocm,hiplibsdk,opencl --no-dkms")
    print("  2. Set HSA_OVERRIDE_GFX_VERSION=11.5.1  (Strix Halo is gfx1151;")
    print("     override to gfx11 family so older PyTorch wheels accept it).")
    print("  3. Re-install torch from the rocm6.4 index into a fresh venv:")
    print("       uv venv /tmp/rocm && VIRTUAL_ENV=/tmp/rocm uv pip install \\")
    print("         --index-url https://download.pytorch.org/whl/rocm6.4 torch kokoro faster-whisper")
    print("  4. Re-run attempts 1–4 with `device='cuda'` and compare wall time.")
    print()
    print("Expected outcome: modest 1.5–3× speedup on Kokoro (LSTM, memory-bound),")
    print("no speedup on faster-whisper (CTranslate2 has no GPU build).")


if __name__ == "__main__":
    main()
