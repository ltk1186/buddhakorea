/**
 * Full-Screen Scripture Library
 * Buddha Korea - AI Chatbot
 *
 * Features:
 * - Server-side filtering (search, tradition, theme)
 * - Infinite scroll with IntersectionObserver
 * - Focus trap and scroll lock
 * - Memory management (1000 card limit)
 * - WCAG 2.1 AA accessibility
 */

// ===== GLOBAL STATE =====

if (typeof window.API_BASE_URL === 'undefined') {
    const host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1') {
        window.API_BASE_URL = 'http://localhost:8000';
    } else if (host === 'ai.buddhakorea.com') {
        window.API_BASE_URL = '';
    } else {
        window.API_BASE_URL = 'https://ai.buddhakorea.com';
    }
}
const MAX_CACHED_CARDS = 1000;
const CARDS_PER_PAGE = 100;
const DEBOUNCE_DELAY = 300; // ms for search debouncing
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes cache TTL

let libraryState = {
    cards: [],
    filteredCards: [],
    totalCount: 0,
    currentOffset: 0,
    isLoading: false,
    hasMoreResults: true,
    filters: {
        search: '',
        tradition: '',
        theme: ''
    }
};

// API response cache
const apiCache = new Map();

// Debounce timer
let searchDebounceTimer = null;

let focusTrap = {
    active: false,
    firstFocusable: null,
    lastFocusable: null,
    previousFocus: null
};

let scrollObserver = null;

// ===== INITIALIZATION =====

// Listen for metadata loaded event
window.onLibraryMetadataLoaded = function(metadata) {
    populateLibraryFilters(metadata);
};

// Initialize when DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLibrary);
} else {
    initLibrary();
}

function initLibrary() {
    // Populate filters if metadata already loaded
    if (window.libraryMetadata) {
        populateLibraryFilters(window.libraryMetadata);
    }
}

// ===== LIBRARY OPEN/CLOSE =====

function openLibrary() {
    const overlay = document.getElementById('libraryOverlay');
    if (!overlay) {
        console.error('Library overlay not found');
        return;
    }

    overlay.classList.add('active');
    lockScroll();
    enableFocusTrap(overlay);

    // Load cards if first time
    if (libraryState.cards.length === 0) {
        loadInitialCards();
    }

    // Auto-focus search input
    setTimeout(() => {
        const searchInput = document.getElementById('librarySearch');
        if (searchInput) searchInput.focus();
    }, 150);

    console.log('Library opened');
}

function closeLibrary() {
    const overlay = document.getElementById('libraryOverlay');
    if (!overlay) return;

    disableFocusTrap(overlay);
    unlockScroll();
    overlay.classList.remove('active');

    // Cleanup infinite scroll observer
    if (scrollObserver) {
        scrollObserver.disconnect();
        scrollObserver = null;
    }

    console.log('Library closed');
}

// Handle ESC key globally when library open
document.addEventListener('keydown', (e) => {
    const overlay = document.getElementById('libraryOverlay');
    if (overlay && overlay.classList.contains('active') && e.key === 'Escape') {
        closeLibrary();
    }
});

// ===== FOCUS MANAGEMENT =====

function enableFocusTrap(container) {
    // Save current focus
    focusTrap.previousFocus = document.activeElement;

    // Get all focusable elements
    const focusableSelectors = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const focusableElements = container.querySelectorAll(focusableSelectors);
    const focusableArray = Array.from(focusableElements);

    if (focusableArray.length === 0) return;

    focusTrap.firstFocusable = focusableArray[0];
    focusTrap.lastFocusable = focusableArray[focusableArray.length - 1];
    focusTrap.active = true;

    // Add trap listener
    container.addEventListener('keydown', handleFocusTrap);
}

function handleFocusTrap(e) {
    if (!focusTrap.active || e.key !== 'Tab') return;

    if (e.shiftKey) {
        // Shift+Tab on first element → focus last
        if (document.activeElement === focusTrap.firstFocusable) {
            e.preventDefault();
            focusTrap.lastFocusable.focus();
        }
    } else {
        // Tab on last element → focus first
        if (document.activeElement === focusTrap.lastFocusable) {
            e.preventDefault();
            focusTrap.firstFocusable.focus();
        }
    }
}

