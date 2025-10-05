// ========================================
// 전자 사경 - 단순하고 확실한 기능
// ========================================

const SUTRAS = {
    metta: {
        title: '자애경',
        text: `도닦음에 능숙한 자, 고요한 경지를 체험하면서 이처럼 행할지라.
유능하고 정직하고 진솔하며 고운 말에 온화하고 겸손하네.
만족하고 공양하기 쉽고 일 없고 검소하며
감관은 고요하여 슬기롭고 거만 떨지 않고 신도 집에 집착하지 않네.
현자가 나무랄 일은 그 어떤 것도 하지 않으니
원컨대 모든 중생 즐겁고 안녕하여 부디 행복할지라.
약하거나 강하거나 길거나 크거나 중간치이거나
짧거나 작거나 통통하거나 살아있는 생명이라면 모두 다
보이거나 보이지 않거나 멀리 있거나 가까이 있거나
태어났거나 앞으로 태어날, 그 모든 중생 부디 행복할지라.
남을 속이지 않고, 어떤 곳에서 어떤 이라도 경멸하지 않으며
성냄과 적개심으로 남의 불행을 바라지 않네.
어머니가 하나 밖에 없는 친아들을 목숨으로 보호하듯
모든 중생들을 향해 한량없는 마음을 개발할지라.
온 세상 위, 아래, 옆으로 장애와 원한과 증오를 넘어
한량없는 자애의 마음을 개발할지라.
섰거나 걷거나 앉았거나 누웠거나 깨어있을 때는 언제나
이 자애의 마음챙김을 개발할지니, 이를 일러 거룩한 삶이라 하네.
계행을 지닌 자, 사견을 따르지 않고 바른 견을 구족하여
감각적 욕망에 집착을 버려 다시는 모태에 들지 않으리라.`
    },
    mangala: {
        title: '행복경',
        text: `이와 같이 나는 들었다. 한 때 세존께서 사왓티의 제따 숲에 있는 급고독원에 머무셨다.
그 때 밤이 아주 깊어갈 즈음 어떤 천신이 아름다운 모습으로 제따 숲을 두루 환하게 밝히면서 세존께 다가왔다.
와서는 세존께 절을 올리고 한 곁에 섰다. 한 곁에 서서 그 천신은 세존께 시로써 이와 같이 말씀드렸다.
많은 천신들과 사람들은 안녕을 바라면서 행복에 대해 생각합니다.
무엇이 으뜸가는 행복인지 말씀해주십시오.
어리석은 사람을 섬기지 않고 현명한 사람을 섬기며 예경할 만한 사람을 예경하는 것, 이것이 으뜸가는 행복이라네.
그러한 적절한 곳에서 살고 일찍이 공덕을 쌓으며 자신을 바르게 확립하는 것, 이것이 으뜸가는 행복이라네.
많이 배우고 기술을 익히며 계행을 철저히 지니고 고운 말을 하는 것, 이것이 으뜸가는 행복이라네.
아버지와 어머니를 봉양하고 아내와 자식을 돌보며 생업에 충실한 것, 이것이 으뜸가는 행복이라네.
베풀고 여법하게 행하며 친척들을 보호하고 비난받을 일이 없는 행위를 하는 것, 이것이 으뜸가는 행복이라네.
불선법을 피하고 여의며 술 마시는 것을 절제하고 선법들을 향해 게으르지 않는 것, 이것이 으뜸가는 행복이라네.
존경하고 겸손하며 만족할 줄 알고 은혜를 알며 시시각각 가르침을 듣는 것, 이것이 으뜸가는 행복이라네.
인내하고 [도반의 말에] 순응하며 출가자를 만나고 때에 맞춰 법을 담론하는 것, 이것이 으뜸가는 행복이라네.
감각 기능을 단속하고 청정범행을 닦으며 [네 가지] 성스러운 진리를 보고 열반을 실현하는 것, 이것이 으뜸가는 행복이라네.
세상사에 부딪쳐 마음이 흔들리지 않고 슬픔 없고 티끌 없이 안온한 것, 이것이 으뜸가는 행복이라네.
이러한 것을 실천하면 어떤 곳에서건 패배하지 않고 모든 곳에서 안녕하리니, 이것이 그들에게 으뜸가는 행복이라네.`
    }
};

let sutraText = '';
let userTyped = '';
let bgSpans = []; // Cached DOM references
let rafId = null; // RequestAnimationFrame ID for debouncing

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
    const sutra = SUTRAS[id];
    sutraText = sutra.text;
    userTyped = '';

    // 제목 설정
    document.getElementById('sutra-name').textContent = sutra.title;

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

    // 마지막 글자부터 순차적으로 애니메이션 (5초 동안)
    const charSpans = charContainer.querySelectorAll('span');
    const totalDuration = 5000; // 5초
    const delayPerChar = totalDuration / charSpans.length;

    console.log('Starting animation for', charSpans.length, 'characters');

    charSpans.forEach((span, i) => {
        const reverseIndex = charSpans.length - 1 - i; // 마지막부터
        setTimeout(() => {
            span.classList.add('char-fade');
            console.log('Fading char', i);
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
    }

    // 텍스트 초기화
    const textBg = document.getElementById('text-bg');
    if (textBg) {
        textBg.innerHTML = '';
        textBg.style.opacity = '1';
    }

    showScreen('screen-select');
    sutraText = '';
    userTyped = '';
    bgSpans = [];
}
