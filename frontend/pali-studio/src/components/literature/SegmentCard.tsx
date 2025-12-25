/**
 * SegmentCard component - displays a single text segment
 *
 * Phase 1 Updates:
 * - Auto-expand when selected (accordion mode)
 * - Progressive disclosure for translation content
 * - Improved accessibility with proper ARIA attributes
 *
 * Phase 5: Memoization for performance
 */
import { memo, useCallback, useState } from 'react';
import { useTranslate } from '@/hooks';
import { useLiteratureStore, useUIStore } from '@/store';
import { Button, Badge, Card, PaliText } from '@/components/common';
import type { Segment } from '@/types/literature';
import styles from './SegmentCard.module.css';

interface SegmentCardProps {
  segment: Segment;
}

function SegmentCardComponent({ segment }: SegmentCardProps) {
  const {
    selectSegment,
    currentSegment,
    isSelectMode,
    selectedSegmentIds,
    lastSelectedSegmentId,
    toggleSelectMode,
    toggleSegmentSelection,
    selectRange
  } = useLiteratureStore();
  const {
    showGrammar,
    showLiteralTranslation,
    showFreeTranslation,
    showExplanation,
    showSummary,
    keyboardFocusedSegmentId,
    isKeyboardNavigating
  } = useUIStore();
  const { translateSegment, isTranslating, streamingContent } = useTranslate();

  const isSelected = currentSegment?.id === segment.id;
  const isChecked = selectedSegmentIds.has(segment.id);
  const isCurrentlyTranslating = isTranslating && isSelected;
  const isSelectable = !segment.is_translated;
  const isKeyboardFocused = isKeyboardNavigating && keyboardFocusedSegmentId === segment.id;

  const [expandedOverride, setExpandedOverride] = useState<boolean | null>(null);

  // Default behavior: translated segments expand when active-selected.
  const isExpanded = expandedOverride ?? (isSelected && segment.is_translated);

  const handleToggleExpanded = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedOverride((prev) => (prev === null ? !isExpanded : !prev));
  }, [isExpanded]);

  const handleClick = useCallback((e: React.MouseEvent) => {
    const rangeAnchorId = lastSelectedSegmentId;
    selectSegment(segment);

    // Shift+click: range selection for batch mode (prevents browser text selection UX)
    if (e.shiftKey) {
      e.preventDefault();
      if (!isSelectMode) {
        toggleSelectMode();
      }

      if (rangeAnchorId !== null) {
        selectRange(rangeAnchorId, segment.id);
      } else if (!segment.is_translated) {
        toggleSegmentSelection(segment.id);
      }
      return;
    }

    // Normal click: active selection always; batch selection only in select mode.
    if (isSelectMode && !segment.is_translated) {
      toggleSegmentSelection(segment.id);
    }
  }, [
    isSelectMode,
    lastSelectedSegmentId,
    segment,
    selectRange,
    selectSegment,
    toggleSegmentSelection,
    toggleSelectMode,
  ]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.shiftKey) {
      e.preventDefault();
    }
  }, []);

  const handleCheckboxChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation();
    toggleSegmentSelection(segment.id);
  }, [segment.id, toggleSegmentSelection]);

  const handleTranslate = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation();
    selectSegment(segment);
    await translateSegment(segment.id);
  }, [segment, selectSegment, translateSegment]);

  return (
    <Card
      className={`${styles.card} ${isSelected ? styles.selected : ''} ${isChecked ? styles.checked : ''} ${isSelectable ? styles.selectable : ''} ${isKeyboardFocused ? styles.keyboardFocused : ''}`}
      onClick={handleClick}
      onMouseDown={handleMouseDown}
      hoverable
      data-segment-id={segment.id}
      aria-current={isKeyboardFocused ? 'true' : undefined}
      aria-label={`세그먼트 ${segment.paragraph_id}, ${segment.is_translated ? '번역 완료' : '미번역'}`}
      role="article"
    >
      <div className={styles.header}>
        {isSelectMode && (
          <label className={styles.checkbox} onClick={(e) => e.stopPropagation()}>
            <input
              type="checkbox"
              checked={isChecked}
              onChange={handleCheckboxChange}
              disabled={segment.is_translated}
              aria-label={`세그먼트 ${segment.paragraph_id} 선택`}
            />
            <span className={styles.checkmark} aria-hidden="true" />
          </label>
        )}
        <div className={styles.location}>
          {segment.page_number !== null && (
            <span className={styles.pageNumber}>p. {segment.page_number}</span>
          )}
          <span className={styles.paragraphId}>§ {segment.paragraph_id}</span>
          {segment.vagga_name && (
            <span className={styles.vagga}>{segment.vagga_name}</span>
          )}
          {segment.sutta_name && (
            <span className={styles.sutta}>{segment.sutta_name}</span>
          )}
        </div>
        <Badge variant={segment.is_translated ? 'success' : 'warning'}>
          {segment.is_translated ? '번역완료' : '미번역'}
        </Badge>
      </div>

      <div className={styles.originalText}>
        <PaliText text={segment.original_text} />
      </div>

      {/* Streaming content during translation */}
      {isCurrentlyTranslating && streamingContent && (
        <div className={styles.streaming}>
          <div className={styles.streamingIndicator}>
            <span className={styles.spinner} />
            <span>번역 중...</span>
          </div>
          <pre className={styles.streamingContent}>{streamingContent}</pre>
        </div>
      )}

      {/* Translation result - auto-expand when selected */}
      {segment.is_translated && segment.translation && (
        <div
          className={`${styles.translation} ${isExpanded ? styles.expanded : ''}`}
          role="region"
          aria-label="번역 내용"
          aria-expanded={isExpanded}
        >
          {!isExpanded && (
            <>
              {/* Collapsed preview: show first sentence's free translation */}
              {segment.translation.sentences[0]?.free_translation && (
                <p className={styles.preview}>
                  {segment.translation.sentences[0].free_translation}
                </p>
              )}

              <button
                type="button"
                className={styles.expandToggle}
                onClick={handleToggleExpanded}
                aria-label="번역 펼치기"
              >
                번역 펼치기
              </button>
            </>
          )}

          {isExpanded && (
            <>
              <div className={styles.translationContent}>
                {segment.translation.sentences.map((sentence, idx) => (
                  <div key={idx} className={styles.sentence}>
                    <div className={styles.paliSentence}>
                      <PaliText text={sentence.original_pali} />
                    </div>

                    {showFreeTranslation && sentence.free_translation && (
                      <div className={styles.section}>
                        <h4>의역</h4>
                        <p>{sentence.free_translation}</p>
                      </div>
                    )}

                    {showLiteralTranslation && sentence.literal_translation && (
                      <div className={styles.section}>
                        <h4>직역</h4>
                        <p>{sentence.literal_translation}</p>
                      </div>
                    )}

                    {showGrammar && sentence.grammatical_analysis && (
                      <div className={styles.section}>
                        <h4>문법 분석</h4>
                        <pre>{sentence.grammatical_analysis}</pre>
                      </div>
                    )}

                    {showExplanation && sentence.explanation && (
                      <div className={styles.section}>
                        <h4>해설</h4>
                        <p>{sentence.explanation}</p>
                      </div>
                    )}
                  </div>
                ))}

                {showSummary && segment.translation.summary && (
                  <div className={styles.summary}>
                    <h4>요약</h4>
                    <p>{segment.translation.summary}</p>
                  </div>
                )}
              </div>

              <button
                type="button"
                className={styles.expandToggle}
                onClick={handleToggleExpanded}
                aria-label="번역 접기"
              >
                번역 접기
              </button>
            </>
          )}
        </div>
      )}

      {/* Translate button for untranslated segments */}
      {!segment.is_translated && !isCurrentlyTranslating && (
        <div className={styles.actions}>
          <Button
            variant="primary"
            size="sm"
            onClick={handleTranslate}
            loading={isTranslating}
          >
            번역하기
          </Button>
        </div>
      )}
    </Card>
  );
}

// Custom comparison for memo - only re-render when segment data changes
function arePropsEqual(prevProps: SegmentCardProps, nextProps: SegmentCardProps) {
  const prev = prevProps.segment;
  const next = nextProps.segment;

  return (
    prev.id === next.id &&
    prev.is_translated === next.is_translated &&
    prev.original_text === next.original_text &&
    prev.translation === next.translation
  );
}

export const SegmentCard = memo(SegmentCardComponent, arePropsEqual);
