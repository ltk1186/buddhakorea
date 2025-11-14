# Repository Guidelines

## Project Structure & Module Organization
This static GitHub Pages site keeps every HTML file (`index.html`, `meditation.html`, `teaching.html`, etc.) as an entry point with its own stylesheet under `css/` and feature script under `js/`, so scope related assets together. Store imagery and downloadable files in `assets/`, and place structured content in `data/` with stable keys so `sutra-data.js` and `teaching.js` can parse updates without code changes. Update the Google Forms SOP inside `feedback/` whenever URLs or instructions shift, and keep `CNAME` to retain the public domain.

## Build, Test, and Development Commands
- `python3 -m http.server 8080` — serve the repo root locally and preview pages at `http://localhost:8080`.
- `npx htmlhint "**/*.html"` — lint structural issues before committing or deploying.
- `npx prettier --check "index.html" "css/*.css" "js/*.js"` — confirm formatting remains consistent; add `--write` only when intentionally reformatting.

## Coding Style & Naming Conventions
Match the 4-space indentation in HTML and keep comments direct. CSS classes stay kebab-case (`.header-nav`, `.experience-card`); group page-specific rules in their dedicated file such as `css/meditation.css` or `css/teaching.css`. JavaScript should remain dependency-free ES6 loaded per page, so favor camelCase identifiers, avoid polluting `window`, and reference assets with relative paths that work inside the GitHub Pages environment.

## Testing Guidelines
No automated harness exists, so rely on quick repeatable checks. Validate JSON fixtures with `npx jsonlint data/*.json` before committing changes. After starting the local server, exercise interactive flows (feedback modal, ephemeral sentences, meditation timer, sutra search) across desktop and mobile breakpoints, noting any quirks or console warnings in the PR description so reviewers can reproduce them quickly.

## Commit & Pull Request Guidelines
Recent commits (`sutra easy mode added`, `교학 섹션 메이저 수정`) use terse, imperative subjects in English or Korean—mirror that tone, keep them under ~50 characters, and focus on one logical change. Reference related issues (`Fixes #12`), bullet the key UI or content updates, and rebase onto `main` so shared HTML sections stay conflict-free. Pull requests should provide a short summary, screenshots for visual tweaks, manual test notes, and mention any documentation or asset additions.

## Security & Content Integrity
Vet every external AI notebook or Google Forms URL against official sources before merging, and keep secrets or user responses out of the repository. Compress and optimize new imagery inside `assets/`, record attribution in an accompanying README entry, and double-check Buddhist references against verified translations to protect community trust.
