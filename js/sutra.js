// ========================================
// 전자 사경 - 단순하고 확실한 기능
// ========================================

import { SUTRA_DATA as SUTRAS, getSutraById, getAnimationClass, dataLoadedPromise } from './sutra-data.js';

// ========================================
// State Management
// ========================================
let sutraText = '';
let userTyped = '';
let bgSpans = []; // Cached DOM references
let rafId = null; // RequestAnimationFrame ID for debouncing
let currentSutraId = null; // Track currently selected sutra for animations
let dataLoaded = false;

// Mode state ('traditional' | 'easy')
let currentMode = 'traditional';

// Easy Mode state
let typedIndices = new Set(); // User-typed character positions
let skippedIndices = new Set(); // Auto-completed character positions
let lastSpaceTime = 0; // For double-space detection

// Wait for data to load
dataLoadedPromise.then(() => {
    dataLoaded = true;
    console.log('Sutra data ready for use');
}).catch(error => {
    console.error('Failed to load sutra data:', error);
    alert('경전 데이터를 불러오는데 실패했습니다. 페이지를 새로고침해주세요.');
});

// ========================================
// 마우스 빛 효과
// ========================================
const mouseLight = document.querySelector('.mouse-light');
if (mouseLight) {
    document.addEventListener('mousemove', (e) => {
        mouseLight.style.transform = `translate(${e.clientX - 300}px, ${e.clientY - 300}px)`;
    });
}

// ========================================
// 모드 전환
// ========================================
function switchMode(mode) {
    if (!['traditional', 'easy'].includes(mode)) {
        console.error('Invalid mode:', mode);
        return;
    }

    currentMode = mode;
    console.log('Mode switched to:', mode);

    // Update UI
    const modeButtons = document.querySelectorAll('.mode-btn');
    modeButtons.forEach(btn => {
        const isActive = btn.dataset.mode === mode;
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-checked', isActive ? 'true' : 'false');
    });

    // Show/hide mode hint
    const modeHint = document.getElementById('mode-hint');
    if (modeHint) {
        modeHint.style.display = mode === 'easy' ? 'flex' : 'none';
    }

    // Toggle input elements
    const textInput = document.getElementById('text-input');
    const textInputEasy = document.getElementById('text-input-easy');
    const textBg = document.getElementById('text-bg');

    if (mode === 'traditional') {
        textInput.style.display = 'block';
        textInputEasy.style.display = 'none';
        if (textBg) {
            textBg.classList.remove('clickable');
            textBg.style.pointerEvents = 'none';
        }
    } else {
        textInput.style.display = 'none';
        textInputEasy.style.display = 'block';
        if (textBg) {
            textBg.classList.add('clickable');
            // Important: Enable pointer events for clicking
            bgSpans.forEach(span => {
                span.style.pointerEvents = 'auto';
                span.style.cursor = 'pointer';
            });
        }
    }

    // Reset state when switching modes
    if (sutraText) {
        resetTypingState();
        const activeInput = mode === 'traditional' ? textInput : textInputEasy;
        setTimeout(() => activeInput.focus(), 100);
    }
}

// Helper function to reset typing state
function resetTypingState() {
    userTyped = '';
    typedIndices.clear();
    skippedIndices.clear();
    lastSpaceTime = 0;

    // Clear inputs
    const textInput = document.getElementById('text-input');
    const textInputEasy = document.getElementById('text-input-easy');
    textInput.value = '';
    textInputEasy.textContent = '';

    // Reset visual state
    bgSpans.forEach(span => {
        span.classList.remove('done', 'skipped');
    });

    // Hide dedication box
    document.getElementById('dedication-box').classList.remove('show');
}

// ========================================
// 화면 전환 (부드럽게)
// ========================================
function showScreen(id) {
    const currentScreen = document.querySelector('.screen.show');

    if (currentScreen) {
        // Fade out current screen
        currentScreen.style.transition = 'opacity 0.5s cubic-bezier(0.16, 1, 0.3, 1)';
        currentScreen.style.opacity = '0';

        setTimeout(() => {
            currentScreen.classList.remove('show');
            currentScreen.style.display = 'none';

            // Fade in new screen
            const newScreen = document.getElementById(id);
            newScreen.style.display = 'flex';
            newScreen.style.opacity = '0';
            newScreen.classList.add('show');

            requestAnimationFrame(() => {
                newScreen.style.transition = 'opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1)';
                newScreen.style.opacity = '1';
            });
        }, 500);
    } else {
        // Initial load
        const newScreen = document.getElementById(id);
        newScreen.style.display = 'flex';
        newScreen.classList.add('show');
        newScreen.style.opacity = '1';
    }
}