function disableFocusTrap(container) {
    container.removeEventListener('keydown', handleFocusTrap);
    focusTrap.active = false;

    // Restore previous focus
    if (focusTrap.previousFocus && focusTrap.previousFocus.focus) {
        setTimeout(() => {
            focusTrap.previousFocus.focus();
        }, 100);
    }
}

// ===== SCROLL LOCK (iOS-safe) =====

function lockScroll() {
    const scrollY = window.scrollY;
    document.body.style.position = 'fixed';
    document.body.style.top = `-${scrollY}px`;
    document.body.style.width = '100%';
    document.body.style.overflow = 'hidden';
    document.body.dataset.scrollY = scrollY;
}

function unlockScroll() {
    const scrollY = document.body.dataset.scrollY;
    document.body.style.position = '';
    document.body.style.top = '';
    document.body.style.width = '';
    document.body.style.overflow = '';
    window.scrollTo(0, parseInt(scrollY || '0'));
    delete document.body.dataset.scrollY;
}

// ===== FILTER POPULATION =====

function populateLibraryFilters(metadata) {
    const themeSelect = document.getElementById('libraryThemeFilter');
    const traditionSelect = document.getElementById('libraryTraditionFilter');

    if (!themeSelect || !traditionSelect) {
        console.error('Library filter selects not found');
        return;
    }

    // Temporarily remove onchange handlers to prevent premature filtering
    const themeHandler = themeSelect.onchange;
    const traditionHandler = traditionSelect.onchange;
    themeSelect.onchange = null;
    traditionSelect.onchange = null;

    // Populate themes (limit to 100 for performance)
    themeSelect.innerHTML = '<option value="">모든 주제</option>';
    const topThemes = metadata.themes.slice(0, 100);
    topThemes.forEach(theme => {
        const option = document.createElement('option');
        option.value = theme;
        option.textContent = theme;
        themeSelect.appendChild(option);
    });

    // Populate traditions
    traditionSelect.innerHTML = '<option value="">모든 전통</option>';
    metadata.traditions.forEach(tradition => {
        const option = document.createElement('option');
        option.value = tradition;
        option.textContent = tradition;
        traditionSelect.appendChild(option);
    });

    // Explicitly set to default values
    themeSelect.value = '';
    traditionSelect.value = '';

    // Restore onchange handlers
    themeSelect.onchange = themeHandler;
    traditionSelect.onchange = traditionHandler;

    console.log('Library filters populated:', {
        themes: topThemes.length,
        traditions: metadata.traditions.length
    });
}

// ===== DATA LOADING =====

