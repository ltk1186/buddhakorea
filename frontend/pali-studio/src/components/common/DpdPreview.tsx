/**
 * DpdPreview - Hover popup for DPD dictionary lookup
 * Shows a brief definition when hovering over Pali words
 */
import { useEffect, useState, useRef } from 'react';
import { lookupWordBrief } from '@/api/dpd';
import { Loading } from './Loading';
import styles from './DpdPreview.module.css';

interface DpdPreviewProps {
  word: string;
  position: { x: number; y: number };
  onClose: () => void;
  onOpenFull: () => void;
}

interface BriefEntry {
  headword: string;
  definition: string;
  grammar: string;
}

type BriefCacheValue =
  | { status: 'ok'; entry: BriefEntry }
  | { status: 'error'; message: string };

const briefCache = new Map<string, BriefCacheValue>();

export function DpdPreview({ word, position, onClose, onOpenFull }: DpdPreviewProps) {
  const [entry, setEntry] = useState<BriefEntry | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const popupRef = useRef<HTMLDivElement>(null);

  // Fetch brief entry on mount
  useEffect(() => {
    let cancelled = false;

    const fetchEntry = async () => {
      try {
        const cached = briefCache.get(word);
        if (cached) {
          if (!cancelled) {
            if (cached.status === 'ok') {
              setEntry(cached.entry);
              setError(null);
            } else {
              setEntry(null);
              setError(cached.message);
            }
            setIsLoading(false);
          }
          return;
        }

        setIsLoading(true);
        setError(null);
        const result = await lookupWordBrief(word);
        if (!cancelled) {
          setEntry(result);
          briefCache.set(word, { status: 'ok', entry: result });
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : 'Unknown error';
          const display = message.includes('404') ? '사전에 없음' : '조회 오류';
          setError(display);
          briefCache.set(word, { status: 'error', message: display });
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchEntry();

    return () => {
      cancelled = true;
    };
  }, [word]);

  // Calculate position to keep popup in viewport
  useEffect(() => {
    if (popupRef.current) {
      const popup = popupRef.current;
      const rect = popup.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      // Adjust horizontal position
      if (rect.right > viewportWidth - 10) {
        popup.style.left = `${viewportWidth - rect.width - 10}px`;
      }
      if (rect.left < 10) {
        popup.style.left = '10px';
      }

      // Adjust vertical position (show above if too low)
      if (rect.bottom > viewportHeight - 10) {
        popup.style.top = `${position.y - rect.height - 10}px`;
      }
    }
  }, [position, entry, error]);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div
      ref={popupRef}
      className={styles.preview}
      style={{
        left: position.x,
        top: position.y + 5,
      }}
      onMouseLeave={onClose}
    >
      {isLoading && (
        <div className={styles.loading}>
          <Loading size="sm" />
        </div>
      )}

      {error && (
        <div className={styles.error}>
          <span className={styles.word}>{word}</span>
          <span className={styles.errorText}>{error}</span>
        </div>
      )}

      {entry && !isLoading && (
        <>
          <div className={styles.header}>
            <span className={styles.headword}>{entry.headword}</span>
            <span className={styles.grammar}>{entry.grammar}</span>
          </div>
          <p className={styles.definition}>{entry.definition}</p>
          <button className={styles.moreButton} onClick={onOpenFull}>
            자세히 보기
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </>
      )}
    </div>
  );
}
