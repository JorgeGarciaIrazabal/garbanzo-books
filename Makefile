.PHONY: setup validate build serve clean test lint ui opencode help

# OpenCode + local Ollama settings. The model/provider are defined in opencode.json;
# override here if you point Ollama elsewhere.
OLLAMA_HOST ?= http://localhost:11434
OPENCODE_MODEL ?= ollama/minimax-m3:cloud

# Environment is managed by uv (https://docs.astral.sh/uv). `uv run` ensures the .venv exists
# and is in sync with pyproject.toml/uv.lock before running. Override RUN to use a plain
# interpreter instead, e.g.  make validate RUN=python3
RUN ?= uv run python

help:
	@echo "Garbanzo Books — storybook studio"
	@echo "  make setup      create .venv from pyproject.toml via uv (uv sync)"
	@echo "  make validate   QA all worlds/stories"
	@echo "  make build      build the static site into site/"
	@echo "  make serve      build + preview at http://localhost:8008"
	@echo "  make test       run the toolchain self-test"
	@echo "  make lint       ruff check the Python tooling"
	@echo "  make ui         run the dynamic UI (FastAPI + OpenCode + local Ollama, no API key)"
	@echo "  make opencode   start OpenCode with local Ollama ($(OPENCODE_MODEL))"
	@echo "  make clean      remove site/ build output"

setup:
	uv sync

validate:
	$(RUN) scripts/validate.py

build:
	$(RUN) scripts/build_site.py

serve: build
	$(RUN) -m http.server -d site 8008

test:
	$(RUN) scripts/selftest.py

lint:
	uv run ruff check scripts

ui:
	cd ui && npm install && npm start

# Launch OpenCode against the local Ollama server. opencode.json already pins the
# provider + model ($(OPENCODE_MODEL)); we just sanity-check Ollama is up first.
opencode:
	@command -v opencode >/dev/null 2>&1 || { echo "opencode not found — install it: https://opencode.ai (npm i -g opencode-ai)"; exit 1; }
	@curl -sf $(OLLAMA_HOST)/api/tags >/dev/null 2>&1 || { echo "Ollama not reachable at $(OLLAMA_HOST) — start it with 'ollama serve'"; exit 1; }
	OLLAMA_HOST=$(OLLAMA_HOST) opencode --model $(OPENCODE_MODEL)

clean:
	rm -rf site
