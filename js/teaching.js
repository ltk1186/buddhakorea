// ========================================
// 교학 페이지 - 사성제 인터랙티브 다이어그램
// ========================================

// 사성제 데이터
const FOUR_TRUTHS = {
    dukkha: {
        title: "고제 (苦諦)",
        pali: "Dukkha-ariyasacca",
        korean: "괴로움의 진리",
        description: "삶에는 괴로움이 있습니다. 태어남, 늙음, 병듦, 죽음, 사랑하는 것과 헤어짐, 싫은 것과 만남, 원하는 것을 얻지 못함 - 이 모든 것이 괴로움입니다. 요약하면, 집착하는 오온(五蘊)이 괴로움입니다.",
        source: "<strong>출처:</strong> 상윳따 니까야 56.11 (전법륜경, Dhammacakkappavattana Sutta)<br><strong>번역:</strong> Bhikkhu Bodhi, The Connected Discourses of the Buddha<br><strong>해설:</strong> 각묵 스님, 초기불교 강의"
    },
    samudaya: {
        title: "집제 (集諦)",
        pali: "Dukkha-samudaya-ariyasacca",
        korean: "괴로움의 원인에 대한 진리",
        description: "괴로움의 원인은 갈애(渴愛, taṇhā)입니다. 감각적 쾌락에 대한 갈애, 존재에 대한 갈애, 비존재에 대한 갈애 - 이러한 갈애가 재생(再生)을 일으키며, 기쁨과 욕망을 동반하여 여기저기서 즐거움을 찾습니다.",
        source: "<strong>출처:</strong> 상윳따 니까야 56.11 (전법륜경)<br><strong>핵심 개념:</strong> 탐(貪), 진(瞋), 치(癡) 삼독(三毒)이 갈애의 근본<br><strong>관련 경전:</strong> 아비담마 - 마음의 작용 분석"
    },
    nirodha: {
        title: "멸제 (滅諦)",
        pali: "Dukkha-nirodha-ariyasacca",
        korean: "괴로움의 소멸에 대한 진리",
        description: "괴로움의 소멸은 갈애의 완전한 소멸입니다. 갈애를 여의고, 버리고, 놓아주고, 집착하지 않는 것 - 이것이 괴로움의 소멸(열반, Nibbāna)입니다. 갈애가 남김없이 사라지면 괴로움도 완전히 소멸합니다.",
        source: "<strong>출처:</strong> 상윳따 니까야 56.11 (전법륜경)<br><strong>실현:</strong> 아라한과(阿羅漢果) - 번뇌가 완전히 소멸된 상태<br><strong>체험:</strong> 위빠사나 명상을 통한 무상·고·무아의 직관"
    },
    magga: {
        title: "도제 (道諦)",
        pali: "Dukkha-nirodha-gāminī-paṭipadā-ariyasacca",
        korean: "괴로움의 소멸로 가는 길에 대한 진리",
        description: "괴로움의 소멸로 가는 길은 팔정도(八正道)입니다. 정견(正見), 정사유(正思惟), 정어(正語), 정업(正業), 정명(正命), 정정진(正精進), 정념(正念), 정정(正定) - 이 여덟 가지 바른 길을 실천하면 괴로움의 소멸에 이릅니다.",
        source: "<strong>출처:</strong> 상윳따 니까야 56.11 (전법륜경)<br><strong>실천:</strong> 계(戒)·정(定)·혜(慧) 삼학(三學)으로 분류<br><strong>연계:</strong> Buddha Korea의 사경, 명상, AI 학습이 모두 팔정도 실천"
    }
};

