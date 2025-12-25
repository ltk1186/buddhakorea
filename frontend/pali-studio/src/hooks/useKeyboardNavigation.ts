/**
 * Keyboard Navigation Hook
 *
 * Provides keyboard shortcuts for navigating segments.
 * Per PHASE0_DECISIONS.md Section 0.5:
 * - `/` = Focus search
 * - `j` = Next segment
 * - `k` = Previous segment
 * - `t` = Translate current segment
 * - `Space` = Toggle segment selection
 * - `Escape` = Close search/clear selection
 * - `?` = Show keyboard shortcuts (todo)
 */
import { useEffect, useCallback } from 'react';
import { useLiteratureStore, useUIStore, toast } from '@/store';

interface UseKeyboardNavigationOptions {
  searchInputRef?: React.RefObject<HTMLInputElement>;
  onTranslate?: (segmentId: number) => Promise<void>;
}

export function useKeyboardNavigation(options: UseKeyboardNavigationOptions = {}) {
  const { searchInputRef, onTranslate } = options;
  const {
    segments,
    currentSegment,
    selectSegment,
    isSearchMode,
    searchResults,
    clearSearch,
    isSelectMode,
    clearSelection,
    toggleSegmentSelection,
  } = useLiteratureStore();

  const {
    keyboardFocusedSegmentId,
    setKeyboardFocusedSegmentId,
    setIsKeyboardNavigating,
  } = useUIStore();

  // Get current list of segments (search results or all segments)
  const activeSegments = isSearchMode ? searchResults : segments;

  // Navigate to next/previous segment
  const navigateSegment = useCallback(
    (direction: 1 | -1) => {
      if (activeSegments.length === 0) return;

      // Use keyboard focused segment or current segment as reference
      const referenceId = keyboardFocusedSegmentId ?? currentSegment?.id;
      const currentIndex = referenceId
        ? activeSegments.findIndex((s) => s.id === referenceId)
        : -1;

      let newIndex: number;
      if (currentIndex === -1) {
        // No current selection, start from beginning or end
        newIndex = direction === 1 ? 0 : activeSegments.length - 1;
      } else {
        newIndex = currentIndex + direction;
        // Clamp to valid range
        newIndex = Math.max(0, Math.min(activeSegments.length - 1, newIndex));
      }

      const newSegment = activeSegments[newIndex];
      if (newSegment) {
        selectSegment(newSegment);
        setKeyboardFocusedSegmentId(newSegment.id);
        // Scroll into view
        scrollToSegment(newSegment.id);
      }
    },
    [activeSegments, currentSegment, keyboardFocusedSegmentId, selectSegment, setKeyboardFocusedSegmentId]
  );

  // Scroll to a segment element
  const scrollToSegment = useCallback((segmentId: number) => {
    // Use requestAnimationFrame to ensure DOM is updated
    requestAnimationFrame(() => {
      const element = document.querySelector(`[data-segment-id="${segmentId}"]`);
      if (element) {
        element.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
        });
      }
    });
  }, []);

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      // Don't handle if typing in an input/textarea
      const target = event.target as HTMLElement;
      const isTextInput =
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable;

      // Let platform/browser shortcuts through (e.g., Cmd/Ctrl+K, Cmd/Ctrl+F).
      if (event.metaKey || event.ctrlKey || event.altKey) return;

      // Allow Escape in text inputs
      if (event.key === 'Escape') {
        if (isSearchMode) {
          clearSearch();
          event.preventDefault();
        } else if (isSelectMode) {
          clearSelection();
          event.preventDefault();
        }
        // Clear keyboard focus
        setKeyboardFocusedSegmentId(null);
        // Blur the input
        if (isTextInput) {
          (target as HTMLElement).blur();
        }
        return;
      }

      // Don't process other shortcuts in text inputs
      if (isTextInput) return;

      switch (event.key) {
        case '/':
          // Focus search input
          event.preventDefault();
          searchInputRef?.current?.focus();
          break;

        case 'j':
        case 'ArrowDown':
          // Next segment
          event.preventDefault();
          navigateSegment(1);
          break;

        case 'k':
        case 'ArrowUp':
          // Previous segment
          event.preventDefault();
          navigateSegment(-1);
          break;

        case 't':
        case 'T':
          // Translate current segment
          event.preventDefault();
          {
            const targetSegment = keyboardFocusedSegmentId
              ? activeSegments.find(s => s.id === keyboardFocusedSegmentId)
              : currentSegment;
            if (targetSegment && !targetSegment.is_translated && onTranslate) {
              onTranslate(targetSegment.id);
            } else if (targetSegment?.is_translated) {
              toast.info('이미 번역된 세그먼트입니다');
            }
          }
          break;

        case ' ':
          // Toggle selection (space)
          event.preventDefault();
          {
            const targetId = keyboardFocusedSegmentId ?? currentSegment?.id;
            const targetSeg = targetId ? activeSegments.find(s => s.id === targetId) : null;
            if (targetSeg && !targetSeg.is_translated) {
              toggleSegmentSelection(targetId!);
            }
          }
          break;

        case 'Enter':
          // Toggle expansion of current segment (handled by SegmentCard)
          break;

        case '?':
          // Show help dialog (future)
          toast.info('키보드 단축키: j/k(이동), t(번역), Space(선택), /(검색), Esc(취소)');
          break;
      }
    },
    [
      isSearchMode,
      isSelectMode,
      clearSearch,
      clearSelection,
      searchInputRef,
      activeSegments,
      currentSegment,
      keyboardFocusedSegmentId,
      navigateSegment,
      onTranslate,
      setKeyboardFocusedSegmentId,
      toggleSegmentSelection,
    ]
  );

  // Clear keyboard focus when user clicks (mouse navigation)
  useEffect(() => {
    const handleMouseDown = () => {
      if (keyboardFocusedSegmentId !== null) {
        setIsKeyboardNavigating(false);
      }
    };
    document.addEventListener('mousedown', handleMouseDown);
    return () => document.removeEventListener('mousedown', handleMouseDown);
  }, [keyboardFocusedSegmentId, setIsKeyboardNavigating]);

  // Register keyboard event listener
  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return {
    navigateSegment,
    scrollToSegment,
    keyboardFocusedSegmentId,
  };
}
