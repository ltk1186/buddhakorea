# CSS Design System

> Generated Documentation | Last Updated: 2025-12-26

## Overview

Buddha Korea uses a CSS design system built on custom properties (CSS variables) for consistent theming. The system follows an Apple/YC-inspired minimalist aesthetic with a sage green color palette.

## File Structure

| File | Purpose | Size |
|------|---------|------|
| `css/styles.css` | Base styles, design tokens, common components | ~934 lines |
| `css/sutra.css` | Digital sutra copying feature | ~1297 lines |
| `css/meditation.css` | Meditation timer styles | - |
| `css/teaching.css` | Interactive diagram styles | - |
| `css/library.css` | Literature library | - |
| `css/search.css` | Search interface | - |

---

## Design Tokens

### Color Palette

```css
:root {
    /* Sage Green Primary Palette */
    --sage-primary: #5A9A6E;      /* Main accent color */
    --sage-light: #8CB89C;         /* Lighter variant */
    --sage-lighter: #B8D4C2;       /* Even lighter */
    --sage-pale: #E8F0EB;          /* Very pale background */
    --sage-glow: #F4F9F6;          /* Subtle glow color */

    /* Gradient Colors (inspired by favicon) */
    --gradient-color-1: #8CB89C;   /* Light sage */
    --gradient-color-2: #A3C9AE;   /* Medium sage */
    --gradient-color-3: #B8D4C2;   /* Pale sage */

    /* Text Colors */
    --color-text-primary: #1d1d1f;   /* Near black */
    --color-text-secondary: #6e6e73; /* Dark gray */
    --color-text-muted: #86868b;     /* Muted gray */

    /* Backgrounds */
    --color-background: #FFFFFF;
    --color-background-subtle: #F8FAF8;

    /* Surfaces */
    --surface-primary: rgba(255, 255, 255, 0.95);
    --surface-secondary: rgba(248, 250, 248, 0.9);

    /* Borders */
    --border-subtle: rgba(90, 154, 110, 0.12);
    --border-accent: rgba(90, 154, 110, 0.25);
}
```

### Spacing Scale

```css
:root {
    --space-xs: 4px;
    --space-sm: 8px;
    --space-md: 16px;
    --space-lg: 24px;
    --space-xl: 32px;
    --space-2xl: 48px;
    --space-3xl: 64px;
}
```

### Border Radius

```css
:root {
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 20px;
    --radius-xl: 24px;
    --radius-full: 100px;  /* For pill shapes */
}
```

### Transitions

```css
:root {
    --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
    --transition-fast: 0.2s var(--ease-out);
    --transition-normal: 0.4s var(--ease-out);
}
```

### Shadows

```css
:root {
    --shadow-soft: 0 15px 60px rgba(0, 0, 0, 0.08);
    --shadow-sage-subtle: 0 15px 80px rgba(90, 154, 110, 0.12);
    --shadow-sage-hover: 0 15px 100px rgba(90, 154, 110, 0.18);
    --shadow-card-hover: 0 25px 60px rgba(90, 154, 110, 0.25);
}
```

---

## Typography

### Font Stack

```css
:root {
    --font-main: 'Pretendard', -apple-system, BlinkMacSystemFont,
                 system-ui, Roboto, 'Helvetica Neue', 'Segoe UI',
                 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic',
                 sans-serif;
}
```

### Font Loading

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
```

### Text Sizing

| Context | Size | Weight |
|---------|------|--------|
| Hero headline | `clamp(2.5rem, 7vw, 4rem)` | 600 |
| Section title | `clamp(1.75rem, 4vw, 2.25rem)` | 600 |
| Card title | `1.25rem` | 600 |
| Body text | `1rem` | 400 |
| Small text | `0.875rem` | 400 |

### Gradient Text

```css
.gradient-text {
    background: linear-gradient(135deg, var(--sage-primary), var(--sage-light));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
```

---

## Component Patterns

### Header (Glassmorphism)

```css
.site-header {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 70px;
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--border-subtle);
    z-index: 1000;
}
```

### Card Component

```css
.card {
    background: rgba(255, 255, 255, 0.7);
    backdrop-filter: blur(10px);
    border-radius: var(--radius-lg);
    border: 1px solid rgba(0, 0, 0, 0.05);
    padding: 40px;
    transition: var(--transition-normal);
    position: relative;
    overflow: hidden;
}

/* Gradient overlay on hover */
.card::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg,
        var(--gradient-color-1),
        var(--gradient-color-2),
        var(--gradient-color-3));
    opacity: 0;
    transition: var(--transition-normal);
}

.card:hover::before {
    opacity: 1;
}

.card:hover {
    transform: translateY(-8px) scale(1.02);
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
}
```

### Button Primary

```css
.btn-primary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 14px 28px;
    background: var(--sage-primary);
    color: #FFFFFF;
    font-size: 1rem;
    font-weight: 600;
    text-decoration: none;
    border: none;
    border-radius: var(--radius-full);
    cursor: pointer;
    transition: all var(--transition-fast);
    box-shadow: 0 2px 8px rgba(90, 154, 110, 0.25);
}

