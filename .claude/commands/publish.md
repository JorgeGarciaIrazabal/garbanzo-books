---
description: Build the static site (world → story → tags) and publish to GitHub Pages.
argument-hint: [--include-drafts] [--deploy]
---

Use the **publishing** skill to build and publish the site: **$ARGUMENTS**

Steps:
1. **Validate first** — `uv run python scripts/validate.py` must pass for every story being
   published; ensure each has `status: published` (or pass `--include-drafts` for a preview).
2. **Build** — `uv run python scripts/build_site.py $ARGUMENTS` to generate `site/` with the worlds
   index, world hubs + character galleries, the interactive reader per story, and `tags/`
   pages. Images, reader runtime, search index, and sitemap are emitted.
3. **Preview** — `uv run python -m http.server -d site 8008`; click through a book end-to-end and
   test the interactions and page-turns.
4. **Deploy** — push to `main` to trigger `.github/workflows/deploy-pages.yml` (enable Pages →
   "GitHub Actions" once), or use the manual `gh-pages` path documented by
   `scripts/build_site.py --deploy`.

Report the built URLs (/, /world/<w>/, /story/<w>/<s>/, /tags/<t>/) and any QA issues found
during preview.
