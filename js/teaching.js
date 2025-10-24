// ========================================
// 교학 페이지 - 사성제 인터랙티브 다이어그램
// ========================================

let FOUR_TRUTHS = {};
let EIGHTFOLD_PATH = {};
let dataLoaded = false;

// Load teaching data from JSON
async function loadTeachingData() {
    try {
        const response = await fetch('data/teachings.json');
        if (!response.ok) {
            throw new Error(`Failed to load teachings.json: ${response.status}`);
        }

        const data = await response.json();
        FOUR_TRUTHS = data.fourTruths;
        EIGHTFOLD_PATH = data.eightfoldPath;
        dataLoaded = true;

        console.log('✅ Teaching data loaded successfully');
        return true;
    } catch (error) {
        console.error('❌ Failed to load teaching data:', error);
        throw error;
    }
}

// Initialize data loading
const dataLoadedPromise = loadTeachingData();

// DOM 초기화
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Teaching page initializing...');

    // Wait for data to load
    try {
        await dataLoadedPromise;
        console.log('Teaching page initialized with data');

        initializeDiagram();
        initializeEventListeners();
        animateConnections();
    } catch (error) {
        console.error('Failed to initialize teaching page:', error);
        alert('교학 데이터를 불러오는데 실패했습니다. 페이지를 새로고침해주세요.');
    }
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
