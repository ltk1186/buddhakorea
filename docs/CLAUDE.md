# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Buddha Korea (붓다코리아) is a static website for exploring Buddhist teachings through interactive experiences and AI chatbots. The site offers spiritual practice tools grounded in early Buddhism (초기불교), Abhidhamma (아비담마), and Visuddhimagga (청정도론) teachings.

**Core Philosophy**: Each feature is designed to embody Buddhist principles - impermanence (무상), suffering (고), and non-self (무아) - through user experience rather than just explaining them intellectually.

## Site Architecture

### Five Main Pages

1. **index.html** - Landing page with NotebookLM AI chatbot links and "Ephemeral Sentences" modal
2. **sutra-writing.html** - Digital sutra copying (전자 사경) with character-by-character typing validation
3. **meditation.html** - Meditation timers with tabbed interface (breathing, Buddha contemplation, mandala)
4. **teaching.html** - Interactive SVG diagrams of Four Noble Truths (사성제) and Noble Eightfold Path (팔정도)
5. **test-*.html** - Development test pages (not production)

### Data-Driven Architecture

**Critical**: Sutra content and teaching data are loaded from JSON files, NOT hardcoded in JavaScript.

- **data/sutras.json** - Contains all sutra text, categories, descriptions, and animation mappings
- **data/teachings.json** - Contains Four Noble Truths and Eightfold Path explanations

**Module Pattern**:
- `js/sutra-data.js` - Loads and exports sutra data with helper functions
- `js/sutra.js` - Imports from sutra-data.js and handles typing/dedication logic
- `js/teaching.js` - Loads teachings.json and manages interactive diagrams

**Always await `dataLoadedPromise`** before accessing SUTRA_DATA or teaching content.

### JavaScript Module System

The site uses ES6 modules (`type="module"` in HTML):

```javascript
// In HTML
<script type="module" src="js/sutra.js"></script>

// In JS
import { SUTRA_DATA, getSutraById, dataLoadedPromise } from './sutra-data.js';
await dataLoadedPromise; // Required before using data
```

**Global Functions**: Some functions must be exposed to `window` for HTML `onclick` handlers:
```javascript
window.selectSutra = selectSutra;
window.goBack = goBack;
window.dedicate = dedicate;
```

## Key Technical Patterns

### 1. Character-by-Character Typing Validation (sutra-writing.html)

Users must type the exact text character-by-character. Incorrect input is **immediately truncated**:

```javascript
function checkInput() {
    const typed = input.value;

    // Find divergence point
    let correctLength = 0;
    for (let i = 0; i < typed.length && i < sutraText.length; i++) {
        if (typed[i] === sutraText[i]) correctLength++;
        else break;
    }

    // Truncate wrong characters
    const correct = typed.slice(0, correctLength);
    if (correct !== typed) {
        input.value = correct;
        input.setSelectionRange(correct.length, correct.length);
    }
}
```

**Korean IME Handling**: Must track `compositionstart/compositionend` events and only validate when `!input.isComposing`.

### 2. Category-Specific Dedication Animations

Different sutra categories have different animation effects on completion (회향):

- **sutra** (문헌): `char-fade` - Characters fade upward like smoke
- **mantra** (진언): `char-radiate` - Characters radiate outward with random vectors
- **name** (명호): `char-pureland` - Characters ascend to Pure Land
- **verse** (게송): `char-fade` - Default fade

Animation class is retrieved via `getAnimationClass(category)` from sutra-data.js.

### 3. Buddha Contemplation Dissolution Effect

The Buddha image dissolves gradually over the meditation duration using CSS animations with **dynamic duration**:

```javascript
// Set animation duration based on user-selected time
cachedBuddhaImage.style.setProperty('--animation-duration', `${buddhaDuration}s`);
const layers = cachedBuddhaImage.querySelectorAll('.buddha-layer');
layers.forEach(layer => {
    layer.style.animationDuration = `${buddhaDuration}s`;
});
cachedBuddhaImage.classList.add('dissolving');
```

The `.dissolving` class triggers a CSS keyframe animation that takes the full meditation duration to complete.

### 4. Performance Optimizations

**Mouse Light Effect**: GPU-accelerated smooth interpolation using RAF
```javascript
// Smooth interpolation instead of direct positioning
currentX += (mouseX - currentX) * 0.15;
currentY += (mouseY - currentY) * 0.15;
mouseLight.style.transform = `translate3d(${currentX - 300}px, ${currentY - 300}px, 0)`;
```

**Timer Updates**: Adaptive update intervals (200ms mobile, 100ms desktop)

**DOM Caching**: Pre-cache frequently accessed DOM elements:
```javascript
let cachedTimeDisplay = null;
let cachedProgressCircle = null;
// Cache on first access, reuse thereafter
```