.btn-primary:hover {
    background: #4A8A5E;
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(90, 154, 110, 0.35);
}
```

### Button Secondary

```css
.btn-secondary {
    display: inline-flex;
    align-items: center;
    padding: 14px 28px;
    background: transparent;
    color: var(--gradient-color-1);
    font-size: 1rem;
    font-weight: 600;
    border: 1.5px solid rgba(90, 154, 110, 0.3);
    border-radius: var(--radius-full);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.btn-secondary:hover {
    background: rgba(90, 154, 110, 0.08);
    border-color: var(--gradient-color-1);
}
```

### Floating Action Button (FAB)

```css
.fab {
    position: fixed;
    bottom: 32px;
    right: 32px;
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: var(--sage-primary);
    border: none;
    box-shadow: 0 4px 16px rgba(90, 154, 110, 0.30);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    transition: all var(--transition-fast);
    z-index: 999;
    color: #FFFFFF;
}

.fab:hover {
    background: #4A8A5E;
    transform: scale(1.05) translateY(-2px);
    box-shadow: 0 6px 24px rgba(90, 154, 110, 0.40);
}
```

---

## Animation System

### Scroll Reveal

```css
.reveal {
    opacity: 0;
    transform: translateY(24px);
    transition: opacity 0.8s var(--ease-out),
                transform 0.8s var(--ease-out);
}

.reveal.is-visible {
    opacity: 1;
    transform: translateY(0);
}
```

### Character Fade Animations

#### Smoke Fade (Sutras)

```css
@keyframes charSmokeAway {
    0% {
        opacity: 1;
        transform: translateY(0) scale(1);
        filter: blur(0);
    }
    50% {
        opacity: 0.6;
        transform: translateY(-30px) scale(1.08);
        filter: blur(1.5px);
    }
    100% {
        opacity: 0;
        transform: translateY(-100px) scale(1.15);
        filter: blur(5px);
    }
}

#char-container span.char-fade {
    animation: charSmokeAway 1.2s ease-out forwards;
    will-change: transform, opacity, filter;
}
```

#### Radiate (Mantras)

```css
@keyframes charBlessingRadiate {
    0% {
        opacity: 1;
        transform: translate(0, 0) scale(1);
        filter: blur(0) brightness(1);
    }
    50% {
        opacity: 0.65;
        transform: translate(
            calc(var(--radiate-x) * 2),
            calc(var(--radiate-y) * 2)
        ) scale(1.3);
        filter: blur(2px) brightness(1.4);
    }
    100% {
        opacity: 0;
        transform: translate(
            calc(var(--radiate-x) * 5),
            calc(var(--radiate-y) * 5)
        ) scale(1.5);
        filter: blur(8px);
    }
}

#char-container span.char-radiate {
    animation: charBlessingRadiate 1.2s ease-out forwards;
}
```

**Note**: `--radiate-x` and `--radiate-y` are set via JavaScript with random angle vectors.

#### Pure Land Ascend (Names)

```css
@keyframes charPureLandAscend {
    0% {
        opacity: 1;
        transform: translateY(0) scale(1);
        color: var(--sage-primary);
    }
    40% {
        opacity: 0.9;
        transform: translateY(-50px) scale(1.1);
        filter: blur(1px) brightness(1.35);
        color: #d4e8da;
    }
    100% {
        opacity: 0;
        transform: translateY(-180px) scale(1.2);
        filter: blur(6px) brightness(1.7);
        color: #ffffff;
    }
}

#char-container span.char-pureland {
    animation: charPureLandAscend 1.2s ease-out forwards;
}
```

### Breathing Glow (Type Box)

```css
@keyframes breathingGlow {
    0%, 100% {
        box-shadow: var(--shadow-sage-subtle);
    }
    50% {
        box-shadow: var(--shadow-sage-hover);
    }
}

.type-box {
    animation: breathingGlow 8s ease-in-out infinite;
    will-change: box-shadow;
}
```

### Hero Icon Float

```css
@keyframes floatIcon {
    0%, 100% {
        transform: translateY(0);
    }
    50% {
        transform: translateY(-8px);
    }
}

.hero-buddha-icon {
    animation: floatIcon 4s ease-in-out infinite;
}
```

---

## Interactive Effects

### Mouse Light Effect

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
    transition: transform 0.15s ease-out;
}
```

Positioned via JavaScript:
```javascript
light.style.transform = `translate(${x}px, ${y}px)`;
```

### Navigation Link Underline

```css
.nav-link::after {
    content: '';
    position: absolute;
    bottom: -4px;
    left: 0;
    width: 0;
    height: 2px;
    background: linear-gradient(90deg,
        var(--gradient-color-1),
        var(--gradient-color-2));
    transition: width 0.3s ease;
}

.nav-link:hover::after {
    width: 100%;
}
```

---

## Responsive Design

### Breakpoints

| Breakpoint | Target |
|------------|--------|
| `900px` | Tablet |
| `768px` | Mobile |
| `500px` | Small mobile |

### Grid Adjustments

