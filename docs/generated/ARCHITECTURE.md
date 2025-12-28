# Buddha Korea Frontend Architecture

> Generated Documentation | Last Updated: 2025-12-26

## System Overview

Buddha Korea (붓다코리아) is a static website for exploring Buddhist teachings through interactive experiences and AI chatbots. The frontend is a pure static site with no build process, using vanilla HTML, CSS, and JavaScript with ES6 modules.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BUDDHA KOREA FRONTEND                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         HTML PAGES (Entry Points)                     │   │
│  │  ┌────────────┐  ┌────────────────┐  ┌─────────────┐  ┌──────────┐  │   │
│  │  │ index.html │  │sutra-writing   │  │ meditation  │  │ teaching │  │   │
│  │  │            │  │     .html      │  │    .html    │  │   .html  │  │   │
│  │  │  Landing   │  │  Digital Sutra │  │  Meditation │  │ Buddhist │  │   │
│  │  │   Page     │  │    Copying     │  │   Timers    │  │ Diagrams │  │   │
│  │  └─────┬──────┘  └───────┬────────┘  └──────┬──────┘  └────┬─────┘  │   │
│  └────────┼─────────────────┼──────────────────┼───────────────┼────────┘   │
│           │                 │                  │               │            │
│  ┌────────┴─────────────────┴──────────────────┴───────────────┴────────┐   │
│  │                       CSS STYLESHEETS                                 │   │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌──────────────────┐   │   │
│  │  │styles.css│  │ sutra.css│  │meditation  │  │   teaching.css   │   │   │
│  │  │  (Base)  │  │          │  │   .css     │  │                  │   │   │
│  │  └──────────┘  └──────────┘  └────────────┘  └──────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    JAVASCRIPT MODULES (ES6)                           │   │
│  │                                                                        │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │   │
│  │  │                      Data Layer                                  │  │   │
│  │  │  ┌─────────────────┐     ┌─────────────────────────────────┐   │  │   │
│  │  │  │  sutra-data.js  │────▶│  data/sutras.json               │   │  │   │
│  │  │  │  (Data Loader)  │     │  (Sutra content & metadata)     │   │  │   │
│  │  │  └─────────────────┘     └─────────────────────────────────┘   │  │   │
│  │  └─────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                        │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │   │
│  │  │                   Feature Modules                                │  │   │
│  │  │  ┌───────────┐  ┌─────────────┐  ┌───────────┐  ┌───────────┐  │  │   │
│  │  │  │  main.js  │  │  sutra.js   │  │meditation │  │ teaching  │  │  │   │
│  │  │  │Light/Anim │  │Typing Valid │  │   .js     │  │   .js     │  │  │   │
│  │  │  └───────────┘  └─────────────┘  │  Timers   │  │ SVG Int.  │  │  │   │
│  │  │                                   └───────────┘  └───────────┘  │  │   │
│  │  │                                                                  │  │   │
│  │  │  ┌─────────────┐  ┌───────────┐                                │  │   │
│  │  │  │ephemeral.js │  │feedback.js│                                │  │   │
│  │  │  │Fading Text  │  │ Forms     │                                │  │   │
│  │  │  └─────────────┘  └───────────┘                                │  │   │
│  │  └─────────────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       EXTERNAL SERVICES                               │   │
│  │  ┌─────────────────┐  ┌───────────────┐  ┌────────────────────────┐  │   │
│  │  │ Google NotebookLM│  │ Backend API   │  │  Pretendard Font CDN   │  │   │
│  │  │  (AI Chatbots)   │  │(Hetzner/Auth) │  │  (Typography)          │  │   │
│  │  └─────────────────┘  └───────────────┘  └────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SUTRA COPYING DATA FLOW                       │
└─────────────────────────────────────────────────────────────────────┘

  ┌──────────────────┐
  │   sutras.json    │ ◀─── Static JSON file with sutra content
  │  (data folder)   │
  └────────┬─────────┘
           │
           ▼ fetch()
  ┌────────────────────────────────────────────────────────────────┐
  │                      sutra-data.js                              │
  │  ┌─────────────────────────────────────────────────────────┐   │
  │  │  loadSutraData()                                         │   │
  │  │  - Fetches JSON                                          │   │
  │  │  - Processes patterns (mantras) → repeated text          │   │
  │  │  - Exports: SUTRA_DATA, dataLoadedPromise                │   │
  │  └─────────────────────────────────────────────────────────┘   │
  │                                                                 │
  │  Exported Functions:                                            │
  │  • getSutraById(id) → sutra object                              │
  │  • getSutrasByCategory(category) → sorted array                 │
  │  • getAnimationClass(category) → CSS class name                 │
  └────────────────────────────────────────────────────────────────┘
           │
           │ import
           ▼
  ┌────────────────────────────────────────────────────────────────┐
  │                        sutra.js                                 │
  │  ┌─────────────────────────────────────────────────────────┐   │
  │  │  State Management:                                       │   │
  │  │  • sutraText, userTyped, bgSpans[]                       │   │
  │  │  • currentMode ('traditional' | 'easy')                  │   │
  │  │  • typedIndices, skippedIndices (Set)                    │   │
  │  └─────────────────────────────────────────────────────────┘   │
  │                                                                 │
  │  ┌─────────────────────────────────────────────────────────┐   │
  │  │  Key Functions:                                          │   │
  │  │  • selectSutra(id)    → Load sutra & setup UI            │   │
  │  │  • checkInput()       → Validate typing (traditional)    │   │
  │  │  • checkInputEasy()   → Validate typing (easy mode)      │   │
  │  │  • dedicate(realm)    → Trigger dedication animation     │   │
  │  └─────────────────────────────────────────────────────────┘   │
  └────────────────────────────────────────────────────────────────┘
           │
           │ window.selectSutra()
           ▼
  ┌────────────────────────────────────────────────────────────────┐
  │                    sutra-writing.html                           │
  │  • Inline module script renders cards from getSutrasByCategory  │
  │  • onclick calls window.selectSutra(id)                         │
  │  • Dedication buttons call window.dedicate(realm)               │
  └────────────────────────────────────────────────────────────────┘
