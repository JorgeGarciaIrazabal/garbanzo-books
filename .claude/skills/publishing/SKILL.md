---
name: publishing
description: Build the static website from worlds/stories and publish it to GitHub Pages, organised as world -> story -> tags, with an interactive reader that plays the puzzles/games. Use when building a preview, generating the site, or deploying to GitHub Pages. Runs scripts/build_site.py and uses the .github/workflows Pages deploy.
---

# Publishing to GitHub Pages

Turns validated content into a browsable, interactive site organised **world → story → tags**.
Read `CLAUDE.md` (conventions) first.

## Procedure
1. **Validate first.** `uv run python scripts/validate.py` must pass for any story you publish; only
   then set its `status: published` (the builder includes drafts only with `--include-drafts`).
2. **Build the site**: `uv run python scripts/build_site.py` →
   - Home page: grid of **worlds**.
   - `world/<slug>/`: world overview, style/palette, character gallery, and its **stories**.
   - `story/<world>/<slug>/`: the interactive **reader** (full-page images + embedded text +
     playable interactions), with prev/next page-turn navigation.
   - `tags/<tag>/`: every story carrying that tag (the third browse axis).
   - Copies page images into `site/`, emits a `search-index.json`, sitemap, and the reader
     runtime (`assets/reader.js` + `assets/styles.css`).
3. **Preview locally**: `uv run python -m http.server -d site 8008` and click through a book as a
   "dummy" before deploying.
4. **Deploy** — two supported paths:
   - **GitHub Actions (recommended):** push to `main`; `.github/workflows/deploy-pages.yml`
     builds `site/` and deploys to Pages. Enable Pages → "GitHub Actions" once in repo
     settings.
   - **Manual:** publish the `site/` folder to a `gh-pages` branch (`scripts/build_site.py
     --deploy` documents the git commands).

## URL structure (world → story → tags)
```
/                              worlds index
/world/<world>/               world hub + character gallery + story list
/story/<world>/<story>/       the interactive reader
/tags/<tag>/                  stories by tag
```

## Quality bar before deploy
- [ ] `validate.py` green for all included stories.
- [ ] Reader: page-turns work, every interaction is playable & winnable, images load.
- [ ] Accessibility: alt text present, contrast ok, dyslexia-font toggle works.
- [ ] Each story reachable from its world and from each of its tags.

## Output
A complete `site/` tree + (optionally) a live GitHub Pages deployment.
