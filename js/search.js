/**
 * Tripitaka Search Functionality
 * Handles searching, filtering, and displaying Buddhist scripture data.
 */

document.addEventListener('DOMContentLoaded', () => {
    initSearch();
});

const STATE = {
    query: '',
    tradition: '',
    period: '',
    offset: 0,
    limit: 24, // 4x6 grid
    total: 0,
    isLoading: false
};

const API_BASE = 'http://localhost:8000/api';

// Elements
const elements = {
    searchInput: document.getElementById('search-input'),
    searchBtn: document.getElementById('search-btn'),
    traditionFilter: document.getElementById('tradition-filter'),
    periodFilter: document.getElementById('period-filter'),
    resultsGrid: document.getElementById('results-grid'),
    resultCount: document.getElementById('result-count'),
    pagination: document.getElementById('pagination'),
    loader: document.getElementById('search-loader'),
    fullscreenBtn: document.getElementById('fullscreen-btn'),
    modal: {
        self: document.getElementById('sutra-modal'),
        closeBtn: document.getElementById('modal-close-btn'),
        badges: document.getElementById('modal-badges'),
        titleKo: document.getElementById('modal-title-ko'),
        titleOrig: document.getElementById('modal-title-orig'),
        author: document.getElementById('modal-author'),
        brief: document.getElementById('modal-brief'),
        detailed: document.getElementById('modal-detailed'),
        themes: document.getElementById('modal-themes'),
        chatBtn: document.getElementById('modal-chat-btn')
    }
};

/**
 * Initialize the search page
 */
async function initSearch() {
    // Load metadata for filters
    await loadMetadata();

    // Initial search (load all)
    performSearch();

    // Event Listeners
    elements.searchBtn.addEventListener('click', () => {
        STATE.offset = 0;
        performSearch();
    });

    elements.searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            STATE.offset = 0;
            performSearch();
        }
    });

    // Debounced search input
    let debounceTimer;
    elements.searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            STATE.offset = 0;
            performSearch();
        }, 500);
    });

    elements.traditionFilter.addEventListener('change', () => {
        STATE.offset = 0;
        performSearch();
    });

    elements.periodFilter.addEventListener('change', () => {
        STATE.offset = 0;
        performSearch();
    });

    elements.fullscreenBtn.addEventListener('click', toggleFullscreen);

    // Modal close handlers
    elements.modal.closeBtn.addEventListener('click', closeModal);
    window.addEventListener('click', (e) => {
        if (e.target === elements.modal.self) closeModal();
    });
    
    // Keyboard ESC to close modal or fullscreen
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (elements.modal.self.classList.contains('active')) {
                closeModal();
            } else if (document.body.classList.contains('fullscreen-mode')) {
                toggleFullscreen();
            }
        }
    });
}

/**
 * Load metadata for filter dropdowns
 */
async function loadMetadata() {
    try {
        const response = await fetch(`${API_BASE}/sutras/meta`);
        if (!response.ok) throw new Error('Failed to load metadata');
        
        const meta = await response.json();
        
        // Populate Tradition Filter
        if (meta.traditions) {
            meta.traditions.forEach(tradition => {
                const option = document.createElement('option');
                option.value = tradition;
                option.textContent = tradition;
                elements.traditionFilter.appendChild(option);
            });
        }

        // Populate Period Filter
        if (meta.periods) {
            meta.periods.forEach(period => {
                const option = document.createElement('option');
                option.value = period;
                option.textContent = period;
                elements.periodFilter.appendChild(option);
            });
        }

    } catch (error) {
        console.error('Error loading metadata:', error);
    }
}

/**
 * Perform search API call
 */
