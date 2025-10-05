// ========================================
// 위빠사나 명상 - 정확한 타이머
// ========================================

let meditationDuration = 0; // 총 시간 (초)
let startTime = 0;
let timerInterval = null;
let audioContext = null;

// Performance: Cache DOM references (avoid repeated queries)
let cachedTimeDisplay = null;
let cachedProgressCircle = null;
const circumference = 2 * Math.PI * 140; // Pre-calculate constant

// Performance: Detect mobile devices and adjust behavior
const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
const updateInterval = isMobile ? 200 : 100; // Reduce update frequency on mobile

// Performance: Monitoring (enable in development)
const PERFORMANCE_MONITORING = false; // Set to true for debugging
let updateTimings = [];

// ========================================
// 마우스 빛 효과 (Performance Optimized)
// ========================================
const mouseLight = document.querySelector('.mouse-light');
// Performance: Skip mouse light on mobile devices
if (mouseLight && !isMobile) {
    let mouseX = 0;
    let mouseY = 0;
    let currentX = 0;
    let currentY = 0;
    let rafId = null;

    // Passive listener for better scroll performance
    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;

        // Schedule animation frame only if not already scheduled
        if (!rafId) {
            rafId = requestAnimationFrame(updateMouseLight);
        }
    }, { passive: true });

    function updateMouseLight() {
        // Smooth interpolation for buttery movement
        currentX += (mouseX - currentX) * 0.15;
        currentY += (mouseY - currentY) * 0.15;

        // Use transform for GPU acceleration
        mouseLight.style.transform = `translate3d(${currentX - 300}px, ${currentY - 300}px, 0)`;

        // Continue animating if not at target
        if (Math.abs(mouseX - currentX) > 0.5 || Math.abs(mouseY - currentY) > 0.5) {
            rafId = requestAnimationFrame(updateMouseLight);
        } else {
            rafId = null;
        }
    }
}

// ========================================
// 수행 안내 토글
// ========================================
function toggleGuidance() {
    const toggle = document.querySelector('.guidance-toggle');
    const content = document.getElementById('guidance-content');

    if (!toggle || !content) {
        console.error('Toggle or content element not found');
        return;
    }

    const isExpanded = toggle.getAttribute('aria-expanded') === 'true';

    if (isExpanded) {
        toggle.setAttribute('aria-expanded', 'false');
        toggle.setAttribute('aria-label', '호흡 마음챙김 수행 안내 열기');
        content.classList.add('closed');
    } else {
        toggle.setAttribute('aria-expanded', 'true');
        toggle.setAttribute('aria-label', '호흡 마음챙김 수행 안내 닫기');
        content.classList.remove('closed');
    }
}

// ========================================
// DOM 초기화 (Event Listeners)
// ========================================
document.addEventListener('DOMContentLoaded', () => {
    console.log('Meditation timer initialized');

    // 수행 안내 토글 이벤트 바인딩
    const guidanceToggle = document.querySelector('.guidance-toggle');
    if (guidanceToggle) {
        guidanceToggle.addEventListener('click', toggleGuidance);

        guidanceToggle.addEventListener('touchstart', (e) => {
            e.preventDefault();
            toggleGuidance();
        }, { passive: false });

        console.log('Guidance toggle bound successfully');
    }

    // 기간 선택 카드 이벤트 바인딩
    const durationCards = document.querySelectorAll('.duration-cards .card');
    durationCards.forEach(card => {
        const duration = parseInt(card.getAttribute('data-duration'));

        // Click event
        card.addEventListener('click', () => {
            console.log(`Starting ${duration} minute meditation`);
            startMeditation(duration);
        });

        // Touch event for mobile (better responsiveness)
        card.addEventListener('touchstart', (e) => {
            e.preventDefault(); // Prevent double-firing
            console.log(`Touch: Starting ${duration} minute meditation`);
            startMeditation(duration);
        }, { passive: false });

        // Keyboard accessibility
        card.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                console.log(`Keyboard: Starting ${duration} minute meditation`);
                startMeditation(duration);
            }
        });
    });

    // 맞춤 시간 버튼
    const customBtn = document.getElementById('custom-start-btn');
    if (customBtn) {
        customBtn.addEventListener('click', () => {
            console.log('Custom meditation start clicked');
            startCustomMeditation();
        });

        customBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            console.log('Touch: Custom meditation start');
            startCustomMeditation();
        }, { passive: false });
    }

    // 맞춤 시간 입력 Enter 키
    const customInput = document.getElementById('custom-minutes');
    if (customInput) {
        customInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                console.log('Enter pressed on custom input');
                startCustomMeditation();
            }
        });
    }

    // 중단 버튼
    const stopBtn = document.getElementById('stop-btn');
    if (stopBtn) {
        stopBtn.addEventListener('click', () => {
            console.log('Stop meditation clicked');
            stopMeditation();
        });

        stopBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            console.log('Touch: Stop meditation');
            stopMeditation();
        }, { passive: false });
    }

    // 다시 시작 버튼
    const returnBtn = document.getElementById('return-btn');
    if (returnBtn) {
        returnBtn.addEventListener('click', () => {
            console.log('Return to setup clicked');
            returnToSetup();
        });

        returnBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            console.log('Touch: Return to setup');
            returnToSetup();
        }, { passive: false });
    }

    console.log('All event listeners bound successfully');
});

