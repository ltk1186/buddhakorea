/**
 * Full-Screen Scripture Library
 * Buddha Korea - AI Chatbot
 *
 * Features:
 * - Hybrid filtering (server: search/tradition, client: theme)
 * - Infinite scroll with IntersectionObserver
 * - Focus trap and scroll lock
 * - Memory management (1000 card limit)
 * - WCAG 2.1 AA accessibility
 */

// ===== GLOBAL STATE =====

const MAX_CACHED_CARDS = 1000;
const CARDS_PER_PAGE = 100;

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

        const response = await fetch(`/api/sources?${params}`);
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
        showError('경전을 불러오는데 실패했습니다.');
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
            ...(libraryState.filters.tradition && { tradition: libraryState.filters.tradition })
        });

        const response = await fetch(`/api/sources?${params}`);
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

function filterLibraryCards() {
    // Update filter state from UI
    const searchInput = document.getElementById('librarySearch');
    const themeSelect = document.getElementById('libraryThemeFilter');
    const traditionSelect = document.getElementById('libraryTraditionFilter');

    const oldSearch = libraryState.filters.search;
    const oldTradition = libraryState.filters.tradition;

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

    // If search or tradition changed → re-fetch from server
    if (libraryState.filters.search !== oldSearch || libraryState.filters.tradition !== oldTradition) {
        refetchCards();
    } else {
        // Theme changed → filter client-side
        displayFilteredCards();
    }

    updateFilterBadges();
}

async function refetchCards() {
    libraryState.isLoading = true;
    libraryState.currentOffset = 0;
    showLoading();

    try {
        const params = new URLSearchParams({
            limit: CARDS_PER_PAGE,
            offset: 0,
            ...(libraryState.filters.search && { search: libraryState.filters.search }),
            ...(libraryState.filters.tradition && { tradition: libraryState.filters.tradition })
        });

        const response = await fetch(`/api/sources?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
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
    let filtered = [...libraryState.cards];

    // Apply client-side theme filter
    if (libraryState.filters.theme) {
        filtered = filtered.filter(card => {
            const themes = Array.isArray(card.key_themes)
                ? card.key_themes
                : (card.key_themes ? [card.key_themes] : []);
            return themes.includes(libraryState.filters.theme);
        });
    }

    libraryState.filteredCards = filtered;
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

    grid.innerHTML = libraryState.filteredCards.map(card => `
        <div class="library-card"
             onclick="showSourceDetail('${escapeHtml(card.sutra_id)}')"
             tabindex="0"
             role="button"
             aria-label="${escapeHtml(card.title_ko || card.original_title)} 상세 보기"
             onkeypress="if(event.key==='Enter'||event.key===' '){event.preventDefault();showSourceDetail('${escapeHtml(card.sutra_id)}');}">
            <h3 class="library-card-title">${escapeHtml(card.title_ko || card.original_title || '제목 없음')}</h3>
            <p class="library-card-summary">${escapeHtml(card.brief_summary || '요약 정보가 없습니다.')}</p>
            <div class="library-card-meta">
                ${card.tradition ? `<span class="library-card-tag">${escapeHtml(card.tradition)}</span>` : ''}
                ${card.period ? `<span class="library-card-tag">${escapeHtml(card.period)}</span>` : ''}
            </div>
        </div>
    `).join('');

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

    countElement.innerHTML = `<span>${total.toLocaleString()}</span>개 경전 표시 중${ofTotal}`;
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

// ===== UTILITY FUNCTIONS =====

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== EXPOSE GLOBAL FUNCTIONS =====

window.openLibrary = openLibrary;
window.closeLibrary = closeLibrary;
window.filterLibraryCards = filterLibraryCards;
window.clearSearch = clearSearch;
window.clearTheme = clearTheme;
window.clearTradition = clearTradition;
window.resetAllFilters = resetAllFilters;
window.libraryState = libraryState;  // Expose for modal navigation