async function loadInitialCards() {
    libraryState.isLoading = true;
    libraryState.currentOffset = 0;
    showLoading();

    try {
        const params = new URLSearchParams({
            limit: CARDS_PER_PAGE,
            offset: 0
        });

        const response = await fetch(`${window.API_BASE_URL}/api/sources?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        libraryState.cards = data.sources || [];
        libraryState.totalCount = data.total || 0;
        libraryState.currentOffset = CARDS_PER_PAGE;
        libraryState.hasMoreResults = libraryState.cards.length < libraryState.totalCount;

        displayFilteredCards();
        setupInfiniteScroll();

        console.log('Initial cards loaded:', libraryState.cards.length);
    } catch (error) {
        console.error('Failed to load cards:', error);
        showError('문헌을 불러오는데 실패했습니다.');
    } finally {
        libraryState.isLoading = false;
    }
}

async function loadMoreCards() {
    if (libraryState.isLoading || !libraryState.hasMoreResults) return;

    // Memory limit check
    if (libraryState.cards.length >= MAX_CACHED_CARDS) {
        showMemoryWarning();
        libraryState.hasMoreResults = false;
        return;
    }

    libraryState.isLoading = true;

    try {
        const params = new URLSearchParams({
            limit: CARDS_PER_PAGE,
            offset: libraryState.currentOffset,
            ...(libraryState.filters.search && { search: libraryState.filters.search }),
            ...(libraryState.filters.tradition && { tradition: libraryState.filters.tradition }),
            ...(libraryState.filters.theme && { theme: libraryState.filters.theme })
        });

        const response = await fetch(`${window.API_BASE_URL}/api/sources?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        const newCards = data.sources || [];

        libraryState.cards.push(...newCards);
        libraryState.currentOffset += CARDS_PER_PAGE;
        libraryState.hasMoreResults = libraryState.cards.length < libraryState.totalCount;

        displayFilteredCards();

        console.log('More cards loaded:', newCards.length, 'Total:', libraryState.cards.length);
    } catch (error) {
        console.error('Failed to load more cards:', error);
    } finally {
        libraryState.isLoading = false;
    }
}

// ===== INFINITE SCROLL =====

function setupInfiniteScroll() {
    const sentinel = document.getElementById('scrollSentinel');
    if (!sentinel) return;

    if (scrollObserver) {
        scrollObserver.disconnect();
    }

    scrollObserver = new IntersectionObserver(
        (entries) => {
            if (entries[0].isIntersecting && libraryState.hasMoreResults && !libraryState.isLoading) {
                loadMoreCards();
            }
        },
        { rootMargin: '100px' }
    );

    scrollObserver.observe(sentinel);
}

// ===== FILTERING =====

/**
 * Debounced search handler - waits for user to stop typing
 */
function handleSearchInput() {
    // Clear existing timer
    if (searchDebounceTimer) {
        clearTimeout(searchDebounceTimer);
    }

    // Show skeleton immediately for feedback
    const searchInput = document.getElementById('librarySearch');
    if (searchInput && searchInput.value.trim() !== libraryState.filters.search) {
        showSkeletonLoading();
    }

    // Debounce the actual search
    searchDebounceTimer = setTimeout(() => {
        filterLibraryCards();
    }, DEBOUNCE_DELAY);
}

function filterLibraryCards() {
    // Update filter state from UI
    const searchInput = document.getElementById('librarySearch');
    const themeSelect = document.getElementById('libraryThemeFilter');
    const traditionSelect = document.getElementById('libraryTraditionFilter');

    // Store old values BEFORE updating
    const oldSearch = libraryState.filters.search;
    const oldTradition = libraryState.filters.tradition;
    const oldTheme = libraryState.filters.theme;

    // Update current filter values
    libraryState.filters.search = searchInput ? searchInput.value.trim() : '';
    libraryState.filters.theme = themeSelect ? themeSelect.value : '';
    libraryState.filters.tradition = traditionSelect ? traditionSelect.value : '';

    // Don't filter if cards haven't been loaded yet
    // (This can happen if filters are populated before library is opened)
    const overlay = document.getElementById('libraryOverlay');
    if (!overlay || !overlay.classList.contains('active')) {
        console.log('Filter changed but library not open yet, skipping filter');
        return;
    }

    // If any filter changed → re-fetch from server
    if (libraryState.filters.search !== oldSearch ||
        libraryState.filters.tradition !== oldTradition ||
        libraryState.filters.theme !== oldTheme) {
        refetchCards();
    } else {
        // No filter changed
        displayFilteredCards();
    }

    updateFilterBadges();
}

async function refetchCards() {
    libraryState.isLoading = true;
    libraryState.currentOffset = 0;
    showSkeletonLoading();

    try {
        const params = new URLSearchParams({
            limit: CARDS_PER_PAGE,
            offset: 0,
            ...(libraryState.filters.search && { search: libraryState.filters.search }),
            ...(libraryState.filters.tradition && { tradition: libraryState.filters.tradition }),
            ...(libraryState.filters.theme && { theme: libraryState.filters.theme })
        });

        const cacheKey = getCacheKey(params);
        let data = getCachedResponse(cacheKey);

        if (!data) {
            const response = await fetch(`${window.API_BASE_URL}/api/sources?${params}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            data = await response.json();
            setCachedResponse(cacheKey, data);
        }

        libraryState.cards = data.sources || [];
        libraryState.totalCount = data.total || 0;
        libraryState.currentOffset = CARDS_PER_PAGE;
        libraryState.hasMoreResults = libraryState.cards.length < libraryState.totalCount;

        displayFilteredCards();

        console.log('Cards refetched:', libraryState.cards.length);
    } catch (error) {
        console.error('Failed to refetch cards:', error);
        showError('필터링에 실패했습니다.');
    } finally {
        libraryState.isLoading = false;
    }
}

function displayFilteredCards() {
    // Server-side filtering is now applied for all filters (search, tradition, theme)
    // Cards returned from API are already filtered
    libraryState.filteredCards = [...libraryState.cards];
    renderCards();
    updateResultCount();
}

// ===== RENDERING =====

function renderCards() {
    const grid = document.getElementById('libraryGrid');
    const loading = document.getElementById('libraryLoading');
    const empty = document.getElementById('libraryEmpty');

    if (!grid) return;

    loading.style.display = 'none';

    if (libraryState.filteredCards.length === 0) {
        grid.style.display = 'none';
        empty.style.display = 'flex';
        return;
    }

    empty.style.display = 'none';
    grid.style.display = 'grid';

    grid.innerHTML = libraryState.filteredCards.map(card => {
        const sutraId = card.sutra_id || '';
        const title = card.title_ko || card.original_title || '제목 없음';
        const summary = card.brief_summary || '요약 정보가 없습니다.';
        const tradition = card.tradition_normalized || card.tradition || '';
        const period = card.period || '';

        // Use data attribute for cleaner event handling
        return `
        <div class="library-card"
             data-sutra-id="${escapeHtml(sutraId)}"
             data-sutra-title="${escapeHtml(title)}"
             tabindex="0"
             role="button"
             aria-label="${escapeHtml(title)} 상세 보기">
            <h3 class="library-card-title">${escapeHtml(title)}</h3>
            <p class="library-card-summary">${escapeHtml(summary)}</p>
            <div class="library-card-footer">
                <div class="library-card-meta">
                    ${tradition ? `<span class="library-card-tag tradition">${escapeHtml(tradition)}</span>` : ''}
                    ${period ? `<span class="library-card-tag period">${escapeHtml(period)}</span>` : ''}
                </div>
                <button class="library-card-ask-btn"
                        onclick="event.stopPropagation(); askAboutSutraFromCard('${escapeHtml(sutraId)}', '${escapeHtml(title.replace(/'/g, "\\'"))}')"
                        aria-label="${escapeHtml(title)}에 대해 질문하기">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                    </svg>
                    질문
                </button>
            </div>
        </div>
    `;
    }).join('');

    // Attach event listeners using event delegation (only once)
    if (!grid.dataset.listenersAttached) {
        grid.addEventListener('click', handleCardClick);
        grid.addEventListener('keypress', handleCardKeypress);
        grid.dataset.listenersAttached = 'true';
    }

    // Add scroll sentinel for infinite scroll
    const sentinel = document.createElement('div');
    sentinel.id = 'scrollSentinel';
    grid.appendChild(sentinel);

    setupInfiniteScroll();
}

function updateResultCount() {
    const countElement = document.getElementById('libraryResultsCount');
    if (!countElement) return;

    const total = libraryState.filteredCards.length;
    const ofTotal = libraryState.totalCount > libraryState.cards.length
        ? ` / 총 ${libraryState.totalCount.toLocaleString()}개`
        : '';

    countElement.innerHTML = `<span>${total.toLocaleString()}</span>개 문헌 표시 중${ofTotal}`;
}

function updateFilterBadges() {
    const container = document.getElementById('libraryFilterBadges');
    if (!container) return;

    const badges = [];

    if (libraryState.filters.search) {
        badges.push(`
            <div class="library-filter-badge">
                검색: "${escapeHtml(libraryState.filters.search)}"
                <button onclick="clearSearch()" aria-label="검색 초기화">✕</button>
            </div>
        `);
    }

    if (libraryState.filters.theme) {
        const themeName = document.querySelector(`#libraryThemeFilter option[value="${libraryState.filters.theme}"]`)?.textContent || libraryState.filters.theme;
        badges.push(`
            <div class="library-filter-badge">
                주제: ${escapeHtml(themeName)}
                <button onclick="clearTheme()" aria-label="주제 필터 초기화">✕</button>
            </div>
        `);
    }

    if (libraryState.filters.tradition) {
        const traditionName = document.querySelector(`#libraryTraditionFilter option[value="${libraryState.filters.tradition}"]`)?.textContent || libraryState.filters.tradition;
        badges.push(`
            <div class="library-filter-badge">
                전통: ${escapeHtml(traditionName)}
                <button onclick="clearTradition()" aria-label="전통 필터 초기화">✕</button>
            </div>
        `);
    }

    container.innerHTML = badges.join('');
}

// ===== UI STATE HELPERS =====

function showLoading() {
    const grid = document.getElementById('libraryGrid');
    const loading = document.getElementById('libraryLoading');
    const empty = document.getElementById('libraryEmpty');

    if (grid) grid.style.display = 'none';
    if (empty) empty.style.display = 'none';
    if (loading) loading.style.display = 'flex';
}

/**
 * Show skeleton loading cards for better perceived performance
 */
function showSkeletonLoading() {
    const grid = document.getElementById('libraryGrid');
    const loading = document.getElementById('libraryLoading');
    const empty = document.getElementById('libraryEmpty');

    if (!grid) return;

    if (loading) loading.style.display = 'none';
    if (empty) empty.style.display = 'none';
    grid.style.display = 'grid';

    // Generate skeleton cards
    const skeletonCount = 12;
    grid.innerHTML = Array(skeletonCount).fill(0).map(() => `
        <div class="library-card skeleton">
            <div class="skeleton-title"></div>
            <div class="skeleton-text"></div>
            <div class="skeleton-text short"></div>
            <div class="skeleton-tags">
                <div class="skeleton-tag"></div>
                <div class="skeleton-tag"></div>
            </div>
        </div>
    `).join('');
}

function showError(message) {
    const empty = document.getElementById('libraryEmpty');
    if (!empty) return;

    empty.querySelector('h3').textContent = '오류 발생';
    empty.querySelector('p').textContent = message;
    empty.style.display = 'flex';

    document.getElementById('libraryGrid').style.display = 'none';
    document.getElementById('libraryLoading').style.display = 'none';
}

function showMemoryWarning() {
    const container = document.getElementById('libraryContainer');
    if (!container) return;

    const existing = document.querySelector('.library-memory-warning');
    if (existing) return;

    const warning = document.createElement('div');
    warning.className = 'library-memory-warning';
    warning.textContent = '메모리 제한으로 더 이상 불러올 수 없습니다. 필터를 사용하여 검색 범위를 좁혀주세요.';

    const header = document.querySelector('.library-header');
    if (header) {
        header.after(warning);
    }
}

// ===== FILTER CLEARING =====

function clearSearch() {
    const searchInput = document.getElementById('librarySearch');
    if (searchInput) searchInput.value = '';
    filterLibraryCards();
}

function clearTheme() {
    const themeSelect = document.getElementById('libraryThemeFilter');
    if (themeSelect) themeSelect.value = '';
    filterLibraryCards();
}

function clearTradition() {
    const traditionSelect = document.getElementById('libraryTraditionFilter');
    if (traditionSelect) traditionSelect.value = '';
    filterLibraryCards();
}

function resetAllFilters() {
    const searchInput = document.getElementById('librarySearch');
    const themeSelect = document.getElementById('libraryThemeFilter');
    const traditionSelect = document.getElementById('libraryTraditionFilter');

    if (searchInput) searchInput.value = '';
    if (themeSelect) themeSelect.value = '';
    if (traditionSelect) traditionSelect.value = '';

    filterLibraryCards();
}

// ===== CARD EVENT HANDLERS =====

/**
 * Handle click events on library cards using event delegation
 */
function handleCardClick(event) {
    const card = event.target.closest('.library-card');
    if (!card) return;

    const sutraId = card.dataset.sutraId;
    console.log('Card clicked, sutraId:', sutraId);

    if (sutraId) {
        showSourceDetail(sutraId);
    }
}

/**
 * Handle keypress events on library cards (Enter/Space)
 */
function handleCardKeypress(event) {
    if (event.key !== 'Enter' && event.key !== ' ') return;

    const card = event.target.closest('.library-card');
    if (!card) return;

    event.preventDefault();
    const sutraId = card.dataset.sutraId;

    if (sutraId) {
        showSourceDetail(sutraId);
    }
}

// ===== UTILITY FUNCTIONS =====

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

/**
 * Debounce function - delays execution until after wait ms have elapsed
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ===== API CACHING =====

/**
 * Generate cache key from URL params
 */
function getCacheKey(params) {
    return Array.from(params.entries()).sort().map(([k, v]) => `${k}=${v}`).join('&');
}

/**
 * Get cached response if valid
 */
function getCachedResponse(cacheKey) {
    const cached = apiCache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
        console.log('Cache hit:', cacheKey);
        return cached.data;
    }
    if (cached) {
        apiCache.delete(cacheKey); // Expired
    }
    return null;
}

/**
 * Store response in cache
 */
function setCachedResponse(cacheKey, data) {
    // Limit cache size to prevent memory issues
    if (apiCache.size > 50) {
        const oldestKey = apiCache.keys().next().value;
        apiCache.delete(oldestKey);
    }
    apiCache.set(cacheKey, { data, timestamp: Date.now() });
}

/**
 * Clear all cached responses
 */
function clearApiCache() {
    apiCache.clear();
    console.log('API cache cleared');
}

// ===== SOURCE DETAIL MODAL =====

let modalState = {
    isOpen: false,
    currentIndex: -1,
    currentSutraId: null
};

/**
 * Show source detail in a modal
 * @param {string} sutraId - The sutra ID (e.g., 'T01n0001')
 */
async function showSourceDetail(sutraId) {
    console.log('showSourceDetail called with:', sutraId);

    if (!sutraId) {
        console.error('showSourceDetail: No sutraId provided');
        return;
    }

    try {
        // Find current index in filtered cards for navigation
        modalState.currentIndex = libraryState.filteredCards.findIndex(s => s.sutra_id === sutraId);
        modalState.currentSutraId = sutraId;
        console.log('Current index:', modalState.currentIndex);

        const response = await fetch(`${window.API_BASE_URL}/api/sources/${sutraId}`);
        if (!response.ok) throw new Error('Failed to load source detail');

        const source = await response.json();

        // Ensure modal exists, create if not
        let modal = document.getElementById('sourceModal');
        if (!modal) {
            createSourceModal();
            modal = document.getElementById('sourceModal');
        }

        // Populate modal content
        document.getElementById('modalTitle').textContent = source.title_ko || source.original_title || '제목 없음';
        document.getElementById('modalMeta').textContent =
            `${source.author || '작자 미상'} | ${source.period || '시대 미상'} | ${source.tradition || '전통 미상'}`;
        document.getElementById('modalBriefSummary').textContent = source.brief_summary || '요약 정보 없음';
        document.getElementById('modalDetailedSummary').textContent = source.detailed_summary || '상세 요약 정보 없음';

        // Key themes
        const themesContainer = document.getElementById('modalThemes');
        if (source.key_themes && source.key_themes.length > 0) {
            themesContainer.innerHTML = source.key_themes.map(theme =>
                `<span class="modal-theme-tag">${escapeHtml(theme)}</span>`
            ).join('');
        } else {
            themesContainer.innerHTML = '<span class="modal-no-themes">주제 정보 없음</span>';
        }

        // Original info
        document.getElementById('modalOriginalInfo').innerHTML = `
            <strong>원제목:</strong> ${escapeHtml(source.original_title || '미상')}<br>
            <strong>저자:</strong> ${escapeHtml(source.author || '미상')}<br>
            <strong>대장경 번호:</strong> ${sutraId}<br>
            <strong>권수:</strong> 제${source.volume || '?'}권 ${source.juan || ''}
        `;

        // Show modal
        console.log('Showing modal for:', sutraId);
        modal.classList.add('active');
        modalState.isOpen = true;

        // Update navigation button states
        updateModalNavButtons();
        console.log('Modal displayed successfully');

        // Add keyboard listener if not already added
        if (!modal.dataset.keyboardListenerAdded) {
            document.addEventListener('keydown', handleModalKeyboard);
            modal.dataset.keyboardListenerAdded = 'true';
        }

    } catch (error) {
        console.error('Error loading source detail:', error);
        alert('문헌 상세 정보를 불러올 수 없습니다.');
    }
}

/**
 * Create the source modal HTML structure
 */
function createSourceModal() {
    const modalHtml = `
    <div class="source-modal" id="sourceModal" onclick="if(event.target === this) closeSourceModal()">
        <div class="source-modal-content" onclick="event.stopPropagation()">
            <!-- Navigation Buttons -->
            <button class="modal-nav-btn prev" id="modalPrevBtn" onclick="navigateModal(-1)" title="이전 문헌 (←)" aria-label="이전 문헌">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M15 18l-6-6 6-6"/>
                </svg>
            </button>
            <button class="modal-nav-btn next" id="modalNextBtn" onclick="navigateModal(1)" title="다음 문헌 (→)" aria-label="다음 문헌">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M9 18l6-6-6-6"/>
                </svg>
            </button>

            <div class="modal-scroll-wrapper">
                <div class="modal-header">
                    <button class="modal-close-btn" onclick="closeSourceModal()" aria-label="닫기">×</button>
                    <h3 id="modalTitle">문헌 제목</h3>
                    <p id="modalMeta" class="modal-meta">저자 | 시대 | 전통</p>
                    <button class="modal-ask-btn" id="modalAskBtn" onclick="askAboutCurrentSutra()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                        </svg>
                        이 문헌에 대해 질문하기
                    </button>
                </div>
                <div class="modal-body">
                    <div class="modal-section">
                        <h4>간략 요약</h4>
                        <p id="modalBriefSummary"></p>
                    </div>
                    <div class="modal-section">
                        <h4>상세 요약</h4>
                        <p id="modalDetailedSummary"></p>
                    </div>
                    <div class="modal-section">
                        <h4>핵심 주제</h4>
                        <div class="modal-themes" id="modalThemes"></div>
                    </div>
                    <div class="modal-section">
                        <h4>원문 정보</h4>
                        <p id="modalOriginalInfo"></p>
                    </div>
                </div>
            </div>
        </div>
    </div>`;

    // Append to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

/**
 * Close the source detail modal
 */
function closeSourceModal() {
    const modal = document.getElementById('sourceModal');
    if (modal) {
        modal.classList.remove('active');
        modalState.isOpen = false;
        modalState.currentIndex = -1;
        modalState.currentSutraId = null;
    }
}

/**
 * Navigate to previous/next source in the modal
 * @param {number} direction - -1 for previous, 1 for next
 */
function navigateModal(direction) {
    const newIndex = modalState.currentIndex + direction;

    // Boundary check
    if (newIndex < 0 || newIndex >= libraryState.filteredCards.length) {
        return;
    }

    // Navigate to new source
    const newSource = libraryState.filteredCards[newIndex];
    if (newSource) {
        showSourceDetail(newSource.sutra_id);
    }
}

/**
 * Update navigation button states (disabled at boundaries)
 */
function updateModalNavButtons() {
    const prevBtn = document.getElementById('modalPrevBtn');
    const nextBtn = document.getElementById('modalNextBtn');

    if (!prevBtn || !nextBtn) return;

    // Disable prev if at start
    prevBtn.disabled = modalState.currentIndex <= 0;

    // Disable next if at end
    nextBtn.disabled = modalState.currentIndex >= libraryState.filteredCards.length - 1;
}

/**
 * Handle keyboard events for modal navigation
 */
function handleModalKeyboard(e) {
    if (!modalState.isOpen) return;

    switch (e.key) {
        case 'Escape':
            closeSourceModal();
            e.preventDefault();
            break;
        case 'ArrowLeft':
            navigateModal(-1);
            e.preventDefault();
            break;
        case 'ArrowRight':
            navigateModal(1);
            e.preventDefault();
            break;
    }
}

// ===== MOBILE FILTER DRAWER =====

let drawerState = {
    isOpen: false,
    startY: 0,
    currentY: 0
};

/**
 * Open mobile filter bottom drawer
 */
function openMobileFilters() {
    const drawer = document.getElementById('mobileFilterDrawer');
    if (!drawer) return;

    // Sync select options with desktop filters
    syncDrawerOptions();

    drawer.classList.add('active');
    drawerState.isOpen = true;

    // Prevent body scroll
    document.body.style.overflow = 'hidden';
}

/**
 * Close mobile filter bottom drawer
 */
function closeMobileFilters() {
    const drawer = document.getElementById('mobileFilterDrawer');
    if (!drawer) return;

    drawer.classList.remove('active');
    drawerState.isOpen = false;

    // Restore body scroll
    document.body.style.overflow = '';
}

/**
 * Sync drawer filter options with desktop filter dropdowns
 */
function syncDrawerOptions() {
    const desktopTheme = document.getElementById('libraryThemeFilter');
    const desktopTradition = document.getElementById('libraryTraditionFilter');
    const mobileTheme = document.getElementById('mobileThemeFilter');
    const mobileTradition = document.getElementById('mobileTraditionFilter');

    if (desktopTheme && mobileTheme) {
        mobileTheme.innerHTML = desktopTheme.innerHTML;
        mobileTheme.value = desktopTheme.value;
    }

    if (desktopTradition && mobileTradition) {
        mobileTradition.innerHTML = desktopTradition.innerHTML;
        mobileTradition.value = desktopTradition.value;
    }
}

/**
 * Sync mobile filter selection to desktop and apply
 */
function syncMobileFilter(type) {
    const mobileTheme = document.getElementById('mobileThemeFilter');
    const mobileTradition = document.getElementById('mobileTraditionFilter');
    const desktopTheme = document.getElementById('libraryThemeFilter');
    const desktopTradition = document.getElementById('libraryTraditionFilter');

    if (type === 'theme' && mobileTheme && desktopTheme) {
        desktopTheme.value = mobileTheme.value;
    }
    if (type === 'tradition' && mobileTradition && desktopTradition) {
        desktopTradition.value = mobileTradition.value;
    }

    filterLibraryCards();
    updateMobileFilterCount();
}

/**
 * Update the mobile filter button badge count
 */
function updateMobileFilterCount() {
    const countBadge = document.getElementById('mobileFilterCount');
    if (!countBadge) return;

    let count = 0;
    if (libraryState.filters.theme) count++;
    if (libraryState.filters.tradition) count++;

    if (count > 0) {
        countBadge.textContent = count;
        countBadge.style.display = 'inline-flex';
    } else {
        countBadge.style.display = 'none';
    }
}

// ===== EXPOSE GLOBAL FUNCTIONS =====

window.openLibrary = openLibrary;
window.closeLibrary = closeLibrary;
window.filterLibraryCards = filterLibraryCards;
window.handleSearchInput = handleSearchInput;
window.clearSearch = clearSearch;
window.clearTheme = clearTheme;
window.clearTradition = clearTradition;
window.resetAllFilters = resetAllFilters;
window.clearApiCache = clearApiCache;
window.libraryState = libraryState;
window.loadInitialCards = loadInitialCards;
window.showSourceDetail = showSourceDetail;
window.closeSourceModal = closeSourceModal;
window.navigateModal = navigateModal;
window.openMobileFilters = openMobileFilters;
window.closeMobileFilters = closeMobileFilters;
window.syncMobileFilter = syncMobileFilter;
window.askAboutCurrentSutra = askAboutCurrentSutra;
window.askAboutSutraFromCard = askAboutSutraFromCard;

/**
 * Ask about a sutra directly from the card
 */
function askAboutSutraFromCard(sutraId, title) {
    if (typeof window.askAboutSutra === 'function') {
        window.askAboutSutra(sutraId, title);
    } else {
        console.error('askAboutSutra function not found');
    }
}

/**
 * Ask about the currently displayed sutra in the modal
 * This function sets the sutra as the chat filter and switches to chat tab
 */
function askAboutCurrentSutra() {
    if (!modalState.currentSutraId) {
        console.error('No sutra currently selected');
        return;
    }

    // Get the title from the modal BEFORE closing
    const titleEl = document.getElementById('modalTitle');
    const title = titleEl ? titleEl.textContent : modalState.currentSutraId;

    // Store the sutraId BEFORE closing (closeSourceModal resets modalState)
    const sutraId = modalState.currentSutraId;

    console.log('[Library] askAboutCurrentSutra - sutraId:', sutraId, 'title:', title);

    // Close the modal
    closeSourceModal();

    // Call the global selectSutraForChat function to set the filter
    if (typeof window.selectSutraForChat === 'function') {
        window.selectSutraForChat(sutraId, title);
        console.log('[Library] selectSutraForChat called successfully');

        // Switch to chat tab
        if (typeof window.switchTab === 'function') {
            window.switchTab('chat');
            console.log('[Library] Switched to chat tab');
        } else {
            console.warn('[Library] switchTab function not found, trying fallback');
            // Fallback: use askAboutSutra which also switches tab
            if (typeof window.askAboutSutra === 'function') {
                window.askAboutSutra(sutraId, title);
            }
        }
    } else if (typeof window.askAboutSutra === 'function') {
        // Fallback to original function
        console.log('[Library] Falling back to askAboutSutra');
        window.askAboutSutra(sutraId, title);
    } else {
        console.error('[Library] Neither selectSutraForChat nor askAboutSutra function found');
    }
}
