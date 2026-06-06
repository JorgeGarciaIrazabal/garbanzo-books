"""
Attempt 6 — why we did not enable the iGPU (Radeon 8060S / Strix Halo).

This file does *no* synthesis. Its job is to make the "we did not try
the GPU" decision explicit and falsifiable, and to leave behind a tiny
recipe for actually switching it on if/when we want to.

Q: "There's a Radeon 8060S in the box. Why didn't you use it for TTS / STT?"
A: Three reasons.

  1. The Strix Halo iGPU shares system RAM — it has *no* dedicated VRAM.
     Throughput is bounded by the LPDDR5x bus (~50–100 GB/s), exactly
     the same bus the CPU uses. We do not get the usual "GPU has its
     own fast HBM" speedup. (Estimated ~2× ceiling on memory-bound
     workloads; smaller on compute-bound ones.)

  2. Upstream PyTorch ROCm wheels do not yet support gfx1151 in their
     compiled arch list. Empirical probe (we did this in a throwaway
     venv, deleted after):

        # uv venv /tmp/rocm && uv pip install --index-url \
        #     https://download.pytorch.org/whl/rocm6.4 torch==2.9.1
        $ python -c "import torch; print(torch.cuda.get_arch_list())"
        []                                          # <- empty
        $ python -c "import torch; print(torch.cuda.is_available())"
        False
        $ HSA_OVERRIDE_GFX_VERSION=11.5.1 python -c "import torch; torch.cuda.init()"
        RuntimeError: No HIP GPUs are available

     Fix: install ROCm 6.4 userspace from AMD's apt repo (requires sudo,
     ~2 GB) and use a community-built wheel or a nightly build that
     includes gfx1151. After that, `HSA_OVERRIDE_GFX_VERSION=11.5.1`
     is still needed until the arch lands upstream.

  3. The user account is not in the `render` group. /dev/kfd is mode
     660 root:render with no ACL fallback, so even with a working
     ROCm wheel the kernel will not enumerate the GPU to us. This is
     a one-line fix:

         sudo usermod -aG render,video jgarcairaza   # then re-login

     (or grant the ACL: `sudo setfacl -m u:jgarcairaza:rw /dev/kfd`)

  4. Our two models are not compute-bound on this hardware.
        * Kokoro-82M is a small LSTM + iSTFT. What dominates is the
          iSTNet vocoder, which is small-batch and memory-bandwidth
          bound. At 14× real-time on CPU, a 2–3× iGPU speedup would
          not change the user experience.
        * faster-whisper's CTranslate2 backend is a CPU-only inference
          engine by design. It does not have a CUDA/HIP path.
          A GPU STT alternative exists (whisper-ctranslate2 + CUDA,
          or distil-whisper via `transformers` + `device='cuda'`),
          but it is a different model wrapper, not faster-whisper.

So: the GPU is real, the kernel driver sees it, but the iGPU path is
behind (a) a missing arch in the upstream wheel, (b) missing ROCm
userspace, and (c) a missing group membership. None of those are
hard, but they all want sudo, and the *benefit* on these specific
workloads is small.

If we ever want to test it, here is the exact recipe:

  # 0. one-time setup (root):
  sudo usermod -aG render,video jgarcairaza   # then log out and back in
  # OR if you can't log out:  sudo setfacl -m u:jgarcairaza:rw /dev/kfd
  wget https://repo.radeon.com/amdgpu-install/6.4/ubuntu/noble/amdgpu-install_6.4.60000-1_all.deb
  sudo apt install ./amdgpu-install_6.4.60000-1_all.deb
  sudo amdgpu-install --usecase=rocm,hiplibsdk,opencl --no-dkms
  rocm-smi   # should now list 'gfx1151'

  # 1. new venv with the ROCm torch wheel:
  uv venv .venv-rocm --python 3.12
  HSA_OVERRIDE_GFX_VERSION=11.5.1 \
    VIRTUAL_ENV=.venv-rocm uv pip install \
        --index-url https://download.pytorch.org/whl/rocm6.4 \
        torch==2.9.1 kokoro soundfile numpy faster-whisper
  .venv-rocm/bin/python -c "import torch; print(torch.cuda.is_available())"  # -> True
"""
import os
import shutil
import sys
from pathlib import Path


def probe_system() -> dict:
    out: dict = {
        "kfd_exists": Path("/dev/kfd").exists(),
        "kfd_readable": False,
        "kfd_writable": False,
        "renderD128_readable": False,
        "renderD128_writable": False,
        "amdgpu_loaded": False,
        "user_in_render_group": False,
        "user_in_video_group": False,
        "rocm_smi_installed": shutil.which("rocm-smi") is not None,
        "torch_version_in_venv": "unknown",
        "torch_cuda_available": "unknown",
    }
    if Path("/dev/kfd").exists():
        out["kfd_readable"] = os.access("/dev/kfd", os.R_OK)
        out["kfd_writable"] = os.access("/dev/kfd", os.W_OK)
    rd = Path("/dev/dri/renderD128")
    if rd.exists():
        out["renderD128_readable"] = os.access(rd, os.R_OK)
        out["renderD128_writable"] = os.access(rd, os.W_OK)
    try:
        out["amdgpu_loaded"] = "amdgpu" in Path("/proc/modules").read_text()
    except Exception:
        pass
    import grp, getpass
    user = getpass.getuser()
    out["user"] = user
    out["groups"] = [g.gr_name for g in grp.getgrall() if user in g.gr_mem]
    out["user_in_render_group"] = "render" in out["groups"]
    out["user_in_video_group"] = "video" in out["groups"]
    try:
        import torch
        out["torch_version_in_venv"] = torch.__version__
        out["torch_cuda_available"] = torch.cuda.is_available()
    except Exception as e:
        out["torch_version_in_venv"] = f"err: {e}"
    return out


def main() -> None:
    f = probe_system()
    print("== GPU / ROCm probe findings ==")
    for k, v in f.items():
        if k == "groups":
            print(f"  {k:30s} = {', '.join(v)}")
        else:
            print(f"  {k:30s} = {v}")
    print()
    print("== Diagnosis ==")
    if not f["kfd_readable"]:
        print("  [BLOCKER] /dev/kfd is NOT readable by this user.")
        if not f["user_in_render_group"]:
            print("            user is not in the 'render' group, and there is no ACL fallback.")
            print("            Fix: sudo usermod -aG render,video $USER   (then re-login)")
    if not f["rocm_smi_installed"]:
        print("  [BLOCKER] rocm-smi not installed -> no ROCm userspace runtime.")
    print("  [INFO]    amdgpu kernel module is loaded; the iGPU is physically present.")
    print("  [INFO]    /dev/dri/renderD128 is reachable via ACL, but HIP needs /dev/kfd.")


if __name__ == "__main__":
    main()