**Visual Updates**: Use `requestAnimationFrame` to batch DOM writes:
```javascript
requestAnimationFrame(() => {
    cachedTimeDisplay.textContent = `${minutes}:${seconds}`;
    cachedProgressCircle.style.strokeDashoffset = offset;
});
```

### 5. Interactive SVG Diagrams (teaching.html)

Four Noble Truths and Eightfold Path are rendered as **inline SVG** in HTML. JavaScript adds interactivity:

- Click/touch handlers on `<g class="truth-card">` elements
- Explanation panels slide up with content from teachings.json
- Keyboard navigation with Enter/Space keys
- ARIA attributes for accessibility

## Development Workflow

This is a **pure static site** with no build process:

1. Edit HTML/CSS/JS directly
2. Use a local server (e.g., `python -m http.server 8000`) to avoid CORS issues with ES6 modules
3. Test in browser (refresh to see changes)
4. For production, serve files as-is (no compilation needed)

**Common CORS Error**: If you see "CORS policy blocked", you're opening HTML files directly (`file://`). Use a local server instead.

## Adding Content

### Adding a New Sutra

1. Edit `data/sutras.json` and add entry with:
   - `id`, `category`, `title`, `subtitle`, `description`
   - `text` (full text) OR `pattern` + `repeat` (for mantras/names)
   - `estimatedTime`, `order`

2. No JavaScript changes needed - sutra-data.js automatically processes it

3. Sutra cards are dynamically rendered by inline script in sutra-writing.html

### Adding a New Teaching

1. Edit `data/teachings.json` in the appropriate section
2. Update teaching.html SVG if adding new diagram elements
3. teaching.js will automatically load and display the content

### Customizing Animations

**Ephemeral Sentences** (찰나의 문장):
- `js/ephemeral.js` has a `CONFIG` object with timing and effects
- `CONFIG.FADE_DELAY` - milliseconds before character fades (default 1500ms)
- `CONFIG.USE_PARTICLE_EFFECT` - toggle particle vs fade animation

**Dedication Animations**:
- Defined in `css/sutra.css` as `@keyframes`
- Mapped in `data/sutras.json` under `categoryAnimations`
- Duration is dynamically calculated: 5 seconds / character count

## Important Constraints

### Korean Language & UTF-8

- All Korean text must be saved with UTF-8 encoding
- HTML files declare `<meta charset="UTF-8">`
- Korean IME composition events require special handling (see sutra.js)

### External Dependencies

- **NotebookLM**: AI chatbots are hosted by Google (requires Google account)
- **Pretendard Font**: Loaded from CDN (https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9)
- **No analytics or tracking** - pure client-side experience

### Performance Targets

- 60fps animations (especially mouse light effect)
- Input lag <50ms (critical for typing validation)
- Mobile-friendly (adaptive update intervals, touch events)

## Color System

All gradient colors are defined as CSS custom properties in `css/styles.css`:

```css
:root {
    --gradient-color-1: #a794e0; /* Purple - 아비담마 */
    --gradient-color-2: #89b8ff; /* Blue - 청정도론 */
    --gradient-color-3: #9bebb4; /* Green - 초기불교 */
    --golden: #daa520;           /* Dedication text */
}
```

These colors are inspired by the favicon and represent the three AI chatbots.

## Testing & Debugging

### Enable Performance Monitoring

In `js/meditation.js`, set `PERFORMANCE_MONITORING = true` to log timer update performance.

### Console Logging

Most files include strategic `console.log()` statements:
- Data loading success/failure
- User interactions (clicks, touches)
- Animation triggers
- State transitions

### Common Issues

**Issue**: Sutras not appearing in selection screen
- **Check**: Browser console for JSON loading errors
- **Fix**: Ensure `data/sutras.json` is valid JSON and server is running

**Issue**: Korean typing behaves strangely
- **Check**: IME composition events are being tracked
- **Fix**: Verify `isComposing` flag is preventing premature validation

**Issue**: Dedication animation doesn't match category
- **Check**: `data/sutras.json` has correct `category` field
- **Fix**: Ensure category maps to valid animation in `categoryAnimations`

## Accessibility Features

- **Skip links**: Jump to main content (hidden until focused)
- **ARIA labels**: All interactive elements have descriptive labels
- **Keyboard navigation**: Tab, Enter, Space, Escape keys work throughout
- **Focus management**: Modals and panels move focus appropriately
- **Semantic HTML**: `<nav>`, `<section>`, `role` attributes used correctly

## Browser Compatibility

Target: Modern browsers (Chrome, Firefox, Safari, Edge) with ES6 module support.

**Not supported**: IE11 (no ES6 modules, no CSS custom properties)

**Mobile**: Fully responsive with mobile-specific optimizations
- Touch events with `{ passive: true }` for scroll performance
- Reduced animation complexity on mobile devices
- Larger touch targets for buttons and cards
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
