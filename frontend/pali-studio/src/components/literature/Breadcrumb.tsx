/**
 * Breadcrumb component - shows current location in literature hierarchy
 */
import { useLiteratureStore } from '@/store';
import { useUrlSync } from '@/hooks/useUrlSync';
import { getLiteraturePrimaryTitle } from '@/utils/literatureDisplay';
import { getHierarchyLabelKo } from '@/utils/hierarchyLabels';
import styles from './Breadcrumb.module.css';

interface BreadcrumbProps {
  vaggaName?: string | null;
  suttaName?: string | null;
}

export function Breadcrumb({ vaggaName, suttaName }: BreadcrumbProps) {
  const {
    currentLiterature,
    currentVaggaId,
    currentSuttaId,
    setCurrentLocation,
    loadSegmentsForLocation,
  } = useLiteratureStore();
  const { copyCurrentLink } = useUrlSync();

  if (!currentLiterature) return null;

  // Get hierarchy labels from literature metadata
  const labels = currentLiterature.hierarchy_labels || {};
  const level1Label = getHierarchyLabelKo(labels.level_1, '품');
  const level2Label = getHierarchyLabelKo(labels.level_2, '경');

  const handleLiteratureClick = () => {
    setCurrentLocation(null, null);
    loadSegmentsForLocation(currentLiterature.id, null, null);
  };

  const handleVaggaClick = () => {
    if (currentVaggaId !== null) {
      setCurrentLocation(currentVaggaId, null);
      loadSegmentsForLocation(currentLiterature.id, currentVaggaId, null);
    }
  };

  const handleCopyLink = async () => {
    const url = copyCurrentLink();
    // Show brief feedback (could enhance with toast)
    alert(`링크가 복사되었습니다:\n${url}`);
  };

  return (
    <nav className={styles.breadcrumb} aria-label="현재 위치">
      <ol className={styles.list}>
        {/* Literature root */}
        <li className={styles.item}>
          <button
            className={`${styles.link} ${!currentVaggaId && !currentSuttaId ? styles.current : ''}`}
            onClick={handleLiteratureClick}
          >
            {getLiteraturePrimaryTitle(currentLiterature)}
          </button>
        </li>

        {/* Vagga level */}
        {currentVaggaId !== null && vaggaName && (
          <>
            <li className={styles.separator} aria-hidden="true">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </li>
            <li className={styles.item}>
              <button
                className={`${styles.link} ${!currentSuttaId ? styles.current : ''}`}
                onClick={handleVaggaClick}
              >
                <span className={styles.label}>{level1Label}:</span>
                {vaggaName}
              </button>
            </li>
          </>
        )}

        {/* Sutta level */}
        {currentSuttaId !== null && suttaName && (
          <>
            <li className={styles.separator} aria-hidden="true">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </li>
            <li className={styles.item}>
              <span className={`${styles.link} ${styles.current}`}>
                <span className={styles.label}>{level2Label}:</span>
                {suttaName}
              </span>
            </li>
          </>
        )}
      </ol>

      {/* Copy link button */}
      <button
        className={styles.copyButton}
        onClick={handleCopyLink}
        title="현재 위치 링크 복사"
        aria-label="현재 위치 링크 복사"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
        </svg>
        <span>링크 복사</span>
      </button>
    </nav>
  );
}
