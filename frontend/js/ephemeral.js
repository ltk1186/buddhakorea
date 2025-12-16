// Ephemeral Sentences - 찰나의 문장
// 타이핑하는 순간 사라지는 글자를 통해 무상(anicca)을 체득

// ========================================
// 💡 커스터마이징 가이드
// ========================================
// 
// 📌 글자 사라지는 시간 조절:
//    FADE_DELAY (아래 참조) - 밀리초 단위
//    현재: 800ms (0.8초) - 타이핑 후 0.8초 뒤에 사라지기 시작
//    빠르게: 500 / 느리게: 1500
//
// 📌 애니메이션 스타일 변경:
//    CSS 파일의 .char-fade 클래스 참조
//    - charFadeUp: 위로 떠오름 (기본)
//    - charFadeDown: 아래로 떨어짐
//    - charFadeSpin: 회전하며 사라짐
//
// 📌 파티클 효과 활성화:
//    USE_PARTICLE_EFFECT를 true로 변경
//    각 글자가 무작위 방향으로 흩어짐
//
// ========================================

// 설정 값
const CONFIG = {
    FADE_DELAY: 3000,              // 글자 사라지기 시작까지 딜레이 (ms)
    USE_PARTICLE_EFFECT: false,   // true: 파티클 효과, false: 황금빛 연기 효과
    PARTICLE_DISTANCE: 150,       // 파티클이 흩어지는 거리 (px)
};

let typingTimer;
let canvas;
let isComposing = false; // Korean IME composition flag

// 모달 열기
function openEphemeralSentences() {
    const modal = document.getElementById('ephemeral-modal');
    modal.classList.add('active');
    
    // 캔버스 초기화
    setTimeout(() => {
        canvas = document.getElementById('ephemeral-canvas');
        canvas.focus();
        setupEventListeners();
    }, 100);
    
    // ESC 키로 닫기
    document.addEventListener('keydown', handleEscapeKey);
}

// 모달 닫기
function closeEphemeralSentences() {
    const modal = document.getElementById('ephemeral-modal');
    modal.classList.remove('active');
    
    // 캔버스 초기화
    if (canvas) {
        canvas.innerHTML = '';
    }
    
    document.removeEventListener('keydown', handleEscapeKey);
}

// ESC 키 핸들러
function handleEscapeKey(e) {
    if (e.key === 'Escape') {
        closeEphemeralSentences();
    }
}

// 이벤트 리스너 설정
function setupEventListeners() {
    if (!canvas) return;

    // 한글 조합 시작
    canvas.addEventListener('compositionstart', () => {
        isComposing = true;
    });

    // 한글 조합 중
    canvas.addEventListener('compositionupdate', () => {
        isComposing = true;
    });

    // 한글 조합 완료
    canvas.addEventListener('compositionend', () => {
        isComposing = false;
        setTimeout(() => handleInput(), 0); // Defer to next tick
    });

    // 타이핑 이벤트 (한글 조합 중이 아닐 때만 처리)
    canvas.addEventListener('input', handleInput);

    // 엔터키 처리 (줄바꿈)
    canvas.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            document.execCommand('insertLineBreak');
        }
    });
}

// 입력 처리
function handleInput() {
    // 한글 조합 중에는 처리하지 않음
    if (isComposing) {
        return;
    }

    clearTimeout(typingTimer);

    // 새로 입력된 글자들을 감지하고 래핑
    wrapNewCharacters();

    // 사라지는 타이머 시작
    typingTimer = setTimeout(() => {
        fadeCharacters();
    }, CONFIG.FADE_DELAY);
}

// 새로운 글자들을 span으로 래핑
// 새로운 글자들을 span으로 래핑
function wrapNewCharacters() {
    // 현재 커서 위치 저장
    const selection = window.getSelection();
    const range = selection.rangeCount > 0 ? selection.getRangeAt(0) : null;
    let cursorOffset = range ? range.startOffset : 0;
    let cursorNode = range ? range.startContainer : null;
    
    const walker = document.createTreeWalker(
        canvas,
        NodeFilter.SHOW_TEXT,
        null,
        false
    );
    
    const textNodes = [];
    let node;
    
    while (node = walker.nextNode()) {
        if (node.nodeValue.trim().length > 0 || node.nodeValue.includes(' ')) {
            textNodes.push(node);
        }
    }
    
    let newCursorNode = null;
    let newCursorOffset = 0;
    
    textNodes.forEach(textNode => {
        const parent = textNode.parentNode;
        
        if (parent.classList && parent.classList.contains('char-wrapper')) {
            return;
        }
        
        const fragment = document.createDocumentFragment();
        const text = textNode.nodeValue;
        const isCursorInThisNode = textNode === cursorNode;
        
        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            const span = document.createElement('span');
            span.className = 'char-wrapper';
            span.innerHTML = char === ' ' ? '&nbsp;' : char;
            span.dataset.timestamp = Date.now();
            fragment.appendChild(span);
            
            // 커서 위치 추적
            if (isCursorInThisNode && i === cursorOffset - 1) {
                newCursorNode = span;
                newCursorOffset = 1;
            }
        }
        
        // 마지막 글자 뒤에 커서가 있는 경우
        if (isCursorInThisNode && cursorOffset >= text.length) {
            const lastSpan = fragment.lastChild;
            if (lastSpan) {
                newCursorNode = lastSpan;
                newCursorOffset = 1;
            }
        }
        
        parent.replaceChild(fragment, textNode);
    });
    
    // 커서 위치 복원
    if (newCursorNode) {
        const newRange = document.createRange();
        const newSelection = window.getSelection();
        
        try {
            newRange.setStart(newCursorNode, newCursorOffset);
            newRange.collapse(true);
            newSelection.removeAllRanges();
            newSelection.addRange(newRange);
        } catch (e) {
            // 커서 복원 실패 시 맨 끝으로
            canvas.focus();
        }
    }
}