```

## Component Interaction

```
┌─────────────────────────────────────────────────────────────────────┐
│                     USER INTERACTION FLOW                            │
└─────────────────────────────────────────────────────────────────────┘

  User Action                 JavaScript Handler              DOM Update
  ═══════════                 ═════════════════               ══════════

  [Selects Sutra Card]
        │
        ▼
  selectSutra(id) ────────────────────────────────────▶ screen-write visible
        │                                                 text-bg populated
        │                                                 input focused
        │
  [Types Character]
        │
        ▼
  input event ───────▶ checkInput() ─────────────────▶ validate character
        │                  │
        │                  ├── if correct ───────────▶ add .done class
        │                  │                            userTyped += char
        │                  │
        │                  └── if wrong ─────────────▶ truncate input
        │                                              cursor restored
        │
  [Completes Sutra]
        │
        ▼
  checkCompletion() ─────────────────────────────────▶ dedication-box visible
        │
        │
  [Clicks Dedication]
        │
        ▼
  dedicate(realm) ───────────────────────────────────▶ Create char-container
        │                                              Category animation
        │                                              5s staggered fade
        │
        └───────────────────────────────────────────▶ screen-dedication-complete
                                                       Auto-return to select
```

## File Structure

```
buddhakorea/frontend/
├── index.html              # Landing page with AI chatbot links
├── sutra-writing.html      # Digital sutra copying feature
├── meditation.html         # Meditation timer with tabs
├── teaching.html           # Interactive Buddhist diagrams
├── chat.html               # RAG AI chat interface
├── mypage.html             # User profile page
│
├── css/
│   ├── styles.css          # Base styles, design tokens, common components
│   ├── sutra.css           # Sutra copying specific styles
│   ├── meditation.css      # Meditation timer styles
│   ├── teaching.css        # Teaching diagrams styles
│   ├── library.css         # Literature library styles
│   └── search.css          # Search interface styles
│
├── js/
│   ├── main.js             # Interactive light, scroll reveal animations
│   ├── sutra-data.js       # Sutra data loader (ES6 module)
│   ├── sutra.js            # Typing validation, dedication animations
│   ├── meditation.js       # Timer logic, Buddha contemplation
│   ├── teaching.js         # Interactive SVG diagram handlers
│   ├── ephemeral.js        # Ephemeral sentences (impermanence demo)
│   ├── feedback.js         # Feedback form handling
│   └── library.js          # Literature library interactions
│
├── data/
│   ├── sutras.json         # Sutra content, categories, metadata
│   └── teachings.json      # Four Noble Truths, Eightfold Path data
│
└── assets/
    ├── favicon.ico         # Site favicon
    ├── buddha-line.png     # Buddha icon for logo
    └── ...                 # Other images
