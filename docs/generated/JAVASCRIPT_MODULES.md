# JavaScript Modules Reference

> Generated Documentation | Last Updated: 2025-12-26

## Overview

Buddha Korea uses vanilla ES6 JavaScript with module imports. All feature modules are loaded with `type="module"` in HTML files.

---

## Module Index

| Module | Purpose | Dependencies |
|--------|---------|--------------|
| `main.js` | Interactive light effect, scroll animations | None |
| `sutra-data.js` | Sutra data loader from JSON | `data/sutras.json` |
| `sutra.js` | Typing validation, dedication animations | `sutra-data.js` |
| `meditation.js` | Timer logic, Buddha contemplation | None |
| `teaching.js` | Interactive SVG diagram handlers | `data/teachings.json` |
| `ephemeral.js` | Ephemeral sentences (impermanence demo) | None |
| `feedback.js` | Feedback modal handling | None |
| `library.js` | Literature library interactions | None |

---

## main.js

**Path**: `frontend/js/main.js`
**Size**: ~48 lines
**Used by**: `index.html`

### Purpose
Provides global site interactivity including the mouse-following light effect and scroll-reveal animations.

### Functions

#### `initInteractiveLight()`
Creates a glowing light effect that follows the mouse cursor.

```javascript
function initInteractiveLight() {
    const light = document.querySelector('.interactive-light');
    if (!light) return;

    window.addEventListener('mousemove', (e) => {
        const x = e.clientX - light.offsetWidth / 2;
        const y = e.clientY - light.offsetHeight / 2;
        light.style.transform = `translate(${x}px, ${y}px)`;
    });
}
```

**Requires DOM element**: `.interactive-light`

#### `initScrollReveal()`
Uses Intersection Observer to animate elements as they scroll into view.

```javascript
function initScrollReveal() {
    const revealElements = document.querySelectorAll('.reveal');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    revealElements.forEach(element => observer.observe(element));
}
```

**CSS class added**: `.is-visible` (triggers CSS transition)

#### `init()`
Main initialization function called on DOMContentLoaded.

```javascript
function init() {
    initInteractiveLight();
    initScrollReveal();
}
```

---

## sutra-data.js

**Path**: `frontend/js/sutra-data.js`
**Size**: ~99 lines
**Used by**: `sutra.js`, `sutra-writing.html` (inline module)

### Purpose
Loads and processes sutra data from JSON. Handles pattern-based text generation for mantras/names.

### Exports

| Export | Type | Description |
|--------|------|-------------|
| `SUTRA_DATA` | Object | All sutras keyed by ID |
| `CATEGORIES` | Object | Category metadata |
| `CATEGORY_ANIMATIONS` | Object | Category → animation class mapping |
| `dataLoadedPromise` | Promise | Resolves when data is loaded |
| `getSutraById(id)` | Function | Get single sutra by ID |
| `getSutrasByCategory(cat)` | Function | Get sutras filtered by category |
| `getCategoryLabel(cat)` | Function | Get human-readable category name |
| `getAnimationClass(cat)` | Function | Get CSS animation class for category |

### Key Functions

#### `loadSutraData()`
Fetches and processes `data/sutras.json`.

```javascript
async function loadSutraData() {
    const response = await fetch('data/sutras.json');
    const data = await response.json();

    // Store categories and animations
    CATEGORIES = data.categories;
    CATEGORY_ANIMATIONS = data.categoryAnimations;

    // Process sutras
    for (const [key, sutra] of Object.entries(data.sutras)) {
        SUTRA_DATA[key] = { ...sutra };

        // Generate text for pattern-based sutras (mantras, names)
        if (sutra.pattern && sutra.repeat) {
            SUTRA_DATA[key].text = generateRepeatedText(
                sutra.pattern,
                sutra.repeat
            );
        }
    }
}
```

#### `generateRepeatedText(pattern, count)`
Creates repeated mantra/name text.

```javascript
function generateRepeatedText(pattern, count) {
    return Array(count).fill(pattern).join(' ');
}
```

