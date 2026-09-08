"""Studio runtime configuration — environment knobs and the chat-model roster.

Kept separate from server.py so the OpenCode client and the chat-streaming module can
import these without pulling in the FastAPI app (which would be a circular import).
"""
from __future__ import annotations

import os

PORT = int(os.environ.get("PORT", "4317"))
PY_CMD = os.environ.get("PY_CMD", "uv run python").split()
OPENCODE_BIN = os.environ.get("OPENCODE_BIN", "opencode")
OPENCODE_MODEL = os.environ.get("OPENCODE_MODEL", "ollama/glm-5.3-flash:cloud")

# Models the studio offers in its model picker. Each must also be registered under the matching
# provider in opencode.json. Four tiers, each tuned to a different job:
#   - GLM-5.3-Flash      : natively multimodal, top agentic/tool scores, 9x cheaper — the
#                         DEFAULT for orchestration, tool-heavy craft, games & QC
#   - GLM-5.3            : #2 on creative-writing benchmarks, best prose — STORY / WORLD /
#                         CHARACTER writing (the words-first gates)
#   - DeepSeek-V4-Pro    : thinking mode, keeps constraints across long agentic loops —
#                         the correctness gate for validate/QA passes
#   - DeepSeek-V4-Flash  : 60+ tok/s summarisation — research (web search, digesting pages)
# The "auto" sentinel lets the studio pick the right model per stage (see STAGE_TO_MODEL).
MODELS = [
    {"id": "ollama/glm-5.3-flash:cloud",
     "label": "GLM-5.3-Flash — fast multimodal (default for orchestration, games & QC)"},
    {"id": "ollama/glm-5.3:cloud",
     "label": "GLM-5.3 — creative writer (best for stories, worlds & characters)"},
    {"id": "ollama/deepseek-v4-pro:cloud",
     "label": "DeepSeek-V4-Pro — deep reasoning (validate / QA)"},
    {"id": "ollama/deepseek-v4-flash:cloud",
     "label": "DeepSeek-V4-Flash — fast research & summarising"},
    {"id": "auto",
     "label": "Auto (switch by stage) — recommended"},
]
ALLOWED_MODELS = {m["id"] for m in MODELS}

# Stage tag → model. The agent emits [[stage:<name>]] (see STUDIO_BRIEF) at the end of its message
# to tell the studio what kind of step it just finished. In Auto mode, the NEXT turn uses the model
# mapped below. (OpenCode's HTTP API binds a model at prompt time, so we can't switch mid-turn —
# the next user reply is the natural place to swap.) The creative stages (story/world/character)
# route to GLM-5.3 (the best prose writer); the tool-heavy "craft"/"build" stages and the
# default orchestration share the fast multimodal GLM-5.3-Flash; "validate" routes to
# DeepSeek-V4-Pro (thinking mode, correctness-critical); "research" routes to DeepSeek-V4-Flash.
STAGE_TO_MODEL = {
    "craft":     "ollama/glm-5.3-flash:cloud",
    "world":     "ollama/glm-5.3:cloud",
    "character": "ollama/glm-5.3:cloud",
    "build":     "ollama/glm-5.3-flash:cloud",
    "validate":  "ollama/deepseek-v4-pro:cloud",
    "done":      "ollama/glm-5.3-flash:cloud",
    "story":     "ollama/glm-5.3:cloud",
    "research":  "ollama/deepseek-v4-flash:cloud",
}