// 글자 사라지기 애니메이션 - 사경 회향과 완전히 동일하게
function fadeCharacters() {
    // 현재 캔버스의 텍스트 가져오기
    const text = canvas.textContent || canvas.innerText;

    if (!text || text.trim().length === 0) return;

    // Get computed styles from canvas to match exactly
    const canvasStyles = window.getComputedStyle(canvas);
    const canvasPadding = canvasStyles.padding;
    const canvasFontSize = canvasStyles.fontSize;
    const canvasFontWeight = canvasStyles.fontWeight;
    const canvasLineHeight = canvasStyles.lineHeight;

    // 새로운 애니메이션 컨테이너 생성 (캔버스와 완전히 동일한 위치/스타일)
    const charContainer = document.createElement('div');
    charContainer.id = 'ephemeral-char-container';
    charContainer.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        padding: ${canvasPadding};
        font-size: ${canvasFontSize};
        font-family: inherit;
        font-weight: ${canvasFontWeight};
        line-height: ${canvasLineHeight};
        white-space: pre-wrap;
        word-break: keep-all;
        pointer-events: none;
        z-index: 100;
        opacity: 1;
    `;

    // 각 글자를 span으로 감싸기 (사경과 완전히 동일)
    const chars = text.split('');
    chars.forEach(char => {
        const span = document.createElement('span');
        span.textContent = char;
        // 사경과 동일한 스타일
        span.style.cssText = `
            color: #daa520;
            font-weight: 400;
            text-shadow: 0 0 20px rgba(218, 165, 32, 0.4), 0 0 40px rgba(218, 165, 32, 0.2);
            display: inline;
        `;
        charContainer.appendChild(span);
    });

    // 모달 내에 컨테이너 추가
    const modalContent = document.querySelector('.ephemeral-input-wrapper');
    if (modalContent) {
        modalContent.appendChild(charContainer);
    }

    // 컨테이너가 DOM에 추가된 후 캔버스 숨기기 (레이아웃 shift 방지)
    requestAnimationFrame(() => {
        canvas.style.opacity = '0';
    });

    // 마지막 글자부터 순차적으로 애니메이션 (사경과 완전히 동일)
    const charSpans = charContainer.querySelectorAll('span');
    const totalDuration = 5000; // 5초 (사경과 동일)
    const delayPerChar = totalDuration / charSpans.length;

    charSpans.forEach((span, i) => {
        const reverseIndex = charSpans.length - 1 - i; // 마지막부터

        setTimeout(() => {
            span.classList.add('char-fade-ephemeral');
        }, reverseIndex * delayPerChar);
    });

    // 모든 애니메이션 완료 후 정리
    setTimeout(() => {
        // 컨테이너 제거
        if (charContainer.parentNode) {
            charContainer.parentNode.removeChild(charContainer);
        }

        // 캔버스 초기화
        canvas.innerHTML = '';
        canvas.style.opacity = '1';
        canvas.focus();
    }, totalDuration + 1200); // 5초 + 마지막 글자 애니메이션 1.2초
}

// 파티클 효과 적용
function applyParticleEffect(char) {
    // 무작위 방향으로 흩어짐
    const angle = Math.random() * Math.PI * 2;
    const distance = CONFIG.PARTICLE_DISTANCE;
    const tx = Math.cos(angle) * distance;
    const ty = Math.sin(angle) * distance;
    
    char.style.setProperty('--tx', `${tx}px`);
    char.style.setProperty('--ty', `${ty}px`);
    char.classList.add('particle-break');
}

// 모달 외부 클릭 시 닫기
document.addEventListener('click', (e) => {
    const modal = document.getElementById('ephemeral-modal');
    if (e.target === modal) {
        closeEphemeralSentences();
    }
});

// ========================================
// 📝 사용 예시 & 팁
// ========================================
//
// 1. 빠른 사라짐 효과:
//    CONFIG.FADE_DELAY = 500;
//
// 2. 파티클 효과 활성화:
//    CONFIG.USE_PARTICLE_EFFECT = true;
//    CONFIG.PARTICLE_DISTANCE = 150; (더 멀리)
//
// 3. 애니메이션 변경:
//    CSS에서 .char-fade의 animation을
//    charFadeDown 또는 charFadeSpin으로 변경
//
// 4. 글자 색상 변경:
//    CSS의 #ephemeral-canvas에서
//    color와 text-shadow 값 조정
//
// ========================================