**Example**: `"나무아미타불"` with count `108` generates 108 repetitions.

#### `getSutrasByCategory(category)`
Returns sorted array of sutras for a category.

```javascript
export function getSutrasByCategory(category) {
    if (category === 'all') {
        return Object.values(SUTRA_DATA).sort((a, b) => a.order - b.order);
    }
    return Object.values(SUTRA_DATA)
        .filter(s => s.category === category)
        .sort((a, b) => a.order - b.order);
}
```

#### `getAnimationClass(category)`
Maps category to CSS animation class.

```javascript
export function getAnimationClass(category) {
    return CATEGORY_ANIMATIONS[category] || 'char-fade';
}
```

| Category | Animation Class |
|----------|----------------|
| sutra | `char-fade` |
| mantra | `char-radiate` |
| name | `char-pureland` |
| verse | `char-fade` |

### Usage Example

```javascript
import {
    getSutraById,
    getSutrasByCategory,
    dataLoadedPromise
} from './sutra-data.js';

// Wait for data to load
await dataLoadedPromise;

// Get a specific sutra
const mettaSutta = getSutraById('metta');
console.log(mettaSutta.title); // "자애경"

// Get all mantras
const mantras = getSutrasByCategory('mantra');
```

---

## sutra.js

**Path**: `frontend/js/sutra.js`
**Size**: ~886 lines
**Used by**: `sutra-writing.html`

### Purpose
Handles the digital sutra copying (전자 사경) feature including typing validation, two input modes, and dedication animations.

### State Variables

| Variable | Type | Description |
|----------|------|-------------|
| `sutraText` | String | NFC-normalized source text |
| `userTyped` | String | User's correctly typed text |
| `bgSpans` | Array | Cached DOM span references |
| `currentSutraId` | String | Currently selected sutra ID |
| `currentMode` | String | `'traditional'` or `'easy'` |
| `typedIndices` | Set | User-typed character positions (Easy mode) |
| `skippedIndices` | Set | Auto-completed positions (Easy mode) |
| `rafId` | Number | RequestAnimationFrame ID |

### Key Functions

#### `selectSutra(id)`
Loads a sutra and sets up the typing interface.

```javascript
function selectSutra(id) {
    currentSutraId = id;
    const sutra = SUTRAS[id];
    sutraText = sutra.text.normalize('NFC');
    userTyped = '';

    // Generate background spans
    const textBg = document.getElementById('text-bg');
    textBg.innerHTML = '';
    for (let i = 0; i < sutraText.length; i++) {
        const span = document.createElement('span');
        span.textContent = sutraText[i];
        span.dataset.index = i;
        textBg.appendChild(span);
    }

    // Cache spans and add click handlers
    bgSpans = Array.from(textBg.children);
    // ... event listener setup

    showScreen('screen-write');
}
```

**Exposed as**: `window.selectSutra`

#### `checkInput()` (Traditional Mode)
Validates typing character-by-character, truncating on mismatch.

```javascript
function checkInput() {
    const input = document.getElementById('text-input');
    const typed = input.value.normalize('NFC');

    if (typed === userTyped) return;

    // Find divergence point
    let correctLength = 0;
    for (let i = 0; i < typed.length && i < sutraText.length; i++) {
        if (typed[i] === sutraText[i]) {
            correctLength++;
        } else {
            break; // Stop at first mismatch
        }
    }

    const correct = typed.slice(0, correctLength);

    // Truncate wrong input
    if (correct !== typed) {
        input.value = correct;
        input.setSelectionRange(correct.length, correct.length);
    }

    userTyped = correct;
    scheduleVisualUpdate();
    checkCompletion();
}
```

#### `checkInputEasy()` (Easy Mode)
Allows clicking to jump positions and double-space to complete lines.

