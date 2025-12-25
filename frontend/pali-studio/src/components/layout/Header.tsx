/**
 * Header component with literature selection
 *
 * Phase 3: Added keyboard navigation support
 * Phase 3+: Added settings panel toggle
 * Phase 5: Added debounced search
 * Phase 6: Added translate shortcut integration
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import { useLiterature, useKeyboardNavigation, useDebounce, useTranslate } from '@/hooks';
import { useUIStore, useLiteratureStore } from '@/store';
import styles from './Header.module.css';
import { LiteratureCombobox } from './LiteratureCombobox';

// Minimum characters for auto-search
const MIN_SEARCH_LENGTH = 2;
// Debounce delay for auto-search (ms)
const SEARCH_DEBOUNCE_DELAY = 400;

export function Header() {
  const { literatures, currentLiterature, loadLiterature } = useLiterature();
  const {
    toggleSidebar,
    toggleChatPanel,
    toggleSettingsPanel,
  } = useUIStore();
  const { isSearchMode, performSearch, clearSearch, isLoading, selectSegment, segments } = useLiteratureStore();
  const { translateSegment } = useTranslate();
  const [localSearchQuery, setLocalSearchQuery] = useState('');

  // Debounced search query for auto-search
  const debouncedSearchQuery = useDebounce(localSearchQuery, SEARCH_DEBOUNCE_DELAY);

  // Search input ref for keyboard navigation (/ to focus)
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Handle translate from keyboard shortcut
  const handleTranslateFromKeyboard = useCallback(async (segmentId: number) => {
    const segment = segments.find(s => s.id === segmentId);
    if (segment) {
      selectSegment(segment);
      await translateSegment(segmentId);
    }
  }, [segments, selectSegment, translateSegment]);

  // Initialize keyboard navigation with search input ref and translate callback
  useKeyboardNavigation({ searchInputRef, onTranslate: handleTranslateFromKeyboard });

  // Auto-search when debounced query changes (minimum length)
  useEffect(() => {
    if (!currentLiterature) return;

    const trimmedQuery = debouncedSearchQuery.trim();

    if (trimmedQuery.length >= MIN_SEARCH_LENGTH) {
      performSearch(currentLiterature.id, trimmedQuery);
    } else if (trimmedQuery.length === 0 && isSearchMode) {
      clearSearch();
    }
  }, [debouncedSearchQuery, currentLiterature, performSearch, clearSearch, isSearchMode]);

  const handleLiteratureSelect = useCallback((literatureId: string) => {
    if (!literatureId) return;
    loadLiterature(literatureId);
    clearSearch();
    setLocalSearchQuery('');
  }, [loadLiterature, clearSearch]);

  const handleSearch = () => {
    if (!currentLiterature || !localSearchQuery.trim()) return;
    performSearch(currentLiterature.id, localSearchQuery);
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
    if (e.key === 'Escape') {
      clearSearch();
      setLocalSearchQuery('');
    }
  };

  const handleClearSearch = () => {
    clearSearch();
    setLocalSearchQuery('');
  };

  return (
    <header className={styles.header}>
      <div className={styles.left}>
        <button
          className={styles.menuButton}
          onClick={toggleSidebar}
          aria-label="사이드바 토글"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 12h18M3 6h18M3 18h18" />
          </svg>
        </button>

        <h1 className={styles.title}>빠알리 스튜디오</h1>
      </div>

      <div className={styles.center}>
        <LiteratureCombobox
          literatures={literatures}
          currentLiterature={currentLiterature}
          onSelect={handleLiteratureSelect}
        />

        <div className={`${styles.searchWrapper} ${isSearchMode ? styles.searchActive : ''}`}>
          <svg className={styles.searchIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
          <input
            ref={searchInputRef}
            type="search"
            className={styles.searchInput}
            placeholder={currentLiterature ? "2글자 이상 입력시 자동검색..." : "문헌을 먼저 선택하세요"}
            value={localSearchQuery}
            onChange={(e) => setLocalSearchQuery(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            disabled={!currentLiterature || isLoading}
          />
          {isSearchMode && (
            <button
              className={styles.clearSearchBtn}
              onClick={handleClearSearch}
              aria-label="검색 취소"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      <div className={styles.right}>
        {/* Settings Button */}
        <button
          className={styles.settingsButton}
          onClick={toggleSettingsPanel}
          aria-label="읽기 설정"
          title="읽기 설정"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>

        <button
          className={styles.chatButton}
          onClick={toggleChatPanel}
          aria-label="채팅 패널 토글"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          <span>질문</span>
        </button>
      </div>
    </header>
  );
}