// ========================================
// 경전 선택
// ========================================
function selectSutra(id) {
    if (!dataLoaded) {
        console.warn('Data not loaded yet, waiting...');
        return;
    }

    currentSutraId = id; // Track for category-specific animations
    const sutra = SUTRAS[id];
    // Normalize to NFC for consistent Korean character comparison
    sutraText = sutra.text.normalize('NFC');
    userTyped = '';
    typedIndices.clear();
    skippedIndices.clear();
    lastSpaceTime = 0;

    // 제목 설정 (subtitle도 표시)
    const sutraNameEl = document.getElementById('sutra-name');
    sutraNameEl.textContent = sutra.title;
    if (sutra.subtitle) {
        sutraNameEl.innerHTML = `${sutra.title}<span style="display:block;font-size:0.7em;margin-top:0.3em;opacity:0.7;">${sutra.subtitle}</span>`;
    }

    // Set up mode button listeners (only once)
    const modeButtons = document.querySelectorAll('.mode-btn');
    modeButtons.forEach(btn => {
        btn.replaceWith(btn.cloneNode(true)); // Remove old listeners
    });
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            switchMode(btn.dataset.mode);
        });
    });

    // 배경 텍스트 생성
    const textBg = document.getElementById('text-bg');
    textBg.innerHTML = '';
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < sutraText.length; i++) {
        const span = document.createElement('span');
        span.textContent = sutraText[i];
        span.dataset.index = i; // Store index for click handling
        fragment.appendChild(span);
    }
    textBg.appendChild(fragment);

    // Cache DOM references for performance
    bgSpans = Array.from(textBg.children);

    // Add click handlers for Easy Mode
    bgSpans.forEach((span, index) => {
        span.addEventListener('click', (e) => {
            console.log('Span clicked:', index, 'mode:', currentMode, 'pointerEvents:', span.style.pointerEvents);
            if (currentMode === 'easy') {
                e.preventDefault();
                handleCharacterClick(index);
            }
        });
    });

    // ========================================
    // Traditional Mode 입력창 초기화
    // ========================================
    const input = document.getElementById('text-input');

    // 기존 이벤트 리스너 완전히 제거
    const newInput = input.cloneNode(true);
    input.parentNode.replaceChild(newInput, input);

    // 새 input 참조
    const textInput = document.getElementById('text-input');
    textInput.value = '';
    textInput.disabled = false;
    textInput.readOnly = false;
    textInput.spellcheck = false;
    textInput.autocomplete = 'off';
    textInput.autocorrect = 'off';
    textInput.autocapitalize = 'off';

    console.log('Traditional input initialized');

    // Traditional Mode 이벤트 설정 (한글 입력 지원)
    textInput.addEventListener('compositionstart', () => {
        textInput.isComposing = true;
    });

    textInput.addEventListener('compositionend', (e) => {
        textInput.isComposing = false;
        setTimeout(() => {
            if (currentMode === 'traditional') {
                checkInput();
            }
        }, 0);
    });

    textInput.addEventListener('input', (e) => {
        if (!textInput.isComposing && currentMode === 'traditional') {
            checkInput();
        }
    });

    // ========================================
    // Easy Mode 입력창 초기화
    // ========================================
    const easyInput = document.getElementById('text-input-easy');
    const newEasyInput = easyInput.cloneNode(true);
    easyInput.parentNode.replaceChild(newEasyInput, easyInput);

    const textInputEasy = document.getElementById('text-input-easy');
    textInputEasy.textContent = '';
    textInputEasy.spellcheck = false;

    console.log('Easy input initialized');

    // Easy Mode 이벤트 설정
    textInputEasy.addEventListener('compositionstart', () => {
        textInputEasy.isComposing = true;
    });

    textInputEasy.addEventListener('compositionend', () => {
        textInputEasy.isComposing = false;
        setTimeout(() => {
            if (currentMode === 'easy') {
                checkInputEasy();
            }
        }, 0);
    });

    textInputEasy.addEventListener('input', (e) => {
        if (!textInputEasy.isComposing && currentMode === 'easy') {
            checkInputEasy();
        }
    });

    // Double-space detection for Easy Mode
    textInputEasy.addEventListener('keydown', (e) => {
        if (currentMode === 'easy' && e.key === ' ') {
            const now = Date.now();
            if (now - lastSpaceTime < 300) {
                // Double-space detected
                e.preventDefault();
                completeToNextLine();
            }
            lastSpaceTime = now;
        }
    });

    // 회향 박스 및 통계 숨기기
    document.getElementById('dedication-box').classList.remove('show');
    document.getElementById('typing-stats').style.display = 'none';

    // Initialize mode to traditional
    switchMode('traditional');

    // 화면 전환 및 포커스
    showScreen('screen-write');
    setTimeout(() => {
        // 페이지 맨 위로 스크롤
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // 포커스 설정
        const activeInput = currentMode === 'traditional' ? textInput : textInputEasy;
        activeInput.focus();

        console.log('Input focused, mode:', currentMode);
    }, 200);
}