```javascript
function checkInputEasy() {
    const input = document.getElementById('text-input-easy');
    const typed = input.textContent.normalize('NFC');

    // Handle deletion
    if (typed.length < userTyped.length) {
        // Remove from typedIndices and skippedIndices
        // ...
    }

    // Validate new characters
    const newChars = typed.slice(userTyped.length);
    for (let i = 0; i < newChars.length; i++) {
        const pos = userTyped.length + i;
        if (newChars[i] === sutraText[pos]) {
            typedIndices.add(pos);
            skippedIndices.delete(pos);
        } else {
            break; // Stop at mismatch
        }
    }
}
```

#### `handleCharacterClick(index)` (Easy Mode)
Auto-completes all characters before clicked position.

```javascript
function handleCharacterClick(index) {
    // Auto-complete characters up to clicked index
    for (let i = 0; i < index; i++) {
        if (!typedIndices.has(i) && !skippedIndices.has(i)) {
            skippedIndices.add(i);
        }
    }

    updateVisualsEasy();
    // Update contenteditable text...
}
```

#### `completeToNextLine()` (Easy Mode)
Triggered by double-space, completes to next line break.

```javascript
function completeToNextLine() {
    const currentPos = userTyped.length;
    let nextLinePos = sutraText.indexOf('\n', currentPos);

    if (nextLinePos === -1) {
        nextLinePos = sutraText.length; // Complete to end
    } else {
        nextLinePos++; // Include line break
    }

    // Mark as skipped
    for (let i = currentPos; i < nextLinePos; i++) {
        if (!typedIndices.has(i)) {
            skippedIndices.add(i);
        }
    }
}
```

#### `dedicate(realm)`
Triggers the dedication animation on completion.

```javascript
function dedicate(realm) {
    const text = currentMode === 'traditional'
        ? textInput.value
        : textInputEasy.textContent;

    // Create character container
    const charContainer = document.createElement('div');
    charContainer.id = 'char-container';

    // Wrap each character in span with golden styling
    text.split('').forEach((char, index) => {
        const span = document.createElement('span');
        span.textContent = char;

        // In Easy Mode, skipped chars shown in blue
        const isSkipped = currentMode === 'easy' && skippedIndices.has(index);
        span.style.color = isSkipped ? '#6BB6FF' : '#daa520';
        charContainer.appendChild(span);
    });

    // Get animation class for category
    const animationClass = getAnimationClass(currentSutra?.category);

    // Staggered animation (last to first)
    charSpans.forEach((span, i) => {
        const reverseIndex = charSpans.length - 1 - i;
        setTimeout(() => {
            span.classList.add(animationClass);
        }, reverseIndex * delayPerChar);
    });
}
```

**Exposed as**: `window.dedicate`

#### `switchMode(mode)`
Toggles between Traditional and Easy modes.

```javascript
function switchMode(mode) {
    currentMode = mode; // 'traditional' or 'easy'

    // Update button states
    modeButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    // Show/hide inputs
    textInput.style.display = mode === 'traditional' ? 'block' : 'none';
    textInputEasy.style.display = mode === 'easy' ? 'block' : 'none';

    // Enable click handlers for Easy mode
    if (mode === 'easy') {
        bgSpans.forEach(span => {
            span.style.pointerEvents = 'auto';
            span.style.cursor = 'pointer';
        });
    }

    resetTypingState();
}
```

### Korean IME Handling

```javascript
// Track composition state
textInput.addEventListener('compositionstart', () => {
    textInput.isComposing = true;
});

textInput.addEventListener('compositionend', () => {
    textInput.isComposing = false;
    setTimeout(() => checkInput(), 0); // Defer to next tick
});

textInput.addEventListener('input', () => {
    if (!textInput.isComposing) {
        checkInput();
    }
});
```

### Global Exports

```javascript
window.selectSutra = selectSutra;
window.goBack = goBack;
window.dedicate = dedicate;
```

---

## meditation.js

**Path**: `frontend/js/meditation.js`
**Size**: ~719 lines
**Used by**: `meditation.html`

### Purpose
Manages meditation timers including breathing meditation and Buddha contemplation with image dissolution effect.

### State Variables

