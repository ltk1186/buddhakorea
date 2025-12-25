/**
 * MobileContentView - Full-screen content/segments view for mobile
 *
 * Purpose: Read Pali text segments and initiate/view translations.
 * Reference: Perplexity answer view, Gemini response cards
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import { useLiterature, useUrlSync } from '@/hooks';
import { useLiteratureStore, useUIStore, toast } from '@/store';
import { Loading, Button, ErrorMessage } from '@/components/common';
import { SegmentCard } from '@/components/literature/SegmentCard';
import { translateBatchStream } from '@/api/translate';
import { getLiteraturePrimaryTitle } from '@/utils/literatureDisplay';
import styles from './MobileContentView.module.css';

export function MobileContentView() {
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
  } = useLiteratureStore();

  const { setMobileView } = useUIStore();

  // Initialize URL sync
  useUrlSync();

  const [isBatchTranslating, setIsBatchTranslating] = useState(false);
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0 });
  const abortControllerRef = useRef<AbortController | null>(null);

  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);

  const translationPercentage = currentLiterature?.total_segments
    ? Math.round((currentLiterature.translated_segments / currentLiterature.total_segments) * 100)
    : 0;

  const selectedCount = selectedSegmentIds.size;
  const untranslatedSelectedCount = Array.from(selectedSegmentIds).filter(id => {
    const segment = segments.find(s => s.id === id);
    return segment && !segment.is_translated;
  }).length;

  // Batch translation handler
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

    let successCount = 0;
    let errorCount = 0;

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
              onSegmentComplete: (segmentId, translation) => {
                updateSegmentTranslation(segmentId, translation);
                successCount++;
                setBatchProgress(prev => ({ ...prev, current: prev.current + 1 }));
              },
              onError: (error, segmentId) => {
                console.error(`Translation error${segmentId ? ` for segment ${segmentId}` : ''}:`, error);
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
          if (err instanceof Error && err.name === 'AbortError') {
            console.log('Batch translation aborted by user');
            break;
          }
          console.error('Batch translation failed:', err);
          errorCount += batch.length;
        }
      }

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
      clearSelection();
      abortControllerRef.current = null;
    }
  };

  const handleCancelBatch = () => {
    abortControllerRef.current?.abort();
  };

  // Navigate to chat with selected segment(s)
  const handleAskQuestion = () => {
    setMobileView('chat');
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

  // Empty state - no literature selected
  if (!currentLiterature) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyContent}>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
          <h2>문헌을 선택하세요</h2>
          <p>목록에서 문헌을 선택하여 시작하세요.</p>
          <Button variant="primary" onClick={() => setMobileView('literature')}>
            문헌 목록 보기
          </Button>
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
    <div className={styles.view}>
      {/* Compact header */}
      <header className={styles.header}>
        <div className={styles.headerMain}>
          <h1 className={styles.title}>{getLiteraturePrimaryTitle(currentLiterature)}</h1>
          <span className={styles.stats}>
            {translationPercentage}% · {currentLiterature.translated_segments}/{currentLiterature.total_segments}
          </span>
        </div>
      </header>

      {/* Selection toolbar */}
      {(selectedCount > 0 || isBatchTranslating) && (
        <div className={styles.toolbar}>
          <div className={styles.toolbarInfo}>
            {isBatchTranslating ? (
              <span className={styles.progress}>
                번역 중 {batchProgress.current}/{batchProgress.total}
              </span>
            ) : (
              <span>{selectedCount}개 선택</span>
            )}
          </div>
          <div className={styles.toolbarActions}>
            {!isBatchTranslating && (
              <>
                <Button variant="ghost" size="sm" onClick={clearSelection}>
                  해제
                </Button>
                {untranslatedSelectedCount > 0 && (
                  <Button variant="primary" size="sm" onClick={handleBatchTranslate}>
                    번역 ({untranslatedSelectedCount})
                  </Button>
                )}
                <Button variant="ghost" size="sm" onClick={handleAskQuestion}>
                  질문
                </Button>
              </>
            )}
            {isBatchTranslating && (
              <Button variant="ghost" size="sm" onClick={handleCancelBatch}>
                취소
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Segment list */}
      <div
        ref={contentRef}
        className={styles.content}
        role="feed"
        aria-label="세그먼트 목록"
        aria-busy={isLoading}
      >
        {segments.map((segment) => (
          <SegmentCard key={segment.id} segment={segment} />
        ))}

        {/* Load more trigger */}
        <div ref={loadMoreRef} className={styles.loadMore}>
          {isLoading && <Loading text="로딩 중..." />}
          {!hasMore && segments.length > 0 && (
            <p className={styles.endMessage}>마지막입니다</p>
          )}
        </div>
      </div>

      {/* Floating action button for asking questions */}
      {selectedCount > 0 && !isBatchTranslating && (
        <button
          className={styles.fab}
          onClick={handleAskQuestion}
          aria-label="선택한 세그먼트에 대해 질문하기"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </button>
      )}
    </div>
  );
}