// 팔정도 데이터
const EIGHTFOLD_PATH = {
    'right-view': {
        title: "정견 (正見)",
        pali: "Sammā-diṭṭhi",
        korean: "바른 견해",
        description: "사성제에 대한 올바른 이해입니다. 괴로움, 괴로움의 원인, 괴로움의 소멸, 소멸로 가는 길을 바르게 아는 것입니다. 또한 업(業)과 그 과보, 무상·고·무아의 삼특상을 이해하는 것입니다.",
        source: "<strong>출처:</strong> 상윳따 니까야 56.11 (전법륜경)<br><strong>분류:</strong> 혜(慧)에 속함<br><strong>실천:</strong> Buddha Korea의 교학 학습과 AI 대화를 통한 바른 이해"
    },
    'right-intention': {
        title: "정사유 (正思惟)",
        pali: "Sammā-saṅkappa",
        korean: "바른 사유",
        description: "출리(出離)에 대한 사유, 악의 없음에 대한 사유, 해치지 않음에 대한 사유입니다. 감각적 쾌락을 버리고, 자애와 연민의 마음을 일으키며, 모든 존재에게 해를 끼치지 않으려는 의도입니다.",
        source: "<strong>출처:</strong> 상윳따 니까야 56.11 (전법륜경)<br><strong>분류:</strong> 혜(慧)에 속함<br><strong>실천:</strong> 명상과 회향을 통한 자비심 함양"
    },
    'right-speech': {
        title: "정어 (正語)",
        pali: "Sammā-vācā",
        korean: "바른 말",
        description: "거짓말을 하지 않고, 이간질하지 않으며, 욕설하지 않고, 잡담하지 않는 것입니다. 진실하고, 화합을 돕고, 부드러우며, 의미 있는 말을 하는 것입니다.",
        source: "<strong>출처:</strong> 상윳따 니까야 56.11 (전법륜경)<br><strong>분류:</strong> 계(戒)에 속함<br><strong>실천:</strong> 일상에서 말의 마음챙김"
    },
    'right-action': {
        title: "정업 (正業)",
        pali: "Sammā-kammanta",
        korean: "바른 행위",
        description: "살생하지 않고, 주지 않은 것을 취하지 않으며, 삿된 음행을 하지 않는 것입니다. 생명을 존중하고, 정직하며, 성적 행위에서 절제하는 것입니다.",
        source: "<strong>출처:</strong> 상윳따 니까야 56.11 (전법륜경)<br><strong>분류:</strong> 계(戒)에 속함<br><strong>실천:</strong> 오계(五戒)의 실천"
    },
    'right-livelihood': {
        title: "정명 (正命)",
        pali: "Sammā-ājīva",
        korean: "바른 생계",
        description: "부정한 생계 수단을 버리고 바른 생계 수단으로 살아가는 것입니다. 무기 거래, 생명 거래, 고기 거래, 술 거래, 독약 거래 등 해로운 직업을 피하고, 정직하고 해롭지 않은 방법으로 생계를 유지합니다.",
        source: "<strong>출처:</strong> 상윳따 니까야 56.11 (전법륜경)<br><strong>분류:</strong> 계(戒)에 속함<br><strong>실천:</strong> 직업 윤리와 생활 방식의 성찰"
    },
    'right-effort': {
        title: "정정진 (正精進)",
        pali: "Sammā-vāyāma",
        korean: "바른 노력",
        description: "일어나지 않은 악을 일어나지 않게 하고, 이미 일어난 악을 제거하며, 일어나지 않은 선을 일으키고, 이미 일어난 선을 증장시키려는 노력입니다. 사정근 - 네 가지 바른 노력을 실천합니다.",
        source: "<strong>출처:</strong> 상윳따 니까야 56.11 (전법륜경)<br><strong>분류:</strong> 정(定)에 속함<br><strong>실천:</strong> 마음 상태의 지속적 관찰과 조절"
    },
    'right-mindfulness': {
        title: "정념 (正念)",
        pali: "Sammā-sati",
        korean: "바른 마음챙김",
        description: "몸, 느낌, 마음, 법에 대한 마음챙김입니다. 사념처(四念處) - 몸을 몸으로, 느낌을 느낌으로, 마음을 마음으로, 법을 법으로 관찰합니다. 현재 순간에 깨어 있는 알아차림입니다.",
        source: "<strong>출처:</strong> 상윳따 니까야 56.11 (전법륜경)<br><strong>분류:</strong> 정(定)에 속함<br><strong>실천:</strong> Buddha Korea의 호흡 명상과 위빠사나 수행"
    },
    'right-concentration': {
        title: "정정 (正定)",
        pali: "Sammā-samādhi",
        korean: "바른 집중",
        description: "선정(禪定), 즉 마음의 고요한 집중 상태입니다. 초선(初禪), 이선(二禪), 삼선(三禪), 사선(四禪)의 사선정(四禪定)을 통해 마음을 하나의 대상에 안정되게 집중시킵니다.",
        source: "<strong>출처:</strong> 상윳따 니까야 56.11 (전법륜경)<br><strong>분류:</strong> 정(定)에 속함<br><strong>실천:</strong> 명상 타이머를 통한 지속적 수행"
    }
};

// DOM 초기화
document.addEventListener('DOMContentLoaded', () => {
    console.log('Teaching page initialized');

    initializeDiagram();
    initializeEventListeners();
    animateConnections();
});

// ========================================
// 다이어그램 초기화
// ========================================
function initializeDiagram() {
    // Scroll reveal 애니메이션
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

    revealElements.forEach(element => {
        observer.observe(element);
    });

    console.log('Diagram initialized');
}

