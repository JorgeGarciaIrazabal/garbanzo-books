#!/usr/bin/env bash
# Enable the Strix Halo iGPU (Radeon 8060S, gfx1151) on this machine.
# One-time, requires sudo. ~2 GB download for ROCm userspace.
#
# What this does:
#   1. Adds you to the `render` and `video` groups so /dev/kfd is reachable.
#   2. Installs AMD's amdgpu-install .deb.
#   3. Installs ROCm 6.4 userspace (rocm, hiplibsdk, opencl).
#
# After it finishes you need to re-login (or `newgrp render video`) for
# the group change to take effect in your shell. `rocm-smi` should then
# list the iGPU as gfx1151.

set -euo pipefail

# 1) groups
sudo usermod -aG render,video "$USER"

# 2) download the AMD installer
cd /tmp
wget -q https://repo.radeon.com/amdgpu-install/6.4/ubuntu/noble/amdgpu-install_6.4.60000-1_all.deb

# 3) install the installer
sudo apt install -y ./amdgpu-install_6.4.60000-1_all.deb

# 4) install ROCm 6.4 userspace
sudo amdgpu-install --usecase=rocm,hiplibsdk,opencl --no-dkms -y

# 5) quick verification
echo
echo "==== Verification (run AFTER re-login) ===="
echo "  rocm-smi"
echo "  groups  # should now include 'render' and 'video'"
echo
echo "After re-login (or 'newgrp render video'), your shell can see /dev/kfd"
echo "and you can install a ROCm PyTorch wheel to use the iGPU."
