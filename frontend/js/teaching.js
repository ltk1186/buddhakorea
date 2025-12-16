// ========================================
// 교학 페이지 - 사성제 인터랙티브 다이어그램
// ========================================

let FOUR_TRUTHS = {};
let EIGHTFOLD_PATH = {};
let THIRTY_SEVEN_BPF = {};
let DEPENDENT_ORIGINATION = {};
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
        THIRTY_SEVEN_BPF = data.thirtySevenBPF;
        DEPENDENT_ORIGINATION = data.dependentOrigination;
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
        initialize37BPF();
        initializeDependentOrigination();
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

    // 방향키로 네비게이션
    document.addEventListener('keydown', handleKeyboardNavigation);

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

    // 키보드 네비게이션 상태 설정
    currentPanelType = 'truth';
    currentIndex = NAVIGATION_ORDER.truth.indexOf(truthId);

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

    // 키보드 네비게이션 상태 초기화
    currentPanelType = null;
    currentIndex = -1;

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

    // 키보드 네비게이션 상태 설정
    currentPanelType = 'path';
    currentIndex = NAVIGATION_ORDER.path.indexOf(pathId);

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

    // 키보드 네비게이션 상태 초기화
    currentPanelType = null;
    currentIndex = -1;

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
// 37보리분법 (37 Bodhi Factors)
// ========================================
function initialize37BPF() {
    const cards = document.querySelectorAll('.bpf-category-card');

    cards.forEach(card => {
        // Click event
        card.addEventListener('click', () => {
            const category = card.getAttribute('data-category');
            show37BPFDetail(category);
        });

        // Keyboard event
        card.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                const category = card.getAttribute('data-category');
                show37BPFDetail(category);
            }
        });
    });

    // Close button
    const closeBtn = document.getElementById('close-bpf-panel');
    if (closeBtn) {
        closeBtn.addEventListener('click', hide37BPFPanel);
    }

    // Panel background click
    const panel = document.getElementById('bpf-detail-panel');
    if (panel) {
        panel.addEventListener('click', (e) => {
            if (e.target === panel) {
                hide37BPFPanel();
            }
        });
    }

    console.log('37BPF initialized');
}

function show37BPFDetail(categoryId) {
    const category = THIRTY_SEVEN_BPF[categoryId];
    if (!category) {
        console.error('Category not found:', categoryId);
        return;
    }

    const panel = document.getElementById('bpf-detail-panel');
    const title = document.getElementById('bpf-panel-title');
    const pali = document.getElementById('bpf-panel-pali');
    const description = document.getElementById('bpf-panel-description');
    const teaching = document.getElementById('bpf-panel-teaching');
    const elementsList = document.getElementById('bpf-elements-list');

    // Special diagrams
    const balanceDiagram = document.getElementById('bpf-balance-diagram');
    const harmonyDiagram = document.getElementById('bpf-harmony-diagram');
    const tripleTraining = document.getElementById('bpf-triple-training');

    // Update content
    title.textContent = category.title;
    pali.textContent = `${category.pali} - ${category.korean}`;
    description.textContent = category.description;
    teaching.innerHTML = category.teaching;

    // Hide all special diagrams first
    balanceDiagram.style.display = 'none';
    harmonyDiagram.style.display = 'none';
    tripleTraining.style.display = 'none';

    // Show special diagrams for specific categories
    if (categoryId === 'indriya' || categoryId === 'bala') {
        // Balance diagram for 오근/오력
        balanceDiagram.style.display = 'block';
        renderBalanceDiagram(category);
    } else if (categoryId === 'bojjhanga') {
        // Harmony diagram for 칠각지
        harmonyDiagram.style.display = 'block';
        renderHarmonyDiagram(category);
    } else if (categoryId === 'magga') {
        // Triple training for 팔정도
        tripleTraining.style.display = 'block';
        renderTripleTraining(category);
    }

    // Render elements list
    elementsList.innerHTML = '';
    const elementsTitle = document.createElement('h4');
    elementsTitle.textContent = `${category.count}가지 요소`;
    elementsList.appendChild(elementsTitle);

    const list = document.createElement('div');
    list.className = 'elements-grid';

    category.elements.forEach((element, index) => {
        const item = document.createElement('div');
        item.className = 'element-item';
        item.innerHTML = `
            <div class="element-number">${index + 1}</div>
            <h5>${element.name}</h5>
            <p class="element-pali">${element.pali}</p>
            <p class="element-description">${element.description}</p>
            <p class="element-practice"><strong>수행:</strong> ${element.practice}</p>
            ${element.balance ? `<p class="element-balance"><strong>균형:</strong> ${element.balance}</p>` : ''}
            ${element.group ? `<p class="element-group"><strong>그룹:</strong> ${element.group}</p>` : ''}
            ${element.training ? `<p class="element-training"><strong>삼학:</strong> ${element.training}</p>` : ''}
        `;
        list.appendChild(item);
    });

    elementsList.appendChild(list);

    // Show panel
    panel.classList.add('show');

    // 키보드 네비게이션 상태 설정
    currentPanelType = 'bpf';
    currentIndex = NAVIGATION_ORDER.bpf.indexOf(categoryId);

    closeBtn.focus();

    console.log(`Showing 37BPF detail for: ${categoryId}`);
}