// ========================================
// 이벤트 리스너
// ========================================
function initializeEventListeners() {
    // 사성제 카드 클릭
    const truthCards = document.querySelectorAll('.truth-card');
    truthCards.forEach(card => {
        // Click event
        card.addEventListener('click', () => {
            const truthId = card.getAttribute('data-truth');
            console.log(`Truth card clicked: ${truthId}`);
            showExplanation(truthId);
        });

        // Touch event for mobile
        card.addEventListener('touchstart', (e) => {
            // e.preventDefault(); // 주석: 스크롤 방해하지 않도록
            const truthId = card.getAttribute('data-truth');
            console.log(`Truth card touched: ${truthId}`);
        }, { passive: true });

        // Keyboard accessibility
        card.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                const truthId = card.getAttribute('data-truth');
                showExplanation(truthId);
            }
        });

        // Add tabindex for keyboard navigation
        card.setAttribute('tabindex', '0');
        card.setAttribute('role', 'button');
        card.setAttribute('aria-label', `${FOUR_TRUTHS[card.getAttribute('data-truth')].title} 설명 보기`);
    });

    // 팔정도 카드 클릭
    const pathCards = document.querySelectorAll('.path-card');
    pathCards.forEach(card => {
        // Click event
        card.addEventListener('click', () => {
            const pathId = card.getAttribute('data-path');
            console.log(`Path card clicked: ${pathId}`);
            showPathExplanation(pathId);
        });

        // Touch event for mobile
        card.addEventListener('touchstart', (e) => {
            const pathId = card.getAttribute('data-path');
            console.log(`Path card touched: ${pathId}`);
        }, { passive: true });

        // Keyboard accessibility
        card.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                const pathId = card.getAttribute('data-path');
                showPathExplanation(pathId);
            }
        });

        // Add tabindex for keyboard navigation
        card.setAttribute('tabindex', '0');
        card.setAttribute('role', 'button');
        card.setAttribute('aria-label', `${EIGHTFOLD_PATH[card.getAttribute('data-path')].title} 설명 보기`);
    });

    // 사성제 패널 닫기 버튼
    const closeBtn = document.getElementById('close-explanation');
    if (closeBtn) {
        closeBtn.addEventListener('click', hideExplanation);
        closeBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            hideExplanation();
        }, { passive: false });
    }

    // 팔정도 패널 닫기 버튼
    const closePathBtn = document.getElementById('close-path-explanation');
    if (closePathBtn) {
        closePathBtn.addEventListener('click', hidePathExplanation);
        closePathBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            hidePathExplanation();
        }, { passive: false });
    }

    // 사성제 패널 배경 클릭 시 닫기
    const panel = document.getElementById('truth-explanation');
    if (panel) {
        panel.addEventListener('click', (e) => {
            if (e.target === panel) {
                hideExplanation();
            }
        });
    }

    // 팔정도 패널 배경 클릭 시 닫기
    const pathPanel = document.getElementById('path-explanation');
    if (pathPanel) {
        pathPanel.addEventListener('click', (e) => {
            if (e.target === pathPanel) {
                hidePathExplanation();
            }
        });
    }

    // ESC 키로 패널 닫기
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            hideExplanation();
            hidePathExplanation();
        }
    });

    console.log('Event listeners bound successfully');
}

// ========================================
// 설명 패널 표시
// ========================================
function showExplanation(truthId) {
    const truth = FOUR_TRUTHS[truthId];
    if (!truth) {
        console.error('Truth not found:', truthId);
        return;
    }

    const panel = document.getElementById('truth-explanation');
    const title = document.getElementById('exp-title');
    const pali = document.getElementById('exp-pali');
    const description = document.getElementById('exp-description');
    const source = document.getElementById('exp-source');

    // 내용 업데이트
    title.textContent = truth.title;
    pali.textContent = `${truth.pali} - ${truth.korean}`;
    description.textContent = truth.description;
    source.innerHTML = truth.source;

    // 패널 표시
    panel.classList.add('show');

    // 접근성: focus 이동
    document.getElementById('close-explanation').focus();

    console.log(`Showing explanation for: ${truthId}`);
}

// ========================================
// 설명 패널 숨기기
// ========================================
function hideExplanation() {
    const panel = document.getElementById('truth-explanation');
    panel.classList.remove('show');

    console.log('Explanation panel closed');
}

// ========================================
// 팔정도 설명 패널 표시
// ========================================
function showPathExplanation(pathId) {
    const path = EIGHTFOLD_PATH[pathId];
    if (!path) {
        console.error('Path not found:', pathId);
        return;
    }

    const panel = document.getElementById('path-explanation');
    const title = document.getElementById('path-exp-title');
    const pali = document.getElementById('path-exp-pali');
    const description = document.getElementById('path-exp-description');
    const source = document.getElementById('path-exp-source');

    // 내용 업데이트
    title.textContent = path.title;
    pali.textContent = `${path.pali} - ${path.korean}`;
    description.textContent = path.description;
    source.innerHTML = path.source;

    // 패널 표시
    panel.classList.add('show');

    // 접근성: focus 이동
    document.getElementById('close-path-explanation').focus();

    console.log(`Showing path explanation for: ${pathId}`);
}

// ========================================
// 팔정도 설명 패널 숨기기
// ========================================
function hidePathExplanation() {
    const panel = document.getElementById('path-explanation');
    panel.classList.remove('show');

    console.log('Path explanation panel closed');
}

// ========================================
// 연결선 애니메이션
// ========================================
function animateConnections() {
    const connections = document.querySelectorAll('.connection-line');

    // 순차적으로 연결선 표시 (stagger animation)
    connections.forEach((line, index) => {
        setTimeout(() => {
            line.classList.add('visible');
        }, index * 600 + 1000); // 1초 후 시작, 각 0.6초 간격
    });

    console.log('Connection animations started');
}

// ========================================
// 유틸리티: 디바이스 감지
// ========================================
const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

if (isMobile) {
    console.log('Mobile device detected');
}

if (isTouchDevice) {
    console.log('Touch device detected');
}