// ========================================
// 입력 검증 (최적화)
// ========================================
function checkInput() {
    const input = document.getElementById('text-input');
    // Normalize typed input to NFC for consistent comparison
    const typed = input.value.normalize('NFC');

    console.log('checkInput called - typed:', typed, 'userTyped:', userTyped);

    // Early exit if no change
    if (typed === userTyped) {
        console.log('No change, exiting');
        return;
    }

    // 올바른 글자만 남기기 (divergence point 찾기)
    let correctLength = 0;
    for (let i = 0; i < typed.length && i < sutraText.length; i++) {
        if (typed[i] === sutraText[i]) {
            correctLength++;
        } else {
            console.log(`Mismatch at ${i}: typed="${typed[i]}" (${typed.charCodeAt(i)}) expected="${sutraText[i]}" (${sutraText.charCodeAt(i)})`);
            break;
        }
    }

    const correct = typed.slice(0, correctLength);
    console.log('Correct portion:', correct);

    // 틀린 부분 제거 (커서 위치 보존)
    if (correct !== typed) {
        const cursorPos = correct.length;
        input.value = correct;
        input.setSelectionRange(cursorPos, cursorPos);
        console.log('Corrected input to:', correct);
    }

    userTyped = correct;

    // Schedule visual update using RAF
    scheduleVisualUpdate();

    // 완성 체크
    checkCompletion();
}

// ========================================
// RAF로 시각 업데이트 스케줄링 (60fps)
// ========================================
function scheduleVisualUpdate() {
    if (!rafId) {
        rafId = requestAnimationFrame(() => {
            if (currentMode === 'traditional') {
                updateVisuals();
            } else {
                updateVisualsEasy();
            }
            rafId = null;
        });
    }
}

// ========================================
// 배치 시각 업데이트 - Traditional Mode
// ========================================
function updateVisuals() {
    const len = userTyped.length;

    // 변경된 span만 업데이트 (배치 처리)
    for (let i = 0; i < bgSpans.length; i++) {
        const shouldBeDone = i < len;
        const isDone = bgSpans[i].classList.contains('done');

        if (shouldBeDone !== isDone) {
            bgSpans[i].classList.toggle('done', shouldBeDone);
        }
    }
}

// ========================================
// Easy Mode Functions
// ========================================

// Handle character click in Easy Mode
function handleCharacterClick(index) {
    console.log('Character clicked:', index);

    // Save reference to clicked span for scroll restoration
    const clickedSpan = bgSpans[index];

    // Auto-complete all characters up to this index
    for (let i = 0; i < index; i++) {
        if (!typedIndices.has(i) && !skippedIndices.has(i)) {
            skippedIndices.add(i);
        }
    }

    // Update visual display
    updateVisualsEasy();

    // Update contenteditable text
    const textInputEasy = document.getElementById('text-input-easy');
    let completedText = '';
    for (let i = 0; i < index; i++) {
        completedText += sutraText[i];
    }
    textInputEasy.textContent = completedText;
    userTyped = completedText;

    // Focus on contenteditable and set cursor to the clicked position
    // Use preventScroll to avoid browser auto-scrolling to input
    textInputEasy.focus({ preventScroll: true });
    setTimeout(() => {
        setCursorPosition(textInputEasy, index);
        // Scroll clicked span into view to maintain position
        if (clickedSpan) {
            clickedSpan.scrollIntoView({ behavior: 'instant', block: 'center' });
        }
    }, 0);

    // Check for completion
    checkCompletion();
}