| Variable | Type | Description |
|----------|------|-------------|
| `meditationDuration` | Number | Total time in seconds |
| `startTime` | Number | `performance.now()` at start |
| `timerInterval` | Number | setInterval ID |
| `cachedTimeDisplay` | Element | Cached DOM reference |
| `cachedProgressCircle` | Element | Cached SVG circle |
| `buddhaDuration` | Number | Buddha contemplation duration |
| `cachedBuddhaImage` | Element | Buddha stack element |

### Constants

```javascript
const circumference = 2 * Math.PI * 140; // SVG circle circumference
const isMobile = /Android|iPhone|iPad/.test(navigator.userAgent);
const updateInterval = isMobile ? 200 : 100; // Adaptive refresh rate
```

### Key Functions

#### `startMeditation(minutes)`
Initiates a breathing meditation session.

```javascript
function startMeditation(minutes) {
    meditationDuration = minutes * 60;
    beginMeditation();
}
```

#### `beginMeditation()`
Transitions to meditation screen and starts timer.

```javascript
function beginMeditation() {
    playBell(); // Start sound
    showScreen('screen-meditation');

    setTimeout(() => {
        startTime = performance.now();
        updateTimer();
        timerInterval = setInterval(updateTimer, updateInterval);
    }, 300);
}
```

#### `updateTimer()`
High-performance timer update with DOM caching.

