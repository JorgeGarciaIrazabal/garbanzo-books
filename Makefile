.PHONY: setup validate report build serve clean test test-backend test-frontend test-all lint format type-check coverage quality ci ui opencode help check-gemini

# OpenCode + local Ollama settings. The model/provider are defined in opencode.json;
# override here if you point Ollama elsewhere.
OLLAMA_HOST ?= http://localhost:11434
OPENCODE_MODEL ?= ollama/minimax-m3:cloud

# Port for the studio UI (ui/server.py also reads $PORT)
UI_PORT ?= 4317

# Environment is managed by uv (https://docs.astral.sh/uv). `uv run` ensures the .venv exists
# and is in sync with pyproject.toml/uv.lock before running. Override RUN to use a plain
# interpreter instead, e.g.  make validate RUN=python3
RUN ?= uv run python

help:
	@echo "Garbanzo Books — storybook studio"
	@echo "  make setup         create .venv from pyproject.toml via uv (uv sync)"
	@echo "  make validate      QA all worlds/stories (pass/fail gate)"
	@echo "  make report        grade all books against the 7-gate quality checklist"
	@echo "  make build         build the static site into site/"
	@echo "  make serve         build + preview at http://localhost:8008"
	@echo "  make test          run the toolchain self-test"
	@echo "  make check-gemini  verify GEMINI_API_KEY is set (image generation)"
	@echo "  make test-backend  run the full pytest suite (lib + scripts + server)"
	@echo "  make test-frontend run the vitest suite (app.js + reader.js)"
	@echo "  make test-all      run backend + frontend (one command)"
	@echo "  make lint          ruff check the Python tooling"
	@echo "  make format        ruff format the Python tooling"
	@echo "  make type-check    mypy type-check the Python tooling"
	@echo "  make coverage      backend tests with a coverage report"
	@echo "  make ci            everything CI runs: lint + type-check + tests + validate"
	@echo "  make ui            run the dynamic UI (FastAPI + OpenCode + local Ollama, no API key)"
	@echo "  make opencode      start OpenCode with local Ollama ($(OPENCODE_MODEL))"
	@echo "  make clean         remove site/ build output"

setup:
	uv sync

validate:
	$(RUN) scripts/validate.py

report:
	$(RUN) scripts/quality_report.py

build:
	$(RUN) scripts/build_site.py

serve: build
	$(RUN) -m http.server -d site 8008

check-gemini:
	@# Quick check for the image-gen key. The studio/server load it the same way
	@# (env first, then .env) so this is the authoritative pre-flight for /illustrate.
	@if [ -n "$$GEMINI_API_KEY" ] || [ -n "$$GOOGLE_API_KEY" ]; then \
		[ -n "$$GEMINI_API_KEY" ] && src="GEMINI_API_KEY (env, length=$${#GEMINI_API_KEY})" \
			|| src="GOOGLE_API_KEY (env, length=$${#GOOGLE_API_KEY})"; \
		printf "  \033[32m✓\033[0m image key present: %s\n" "$$src"; \
		printf "    /illustrate will render real images (provider: nano-banana).\n"; \
	else \
		if [ -f .env ] && grep -qE '^(GEMINI_API_KEY|GOOGLE_API_KEY)=.+\S' .env; then \
			val=$$(grep -E '^(GEMINI_API_KEY|GOOGLE_API_KEY)=' .env | head -1 | cut -d= -f2-); \
			printf "  \033[32m✓\033[0m image key present: .env (length=%d)\n" "$${#val}"; \
			printf "    /illustrate will render real images (provider: nano-banana).\n"; \
		else \
			printf "  \033[31m✗\033[0m no image key found.\n"; \
			printf "    Image generation will fall back to labeled placeholders.\n"; \
			printf "    To render real images:\n"; \
			printf "      1. Get a free key at https://aistudio.google.com/apikey\n"; \
			printf "      2. Add to .env:   GEMINI_API_KEY=your-key\n"; \
			printf "      3. Run \`make ui\` again so the server reloads .env\n"; \
			exit 1; \
		fi; \
	fi

test:
	$(RUN) scripts/selftest.py

test-backend:
	$(RUN) -m pytest tests/backend/ -q

test-frontend:
	cd tests/frontend && npm install --no-fund --no-audit --silent && npx vitest run

test-all:
	$(MAKE) test-backend
	$(MAKE) test-frontend

lint:
	uv run ruff check scripts

format:
	uv run ruff format scripts

type-check:
	uv run mypy

coverage:
	$(RUN) -m pytest tests/backend/ --cov --cov-report=term-missing

# The full local gate — mirrors .github/workflows/deploy-pages.yml so you can catch
# everything before pushing.
quality: lint type-check test-backend validate

ci: quality

ui:
	# The studio UI is a Python FastAPI server (ui/server.py). It shells out to the Python
	# tools for library/validate/build and embeds `opencode serve` for the chat box. Override
	# PORT to change the port (default 4317). Open http://localhost:$${PORT:-4317} when ready.
	# We invoke `uv run --group ui --group tts` directly so the FastAPI/uvicorn/httpx deps AND
	# the local read-aloud stack (Kokoro TTS + faster-whisper STT) are pulled in (the default
	# `RUN` doesn't pass either group).
	@pids="$$(lsof -ti tcp:$(UI_PORT) 2>/dev/null)"; \
	if [ -n "$$pids" ]; then \
		echo "Port $(UI_PORT) is in use by PID(s): $$pids — killing"; \
		kill $$pids 2>/dev/null || true; \
		sleep 1; \
		pids="$$(lsof -ti tcp:$(UI_PORT) 2>/dev/null)"; \
		if [ -n "$$pids" ]; then \
			echo "Still alive — sending SIGKILL"; \
			kill -9 $$pids 2>/dev/null || true; \
			sleep 1; \
		fi; \
	fi
	PORT=$(UI_PORT) uv run --group ui --group tts python ui/server.py

# Launch OpenCode against the local Ollama server. opencode.json already pins the
# provider + model ($(OPENCODE_MODEL)); we just sanity-check Ollama is up first.
opencode:
	@command -v opencode >/dev/null 2>&1 || { echo "opencode not found — install it: https://opencode.ai (npm i -g opencode-ai)"; exit 1; }
	@curl -sf $(OLLAMA_HOST)/api/tags >/dev/null 2>&1 || { echo "Ollama not reachable at $(OLLAMA_HOST) — start it with 'ollama serve'"; exit 1; }
	OLLAMA_HOST=$(OLLAMA_HOST) opencode --model $(OPENCODE_MODEL)

clean:
	rm -rf site