// Complete to next line break (double-space feature)
function completeToNextLine() {
    const currentPos = userTyped.length;
    console.log('Double-space detected at position:', currentPos, '/', sutraText.length);

    // If already at the end, do nothing
    if (currentPos >= sutraText.length) {
        console.log('Already at end, no more to complete');
        return;
    }

    // Find next line break
    let nextLinePos = sutraText.indexOf('\n', currentPos);
    if (nextLinePos === -1 || nextLinePos < currentPos) {
        // No line break found, complete to end
        nextLinePos = sutraText.length;
        console.log('No more line breaks, completing to end:', nextLinePos);
    } else {
        // Include the line break
        nextLinePos++;
        console.log('Completing to next line break at:', nextLinePos);
    }

    // Mark characters as skipped
    for (let i = currentPos; i < nextLinePos; i++) {
        if (!typedIndices.has(i)) {
            skippedIndices.add(i);
        }
    }

    // Update text
    const textInputEasy = document.getElementById('text-input-easy');
    userTyped = sutraText.slice(0, nextLinePos);
    textInputEasy.textContent = userTyped;

    console.log('Updated userTyped length:', userTyped.length, '/', sutraText.length);

    // Update visuals
    updateVisualsEasy();

    // Focus and set cursor to new position
    textInputEasy.focus();
    setTimeout(() => {
        setCursorPosition(textInputEasy, nextLinePos);
    }, 0);

    // Check for completion
    checkCompletion();
}

// Check input for Easy Mode
function checkInputEasy() {
    const input = document.getElementById('text-input-easy');
    // Normalize typed input to NFC for consistent comparison
    const typed = input.textContent.normalize('NFC');

    console.log('checkInputEasy - typed length:', typed.length, 'userTyped length:', userTyped.length);

    // Handle backspace/deletion
    if (typed.length < userTyped.length) {
        // User deleted characters
        const deletedCount = userTyped.length - typed.length;
        for (let i = 0; i < deletedCount; i++) {
            const pos = userTyped.length - 1 - i;
            typedIndices.delete(pos);
            skippedIndices.delete(pos);
        }
        userTyped = typed;
        updateVisualsEasy();
        return;
    }

    // Check if new characters match sutra text
    const newChars = typed.slice(userTyped.length);
    let validText = userTyped;

    for (let i = 0; i < newChars.length; i++) {
        const pos = userTyped.length + i;
        if (pos >= sutraText.length) break;

        const typedChar = newChars[i];
        const expectedChar = sutraText[pos];

        if (typedChar === expectedChar) {
            validText += typedChar;
            typedIndices.add(pos);
            skippedIndices.delete(pos); // Override skipped if user types it
        } else {
            // Invalid character - truncate
            break;
        }
    }

    // Update if different
    if (validText !== typed) {
        input.textContent = validText;
        setCursorPosition(input, validText.length);
    }

    userTyped = validText;
    updateVisualsEasy();

    // Check for completion
    checkCompletion();
}

// Update visuals for Easy Mode
function updateVisualsEasy() {
    for (let i = 0; i < bgSpans.length; i++) {
        const span = bgSpans[i];
        const isTyped = typedIndices.has(i);
        const isSkipped = skippedIndices.has(i);

        // Remove all state classes first
        span.classList.remove('done', 'skipped');

        // Apply appropriate class
        if (isTyped) {
            span.classList.add('done');
        } else if (isSkipped) {
            span.classList.add('skipped');
        }
    }
}

// Helper: Set cursor position in contenteditable
function setCursorPosition(element, position) {
    try {
        const range = document.createRange();
        const sel = window.getSelection();
        const textNode = element.firstChild;

        if (textNode && textNode.nodeType === Node.TEXT_NODE) {
            const safePos = Math.min(position, textNode.length);
            range.setStart(textNode, safePos);
            range.collapse(true);
            sel.removeAllRanges();
            sel.addRange(range);
        }
    } catch (e) {
        console.warn('Failed to set cursor position:', e);
    }
}