```javascript
function updateTimer() {
    const elapsed = (performance.now() - startTime) / 1000;
    const remaining = Math.max(0, meditationDuration - elapsed);

    // Cache DOM references on first call
    if (!cachedTimeDisplay) {
        cachedTimeDisplay = document.getElementById('time-remaining');
        cachedProgressCircle = document.querySelector('.progress-ring-circle');
    }

    const minutes = Math.floor(remaining / 60);
    const seconds = Math.floor(remaining % 60);
    const progress = remaining / meditationDuration;
    const offset = circumference * (1 - progress);

    // Batch DOM updates in RAF
    requestAnimationFrame(() => {
        cachedTimeDisplay.textContent =
            `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        cachedProgressCircle.style.strokeDashoffset = offset;
    });

    if (remaining <= 0) {
        clearInterval(timerInterval);
        completeMeditation();
    }
}
```

#### `beginBuddhaContemplation()`
Starts Buddha contemplation with dissolution animation.

```javascript
function beginBuddhaContemplation() {
    playBell();
    showBuddhaScreen('screen-buddha-meditation');

    setTimeout(() => {
        cachedBuddhaImage = document.getElementById('buddha-stack');

        // Set dynamic animation duration
        cachedBuddhaImage.style.setProperty(
            '--animation-duration',
            `${buddhaDuration}s`
        );

        // Set duration on all layers
        const layers = cachedBuddhaImage.querySelectorAll('.buddha-layer');
        layers.forEach(layer => {
            layer.style.animationDuration = `${buddhaDuration}s`;
        });

        cachedBuddhaImage.classList.add('dissolving');

        // Start timer
        buddhaStartTime = performance.now();
        updateBuddhaTimer();
        buddhaTimerInterval = setInterval(updateBuddhaTimer, updateInterval);
    }, 300);
}
```

#### `playBell()`
Generates meditation bell sound using Web Audio API.

```javascript
function playBell() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }

    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);

    oscillator.frequency.setValueAtTime(432, audioContext.currentTime); // 432Hz
    oscillator.type = 'sine';

    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 2);

    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 2);
}
```

#### `switchTab(tabName)`
Handles tab navigation between meditation types.

```javascript
function switchTab(tabName) {
    // Hide all panels
    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.remove('active');
    });

    // Deactivate all buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        btn.setAttribute('aria-selected', 'false');
    });

    // Show selected panel
    document.getElementById(`tab-${tabName}`).classList.add('active');

    // Activate selected button
    const selectedBtn = document.getElementById(`tab-btn-${tabName}`);
    selectedBtn.classList.add('active');
    selectedBtn.setAttribute('aria-selected', 'true');

    currentTab = tabName;
}
```

### Mouse Light Effect (Performance Optimized)

```javascript
if (mouseLight && !isMobile) {
    let mouseX = 0, mouseY = 0;
    let currentX = 0, currentY = 0;
    let rafId = null;

    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;
        if (!rafId) {
            rafId = requestAnimationFrame(updateMouseLight);
        }
    }, { passive: true });

    function updateMouseLight() {
        // Smooth interpolation
        currentX += (mouseX - currentX) * 0.15;
        currentY += (mouseY - currentY) * 0.15;

        // GPU-accelerated transform
        mouseLight.style.transform =
            `translate3d(${currentX - 300}px, ${currentY - 300}px, 0)`;

        // Continue if not at target
        if (Math.abs(mouseX - currentX) > 0.5 ||
            Math.abs(mouseY - currentY) > 0.5) {
            rafId = requestAnimationFrame(updateMouseLight);
        } else {
            rafId = null;
        }
    }
}
```

---

## ephemeral.js

**Path**: `frontend/js/ephemeral.js`
**Size**: ~333 lines
**Used by**: `index.html` (via onclick)

### Purpose
Implements "Ephemeral Sentences" (찰나의 문장) - typed text gradually fades to demonstrate impermanence (무상/anicca).

### Configuration

```javascript
const CONFIG = {
    FADE_DELAY: 3000,          // ms before fade begins
    USE_PARTICLE_EFFECT: false, // true: particles, false: golden smoke
    PARTICLE_DISTANCE: 150,     // px scatter distance
};
```

### State Variables

| Variable | Type | Description |
|----------|------|-------------|
| `typingTimer` | Number | setTimeout ID for fade trigger |
| `canvas` | Element | Contenteditable div reference |
| `isComposing` | Boolean | Korean IME composition flag |

### Key Functions

#### `openEphemeralSentences()`
Opens the ephemeral sentences modal.

```javascript
function openEphemeralSentences() {
    const modal = document.getElementById('ephemeral-modal');
    modal.classList.add('active');

    setTimeout(() => {
        canvas = document.getElementById('ephemeral-canvas');
        canvas.focus();
        setupEventListeners();
    }, 100);

    document.addEventListener('keydown', handleEscapeKey);
}
```

#### `handleInput()`
Processes text input with fade timer.

```javascript
function handleInput() {
    if (isComposing) return; // Skip during Korean composition

    clearTimeout(typingTimer);
    wrapNewCharacters();

    typingTimer = setTimeout(() => {
        fadeCharacters();
    }, CONFIG.FADE_DELAY);
}
```

#### `wrapNewCharacters()`
Wraps each character in a span for individual animation.

```javascript
function wrapNewCharacters() {
    const selection = window.getSelection();
    const range = selection.rangeCount > 0 ? selection.getRangeAt(0) : null;

    // Walk text nodes
    const walker = document.createTreeWalker(
        canvas,
        NodeFilter.SHOW_TEXT
    );

    const textNodes = [];
    let node;
    while (node = walker.nextNode()) {
        textNodes.push(node);
    }

    textNodes.forEach(textNode => {
        const parent = textNode.parentNode;
        if (parent.classList?.contains('char-wrapper')) return;

        const fragment = document.createDocumentFragment();
        const text = textNode.nodeValue;

        for (let i = 0; i < text.length; i++) {
            const span = document.createElement('span');
            span.className = 'char-wrapper';
            span.innerHTML = text[i] === ' ' ? '&nbsp;' : text[i];
            span.dataset.timestamp = Date.now();
            fragment.appendChild(span);
        }

        parent.replaceChild(fragment, textNode);
    });

    // Restore cursor position...
}
```

#### `fadeCharacters()`
Creates overlay and animates character-by-character fade.

```javascript
function fadeCharacters() {
    const text = canvas.textContent || canvas.innerText;
    if (!text?.trim()) return;

    // Create animation container matching canvas styles
    const charContainer = document.createElement('div');
    charContainer.id = 'ephemeral-char-container';
    charContainer.style.cssText = `
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        pointer-events: none;
        z-index: 100;
    `;

    // Wrap each character with golden styling
    text.split('').forEach(char => {
        const span = document.createElement('span');
        span.textContent = char;
        span.style.cssText = `
            color: #daa520;
            text-shadow: 0 0 20px rgba(218, 165, 32, 0.4);
        `;
        charContainer.appendChild(span);
    });

    document.querySelector('.ephemeral-input-wrapper')
        .appendChild(charContainer);

    // Hide original canvas
    canvas.style.opacity = '0';

    // Staggered animation (last to first)
    const charSpans = charContainer.querySelectorAll('span');
    const totalDuration = 5000;
    const delayPerChar = totalDuration / charSpans.length;

    charSpans.forEach((span, i) => {
        const reverseIndex = charSpans.length - 1 - i;
        setTimeout(() => {
            span.classList.add('char-fade-ephemeral');
        }, reverseIndex * delayPerChar);
    });

    // Cleanup after animation
    setTimeout(() => {
        charContainer.remove();
        canvas.innerHTML = '';
        canvas.style.opacity = '1';
        canvas.focus();
    }, totalDuration + 1200);
}
```

#### `applyParticleEffect(char)` (Optional)
Applies particle scatter effect instead of fade.

```javascript
function applyParticleEffect(char) {
    const angle = Math.random() * Math.PI * 2;
    const distance = CONFIG.PARTICLE_DISTANCE;
    const tx = Math.cos(angle) * distance;
    const ty = Math.sin(angle) * distance;

    char.style.setProperty('--tx', `${tx}px`);
    char.style.setProperty('--ty', `${ty}px`);
    char.classList.add('particle-break');
}
```

---

## teaching.js

**Path**: `frontend/js/teaching.js`
**Used by**: `teaching.html`

### Purpose
Handles interactive SVG diagrams for Four Noble Truths (사성제) and Noble Eightfold Path (팔정도).

### Key Functions

#### Click Handlers for SVG Elements

```javascript
document.querySelectorAll('.truth-card').forEach(card => {
    card.addEventListener('click', () => {
        const truthId = card.dataset.truth;
        showTruthExplanation(truthId);
    });

    // Keyboard accessibility
    card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            showTruthExplanation(card.dataset.truth);
        }
    });
});
```

#### Data Loading

```javascript
async function loadTeachingData() {
    const response = await fetch('data/teachings.json');
    const data = await response.json();
    return data;
}
```

---

## feedback.js

**Path**: `frontend/js/feedback.js`
**Used by**: All pages (feedback FAB)

### Purpose
Handles the feedback modal that redirects to Google Forms.

### Key Functions

#### `openFeedbackModal()`
Opens the feedback modal overlay.

```javascript
function openFeedbackModal() {
    const modal = document.getElementById('feedback-modal');
    modal.classList.add('active');
}
```

#### `closeFeedbackModal()`
Closes the feedback modal.

```javascript
function closeFeedbackModal() {
    const modal = document.getElementById('feedback-modal');
    modal.classList.remove('active');
}
```

---

## Common Patterns

### Awaiting Data Load

```javascript
import { dataLoadedPromise } from './sutra-data.js';

document.addEventListener('DOMContentLoaded', async () => {
    await dataLoadedPromise;
    // Now safe to use SUTRA_DATA
});
```

### Screen Transitions

```javascript
function showScreen(id) {
    const currentScreen = document.querySelector('.screen.show');

    if (currentScreen) {
        currentScreen.classList.add('screen-exit');

        setTimeout(() => {
            currentScreen.classList.remove('show', 'screen-exit');

            const newScreen = document.getElementById(id);
            newScreen.classList.add('show', 'screen-enter');

            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    newScreen.classList.remove('screen-enter');
                });
            });
        }, 300);
    } else {
        document.getElementById(id).classList.add('show');
    }
}
```

### Exposing Functions to Global Scope

For HTML `onclick` handlers:

```javascript
// At end of module
window.selectSutra = selectSutra;
window.goBack = goBack;
window.dedicate = dedicate;
```

---

*This document was auto-generated from codebase analysis.*
