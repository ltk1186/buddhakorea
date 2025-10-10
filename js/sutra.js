// ========================================
// 전자 사경 - 단순하고 확실한 기능
// ========================================

import { SUTRA_DATA as SUTRAS, getSutraById, getAnimationClass } from './sutra-data.js';

let sutraText = '';
let userTyped = '';
let bgSpans = []; // Cached DOM references
let rafId = null; // RequestAnimationFrame ID for debouncing
let currentSutraId = null; // Track currently selected sutra for animations

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
    currentSutraId = id; // Track for category-specific animations
    const sutra = SUTRAS[id];
    sutraText = sutra.text;
    userTyped = '';

    // 제목 설정 (subtitle도 표시)
    const sutraNameEl = document.getElementById('sutra-name');
    sutraNameEl.textContent = sutra.title;
    if (sutra.subtitle) {
        sutraNameEl.innerHTML = `${sutra.title}<span style="display:block;font-size:0.7em;margin-top:0.3em;opacity:0.7;">${sutra.subtitle}</span>`;
    }

    // 배경 텍스트 생성
    const textBg = document.getElementById('text-bg');
    textBg.innerHTML = '';
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < sutraText.length; i++) {
        const span = document.createElement('span');
        span.textContent = sutraText[i];
        fragment.appendChild(span);
    }
    textBg.appendChild(fragment);

    // Cache DOM references for performance
    bgSpans = Array.from(textBg.children);

    // 입력창 초기화
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

    console.log('Input initialized, element:', textInput);

    // 이벤트 설정 (한글 입력 지원)
    textInput.addEventListener('compositionstart', () => {
        textInput.isComposing = true;
        console.log('Composition started');
    });

    textInput.addEventListener('compositionupdate', (e) => {
        console.log('Composing:', e.data);
    });

    textInput.addEventListener('compositionend', (e) => {
        textInput.isComposing = false;
        console.log('Composition ended:', e.data);
        setTimeout(() => checkInput(), 0);
    });

    textInput.addEventListener('input', (e) => {
        console.log('Input event:', e.inputType, 'value:', textInput.value, 'isComposing:', textInput.isComposing);
        if (!textInput.isComposing) {
            checkInput();
        }
    });

    textInput.addEventListener('keydown', (e) => {
        console.log('Keydown:', e.key);
    });

    // 회향 박스 숨기기
    document.getElementById('dedication-box').classList.remove('show');

    // 화면 전환 및 포커스
    showScreen('screen-write');
    setTimeout(() => {
        textInput.focus();
        console.log('Input focused, active element:', document.activeElement);
    }, 200);
}

// ========================================
// 입력 검증 (최적화)
// ========================================
function checkInput() {
    const input = document.getElementById('text-input');
    const typed = input.value;

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
            console.log(`Mismatch at ${i}: typed="${typed[i]}" expected="${sutraText[i]}"`);
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
    if (userTyped.length === sutraText.length) {
        input.disabled = true;
        setTimeout(() => {
            const dedicationBox = document.getElementById('dedication-box');
            dedicationBox.classList.add('show');
            dedicationBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 600);
    }
}

// ========================================
// RAF로 시각 업데이트 스케줄링 (60fps)
// ========================================
function scheduleVisualUpdate() {
    if (!rafId) {
        rafId = requestAnimationFrame(() => {
            updateVisuals();
            rafId = null;
        });
    }
}

// ========================================
// 배치 시각 업데이트 (DOM 쿼리 제거)
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
// 회향
// ========================================
function dedicate(realm) {
    console.log('Dedication started for:', realm);

    // 회향 박스 숨기기
    document.getElementById('dedication-box').style.display = 'none';

    // 배경 텍스트 숨기기
    const textBg = document.getElementById('text-bg');
    textBg.style.opacity = '0';

    // 입력된 텍스트를 div overlay로 표시
    const textInput = document.getElementById('text-input');
    const text = textInput.value;

    // textarea 숨기기
    textInput.style.opacity = '0';

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
    chars.forEach(char => {
        const span = document.createElement('span');
        span.textContent = char;
        span.style.cssText = `
            color: #daa520;
            font-weight: 400;
            text-shadow: 0 0 20px rgba(218, 165, 32, 0.4), 0 0 40px rgba(218, 165, 32, 0.2);
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

    // 입력창 초기화 및 활성화
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

    // 텍스트 초기화
    const textBg = document.getElementById('text-bg');
    if (textBg) {
        textBg.innerHTML = '';
        textBg.style.opacity = '1';
    }

    // 회향 박스 숨기기 및 초기화
    const dedicationBox = document.getElementById('dedication-box');
    if (dedicationBox) {
        dedicationBox.classList.remove('show');
        dedicationBox.style.display = 'none';
    }

    // RAF cleanup
    if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = null;
    }

    showScreen('screen-select');
    sutraText = '';
    userTyped = '';
    bgSpans = [];
    currentSutraId = null;

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