function renderBalanceDiagram(category) {
    const container = document.querySelector('#bpf-balance-diagram .balance-visualization');
    if (!category.balance) return;

    container.innerHTML = `
        <div class="balance-scale">
            <div class="balance-description">${category.balance.description}</div>
            ${category.balance.pairs.map(pair => `
                <div class="balance-pair">
                    <div class="balance-left">${pair.left}</div>
                    <div class="balance-symbol">⚖️</div>
                    <div class="balance-right">${pair.right}</div>
                    <div class="balance-principle">${pair.principle}</div>
                </div>
            `).join('')}
            <div class="balance-always">
                <div class="balance-always-label">항상 필요:</div>
                <div class="balance-always-value">${category.balance.always}</div>
            </div>
        </div>
    `;
}

function renderHarmonyDiagram(category) {
    const container = document.querySelector('#bpf-harmony-diagram .harmony-visualization');
    if (!category.harmony) return;

    container.innerHTML = `
        <div class="harmony-groups">
            <div class="harmony-principle">${category.harmony.principle}</div>
            ${category.harmony.groups.map(group => `
                <div class="harmony-group">
                    <h5>${group.name}</h5>
                    <div class="harmony-when">${group.when}</div>
                    <div class="harmony-elements">${group.elements.join(' • ')}</div>
                    <div class="harmony-effect">→ ${group.effect}</div>
                </div>
            `).join('')}
        </div>
    `;
}

function renderTripleTraining(category) {
    const container = document.querySelector('#bpf-triple-training .triple-training-visualization');
    if (!category.tripleTraining) return;

    container.innerHTML = `
        <div class="triple-training-grid">
            <div class="training-group sila">
                <h5>계(戒) - Sīla</h5>
                <div class="training-elements">${category.tripleTraining.sila.join(', ')}</div>
            </div>
            <div class="training-group samadhi">
                <h5>정(定) - Samādhi</h5>
                <div class="training-elements">${category.tripleTraining.samadhi.join(', ')}</div>
            </div>
            <div class="training-group panna">
                <h5>혜(慧) - Paññā</h5>
                <div class="training-elements">${category.tripleTraining.panna.join(', ')}</div>
            </div>
        </div>
    `;
}

function hide37BPFPanel() {
    const panel = document.getElementById('bpf-detail-panel');
    panel.classList.remove('show');

    // 키보드 네비게이션 상태 초기화
    currentPanelType = null;
    currentIndex = -1;

    console.log('37BPF panel closed');
}

// ========================================
// 12연기 (Dependent Origination)
// ========================================
let doCurrentMode = 'forward'; // 'forward' or 'reverse'
let doCurrentStep = 0;
let doAnimationInterval = null;