```

## Module Dependencies

```
                    ┌───────────────────┐
                    │   sutras.json     │
                    │  (Static Data)    │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │  sutra-data.js    │
                    │  ┌─────────────┐  │
                    │  │loadSutraData│  │
                    │  └─────────────┘  │
                    │                   │
                    │  Exports:         │
                    │  • SUTRA_DATA     │
                    │  • getSutraById   │
                    │  • getSutrasByCat │
                    │  • getAnimClass   │
                    │  • dataLoadedProm │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────────┐ ┌───────────┐ ┌─────────────────┐
    │    sutra.js     │ │sutra-     │ │  (future use)   │
    │                 │ │writing    │ │                 │
    │ State:          │ │.html      │ │                 │
    │ • sutraText     │ │           │ │                 │
    │ • userTyped     │ │ Inline    │ │                 │
    │ • bgSpans[]     │ │ script    │ │                 │
    │                 │ │           │ │                 │
    │ Functions:      │ └───────────┘ └─────────────────┘
    │ • selectSutra   │
    │ • checkInput    │
    │ • dedicate      │
    │                 │
    │ Exposes:        │
    │ • window.*      │
    └─────────────────┘
```

## Animation System

### Dedication Animations by Category

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CATEGORY → ANIMATION MAPPING                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Category         Animation Class      Visual Effect                 │
│  ────────────     ───────────────      ─────────────                 │
│                                                                      │
│  sutra (문헌)     char-fade            Characters fade upward        │
│                                        like smoke ascending          │
│                                                                      │
│  mantra (진언)    char-radiate         Characters radiate outward    │
│                                        with random vector angles     │
│                                                                      │
│  name (명호)      char-pureland        Characters ascend to          │
│                                        Pure Land (extreme upward)    │
│                                                                      │
│  verse (게송)     char-fade            Default fade animation        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

Animation Timing:
• Total duration: 5 seconds
• Delay per char: 5000ms / totalChars
• Order: Last character first → First character last (마지막부터)
• Post-animation: 1.2s buffer before screen transition
```

### Ephemeral Sentences Animation

