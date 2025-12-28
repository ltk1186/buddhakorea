# Feature Documentation

> Generated Documentation | Last Updated: 2025-12-26

## Overview

This document provides detailed technical documentation for each feature in the Buddha Korea frontend.

---

## Table of Contents

1. [Digital Sutra Copying (전자 사경)](#digital-sutra-copying)
2. [Ephemeral Sentences (찰나의 문장)](#ephemeral-sentences)
3. [Meditation Timer](#meditation-timer)
4. [Interactive Teaching Diagrams](#interactive-teaching-diagrams)
5. [Interactive Mouse Light](#interactive-mouse-light)
6. [Scroll Reveal Animations](#scroll-reveal-animations)
7. [Authentication System](#authentication-system)

---

## Digital Sutra Copying

### Feature Summary

| Aspect | Details |
|--------|---------|
| **Page** | `sutra-writing.html` |
| **JavaScript** | `sutra.js`, `sutra-data.js` |
| **CSS** | `sutra.css` |
| **Data** | `data/sutras.json` |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  SUTRA COPYING SYSTEM                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐         ┌────────────────────────────┐ │
│  │  sutras.json    │────────▶│      sutra-data.js         │ │
│  │  (Source Data)  │         │  • loadSutraData()         │ │
│  │  - 12 sutras    │         │  • getSutraById()          │ │
│  │  - Categories   │         │  • getSutrasByCategory()   │ │
│  │  - Animations   │         │  • getAnimationClass()     │ │
│  └─────────────────┘         └──────────────┬─────────────┘ │
│                                             │               │
│                                             ▼               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                     sutra.js                          │  │
│  │  ┌──────────────────────────────────────────────────┐│  │
│  │  │  State                                           ││  │
│  │  │  • sutraText (NFC normalized)                    ││  │
│  │  │  • userTyped                                     ││  │
│  │  │  • bgSpans[] (cached DOM)                        ││  │
│  │  │  • currentMode ('traditional' | 'easy')          ││  │
│  │  │  • typedIndices (Set) - Easy mode                ││  │
│  │  │  • skippedIndices (Set) - Easy mode              ││  │
│  │  └──────────────────────────────────────────────────┘│  │
│  │                                                       │  │
│  │  ┌──────────────────────────────────────────────────┐│  │
│  │  │  Core Functions                                  ││  │
│  │  │  • selectSutra(id)                               ││  │
│  │  │  • switchMode(mode)                              ││  │
│  │  │  • checkInput() - Traditional mode               ││  │
│  │  │  • checkInputEasy() - Easy mode                  ││  │
│  │  │  • handleCharacterClick(index)                   ││  │
│  │  │  • completeToNextLine()                          ││  │
│  │  │  • checkCompletion()                             ││  │
│  │  │  • dedicate(realm)                               ││  │
│  │  └──────────────────────────────────────────────────┘│  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Data Model

```json
{
  "categories": {
    "sutra": { "label": "문헌", "order": 1 },
    "mantra": { "label": "진언", "order": 2 },
    "name": { "label": "명호", "order": 3 },
    "verse": { "label": "게송", "order": 4 }
  },
  "categoryAnimations": {
    "sutra": "char-fade",
    "mantra": "char-radiate",
    "name": "char-pureland",
    "verse": "char-fade"
  },
  "sutras": {
    "metta": {
      "id": "metta",
      "category": "sutra",
      "title": "자애경",
      "subtitle": "慈愛經",
      "description": "자비와 사랑의 가르침",
      "text": "전체 경문 텍스트...",
      "estimatedTime": "15-20분",
      "order": 1
    },
    "om-mani": {
      "id": "om-mani",
      "category": "mantra",
      "title": "옴마니반메훔",
      "pattern": "옴마니반메훔",
      "repeat": 108,
      "estimatedTime": "10-15분"
    }
  }
}
```

### Typing Validation Algorithm

```javascript
function checkInput() {
    const typed = input.value.normalize('NFC');

    // Find first divergence point
    let correctLength = 0;
    for (let i = 0; i < typed.length && i < sutraText.length; i++) {
        if (typed[i] === sutraText[i]) {
            correctLength++;
        } else {
            break;  // Stop at first wrong character
        }
    }

    // Truncate to correct portion only
    const correct = typed.slice(0, correctLength);

    if (correct !== typed) {
        // Restore cursor position after truncation
        input.value = correct;
        input.setSelectionRange(correct.length, correct.length);
    }

    userTyped = correct;
    scheduleVisualUpdate();
    checkCompletion();
}
```

### Korean IME Handling

```javascript
// Track composition state
input.addEventListener('compositionstart', () => {
    input.isComposing = true;
});

input.addEventListener('compositionend', () => {
    input.isComposing = false;
    // Defer validation to next tick
    setTimeout(() => checkInput(), 0);
});

input.addEventListener('input', () => {
    // Only validate when not composing
    if (!input.isComposing) {
        checkInput();
    }
});
```

### Dedication Animation System

```javascript
function dedicate(realm) {
    const text = getTypedText();

    // 1. Create character container
    const charContainer = document.createElement('div');
    charContainer.id = 'char-container';

    // 2. Wrap each character with styling
    text.split('').forEach((char, index) => {
        const span = document.createElement('span');
        span.textContent = char;

        // Easy mode: different colors for typed vs skipped
        const isSkipped = skippedIndices.has(index);
        span.style.color = isSkipped ? '#6BB6FF' : '#daa520';

        charContainer.appendChild(span);
    });

    // 3. Get category-specific animation class
    const animClass = getAnimationClass(currentSutra.category);
    // 'char-fade' | 'char-radiate' | 'char-pureland'

    // 4. Staggered animation (last to first)
    const charSpans = charContainer.querySelectorAll('span');
    const totalDuration = 5000;
    const delayPerChar = totalDuration / charSpans.length;

    charSpans.forEach((span, i) => {
        const reverseIndex = charSpans.length - 1 - i;

        // For radiate animation, set random direction
        if (animClass === 'char-radiate') {
            const angle = Math.random() * Math.PI * 2;
            span.style.setProperty('--radiate-x', `${Math.cos(angle) * 20}px`);
            span.style.setProperty('--radiate-y', `${Math.sin(angle) * 20}px`);
        }

        setTimeout(() => {
            span.classList.add(animClass);
        }, reverseIndex * delayPerChar);
    });

    // 5. Cleanup after animation
    setTimeout(() => {
        charContainer.remove();
        showScreen('screen-dedication-complete');
    }, totalDuration + 1200);
}
```

### Easy Mode Features

**Click to Jump**:
```javascript
function handleCharacterClick(index) {
    // Auto-complete all chars before clicked position
    for (let i = 0; i < index; i++) {
        if (!typedIndices.has(i) && !skippedIndices.has(i)) {
            skippedIndices.add(i);
        }
    }

    // Update visual display
    updateVisualsEasy();

    // Focus input at new position
    textInputEasy.focus({ preventScroll: true });
    setCursorPosition(textInputEasy, index);
}
```

**Double-Space Line Completion**:
```javascript
textInputEasy.addEventListener('keydown', (e) => {
    if (e.key === ' ') {
        const now = Date.now();
        if (now - lastSpaceTime < 300) {
            e.preventDefault();
            completeToNextLine();
        }
        lastSpaceTime = now;
    }
});

function completeToNextLine() {
    const currentPos = userTyped.length;

    // Find next line break
    let nextLinePos = sutraText.indexOf('\n', currentPos);
    if (nextLinePos === -1) {
        nextLinePos = sutraText.length;
    } else {
        nextLinePos++;  // Include line break
    }

    // Mark all as skipped
    for (let i = currentPos; i < nextLinePos; i++) {
        skippedIndices.add(i);
    }

    updateVisualsEasy();
    checkCompletion();
}
```

---

## Ephemeral Sentences

### Feature Summary

| Aspect | Details |
|--------|---------|
| **Page** | `index.html` (modal) |
| **JavaScript** | `ephemeral.js` |
| **CSS** | `styles.css` |

### Configuration

```javascript
const CONFIG = {
    FADE_DELAY: 3000,          // ms before fade starts
    USE_PARTICLE_EFFECT: false, // Toggle particle vs smoke
    PARTICLE_DISTANCE: 150      // px scatter distance
};
```

### Character Wrapping

```javascript
function wrapNewCharacters() {
    // Walk all text nodes in canvas
    const walker = document.createTreeWalker(
        canvas,
        NodeFilter.SHOW_TEXT
    );

    const textNodes = [];
    while (node = walker.nextNode()) {
        textNodes.push(node);
    }

    textNodes.forEach(textNode => {
        // Skip already-wrapped characters
        if (textNode.parentNode.classList?.contains('char-wrapper')) {
            return;
        }

        const fragment = document.createDocumentFragment();

        // Wrap each character individually
        for (const char of textNode.nodeValue) {
            const span = document.createElement('span');
            span.className = 'char-wrapper';
            span.innerHTML = char === ' ' ? '&nbsp;' : char;
            span.dataset.timestamp = Date.now();
            fragment.appendChild(span);
        }

        textNode.parentNode.replaceChild(fragment, textNode);
    });

    // Restore cursor position...
}
```

### Fade Animation

```javascript
function fadeCharacters() {
    const text = canvas.textContent;

    // Create animation overlay
    const container = document.createElement('div');
    container.style.cssText = `
        position: absolute;
        inset: 0;
        z-index: 100;
    `;

    // Clone text with golden styling
    text.split('').forEach(char => {
        const span = document.createElement('span');
        span.textContent = char;
        span.style.color = '#daa520';
        span.style.textShadow = '0 0 20px rgba(218, 165, 32, 0.4)';
        container.appendChild(span);
    });

    // Hide original canvas
    canvas.style.opacity = '0';

    // Animate last-to-first
    const spans = container.querySelectorAll('span');
    const duration = 5000;
    const delay = duration / spans.length;

    spans.forEach((span, i) => {
        const reverse = spans.length - 1 - i;
        setTimeout(() => {
            span.classList.add('char-fade-ephemeral');
        }, reverse * delay);
    });

    // Cleanup
    setTimeout(() => {
        container.remove();
        canvas.innerHTML = '';
        canvas.style.opacity = '1';
        canvas.focus();
    }, duration + 1200);
}
```

---

## Meditation Timer

### Feature Summary

| Aspect | Details |
|--------|---------|
| **Page** | `meditation.html` |
| **JavaScript** | `meditation.js` |
| **CSS** | `meditation.css` |

### Timer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   MEDITATION TIMER SYSTEM                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  State Variables                                      │   │
│  │  • meditationDuration (seconds)                       │   │
│  │  • startTime (performance.now())                      │   │
│  │  • timerInterval (setInterval ID)                     │   │
│  │  • cachedTimeDisplay (DOM element)                    │   │
│  │  • cachedProgressCircle (SVG element)                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Timer Flow                                           │   │
│  │                                                       │   │
│  │  startMeditation(minutes)                             │   │
│  │       ↓                                               │   │
│  │  beginMeditation()                                    │   │
│  │       ├─ playBell()                                   │   │
│  │       ├─ showScreen('screen-meditation')              │   │
│  │       └─ setInterval(updateTimer, 100/200ms)          │   │
│  │               ↓                                       │   │
│  │  updateTimer() [loop]                                 │   │
│  │       ├─ Calculate remaining time                     │   │
│  │       ├─ Update time display (RAF batched)            │   │
│  │       ├─ Update progress circle (stroke-dashoffset)   │   │
│  │       └─ if (remaining <= 0) → completeMeditation()   │   │
│  │               ↓                                       │   │
│  │  completeMeditation()                                 │   │
│  │       ├─ playBell()                                   │   │
│  │       └─ showScreen('screen-complete')                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Performance Optimizations

```javascript
// Adaptive update interval
const isMobile = /Android|iPhone|iPad/.test(navigator.userAgent);
const updateInterval = isMobile ? 200 : 100;

// DOM caching
let cachedTimeDisplay = null;
let cachedProgressCircle = null;

function updateTimer() {
    // Cache on first call
    if (!cachedTimeDisplay) {
        cachedTimeDisplay = document.getElementById('time-remaining');
        cachedProgressCircle = document.querySelector('.progress-ring-circle');
    }

    // Calculate once
    const elapsed = (performance.now() - startTime) / 1000;
    const remaining = Math.max(0, meditationDuration - elapsed);
    const progress = remaining / meditationDuration;

    // Batch DOM writes in RAF
    requestAnimationFrame(() => {
        cachedTimeDisplay.textContent = formatTime(remaining);
        cachedProgressCircle.style.strokeDashoffset =
            circumference * (1 - progress);
    });
}
```

### Buddha Contemplation

```javascript
function beginBuddhaContemplation() {
    playBell();
    showBuddhaScreen('screen-buddha-meditation');

    setTimeout(() => {
        const buddhaImage = document.getElementById('buddha-stack');

        // Set dynamic animation duration via CSS variable
        buddhaImage.style.setProperty(
            '--animation-duration',
            `${buddhaDuration}s`
        );

        // Apply to all layers
        buddhaImage.querySelectorAll('.buddha-layer').forEach(layer => {
            layer.style.animationDuration = `${buddhaDuration}s`;
        });

        // Trigger dissolution
        buddhaImage.classList.add('dissolving');

        // Start timer
        startTimer();
    }, 300);
}
```

### Web Audio Bell

```javascript
function playBell() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || webkitAudioContext)();
    }

    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);

    // 432Hz singing bowl frequency
    oscillator.frequency.setValueAtTime(432, audioContext.currentTime);
    oscillator.type = 'sine';

    // 2-second fade out
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(
        0.01,
        audioContext.currentTime + 2
    );

    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 2);
}
```

---

## Interactive Teaching Diagrams

### Feature Summary

| Aspect | Details |
|--------|---------|
| **Page** | `teaching.html` |
| **JavaScript** | `teaching.js` |
| **CSS** | `teaching.css` |
| **Data** | `data/teachings.json` |

### SVG Interaction

```javascript
// Click handlers for diagram elements
document.querySelectorAll('.truth-card').forEach(card => {
    card.addEventListener('click', () => {
        showTruthExplanation(card.dataset.truth);
    });

    // Keyboard accessibility
    card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            showTruthExplanation(card.dataset.truth);
        }
    });
});

function showTruthExplanation(truthId) {
    const truth = teachingData.fourNobleTruths[truthId];

    // Show explanation panel
    const panel = document.getElementById('explanation-panel');
    panel.querySelector('.title').textContent = truth.title;
    panel.querySelector('.content').innerHTML = truth.explanation;
    panel.classList.add('active');

    // Focus management
    panel.focus();
}
```

---

## Interactive Mouse Light

### Feature Summary

| Aspect | Details |
|--------|---------|
| **Pages** | All pages |
| **JavaScript** | `main.js`, `meditation.js` |
| **CSS** | `styles.css` |

### Implementation

```javascript
const mouseLight = document.querySelector('.interactive-light');

if (mouseLight && !isMobile) {
    let mouseX = 0, mouseY = 0;
    let currentX = 0, currentY = 0;
    let rafId = null;

    // Passive listener for performance
    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;

        if (!rafId) {
            rafId = requestAnimationFrame(updateLight);
        }
    }, { passive: true });

    function updateLight() {
        // Smooth interpolation (easing)
        currentX += (mouseX - currentX) * 0.15;
        currentY += (mouseY - currentY) * 0.15;

        // GPU-accelerated transform
        mouseLight.style.transform =
            `translate3d(${currentX - 300}px, ${currentY - 300}px, 0)`;

        // Continue animating if not at target
        if (Math.abs(mouseX - currentX) > 0.5 ||
            Math.abs(mouseY - currentY) > 0.5) {
            rafId = requestAnimationFrame(updateLight);
        } else {
            rafId = null;
        }
    }
}
```

### CSS

```css
.interactive-light {
    position: fixed;
    top: 0;
    left: 0;
    width: 600px;
    height: 600px;
    background: radial-gradient(circle,
        rgba(140, 184, 156, 0.30) 0%,
        rgba(90, 154, 110, 0.12) 50%,
        transparent 70%
    );
    border-radius: 50%;
    pointer-events: none;
    filter: blur(80px);
    z-index: 1;
}
```

---

## Scroll Reveal Animations

### Feature Summary

| Aspect | Details |
|--------|---------|
| **JavaScript** | `main.js` |
| **CSS** | `styles.css` |

### Implementation

```javascript
function initScrollReveal() {
    const revealElements = document.querySelectorAll('.reveal');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);  // One-time
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    revealElements.forEach(el => observer.observe(el));
}
```

### CSS

```css
.reveal {
    opacity: 0;
    transform: translateY(24px);
    transition: opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1),
                transform 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

.reveal.is-visible {
    opacity: 1;
    transform: translateY(0);
}
```

### Usage

```html
<div class="section-header reveal">
    <h2>Section Title</h2>
</div>

<div class="card-grid reveal" style="transition-delay: 100ms;">
    <!-- Cards -->
</div>
```

---

## Authentication System

### Feature Summary

| Aspect | Details |
|--------|---------|
| **Backend** | `ai.buddhakorea.com` (Hetzner) |
| **Providers** | Google, Naver, Kakao |
| **Storage** | HTTP-only cookies |

### Auth Flow

```javascript
const API_BASE_URL = 'https://ai.buddhakorea.com';

async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/users/me`, {
            credentials: 'include'  // Send cookies
        });

        const authContainer = document.getElementById('auth-container');

        if (response.ok) {
            const user = await response.json();
            // Show logged-in state
            authContainer.innerHTML = `
                <a href="mypage.html">${user.nickname}님</a>
                <a href="#" onclick="logout()">로그아웃</a>
            `;
        } else {
            // Show login button
            authContainer.innerHTML = `
                <a href="#" onclick="showLoginModal()">로그인</a>
            `;
        }
    } catch (e) {
        console.error("Auth check failed", e);
    }
}

async function logout() {
    await fetch(`${API_BASE_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
    });
    window.location.reload();
}
```

### Login Modal

```javascript
function showLoginModal() {
    document.getElementById('loginModal').classList.add('active');
}

function closeLoginModal() {
    document.getElementById('loginModal').classList.remove('active');
}
```

### OAuth URLs

| Provider | Login URL |
|----------|-----------|
| Google | `/auth/login/google` |
| Naver | `/auth/login/naver` |
| Kakao | `/auth/login/kakao` |

---

## Performance Metrics

### Target Performance

| Metric | Target |
|--------|--------|
| Animations | 60fps |
| Input lag | <50ms |
| Time to Interactive | <3s |
| First Contentful Paint | <1.5s |

### Optimization Techniques

1. **DOM Caching**: Pre-cache frequently accessed elements
2. **RAF Batching**: Group DOM writes in requestAnimationFrame
3. **Passive Listeners**: `{ passive: true }` for scroll/touch
4. **GPU Acceleration**: Use `transform` and `opacity` for animations
5. **Adaptive Intervals**: Slower updates on mobile devices
6. **Smooth Interpolation**: Easing for mouse following effects

---

*This document was auto-generated from codebase analysis.*