function initializeDependentOrigination() {
    // Toggle buttons
    const forwardBtn = document.getElementById('do-toggle-forward');
    const reverseBtn = document.getElementById('do-toggle-reverse');

    if (forwardBtn) {
        forwardBtn.addEventListener('click', () => {
            doCurrentMode = 'forward';
            forwardBtn.classList.add('active');
            reverseBtn.classList.remove('active');
            renderDODiagram();
            resetDOAnimation();
        });
    }

    if (reverseBtn) {
        reverseBtn.addEventListener('click', () => {
            doCurrentMode = 'reverse';
            reverseBtn.classList.add('active');
            forwardBtn.classList.remove('active');
            renderDODiagram();
            resetDOAnimation();
        });
    }

    // Playback controls
    const playBtn = document.getElementById('do-play');
    const pauseBtn = document.getElementById('do-pause');
    const resetBtn = document.getElementById('do-reset');
    const speedSlider = document.getElementById('do-speed');
    const speedLabel = document.getElementById('do-speed-label');

    if (playBtn) {
        playBtn.addEventListener('click', () => {
            startDOAnimation();
            playBtn.disabled = true;
            pauseBtn.disabled = false;
        });
    }

    if (pauseBtn) {
        pauseBtn.addEventListener('click', () => {
            pauseDOAnimation();
            playBtn.disabled = false;
            pauseBtn.disabled = true;
        });
    }

    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            resetDOAnimation();
            playBtn.disabled = false;
            pauseBtn.disabled = true;
        });
    }

    if (speedSlider) {
        speedSlider.addEventListener('input', (e) => {
            const speed = parseInt(e.target.value);
            speedLabel.textContent = `${(speed / 1000).toFixed(1)}초`;
            if (doAnimationInterval) {
                pauseDOAnimation();
                startDOAnimation();
            }
        });
    }

    // Initial render
    renderDODiagram();
    console.log('Dependent Origination initialized');
}

