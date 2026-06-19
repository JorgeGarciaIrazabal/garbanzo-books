"""Studio runtime configuration — environment knobs and the chat-model roster.

Kept separate from server.py so the OpenCode client and the chat-streaming module can
import these without pulling in the FastAPI app (which would be a circular import).
"""
from __future__ import annotations

import os

PORT = int(os.environ.get("PORT", "4317"))
PY_CMD = os.environ.get("PY_CMD", "uv run python").split()
OPENCODE_BIN = os.environ.get("OPENCODE_BIN", "opencode")
OPENCODE_MODEL = os.environ.get("OPENCODE_MODEL", "ollama/nemotron-3-ultra:cloud")

# Models the studio offers in its model picker. Each must also be registered under the matching
# provider in opencode.json. Four tiers, each tuned to a different job:
#   - Nemotron-3-Ultra  : fast + reliable, the default for building/validation
#   - GLM-5.2           : strong creative writer, the default for STORY / WORLD / CHARACTER work
#   - DeepSeek-V4-Pro   : slower but more creative (alt story model)
#   - MiniMax-M3        : best for information gathering (web search, summarising, looking things up)
# The "auto" sentinel lets the studio pick the right model per stage (see STAGE_TO_MODEL).
MODELS = [
    {"id": "ollama/nemotron-3-ultra:cloud",
     "label": "Nemotron-3-Ultra — fast & reliable (default for build/validate)"},
    {"id": "ollama/glm-5.2:cloud",
     "label": "GLM-5.2 — creative writer (best for stories, worlds & characters)"},
    {"id": "ollama/deepseek-v4-pro:cloud",
     "label": "DeepSeek-V4-Pro — more creative (alt story model)"},
    {"id": "ollama/minimax-m3:cloud",
     "label": "MiniMax-M3 — best for research & information gathering"},
    {"id": "auto",
     "label": "Auto (switch by stage) — recommended"},
]
ALLOWED_MODELS = {m["id"] for m in MODELS}

# Stage tag → model. The agent emits [[stage:<name>]] (see STUDIO_BRIEF) at the end of its message
# to tell the studio what kind of step it just finished. In Auto mode, the NEXT turn uses the model
# mapped below. (OpenCode's HTTP API binds a model at prompt time, so we can't switch mid-turn —
# the next user reply is the natural place to swap.) The creative stages (story/world/character)
# route to GLM-5.2; the tool-heavy "build"/"validate"/"done" stages share the fast default;
# "research" routes to MiniMax.
STAGE_TO_MODEL = {
    "craft":     "ollama/glm-5.2:cloud",
    "world":     "ollama/glm-5.2:cloud",
    "character": "ollama/glm-5.2:cloud",
    "build":     "ollama/nemotron-3-ultra:cloud",
    "validate":  "ollama/nemotron-3-ultra:cloud",
    "done":      "ollama/nemotron-3-ultra:cloud",
    "story":     "ollama/glm-5.2:cloud",
    "research":  "ollama/minimax-m3:cloud",
}
