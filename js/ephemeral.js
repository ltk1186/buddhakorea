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
    FADE_DELAY: 1500,              // 글자 사라지기 시작까지 딜레이 (ms)
    USE_PARTICLE_EFFECT: true,   // true: 파티클 효과, false: 기본 페이드
    PARTICLE_DISTANCE: 150,       // 파티클이 흩어지는 거리 (px)
};

let typingTimer;
let canvas;

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
    
    // 타이핑 이벤트 (한글 조합 완료 시에만 처리)
    canvas.addEventListener('input', handleInput);
    
    // 한글 조합 완료 감지
    canvas.addEventListener('compositionend', handleInput);
    
    // 엔터키 처리 (줄바꿈)
    canvas.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            document.execCommand('insertLineBreak');
        }
    });
}

// 입력 처리
function handleInput(e) {
    clearTimeout(typingTimer);
    
    // 한글 조합 중인지 확인 (IME composing)
    if (e && e.isComposing) {
        return; // 조합 중에는 처리하지 않음
    }
    
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

// 글자 사라지기 애니메이션
function fadeCharacters() {
    const chars = canvas.querySelectorAll('.char-wrapper:not(.char-fade)');
    
    chars.forEach((char, index) => {
        // 순차적으로 사라지기 (맨 앞부터)
        setTimeout(() => {
            if (CONFIG.USE_PARTICLE_EFFECT) {
                applyParticleEffect(char);
            } else {
                char.classList.add('char-fade');
            }
            
            // 애니메이션 완료 후 DOM에서 제거
            setTimeout(() => {
                if (char.parentNode) {
                    char.remove();
                }
            }, 2000); // CSS 애니메이션 duration과 맞춤
            
        }, index * 1000); // 각 글자마다 원하는 ms 딜레이
    });
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