async function performSearch() {
    if (STATE.isLoading) return;
    
    STATE.isLoading = true;
    STATE.query = elements.searchInput.value.trim();
    STATE.tradition = elements.traditionFilter.value;
    STATE.period = elements.periodFilter.value;

    // UI Updates
    elements.loader.style.display = 'block';
    elements.resultsGrid.style.opacity = '0.5';

    try {
        // Build URL parameters
        const params = new URLSearchParams({
            limit: STATE.limit,
            offset: STATE.offset
        });

        if (STATE.query) params.append('search', STATE.query);
        if (STATE.tradition) params.append('tradition', STATE.tradition);
        if (STATE.period) params.append('period', STATE.period);

        const response = await fetch(`${API_BASE}/sources?${params.toString()}`);
        if (!response.ok) throw new Error('Search failed');

        const data = await response.json();
        
        STATE.total = data.total;
        renderResults(data.sources);
        renderPagination();
        
        elements.resultCount.textContent = `${STATE.total.toLocaleString()}개의 경전이 발견되었습니다.`;

    } catch (error) {
        console.error('Search error:', error);
        elements.resultsGrid.innerHTML = '<div class="error-message">검색 중 오류가 발생했습니다. 다시 시도해주세요.</div>';
    } finally {
        STATE.isLoading = false;
        elements.loader.style.display = 'none';
        elements.resultsGrid.style.opacity = '1';
    }
}

/**
 * Render search results grid
 */