function renderDODiagram() {
    const svg = document.getElementById('dependent-origination-svg');
    const data = doCurrentMode === 'forward' ? DEPENDENT_ORIGINATION.forward : DEPENDENT_ORIGINATION.reverse;

    // Clear existing content
    svg.innerHTML = '';

    // Create circular layout
    const centerX = 400;
    const centerY = 400;
    const radius = 300;
    const steps = data.length;

    // Draw connecting circle
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', centerX);
    circle.setAttribute('cy', centerY);
    circle.setAttribute('r', radius);
    circle.setAttribute('fill', 'none');
    circle.setAttribute('stroke', '#daa520');
    circle.setAttribute('stroke-width', '2');
    circle.setAttribute('opacity', '0.2');
    svg.appendChild(circle);

    // Draw steps
    data.forEach((step, index) => {
        const angle = (index / steps) * 2 * Math.PI - Math.PI / 2; // Start from top
        const x = centerX + radius * Math.cos(angle);
        const y = centerY + radius * Math.sin(angle);

        // Create group for each step
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.classList.add('do-step');
        g.setAttribute('data-step', index);
        g.style.cursor = 'pointer';

        // Circle for step
        const stepCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        stepCircle.setAttribute('cx', x);
        stepCircle.setAttribute('cy', y);
        stepCircle.setAttribute('r', '35');
        stepCircle.setAttribute('fill', '#1a1a1a');
        stepCircle.setAttribute('stroke', '#daa520');
        stepCircle.setAttribute('stroke-width', '2');
        g.appendChild(stepCircle);

        // Number
        const number = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        number.setAttribute('x', x);
        number.setAttribute('y', y - 5);
        number.setAttribute('text-anchor', 'middle');
        number.setAttribute('class', 'do-step-number');
        number.textContent = step.number;
        g.appendChild(number);

        // Short name (extract first word)
        const shortName = step.name.split(' ')[0];
        const name = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        name.setAttribute('x', x);
        name.setAttribute('y', y + 15);
        name.setAttribute('text-anchor', 'middle');
        name.setAttribute('class', 'do-step-name');
        name.textContent = shortName;
        g.appendChild(name);

        // Click handler
        g.addEventListener('click', () => {
            showDOStep(index);
        });

        svg.appendChild(g);

        // Draw arrow to next step
        if (index < steps - 1) {
            const nextAngle = ((index + 1) / steps) * 2 * Math.PI - Math.PI / 2;
            const nextX = centerX + radius * Math.cos(nextAngle);
            const nextY = centerY + radius * Math.sin(nextAngle);

            const arrow = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            arrow.setAttribute('d', `M ${x} ${y} Q ${centerX} ${centerY} ${nextX} ${nextY}`);
            arrow.setAttribute('fill', 'none');
            arrow.setAttribute('stroke', '#daa520');
            arrow.setAttribute('stroke-width', '1.5');
            arrow.setAttribute('opacity', '0.3');
            arrow.setAttribute('marker-end', 'url(#arrowhead)');
            svg.insertBefore(arrow, svg.firstChild); // Insert before circles
        }
    });

    // Add arrowhead marker
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
    marker.setAttribute('id', 'arrowhead');
    marker.setAttribute('markerWidth', '10');
    marker.setAttribute('markerHeight', '10');
    marker.setAttribute('refX', '5');
    marker.setAttribute('refY', '3');
    marker.setAttribute('orient', 'auto');
    const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    polygon.setAttribute('points', '0 0, 10 3, 0 6');
    polygon.setAttribute('fill', '#daa520');
    polygon.setAttribute('opacity', '0.3');
    marker.appendChild(polygon);
    defs.appendChild(marker);
    svg.insertBefore(defs, svg.firstChild);

    // Center label
    const centerLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    centerLabel.setAttribute('x', centerX);
    centerLabel.setAttribute('y', centerY - 10);
    centerLabel.setAttribute('text-anchor', 'middle');
    centerLabel.setAttribute('class', 'center-label');
    centerLabel.textContent = '12연기';
    svg.appendChild(centerLabel);

    const centerSublabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    centerSublabel.setAttribute('x', centerX);
    centerSublabel.setAttribute('y', centerY + 15);
    centerSublabel.setAttribute('text-anchor', 'middle');
    centerSublabel.setAttribute('class', 'center-sublabel');
    centerSublabel.textContent = doCurrentMode === 'forward' ? '順觀' : '逆觀';
    svg.appendChild(centerSublabel);
}

function showDOStep(stepIndex) {
    doCurrentStep = stepIndex;
    const data = doCurrentMode === 'forward' ? DEPENDENT_ORIGINATION.forward : DEPENDENT_ORIGINATION.reverse;
    const step = data[stepIndex];

    // Update step panel
    document.getElementById('do-step-title').textContent = step.name;
    document.getElementById('do-step-pali').textContent = step.pali;
    document.getElementById('do-step-description').textContent = step.description;
    document.getElementById('do-step-condition').textContent = step.condition;
    document.getElementById('do-step-teaching').innerHTML = step.teaching;

    // Highlight current step
    const steps = document.querySelectorAll('.do-step');
    steps.forEach((s, i) => {
        if (i === stepIndex) {
            s.classList.add('active');
        } else {
            s.classList.remove('active');
        }
    });

    console.log(`Showing DO step ${stepIndex + 1}: ${step.name}`);
}

function startDOAnimation() {
    const speed = parseInt(document.getElementById('do-speed').value);
    const data = doCurrentMode === 'forward' ? DEPENDENT_ORIGINATION.forward : DEPENDENT_ORIGINATION.reverse;

    doAnimationInterval = setInterval(() => {
        showDOStep(doCurrentStep);
        doCurrentStep = (doCurrentStep + 1) % data.length;
    }, speed);
}

function pauseDOAnimation() {
    if (doAnimationInterval) {
        clearInterval(doAnimationInterval);
        doAnimationInterval = null;
    }
}

