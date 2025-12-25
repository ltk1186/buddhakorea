/**
 * PaliText Component
 *
 * Renders Pali text with tokenization and double-click word lookup.
 * Per PHASE0_DECISIONS.md Section 0.3: Double-click triggers DPD lookup.
 *
 * Phase 3: Added search highlighting support
 * Phase 4: Added hover preview support (300ms delay)
 */
import { useCallback, useMemo, useRef } from 'react';
import { tokenizePali, normalizeWord, isValidLookupWord } from '@/utils/paliTokenizer';
import { highlightMatches } from '@/utils/textHighlight';
import { useDpd } from '@/hooks';
import { useLiteratureStore, useUIStore } from '@/store';
import styles from './PaliText.module.css';

interface PaliTextProps {
  text: string;
  className?: string;
  highlightQuery?: string;
}

export function PaliText({ text, className = '', highlightQuery }: PaliTextProps) {
  const { lookupAndAddToChat } = useDpd();
  const { isSearchMode, searchQuery } = useLiteratureStore();
  const {
    enableDpdHoverPreview,
    dpdHoverDelay,
    showDpdPreview,
  } = useUIStore();

  // Ref for hover timeout
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Use provided highlightQuery or global search query
  const query = highlightQuery ?? (isSearchMode ? searchQuery : '');

  // Tokenize text (memoized)
  const tokens = useMemo(() => tokenizePali(text), [text]);

  // Handle double-click on a word
  const handleWordDoubleClick = useCallback(
    (word: string) => {
      if (isValidLookupWord(word)) {
        lookupAndAddToChat(word);
        // Remove browser selection highlight to make lookup feel instant/intentional.
        window.getSelection()?.removeAllRanges();
      }
    },
    [lookupAndAddToChat]
  );

  // Handle mouse enter on a word (hover preview)
  const handleWordMouseEnter = useCallback(
    (word: string, event: React.MouseEvent) => {
      if (!enableDpdHoverPreview || !isValidLookupWord(word)) return;

      // Clear any existing timeout
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current);
      }

      // Set new timeout for delayed preview
      hoverTimeoutRef.current = setTimeout(() => {
        const rect = (event.target as HTMLElement).getBoundingClientRect();
        showDpdPreview(normalizeWord(word), {
          x: rect.left,
          y: rect.bottom
        });
      }, dpdHoverDelay);
    },
    [enableDpdHoverPreview, dpdHoverDelay, showDpdPreview]
  );

  // Handle mouse leave on a word
  const handleWordMouseLeave = useCallback(() => {
    // Clear timeout if still pending
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
      hoverTimeoutRef.current = null;
    }
  }, []);

  // Render text with highlighting
  const renderWithHighlight = useCallback(
    (tokenText: string) => {
      if (!query) return tokenText;

      const parts = highlightMatches(tokenText, query);
      return parts.map((part, idx) =>
        part.isMatch ? (
          <mark key={idx} className={styles.highlight}>
            {part.text}
          </mark>
        ) : (
          part.text
        )
      );
    },
    [query]
  );

  return (
    <span className={`${styles.paliText} ${className}`}>
      {tokens.map((token, index) => {
        if (token.isWord) {
          return (
            <span
              key={index}
              className={styles.word}
              onDoubleClick={() => handleWordDoubleClick(token.text)}
              onMouseEnter={(e) => handleWordMouseEnter(token.text, e)}
              onMouseLeave={handleWordMouseLeave}
              title={enableDpdHoverPreview ? "호버로 미리보기, 더블클릭하여 상세 조회" : "더블클릭하여 사전 조회"}
            >
              {renderWithHighlight(token.text)}
            </span>
          );
        }
        // Non-word tokens (spaces, punctuation)
        return <span key={index}>{token.text}</span>;
      })}
    </span>
  );
}