```
┌─────────────────────────────────────────────────────────────────────┐
│                    EPHEMERAL SENTENCES FLOW                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  [User Types]                                                        │
│       │                                                              │
│       ▼                                                              │
│  handleInput()                                                       │
│       │                                                              │
│       ├── wrapNewCharacters()  →  Each char in <span.char-wrapper>  │
│       │                                                              │
│       └── setTimeout(fadeCharacters, CONFIG.FADE_DELAY)             │
│                    │                                                 │
│                    ▼ (after 3000ms default)                         │
│              fadeCharacters()                                        │
│                    │                                                 │
│                    ├── Create overlay container                     │
│                    ├── Clone text as individual spans               │
│                    ├── Apply golden text-shadow                     │
│                    └── Staggered .char-fade-ephemeral class         │
│                                                                      │
│  Animation completes → Container removed → Canvas cleared           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Performance Optimizations

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PERFORMANCE PATTERNS                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. DOM CACHING                                                      │
│     ┌─────────────────────────────────────────────────────────────┐ │
│     │  let cachedTimeDisplay = null;                               │ │
│     │  let cachedProgressCircle = null;                            │ │
│     │                                                              │ │
│     │  if (!cachedTimeDisplay) {                                   │ │
│     │      cachedTimeDisplay = document.getElementById(...);       │ │
│     │  }                                                           │ │
│     └─────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  2. RAF BATCHING                                                     │
│     ┌─────────────────────────────────────────────────────────────┐ │
│     │  let rafId = null;                                           │ │
│     │                                                              │ │
│     │  function scheduleVisualUpdate() {                           │ │
│     │      if (!rafId) {                                           │ │
│     │          rafId = requestAnimationFrame(() => {               │ │
│     │              updateVisuals();                                │ │
│     │              rafId = null;                                   │ │
│     │          });                                                 │ │
│     │      }                                                       │ │
│     │  }                                                           │ │
│     └─────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  3. ADAPTIVE INTERVALS                                               │
│     ┌─────────────────────────────────────────────────────────────┐ │
│     │  const isMobile = /iPhone|Android/.test(navigator.userAgent);│ │
│     │  const updateInterval = isMobile ? 200 : 100;                │ │
│     └─────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  4. GPU-ACCELERATED TRANSFORMS                                       │
│     ┌─────────────────────────────────────────────────────────────┐ │
│     │  mouseLight.style.transform =                                │ │
│     │      `translate3d(${x}px, ${y}px, 0)`;                      │ │
│     └─────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  5. SMOOTH INTERPOLATION                                             │
│     ┌─────────────────────────────────────────────────────────────┐ │
│     │  currentX += (mouseX - currentX) * 0.15;                     │ │
│     │  currentY += (mouseY - currentY) * 0.15;                     │ │
│     └─────────────────────────────────────────────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Korean IME Handling

```
┌─────────────────────────────────────────────────────────────────────┐
│                    KOREAN INPUT METHOD HANDLING                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Problem: Korean characters are composed from multiple keystrokes    │
│           (ㄱ + ㅏ = 가). Browser fires input events during          │
│           composition, causing premature validation failures.        │
│                                                                      │
│  Solution:                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  input.addEventListener('compositionstart', () => {             ││
│  │      input.isComposing = true;  // Flag: composition in progress││
│  │  });                                                            ││
│  │                                                                 ││
│  │  input.addEventListener('compositionend', () => {               ││
│  │      input.isComposing = false;                                 ││
│  │      setTimeout(() => checkInput(), 0);  // Defer validation    ││
│  │  });                                                            ││
│  │                                                                 ││
│  │  input.addEventListener('input', () => {                        ││
│  │      if (!input.isComposing) {  // Only validate when complete  ││
│  │          checkInput();                                          ││
│  │      }                                                          ││
│  │  });                                                            ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  Unicode Normalization:                                              │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  sutraText = sutra.text.normalize('NFC');                       ││
│  │  const typed = input.value.normalize('NFC');                    ││
│  │  // Ensures consistent comparison of Korean characters          ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## External Integrations

| Service | Purpose | Notes |
|---------|---------|-------|
| Google NotebookLM | AI chatbot hosting | External links, requires Google account |
| Backend API (Hetzner) | User auth, RAG queries | `ai.buddhakorea.com` |
| Pretendard Font CDN | Korean typography | Loaded via `<link>` |
| Google Analytics 4 | Usage tracking | GA4 tag in index.html |

## Design Tokens

The design system uses CSS custom properties for consistent theming:

```css
:root {
    /* Sage Green Palette (Primary) */
    --sage-primary: #5A9A6E;
    --sage-light: #8CB89C;
    --sage-lighter: #B8D4C2;

    /* Spacing Scale */
    --space-xs: 4px;
    --space-sm: 8px;
    --space-md: 16px;
    --space-lg: 24px;
    --space-xl: 32px;

    /* Border Radius */
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 20px;

    /* Transitions */
    --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
    --transition-fast: 0.2s var(--ease-out);
}
```

---

*This document was auto-generated from codebase analysis.*
