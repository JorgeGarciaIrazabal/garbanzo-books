"""The OpenCode subprocess lifecycle — spawn, wait-for-ready, and kill it cleanly.

The studio chat is OpenCode driving a LOCAL Ollama model (no API key). We manage an
`opencode serve` child on a random port and talk to its HTTP API elsewhere (see chat.py).
The single shared `oc` holds the live process/base-URL/port; start/stop manage it, and the
PR_SET_PDEATHSIG + atexit belts guarantee the child never outlives us.
"""
from __future__ import annotations

import asyncio
import atexit
import ctypes
import ctypes.util
import os
import random
import signal
import subprocess
from pathlib import Path

import httpx

from config import OPENCODE_BIN

ROOT = Path(__file__).resolve().parent.parent  # repo root = the workspace OpenCode operates in


class OpenCode:
    proc: subprocess.Popen | None = None
    base: str | None = None
    port: int | None = None


oc = OpenCode()


def _child_preexec():
    """Run in the OpenCode child after fork, before exec:
    - os.setsid(): give it its own session/group so we can kill the whole group.
    - PR_SET_PDEATHSIG=SIGKILL: the kernel kills it the moment THIS python process dies, for
      ANY reason (SIGKILL, crash, terminal close) — the real guarantee against orphans."""
    os.setsid()
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
        libc.prctl(1, signal.SIGKILL)  # PR_SET_PDEATHSIG = 1
    except Exception:
        pass  # non-Linux: fall back to the explicit kills in stop_opencode()


async def start_opencode() -> None:
    """Spawn `opencode serve` on a random port, in the repo root so it reads ./opencode.json
    (provider, model, instructions, permissions). The child dies with us (see _child_preexec)."""
    port = random.randint(40000, 60000)
    proc = subprocess.Popen(
        [OPENCODE_BIN, "serve", "--hostname", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        preexec_fn=_child_preexec,
    )
    base = f"http://127.0.0.1:{port}"
    # 240 retries × 0.25s = ~60s. The default opencode cold start is <2s, but on the first
    # ever launch the local model may need to be loaded by Ollama, which can take much longer
    # — the longer window makes a one-time cold start finish cleanly instead of erroring out.
    max_retries = 240
    async with httpx.AsyncClient() as client:
        for i in range(max_retries):
            if proc.poll() is not None:
                raise RuntimeError(f"opencode serve exited early (code {proc.returncode})")
            try:
                await client.get(base + "/config", timeout=2.0)
                oc.proc, oc.base, oc.port = proc, base, port
                print(f"  opencode server: {base} (pid {proc.pid})", flush=True)
                return
            except Exception:
                if i > 0 and i % 40 == 0:  # progress ping every ~10s
                    print(f"  …waiting for opencode serve ({i*0.25:.0f}s)", flush=True)
                await asyncio.sleep(0.25)
    proc.kill()
    raise RuntimeError(
        f"opencode serve did not become ready in {max_retries*0.25:.0f}s "
        f"(is 'opencode' installed and reachable on PATH?)"
    )


def stop_opencode() -> None:
    if oc.proc is not None:
        try:
            os.killpg(os.getpgid(oc.proc.pid), signal.SIGKILL)  # whole session group
        except Exception:
            try:
                oc.proc.kill()
            except Exception:
                pass
    if oc.port is not None:  # belt: opencode may daemonize its real server into a new session
        try:
            subprocess.run(
                ["pkill", "-9", "-f", f"opencode serve --hostname 127.0.0.1 --port {oc.port}"],
                check=False,
            )
        except Exception:
            pass
    oc.proc = oc.base = oc.port = None


atexit.register(stop_opencode)  # belt for normal interpreter exit (PDEATHSIG covers hard kills)