function resetDOAnimation() {
    pauseDOAnimation();
    doCurrentStep = 0;
    document.getElementById('do-step-title').textContent = '12연기를 클릭하여 시작하세요';
    document.getElementById('do-step-pali').textContent = '';
    document.getElementById('do-step-description').textContent = '';
    document.getElementById('do-step-condition').textContent = '';
    document.getElementById('do-step-teaching').textContent = '';

    // Remove all highlights
    const steps = document.querySelectorAll('.do-step');
    steps.forEach(s => s.classList.remove('active'));
}

// ========================================
// 키보드 네비게이션
// ========================================
let currentPanelType = null; // 'truth', 'path', 'bpf', null
let currentIndex = -1;

// 네비게이션 순서 정의
const NAVIGATION_ORDER = {
    truth: ['dukkha', 'samudaya', 'nirodha', 'magga'],
    path: ['right-view', 'right-intention', 'right-speech', 'right-action',
           'right-livelihood', 'right-effort', 'right-mindfulness', 'right-concentration'],
    bpf: ['satipatthana', 'sammappadhana', 'iddhipada', 'indriya', 'bala', 'bojjhanga', 'magga']
};

// 섹션 순서 정의 (위/아래 키 네비게이션)
const SECTION_ORDER = ['truth', 'path', 'bpf'];

// 현재 열린 패널을 조용히 닫기 (상태는 유지하지 않음)
function closeCurrentPanelSilently() {
    // 모든 패널 닫기
    const truthPanel = document.getElementById('truth-explanation');
    const pathPanel = document.getElementById('path-explanation');
    const bpfPanel = document.getElementById('bpf-detail-panel');

    if (truthPanel) truthPanel.classList.remove('show');
    if (pathPanel) pathPanel.classList.remove('show');
    if (bpfPanel) bpfPanel.classList.remove('show');

    // currentPanelType과 currentIndex는 초기화하지 않음 (handleKeyboardNavigation에서 업데이트됨)
}

function handleKeyboardNavigation(e) {
    // 패널이 열려있지 않으면 무시
    if (currentPanelType === null) return;

    // 방향키만 처리
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) return;

    e.preventDefault();

    // 위/아래 키: 섹션 간 이동
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        const currentSectionIndex = SECTION_ORDER.indexOf(currentPanelType);
        let nextSectionIndex;

        if (e.key === 'ArrowDown') {
            nextSectionIndex = (currentSectionIndex + 1) % SECTION_ORDER.length;
        } else {
            nextSectionIndex = (currentSectionIndex - 1 + SECTION_ORDER.length) % SECTION_ORDER.length;
        }

        const nextSectionType = SECTION_ORDER[nextSectionIndex];
        const nextId = NAVIGATION_ORDER[nextSectionType][0]; // 첫 번째 항목으로 이동

        // 현재 패널 닫기 (애니메이션 없이)
        closeCurrentPanelSilently();

        // 패널 타입에 따라 적절한 함수 호출
        if (nextSectionType === 'truth') {
            showExplanation(nextId);
        } else if (nextSectionType === 'path') {
            showPathExplanation(nextId);
        } else if (nextSectionType === 'bpf') {
            show37BPFDetail(nextId);
        }
        return;
    }

    // 좌우 키: 같은 섹션 내 이동
    const order = NAVIGATION_ORDER[currentPanelType];
    if (!order) return;

    // 다음/이전 인덱스 계산
    if (e.key === 'ArrowRight') {
        currentIndex = (currentIndex + 1) % order.length;
    } else if (e.key === 'ArrowLeft') {
        currentIndex = (currentIndex - 1 + order.length) % order.length;
    }

    const nextId = order[currentIndex];

    // 패널 타입에 따라 적절한 함수 호출
    if (currentPanelType === 'truth') {
        showExplanation(nextId);
    } else if (currentPanelType === 'path') {
        showPathExplanation(nextId);
    } else if (currentPanelType === 'bpf') {
        show37BPFDetail(nextId);
    }
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