// Check completion (for both modes)
function checkCompletion() {
    // Ensure we have the sutra text
    if (!sutraText || sutraText.length === 0) {
        console.warn('No sutra text loaded');
        return;
    }

    // Check if all characters are completed
    const isComplete = userTyped.length >= sutraText.length;

    console.log('Checking completion:', {
        userTypedLength: userTyped.length,
        sutraTextLength: sutraText.length,
        typedIndices: typedIndices.size,
        skippedIndices: skippedIndices.size,
        isComplete,
        mode: currentMode
    });

    if (isComplete) {
        console.log('✅ Sutra completed! Showing dedication box...');

        // Disable inputs
        const textInput = document.getElementById('text-input');
        const textInputEasy = document.getElementById('text-input-easy');
        if (textInput) textInput.disabled = true;
        if (textInputEasy) textInputEasy.contentEditable = 'false';

        // Show statistics in Easy Mode
        if (currentMode === 'easy') {
            const typingStats = document.getElementById('typing-stats');
            if (typingStats) {
                typingStats.style.display = 'flex';

                const typedCount = typedIndices.size;
                const skippedCount = skippedIndices.size;
                const total = sutraText.length;

                const typedPercent = Math.round((typedCount / total) * 100);
                const skippedPercent = Math.round((skippedCount / total) * 100);

                const typedCountEl = document.getElementById('typed-count');
                const skippedCountEl = document.getElementById('skipped-count');
                if (typedCountEl) typedCountEl.textContent = `${typedCount}자 (${typedPercent}%)`;
                if (skippedCountEl) skippedCountEl.textContent = `${skippedCount}자 (${skippedPercent}%)`;

                console.log('Statistics updated:', { typedCount, skippedCount, total });
            }
        }

        // Force show dedication box immediately
        const dedicationBox = document.getElementById('dedication-box');
        if (dedicationBox) {
            dedicationBox.style.display = 'block';
            setTimeout(() => {
                dedicationBox.classList.add('show');
                dedicationBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
                console.log('✅ Dedication box displayed and scrolled into view');
            }, 100);
        } else {
            console.error('❌ Dedication box not found!');
        }
    } else {
        console.log('Not yet complete:', userTyped.length, '/', sutraText.length);
    }
}

// ========================================
// 회향
// ========================================
function dedicate(realm) {
    console.log('Dedication started for:', realm, 'mode:', currentMode);

    // 회향 박스 숨기기
    document.getElementById('dedication-box').style.display = 'none';

    // 배경 텍스트 숨기기
    const textBg = document.getElementById('text-bg');
    textBg.style.opacity = '0';

    // 입력된 텍스트 가져오기 (mode에 따라)
    const textInput = document.getElementById('text-input');
    const textInputEasy = document.getElementById('text-input-easy');
    const text = currentMode === 'traditional' ? textInput.value : textInputEasy.textContent;

    // 입력창 숨기기
    textInput.style.opacity = '0';
    textInputEasy.style.opacity = '0';

    // 새로운 div로 글자 표시
    const charContainer = document.createElement('div');
    charContainer.id = 'char-container';
    charContainer.style.cssText = `
        position: absolute;
        top: 60px;
        left: 60px;
        right: 60px;
        bottom: 60px;
        font-size: 1.8rem;
        line-height: 2.6;
        white-space: pre-wrap;
        word-break: keep-all;
        pointer-events: none;
        z-index: 20;
    `;

    // 각 글자를 span으로 감싸기
    const chars = text.split('');
    chars.forEach((char, index) => {
        const span = document.createElement('span');
        span.textContent = char;

        // In Easy Mode, show skipped characters with vivid sky blue
        const isSkipped = currentMode === 'easy' && skippedIndices.has(index);
        const color = isSkipped ? '#6BB6FF' : '#daa520';
        const textShadow = isSkipped
            ? '0 0 15px rgba(107, 182, 255, 0.5), 0 0 30px rgba(107, 182, 255, 0.3)'
            : '0 0 20px rgba(218, 165, 32, 0.4), 0 0 40px rgba(218, 165, 32, 0.2)';

        span.style.cssText = `
            color: ${color};
            font-weight: 400;
            text-shadow: ${textShadow};
            display: inline;
        `;
        charContainer.appendChild(span);
    });

    document.querySelector('.type-box').appendChild(charContainer);

    // Get animation class based on sutra category
    const currentSutra = getSutraById(currentSutraId);
    const animationClass = getAnimationClass(currentSutra?.category || 'sutra');
    console.log(`Using animation: ${animationClass} for category: ${currentSutra?.category}`);

    // 마지막 글자부터 순차적으로 애니메이션 (5초 동안)
    const charSpans = charContainer.querySelectorAll('span');
    const totalDuration = 5000; // 5초
    const delayPerChar = totalDuration / charSpans.length;

    console.log('Starting animation for', charSpans.length, 'characters');

    charSpans.forEach((span, i) => {
        const reverseIndex = charSpans.length - 1 - i; // 마지막부터

        // For mantra radiation, add random direction vectors
        if (animationClass === 'char-radiate') {
            const angle = Math.random() * Math.PI * 2;
            const distance = 15 + Math.random() * 10; // 15-25px
            const x = Math.cos(angle) * distance;
            const y = Math.sin(angle) * distance;
            span.style.setProperty('--radiate-x', `${x}px`);
            span.style.setProperty('--radiate-y', `${y}px`);
        }

        setTimeout(() => {
            span.classList.add(animationClass);
            console.log(`Animating char ${i} with ${animationClass}`);
        }, reverseIndex * delayPerChar);
    });

    // 모든 애니메이션 완료 후 회향 완료 화면 표시
    setTimeout(() => {
        // charContainer 제거
        if (charContainer.parentNode) {
            charContainer.parentNode.removeChild(charContainer);
        }

        // 회향 완료 화면 표시
        showScreen('screen-dedication-complete');

        // 2초 후 사경 선택 화면으로
        setTimeout(() => {
            goBack();
        }, 2000);
    }, totalDuration + 1200); // 5초 + 마지막 글자 애니메이션 1.2초
}

