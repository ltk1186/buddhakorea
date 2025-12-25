/**
 * LiteraturePanel - main content panel showing segments
 * Phase 6: Added toast notifications for translation feedback
 */
import { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import { useLiterature, useUrlSync } from '@/hooks';
import { useLiteratureStore, useUIStore, toast } from '@/store';
import { Loading, Button, ErrorMessage } from '@/components/common';
import { SegmentCard } from './SegmentCard';
import { Breadcrumb } from './Breadcrumb';
import { translateBatchStream } from '@/api/translate';
import styles from './LiteraturePanel.module.css';
import { getLiteraturePrimaryTitle } from '@/utils/literatureDisplay';

const FONT_SIZE_ORDER = ['small', 'medium', 'large', 'xlarge', 'xxlarge'] as const;

export function LiteraturePanel() {
  const {
    currentLiterature,
    segments,
    isLoading,
    error,
    hasMore,
    loadMoreSegments,
  } = useLiterature();

  const {
    selectedSegmentIds,
    clearSelection,
    updateSegmentTranslation,
    isSearchMode,
    searchQuery,
    searchPage,
    searchResults,
    searchMeta,
    performSearch,
    clearSearch,
    translatingSegmentIds,
    startTranslating,
    stopTranslating,
  } = useLiteratureStore();

  const { fontSize, setFontSize, contentMaxWidth, setContentMaxWidth } = useUIStore();

  // Initialize URL sync
  useUrlSync();

  // Get vagga/sutta names from first segment
  const { vaggaName, suttaName } = useMemo(() => {
    const firstSegment = segments[0];
    return {
      vaggaName: firstSegment?.vagga_name || null,
      suttaName: firstSegment?.sutta_name || null,
    };
  }, [segments]);

  const [isBatchTranslating, setIsBatchTranslating] = useState(false);
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0 });
  const abortControllerRef = useRef<AbortController | null>(null);

  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  // Sticky header with toggle
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [isHeaderExpanded, setIsHeaderExpanded] = useState(false);

  // Batch translation handler using the new batch endpoint (max 5 segments per request)
  const handleBatchTranslate = async () => {
    if (!currentLiterature || selectedSegmentIds.size === 0) return;

    const selectedIds = Array.from(selectedSegmentIds);
    const untranslatedIds = selectedIds.filter(id => {
      const segment = segments.find(s => s.id === id);
      return segment && !segment.is_translated;
    });

    if (untranslatedIds.length === 0) return;

    setIsBatchTranslating(true);
    setBatchProgress({ current: 0, total: untranslatedIds.length });
    abortControllerRef.current = new AbortController();

    // Mark all segments as translating in global state
    untranslatedIds.forEach(id => startTranslating(id));

    let successCount = 0;
    let errorCount = 0;

    // Split into batches of 3 (server max, reduced for reliability)
    const BATCH_SIZE = 3;
    const batches: number[][] = [];
    for (let i = 0; i < untranslatedIds.length; i += BATCH_SIZE) {
      batches.push(untranslatedIds.slice(i, i + BATCH_SIZE));
    }

    try {
      for (const batch of batches) {
        if (abortControllerRef.current?.signal.aborted) break;

        try {
          await translateBatchStream(
            {
              literature_id: currentLiterature.id,
              segment_ids: batch,
              force: false,
            },
            {
              onStart: (segmentIds) => {
                console.log('Batch translation started:', segmentIds);
              },
              onSegmentComplete: (segmentId, translation) => {
                console.log('Segment complete:', segmentId);
                updateSegmentTranslation(segmentId, translation);
                stopTranslating(segmentId);
                successCount++;
                setBatchProgress(prev => ({ ...prev, current: prev.current + 1 }));
              },
              onError: (error, segmentId) => {
                console.error(`Translation error${segmentId ? ` for segment ${segmentId}` : ''}:`, error);
                if (segmentId) stopTranslating(segmentId);
                errorCount++;
                setBatchProgress(prev => ({ ...prev, current: prev.current + 1 }));
              },
              onFallbackStart: (reason) => {
                console.log('Fallback triggered:', reason);
              },
            },
            { signal: abortControllerRef.current?.signal }
          );
        } catch (err) {
          // Check if this was an abort
          if (err instanceof Error && err.name === 'AbortError') {
            console.log('Batch translation aborted by user');
            batch.forEach(id => stopTranslating(id));
            break;
          }
          console.error('Batch translation failed:', err);
          // Mark all batch segments as done on failure
          batch.forEach(id => stopTranslating(id));
          errorCount += batch.length;
        }
      }

      // Show result toast
      if (abortControllerRef.current?.signal.aborted) {
        toast.warning(`번역이 취소되었습니다 (${successCount}개 완료)`);
      } else if (errorCount > 0) {
        toast.warning(`번역 완료: ${successCount}개 성공, ${errorCount}개 실패`);
      } else {
        toast.success(`${successCount}개 세그먼트 번역 완료`);
      }
    } catch (err) {
      toast.error('번역 중 오류가 발생했습니다');
    } finally {
      setIsBatchTranslating(false);
      setBatchProgress({ current: 0, total: 0 });
      // Clear all translating states in case any are left
      untranslatedIds.forEach(id => stopTranslating(id));
      clearSelection();
      abortControllerRef.current = null;
    }
  };

  const handleCancelBatch = () => {
    abortControllerRef.current?.abort();
  };

  const selectedCount = selectedSegmentIds.size;
  const untranslatedSelectedCount = Array.from(selectedSegmentIds).filter(id => {
    const segment = segments.find(s => s.id === id);
    return segment && !segment.is_translated;
  }).length;

  const translationPercentage = currentLiterature?.total_segments
    ? Math.round((currentLiterature.translated_segments / currentLiterature.total_segments) * 100)
    : 0;

  const fontSizeIndex = FONT_SIZE_ORDER.indexOf(fontSize);
  const isMinFontSize = fontSizeIndex <= 0;
  const isMaxFontSize = fontSizeIndex >= FONT_SIZE_ORDER.length - 1;

  const handleDecreaseFont = () => {
    if (isMinFontSize) return;
    setFontSize(FONT_SIZE_ORDER[Math.max(0, fontSizeIndex - 1)]);
  };

  const handleIncreaseFont = () => {
    if (isMaxFontSize) return;
    setFontSize(FONT_SIZE_ORDER[Math.min(FONT_SIZE_ORDER.length - 1, fontSizeIndex + 1)]);
  };

  // Infinite scroll
  const handleObserver = useCallback((entries: IntersectionObserverEntry[]) => {
    const target = entries[0];
    if (target.isIntersecting && hasMore && !isLoading) {
      loadMoreSegments();
    }
  }, [hasMore, isLoading, loadMoreSegments]);

  useEffect(() => {
    if (observerRef.current) {
      observerRef.current.disconnect();
    }

    observerRef.current = new IntersectionObserver(handleObserver, {
      root: null,
      rootMargin: '100px',
      threshold: 0,
    });

    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current);
    }

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [handleObserver]);

  // Toggle header expansion
  const toggleHeader = useCallback(() => {
    setIsHeaderExpanded(prev => !prev);
  }, []);

  if (!currentLiterature) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyContent}>
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
          <h2>문헌을 선택하세요</h2>
          <p>드롭다운 또는 사이드바에서 빠알리 주석서를 선택하여 시작하세요.</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.errorContainer}>
        <ErrorMessage
          title="데이터 로딩 오류"
          message={error}
          onRetry={() => window.location.reload()}
        />
      </div>
    );
  }

  return (
    <div ref={panelRef} className={styles.panel}>
      {/* Compact sticky header with toggle */}
      <header
        className={`${styles.stickyHeader} ${isHeaderExpanded ? styles.expanded : ''}`}
        role="banner"
      >
        {/* Main row - always visible */}
        <div className={styles.headerMain}>
          <div className={styles.titleRow}>
            <h2 className={styles.title}>
              {getLiteraturePrimaryTitle(currentLiterature)}
            </h2>
            <span className={styles.paliNameInline}>· {currentLiterature.pali_name || currentLiterature.id}</span>
            {translatingSegmentIds.size > 0 && (
              <span className={styles.translatingInline}>
                <span className={styles.spinner} />
                {translatingSegmentIds.size === 1 ? '번역 중' : `${translatingSegmentIds.size}개 번역 중`}
              </span>
            )}
            <button
              type="button"
              className={styles.toggleButton}
              onClick={toggleHeader}
              aria-expanded={isHeaderExpanded}
              aria-label={isHeaderExpanded ? '헤더 접기' : '헤더 펼치기'}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className={isHeaderExpanded ? styles.rotated : ''}
              >
                <path d="M6 9l6 6 6-6" />
              </svg>
            </button>
          </div>

          <div className={styles.headerControls}>
            <div className={styles.fontControls} aria-label="글자 크기 조절">
              <button
                type="button"
                className={styles.fontButton}
                onClick={handleDecreaseFont}
                disabled={isMinFontSize}
                aria-label="글자 크기 줄이기"
              >
                -
              </button>
              <button
                type="button"
                className={styles.fontButton}
                onClick={handleIncreaseFont}
                disabled={isMaxFontSize}
                aria-label="글자 크기 늘리기"
              >
                +
              </button>
            </div>
            <div className={styles.contentWidthControl} aria-label="컨텐츠 너비 조절">
              <input
                type="range"
                min="600"
                max="1600"
                step="50"
                value={contentMaxWidth}
                onChange={(e) => setContentMaxWidth(parseInt(e.target.value))}
                className={styles.contentWidthSlider}
                aria-label="너비 조절"
              />
            </div>
            <div className={styles.statsCompact}>
              {translatingSegmentIds.size > 0 ? (
                <span className={styles.translatingBadge}>
                  <span className={styles.spinner} />
                  {isBatchTranslating
                    ? `번역 중 ${batchProgress.current}/${batchProgress.total}`
                    : translatingSegmentIds.size === 1
                      ? '번역 중'
                      : `${translatingSegmentIds.size}개 번역 중`
                  }
                </span>
              ) : (
                <span className={styles.stat}>
                  {currentLiterature.translated_segments}/{currentLiterature.total_segments} ({translationPercentage}%)
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Expanded content - description */}
        {isHeaderExpanded && currentLiterature.display_metadata?.description && (
          <div className={styles.headerExpanded}>
            <p className={styles.description}>{currentLiterature.display_metadata.description}</p>
          </div>
        )}

        {/* Selection/batch translation row */}
        {(selectedCount > 0 || isBatchTranslating) && (
          <div className={styles.headerStatusRow} role="status" aria-live="polite">
            <div className={styles.statusIndicators}>
              {selectedCount > 0 && (
                <span className={styles.selectionBadge}>
                  {selectedCount}개 선택
                  {untranslatedSelectedCount > 0 && untranslatedSelectedCount !== selectedCount && (
                    <span className={styles.untranslatedNote}> (미번역 {untranslatedSelectedCount})</span>
                  )}
                </span>
              )}
            </div>
            <div className={styles.statusActions}>
              {selectedCount > 0 && !isBatchTranslating && (
                <Button variant="ghost" size="sm" onClick={clearSelection}>
                  선택 해제
                </Button>
              )}
              {untranslatedSelectedCount > 0 && !isBatchTranslating && (
                <Button variant="primary" size="sm" onClick={handleBatchTranslate}>
                  일괄 번역 ({untranslatedSelectedCount}개)
                </Button>
              )}
              {isBatchTranslating && (
                <Button variant="ghost" size="sm" onClick={handleCancelBatch}>
                  취소
                </Button>
              )}
            </div>
          </div>
        )}
      </header>

      {/* Breadcrumb navigation */}
      <Breadcrumb vaggaName={vaggaName} suttaName={suttaName} />

      {/* Search results banner */}
      {isSearchMode && (
        <div
          className={styles.searchResultsBanner}
          role="status"
          aria-live="polite"
          aria-label="검색 결과"
        >
          <div className={styles.searchResultsInfo}>
            <div className={styles.searchSummary}>
              <span className={styles.searchQuery}>"{searchQuery}"</span>
              {searchMeta && (
                <span className={styles.searchStats}>
                  총 {searchMeta.total_occurrences}회 · {searchMeta.hit_segments_count}개 세그먼트
                  {searchMeta.hit_segments_count > searchMeta.returned_count && (
                    <> (상위 {searchMeta.returned_count}개 표시)</>
                  )}
                </span>
              )}
              {!searchMeta && <span>검색 결과: {searchResults.length}개</span>}
            </div>

            {currentLiterature && searchMeta && (searchMeta.pages.length > 0 || searchMeta.unknown_page_occurrences > 0) && (
              <div className={styles.searchPages} role="list" aria-label="페이지 분포">
                <button
                  type="button"
                  className={`${styles.pageChip} ${searchPage === null ? styles.pageChipActive : ''}`}
                  onClick={() => performSearch(currentLiterature.id, searchQuery, { page: null })}
                >
                  전체
                </button>
                {searchMeta.pages.map((p) => (
                  <button
                    key={p.page_number}
                    type="button"
                    className={`${styles.pageChip} ${searchPage === p.page_number ? styles.pageChipActive : ''}`}
                    onClick={() => performSearch(currentLiterature.id, searchQuery, { page: p.page_number })}
                  >
                    p.{p.page_number} ({p.occurrences})
                  </button>
                ))}
                {searchMeta.unknown_page_occurrences > 0 && (
                  <button
                    type="button"
                    className={`${styles.pageChip} ${searchPage === 0 ? styles.pageChipActive : ''}`}
                    onClick={() => performSearch(currentLiterature.id, searchQuery, { page: 0 })}
                  >
                    미상 ({searchMeta.unknown_page_occurrences})
                  </button>
                )}
              </div>
            )}

            {searchMeta && searchMeta.pages.length === 0 && searchMeta.total_occurrences > 0 && (
              <div className={styles.searchPagesHint}>
                페이지 정보 없음 (PDF 재파싱 시 표시 가능)
              </div>
            )}
          </div>
          <Button variant="ghost" size="sm" onClick={clearSearch} aria-label="검색 결과 닫기">
            검색 취소
          </Button>
        </div>
      )}

      <div
        className={styles.segments}
        role="feed"
        aria-label={isSearchMode ? '검색 결과 목록' : '세그먼트 목록'}
        aria-busy={isLoading}
      >
        {/* Show search results or regular segments */}
        {(isSearchMode ? searchResults : segments).map((segment) => (
          <SegmentCard key={segment.id} segment={segment} />
        ))}

        {/* Load more trigger (only for non-search mode) */}
        {!isSearchMode && (
          <div ref={loadMoreRef} className={styles.loadMore}>
            {isLoading && <Loading text="세그먼트 로딩 중..." />}
            {!hasMore && segments.length > 0 && (
              <p className={styles.endMessage}>마지막 세그먼트입니다</p>
            )}
          </div>
        )}

        {/* Empty search results */}
        {isSearchMode && searchResults.length === 0 && !isLoading && (
          <div className={styles.emptySearch}>
            <p>검색 결과가 없습니다.</p>
          </div>
        )}
      </div>
    </div>
  );
}