// ========================================
// 화면 전환 (Performance Optimized)
// ========================================
function showScreen(id) {
    const currentScreen = document.querySelector('.screen.show');

    if (currentScreen) {
        // Performance: Use GPU-accelerated transform + opacity
        currentScreen.classList.add('screen-exit');

        // Wait for exit animation to complete
        setTimeout(() => {
            currentScreen.classList.remove('show', 'screen-exit');

            const newScreen = document.getElementById(id);
            newScreen.classList.add('show', 'screen-enter');

            // Trigger GPU-accelerated entrance
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    newScreen.classList.remove('screen-enter');
                });
            });
        }, 300);
    } else {
        const newScreen = document.getElementById(id);
        newScreen.classList.add('show');
    }
}

// ========================================
// 명상 시작
// ========================================
function startMeditation(minutes) {
    meditationDuration = minutes * 60; // 분을 초로 변환
    beginMeditation();
}

function startCustomMeditation() {
    const input = document.getElementById('custom-minutes');
    const rawValue = input.value.trim();

    // Reject non-numeric input (security: prevent XSS/injection)
    if (!/^\d+$/.test(rawValue)) {
        alert('숫자만 입력해주세요.');
        input.value = '';
        return;
    }

    const minutes = parseInt(rawValue, 10);

    // Range validation
    if (isNaN(minutes) || minutes < 1 || minutes > 120) {
        alert('1분에서 120분 사이의 시간을 입력해주세요.');
        input.value = '';
        return;
    }

    meditationDuration = minutes * 60;
    beginMeditation();
}

function beginMeditation() {
    // 벨 소리 재생 (시작)
    playBell();

    // 명상 화면으로 전환
    showScreen('screen-meditation');

    // 타이머 시작 (화면 전환 후)
    setTimeout(() => {
        startTime = performance.now();
        updateTimer();
        // Performance: Adaptive update interval (200ms on mobile, 100ms on desktop)
        timerInterval = setInterval(updateTimer, updateInterval);
    }, 300); // Reduced from 600ms to match new animation duration
}

// ========================================
// 타이머 업데이트 (Performance Optimized)
// ========================================
function updateTimer() {
    const startMeasure = PERFORMANCE_MONITORING ? performance.now() : 0;

    // Performance: Single timestamp read
    const elapsed = (performance.now() - startTime) / 1000;
    const remaining = Math.max(0, meditationDuration - elapsed);

    // Performance: Batch DOM reads/writes, use cached references
    if (!cachedTimeDisplay) {
        cachedTimeDisplay = document.getElementById('time-remaining');
        cachedProgressCircle = document.querySelector('.progress-ring-circle');
    }

    // Calculate values before any DOM manipulation
    const minutes = Math.floor(remaining / 60);
    const seconds = Math.floor(remaining % 60);
    const progress = remaining / meditationDuration;
    const offset = circumference * (1 - progress);

    // Batch DOM writes together (minimize reflow)
    requestAnimationFrame(() => {
        // Update time display
        cachedTimeDisplay.textContent =
            `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

        // Update progress ring
        cachedProgressCircle.style.strokeDashoffset = offset;
    });

    // Performance monitoring
    if (PERFORMANCE_MONITORING) {
        const duration = performance.now() - startMeasure;
        updateTimings.push(duration);

        // Log every 50 updates
        if (updateTimings.length === 50) {
            const avg = updateTimings.reduce((a, b) => a + b, 0) / updateTimings.length;
            const max = Math.max(...updateTimings);
            console.log(`Timer Update Performance - Avg: ${avg.toFixed(2)}ms, Max: ${max.toFixed(2)}ms`);
            updateTimings = [];
        }
    }

    // Completion check
    if (remaining <= 0) {
        clearInterval(timerInterval);
        timerInterval = null;
        completeMeditation();
    }
}

// ========================================
// 명상 완료
// ========================================
function completeMeditation() {
    // 벨 소리 재생 (완료)
    playBell();

    // 완료 화면으로 전환
    setTimeout(() => {
        showScreen('screen-complete');
    }, 500);
}

// ========================================
// 명상 중단
// ========================================
function stopMeditation() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }

    // Performance: Use cached reference if available
    if (cachedProgressCircle) {
        cachedProgressCircle.style.strokeDashoffset = circumference;
    }

    // Reset cache for next session
    cachedTimeDisplay = null;
    cachedProgressCircle = null;

    // 설정 화면으로 돌아가기
    showScreen('screen-setup');
}

// ========================================
// 설정 화면으로 돌아가기
// ========================================
function returnToSetup() {
    // Performance: Use cached reference or query if needed
    const progressCircle = cachedProgressCircle || document.querySelector('.progress-ring-circle');
    if (progressCircle) {
        progressCircle.style.strokeDashoffset = circumference;
    }

    // Reset cache for next session
    cachedTimeDisplay = null;
    cachedProgressCircle = null;

    showScreen('screen-setup');
}

// ========================================
// 벨 소리 (Web Audio API로 생성)
// ========================================
function playBell() {
    // AudioContext 초기화 (첫 사용자 상호작용 후)
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }

    // 명상 벨 소리 (Singing Bowl 스타일)
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);

    // 주파수: 432Hz (명상용 주파수)
    oscillator.frequency.setValueAtTime(432, audioContext.currentTime);
    oscillator.type = 'sine';

    // 볼륨 페이드 (2초간)
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 2);

    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 2);
}