// ========================================
// 뒤로가기
// ========================================
function goBack() {
    // 타이핑 박스 초기화
    const typeBox = document.querySelector('.type-box');
    if (typeBox) {
        typeBox.style.opacity = '1';
    }

    // char-container 제거 (있다면)
    const charContainer = document.getElementById('char-container');
    if (charContainer && charContainer.parentNode) {
        charContainer.parentNode.removeChild(charContainer);
    }

    // 입력창 초기화 및 활성화 - Traditional
    const input = document.getElementById('text-input');
    if (input) {
        input.disabled = false;
        input.style.opacity = '1';
        input.value = '';
        input.readOnly = false;
        // Clear any event listeners by cloning
        const newInput = input.cloneNode(true);
        input.parentNode.replaceChild(newInput, input);
    }

    // 입력창 초기화 - Easy Mode
    const easyInput = document.getElementById('text-input-easy');
    if (easyInput) {
        easyInput.contentEditable = 'true';
        easyInput.style.opacity = '1';
        easyInput.textContent = '';
        // Clear any event listeners by cloning
        const newEasyInput = easyInput.cloneNode(true);
        easyInput.parentNode.replaceChild(newEasyInput, easyInput);
    }

    // 텍스트 초기화
    const textBg = document.getElementById('text-bg');
    if (textBg) {
        textBg.innerHTML = '';
        textBg.style.opacity = '1';
        textBg.classList.remove('clickable');
        textBg.style.pointerEvents = 'none';
    }

    // 회향 박스 및 통계 숨기기
    const dedicationBox = document.getElementById('dedication-box');
    if (dedicationBox) {
        dedicationBox.classList.remove('show');
        dedicationBox.style.display = 'none';
    }

    const typingStats = document.getElementById('typing-stats');
    if (typingStats) {
        typingStats.style.display = 'none';
    }

    // RAF cleanup
    if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = null;
    }

    // Reset all state
    showScreen('screen-select');
    sutraText = '';
    userTyped = '';
    bgSpans = [];
    currentSutraId = null;
    currentMode = 'traditional';
    typedIndices.clear();
    skippedIndices.clear();
    lastSpaceTime = 0;

    console.log('Session cleaned up - ready for new 사경');
}

// ========================================
// AI Navigation Button
// ========================================
document.addEventListener('DOMContentLoaded', () => {
    const aiNavButton = document.getElementById('ai-nav-button');
    if (aiNavButton) {
        aiNavButton.addEventListener('click', (event) => {
            // On mobile: redirect to main page AI section and prevent dropdown
            // On desktop: allow dropdown to open
            const isMobile = window.innerWidth <= 768;

            if (isMobile) {
                event.preventDefault();
                event.stopPropagation();
                // Redirect to index page AI section
                window.location.href = 'index.html#ai-tools';
            }
            // On desktop, do nothing - let dropdown work normally
        });
    }
});

// ========================================
// Expose functions globally for HTML onclick handlers
// ========================================
window.selectSutra = selectSutra;
window.goBack = goBack;
window.dedicate = dedicate;