function renderResults(sources) {
    elements.resultsGrid.innerHTML = '';

    if (sources.length === 0) {
        elements.resultsGrid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 60px; color: #888;">
                <h3>검색 결과가 없습니다.</h3>
                <p>다른 검색어나 필터를 사용해보세요.</p>
            </div>
        `;
        return;
    }

    sources.forEach(sutra => {
        const card = document.createElement('div');
        card.className = 'sutra-card';
        card.innerHTML = `
            <div class="sutra-card-header">
                <div class="sutra-card-badges">
                    <span class="badge tradition">${sutra.tradition || '미분류'}</span>
                    <span class="badge period">${sutra.period || '시대 미상'}</span>
                </div>
                <h3 class="sutra-title-ko">${sutra.title_ko}</h3>
                <p class="sutra-title-orig">${sutra.original_title}</p>
            </div>
            <div class="sutra-card-body">
                <p class="sutra-summary">${sutra.brief_summary || '요약 없음'}</p>
            </div>
            <div class="sutra-card-footer">
                <span>${sutra.author || '작자 미상'}</span>
                <span class="read-more">상세보기 →</span>
            </div>
        `;
        
        card.addEventListener('click', () => openModal(sutra.sutra_id));
        elements.resultsGrid.appendChild(card);
    });
}

/**
 * Render Pagination
 */
function renderPagination() {
    elements.pagination.innerHTML = '';
    
    const totalPages = Math.ceil(STATE.total / STATE.limit);
    if (totalPages <= 1) return;
    
    const currentPage = Math.floor(STATE.offset / STATE.limit) + 1;
    
    // Previous Button
    const prevBtn = document.createElement('button');
    prevBtn.className = 'page-btn';
    prevBtn.innerHTML = '←';
    prevBtn.disabled = currentPage === 1;
    prevBtn.onclick = () => {
        if (currentPage > 1) {
            STATE.offset = (currentPage - 2) * STATE.limit;
            performSearch();
            scrollToTop();
        }
    };
    elements.pagination.appendChild(prevBtn);
    
    // Page Numbers (Smart rendering: 1, ... 4, 5, 6 ... 10)
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, currentPage + 2);
    
    if (startPage > 1) {
        elements.pagination.appendChild(createPageBtn(1, currentPage));
        if (startPage > 2) {
            const ellipsis = document.createElement('span');
            ellipsis.style.padding = '10px';
            ellipsis.textContent = '...';
            elements.pagination.appendChild(ellipsis);
        }
    }
    
    for (let i = startPage; i <= endPage; i++) {
        elements.pagination.appendChild(createPageBtn(i, currentPage));
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            const ellipsis = document.createElement('span');
            ellipsis.style.padding = '10px';
            ellipsis.textContent = '...';
            elements.pagination.appendChild(ellipsis);
        }
        elements.pagination.appendChild(createPageBtn(totalPages, currentPage));
    }
    
    // Next Button
    const nextBtn = document.createElement('button');
    nextBtn.className = 'page-btn';
    nextBtn.innerHTML = '→';
    nextBtn.disabled = currentPage === totalPages;
    nextBtn.onclick = () => {
        if (currentPage < totalPages) {
            STATE.offset = currentPage * STATE.limit;
            performSearch();
            scrollToTop();
        }
    };
    elements.pagination.appendChild(nextBtn);
}

function createPageBtn(pageNum, currentPage) {
    const btn = document.createElement('button');
    btn.className = `page-btn ${pageNum === currentPage ? 'active' : ''}`;
    btn.textContent = pageNum;
    btn.onclick = () => {
        STATE.offset = (pageNum - 1) * STATE.limit;
        performSearch();
        scrollToTop();
    };
    return btn;
}

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (document.body.classList.contains('fullscreen-mode')) {
        const section = document.querySelector('.search-section');
        if (section) section.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

/**
 * Modal Logic
 */
async function openModal(sutraId) {
    // Show loading state in modal or simply open it
    elements.modal.self.classList.add('active');
    
    // Reset Content
    elements.modal.titleKo.textContent = '불러오는 중...';
    elements.modal.brief.textContent = '';
    elements.modal.detailed.textContent = '';
    elements.modal.themes.innerHTML = '';
    
    try {
        const response = await fetch(`${API_BASE}/sources/${sutraId}`);
        if (!response.ok) throw new Error('Failed to load details');
        
        const data = await response.json();
        
        // Populate Content
        elements.modal.titleKo.textContent = data.title_ko;
        elements.modal.titleOrig.textContent = `${data.original_title} (Vol.${data.volume}, ${data.juan})`;
        elements.modal.author.textContent = `${data.author} | ${data.period} | ${data.tradition}`;
        
        // Badges
        elements.modal.badges.innerHTML = `
            <span class="badge tradition">${data.tradition}</span>
            <span class="badge period">${data.period}</span>
        `;
        
        elements.modal.brief.textContent = data.brief_summary || '요약 정보가 없습니다.';
        elements.modal.detailed.textContent = data.detailed_summary || '상세 내용이 없습니다.';
        
        // Themes
        elements.modal.themes.innerHTML = '';
        if (data.key_themes && data.key_themes.length > 0) {
            data.key_themes.forEach(theme => {
                const tag = document.createElement('span');
                tag.className = 'tag';
                tag.textContent = `#${theme}`;
                elements.modal.themes.appendChild(tag);
            });
        }

        // Update Chat Button Action
        elements.modal.chatBtn.onclick = () => {
            // Store intention in sessionStorage to handle in chat page
            sessionStorage.setItem('chat_context', JSON.stringify({
                type: 'sutra_question',
                sutraId: sutraId,
                sutraTitle: data.title_ko,
                initialQuery: `"${data.title_ko}"에 대해 자세히 설명해줘.`
            }));
            window.location.href = '/chat';
        };

    } catch (error) {
        console.error(error);
        elements.modal.titleKo.textContent = '오류 발생';
        elements.modal.brief.textContent = '데이터를 불러올 수 없습니다.';
    }
}

function closeModal() {
    elements.modal.self.classList.remove('active');
}

/**
 * Fullscreen Mode
 */
function toggleFullscreen() {
    document.body.classList.toggle('fullscreen-mode');
    const isFullscreen = document.body.classList.contains('fullscreen-mode');
    
    const btnText = elements.fullscreenBtn.querySelector('span');
    btnText.textContent = isFullscreen ? '모드 종료' : '몰입 모드';
    
    if (isFullscreen) {
        // Add Escape key hint if not present
        if (!document.getElementById('esc-hint')) {
            const hint = document.createElement('div');
            hint.id = 'esc-hint';
            hint.style.cssText = 'position: fixed; bottom: 20px; right: 20px; background: rgba(0,0,0,0.5); color: white; padding: 8px 16px; border-radius: 20px; font-size: 0.8rem; opacity: 0; transition: opacity 0.5s; pointer-events: none; z-index: 3000;';
            hint.textContent = 'ESC 키를 눌러 종료';
            document.body.appendChild(hint);
            setTimeout(() => hint.style.opacity = '1', 500);
            setTimeout(() => hint.style.opacity = '0', 3500);
        }
    }
}
