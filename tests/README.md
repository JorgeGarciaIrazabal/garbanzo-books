# Tests

A meaningful test suite covering the real business logic of the Garbanzo Books
Studio — both the Python toolchain and the vanilla-JS front-ends. These
exercise actual invariants, not library plumbing or configuration.

## Layout

```
tests/
├── conftest.py                    # pytest fixtures: isolated worlds dir, data factories
├── backend/                       # pytest — every Python module under test
│   ├── test_model.py              # scripts/lib/model.py
│   ├── test_readability.py        # scripts/lib/readability.py
│   ├── test_prompt_assembly.py    # scripts/lib/prompt_assembly.py
│   ├── test_validate.py           # scripts/validate.py (QA gate)
│   ├── test_build_site.py         # scripts/build_site.py (static site)
│   ├── test_library.py            # scripts/library.py (JSON exporter)
│   ├── test_scaffolders.py        # new_world / new_character / new_story
│   ├── test_reading_level.py      # scripts/reading_level.py
│   ├── test_generate_images.py    # scripts/generate_images.py
│   └── test_server.py             # ui/server.py (FastAPI studio)
├── frontend/                      # vitest + jsdom — the browser code
│   ├── package.json
│   ├── vitest.config.js
│   ├── harness.js                 # loads app.js's pure helpers into a test ns
│   ├── setup.js                   # vitest setup (DOM stubs, fetch, etc.)
│   ├── app.helpers.test.js        # pure helpers in ui/public/app.js
│   └── reader.test.js             # interactive reader runtime (IIFE)
└── fixtures/                      # (reserved) shared per-test sample data
```

## Running

```bash
make test-backend    # 287 tests — pytest, no API key, no network
make test-frontend   # 78 tests — vitest + jsdom, no API key, no network
make test-all        # both
```

The suite is offline-friendly by design — it never calls the Gemini API, never
spawns an OpenCode process, and never makes a network request. The image-gen
tests run through the `placeholder` provider, which writes labeled SVG files
instead of real images.

## Conventions

* **Isolated workspaces.** Every backend test gets its own throwaway `worlds/`
  tree under `tmp_path`. The `conftest.py` workspace fixture monkey-patches
  the module-level `ROOT` / `WORLDS` constants in every script that captures
  them at import time, so no test can leak files into another test's view or
  into the real workspace.

* **Data factories over hard-coded YAML.** `tests/conftest.py` exposes
  `factories.world()`, `factories.character()`, `factories.story()` — each
  returns a **schema-valid** dict that the test can mutate. Mutations are
  isolated by `copy.deepcopy`, so tests can target one invariant at a time
  without the surrounding fields sinking the test.

* **Assert the contract, not the implementation.** Tests describe the
  business rule in the test name ("FK grade cap doesn't apply to read-aloud
  bands") and exercise it through the public API. We don't test that a
  private helper does `len(x) + 1`; we test that the user's workflow produces
  the right outcome.

* **Frontend tests evaluate real source.** `tests/frontend/harness.js` reads
  the actual `ui/public/app.js` and re-evaluates it in a Function closure
  with the side-effecting bottom block stripped — so we're testing the same
  code the browser runs, not a hand-rolled copy.