```css
/* Desktop: 4 columns */
.sutra-cards {
    grid-template-columns: repeat(4, 1fr);
}

/* Tablet: 3 columns */
@media (max-width: 1100px) {
    .sutra-cards {
        grid-template-columns: repeat(3, 1fr);
    }
}

/* Small tablet: 2 columns */
@media (max-width: 800px) {
    .sutra-cards {
        grid-template-columns: repeat(2, 1fr);
    }
}

/* Mobile: 1 column */
@media (max-width: 500px) {
    .sutra-cards {
        grid-template-columns: 1fr;
    }
}
```

### Mobile Header

```css
@media (max-width: 768px) {
    .site-header {
        height: 60px;
    }

    .header-spacer {
        height: 60px;
    }

    .logo-text {
        display: none;  /* Hide text, show only icon */
    }

    .header-nav {
        gap: var(--space-lg);
    }

    .nav-link {
        font-size: 0.875rem;
    }
}
```

### Mobile Content

```css
@media (max-width: 768px) {
    .container {
        padding: 0 var(--space-lg);
    }

    .section {
        padding: var(--space-2xl) 0;
    }

    .hero-new {
        min-height: auto;
        padding: var(--space-2xl) 0;
    }

    .hero-buddha-icon {
        width: 120px;
    }

    .fab {
        width: 56px;
        height: 56px;
        bottom: 24px;
        right: 24px;
    }
}
```

---

## Accessibility

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
    .type-box {
        animation: none;
        box-shadow: var(--shadow-sage-subtle);
    }

    .reveal {
        transition: none;
    }

    #char-container span.char-fade,
    #char-container span.char-radiate,
    #char-container span.char-pureland {
        animation-duration: 0.4s;
    }

    .sutra-cards .card:hover {
        transform: none;
    }
}
```

### Focus Indicators

```css
/* Global focus style */
*:focus-visible {
    outline: 2px solid var(--gradient-color-1);
    outline-offset: 4px;
    border-radius: var(--radius-sm);
}

/* Card focus */
.sutra-cards .card:focus-visible {
    outline: 3px solid var(--sage-primary);
    outline-offset: 4px;
    box-shadow: 0 0 0 6px rgba(90, 154, 110, 0.15);
}

/* Button focus */
.realm-buttons button:focus-visible {
    outline: 2px solid var(--sage-primary);
    outline-offset: 3px;
    box-shadow: 0 0 0 5px rgba(90, 154, 110, 0.18);
}
```

### Skip Link

```css
.skip-link {
    position: absolute;
    top: -40px;
    left: 0;
    background: var(--gradient-color-1);
    color: var(--white);
    padding: var(--spacing-xs) var(--spacing-sm);
    z-index: 1000;
    transition: top 0.3s ease;
}

.skip-link:focus {
    top: 0;
}
```

---

## Special States

### Completed Characters (Sutra Typing)

```css
/* Traditional Mode: Hide completed characters */
.text-bg span.done {
    opacity: 0;
}

/* Easy Mode: Show completed in sage green */
.text-bg.clickable span.done {
    opacity: 1;
    color: var(--sage-primary);
    text-shadow: 0 0 20px rgba(90, 154, 110, 0.4);
}

/* Easy Mode: Skipped characters in sky blue */
.text-bg span.skipped {
    opacity: 0.75;
    color: #6BB6FF;
    text-shadow: 0 0 15px rgba(107, 182, 255, 0.5);
}
```

### Clickable Background (Easy Mode)

```css
.text-bg.clickable {
    pointer-events: auto;
    z-index: 15;
}

.text-bg.clickable span {
    cursor: pointer;
    pointer-events: auto !important;
    transition: all 0.2s ease;
}

.text-bg.clickable span:hover:not(.done):not(.skipped) {
    color: var(--gradient-color-1) !important;
    opacity: 0.8 !important;
    transform: scale(1.1);
}
```

---

## Z-Index Layering

| Layer | Z-Index | Element |
|-------|---------|---------|
| Background light | 1 | `.interactive-light` |
| Content | 2 | `.sutra-page` |
| Background text | 5 | `.text-bg` (default) |
| Input field | 10 | `.text-input`, `.text-input-easy` |
| Easy mode bg | 15 | `.text-bg.clickable` |
| Character animation | 20 | `#char-container` |
| FAB | 999 | `.fab` |
| Header | 1000 | `.site-header` |
| Skip link | 1000 | `.skip-link` |

---

## Best Practices

### Performance

1. Use `will-change` sparingly for animated elements
2. Prefer `transform` and `opacity` for animations (GPU-accelerated)
3. Use `contain: layout` for isolated components
4. Minimize `backdrop-filter` usage on mobile

### Consistency

1. Always use design tokens from `:root`
2. Use consistent border-radius scale
3. Apply transitions via predefined variables
4. Follow spacing scale for margins/padding

### Maintainability

1. Group related properties together
2. Comment section boundaries clearly
3. Use BEM-like naming where appropriate
4. Keep responsive styles near their base rules

---

*This document was auto-generated from codebase analysis.*
