/**
 * Sidebar component with Tripitaka navigation
 *
 * Responsive behavior:
 * - Desktop: Static sidebar with fixed width
 * - Tablet/Mobile: Drawer pattern with backdrop overlay
 */
import { useEffect, useCallback, useState, useRef } from 'react';
import { useLiterature, useIsMobile, useIsTablet } from '@/hooks';
import { useUIStore } from '@/store';
import { HierarchyNav } from '@/components/literature';
import type { Literature } from '@/types/literature';
import { buildLiteratureSecondaryLine, getLiteraturePrimaryTitle } from '@/utils/literatureDisplay';
import styles from './Sidebar.module.css';

interface SidebarProps {
  width?: number;
  isOpen?: boolean;
  onClose?: () => void;
}

// Calculate translation percentage
const getTranslationPercentage = (lit: Literature): number => {
  if (!lit.total_segments || lit.total_segments === 0) return 0;
  return Math.round((lit.translated_segments / lit.total_segments) * 100);
};

// Get status variant based on percentage
const getStatusVariant = (percentage: number): string => {
  if (percentage === 100) return 'completed';
  if (percentage > 0) return 'inProgress';
  return 'notStarted';
};

const MIN_HIERARCHY_HEIGHT = 100;
const MAX_HIERARCHY_HEIGHT = 500;
const DEFAULT_HIERARCHY_HEIGHT = 250;

export function Sidebar({ width = 320 }: SidebarProps) {
  const { pitakaStructure, literatures, currentLiterature, loadLiterature } = useLiterature();
  const { showSidebar, toggleSidebar } = useUIStore();
  const isMobile = useIsMobile();
  const isTablet = useIsTablet();
  const isDrawerMode = isMobile || isTablet;

  // Hierarchy resizer state
  const [hierarchyHeight, setHierarchyHeight] = useState(() => {
    const stored = localStorage.getItem('hierarchyNavHeight');
    return stored ? parseInt(stored, 10) : DEFAULT_HIERARCHY_HEIGHT;
  });
  const [isResizing, setIsResizing] = useState(false);
  const resizeRef = useRef<{ startY: number; startHeight: number } | null>(null);

  // Determine if drawer is open (only relevant for mobile/tablet)
  const isOpen = isDrawerMode ? showSidebar : true;

  // Close drawer handler
  const handleClose = useCallback(() => {
    if (isDrawerMode) {
      toggleSidebar();
    }
  }, [isDrawerMode, toggleSidebar]);

  // Lock body scroll when drawer is open on mobile/tablet
  useEffect(() => {
    if (isDrawerMode && isOpen) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }
  }, [isDrawerMode, isOpen]);

  // Close drawer on escape key
  useEffect(() => {
    if (!isDrawerMode || !isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isDrawerMode, isOpen, handleClose]);

  // Close drawer when selecting a literature item on mobile
  const handleLiteratureClick = useCallback((literatureId: string) => {
    loadLiterature(literatureId);
    if (isDrawerMode) {
      handleClose();
    }
  }, [loadLiterature, isDrawerMode, handleClose]);

  // Hierarchy resizer handlers
  const handleResizeStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    resizeRef.current = { startY: clientY, startHeight: hierarchyHeight };
    setIsResizing(true);
  }, [hierarchyHeight]);

  useEffect(() => {
    if (!isResizing) return;

    const handleMove = (e: MouseEvent | TouchEvent) => {
      if (!resizeRef.current) return;
      const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
      // Dragging up increases height, dragging down decreases
      const delta = resizeRef.current.startY - clientY;
      const newHeight = Math.min(
        MAX_HIERARCHY_HEIGHT,
        Math.max(MIN_HIERARCHY_HEIGHT, resizeRef.current.startHeight + delta)
      );
      setHierarchyHeight(newHeight);
    };

    const handleEnd = () => {
      setIsResizing(false);
      localStorage.setItem('hierarchyNavHeight', hierarchyHeight.toString());
      resizeRef.current = null;
    };

    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleEnd);
    document.addEventListener('touchmove', handleMove);
    document.addEventListener('touchend', handleEnd);

    return () => {
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleEnd);
      document.removeEventListener('touchmove', handleMove);
      document.removeEventListener('touchend', handleEnd);
    };
  }, [isResizing, hierarchyHeight]);

  const getLiteratureByIdList = (ids: string[]) => {
    return ids.map(id => literatures.find(l => l.id === id)).filter(Boolean);
  };

  // Build class names for drawer mode
  const sidebarClasses = [
    styles.sidebar,
    isDrawerMode && isOpen ? styles.open : '',
  ].filter(Boolean).join(' ');

  return (
    <>
      {/* Backdrop for drawer mode */}
      {isDrawerMode && (
        <div
          className={`${styles.backdrop} ${isOpen ? styles.visible : ''}`}
          onClick={handleClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={sidebarClasses}
        style={!isDrawerMode ? { width: `${width}px` } : undefined}
        role="navigation"
        aria-label="문헌 탐색"
        aria-hidden={isDrawerMode && !isOpen}
      >
      <div className={styles.content}>
        <h2 className={styles.sectionTitle}>삼장</h2>

        {/* Sutta Pitaka */}
        <div className={styles.pitaka}>
          <h3 className={styles.pitakaTitle}>경장 (Sutta Pitaka)</h3>
          {pitakaStructure && Object.entries(pitakaStructure.sutta).map(([nikaya, ids]) => (
            <div key={nikaya} className={styles.nikaya}>
              <h4 className={styles.nikayaTitle}>{nikaya}</h4>
              <ul className={styles.literatureList}>
                {getLiteratureByIdList(ids).map((lit) => {
                  const percentage = getTranslationPercentage(lit!);
                  const variant = getStatusVariant(percentage);
                  const secondary = buildLiteratureSecondaryLine(lit!);
                  return (
                    <li key={lit!.id}>
                      <button
                        className={`${styles.literatureItem} ${
                          currentLiterature?.id === lit!.id ? styles.active : ''
                        }`}
                        onClick={() => handleLiteratureClick(lit!.id)}
                      >
                        <span className={styles.literatureText}>
                          <span className={styles.literaturePrimary}>{getLiteraturePrimaryTitle(lit!)}</span>
                          <span className={styles.literatureSecondary}>{secondary}</span>
                        </span>
                        <span className={`${styles.status} ${styles[variant]}`}>
                          번역 {percentage}%
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>

        {/* Vinaya Pitaka */}
        {pitakaStructure && pitakaStructure.vinaya.length > 0 && (
          <div className={styles.pitaka}>
            <h3 className={styles.pitakaTitle}>율장 (Vinaya Pitaka)</h3>
            <ul className={styles.literatureList}>
              {getLiteratureByIdList(pitakaStructure.vinaya).map((lit) => {
                const percentage = getTranslationPercentage(lit!);
                const variant = getStatusVariant(percentage);
                const secondary = buildLiteratureSecondaryLine(lit!);
                return (
                  <li key={lit!.id}>
                    <button
                      className={`${styles.literatureItem} ${
                        currentLiterature?.id === lit!.id ? styles.active : ''
                      }`}
                      onClick={() => handleLiteratureClick(lit!.id)}
                    >
                      <span className={styles.literatureText}>
                        <span className={styles.literaturePrimary}>{getLiteraturePrimaryTitle(lit!)}</span>
                        <span className={styles.literatureSecondary}>{secondary}</span>
                      </span>
                      <span className={`${styles.status} ${styles[variant]}`}>
                        번역 {percentage}%
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {/* Abhidhamma Pitaka */}
        {pitakaStructure && pitakaStructure.abhidhamma.length > 0 && (
          <div className={styles.pitaka}>
            <h3 className={styles.pitakaTitle}>논장 (Abhidhamma Pitaka)</h3>
            <ul className={styles.literatureList}>
              {getLiteratureByIdList(pitakaStructure.abhidhamma).map((lit) => {
                const percentage = getTranslationPercentage(lit!);
                const variant = getStatusVariant(percentage);
                const secondary = buildLiteratureSecondaryLine(lit!);
                return (
                  <li key={lit!.id}>
                    <button
                      className={`${styles.literatureItem} ${
                        currentLiterature?.id === lit!.id ? styles.active : ''
                      }`}
                      onClick={() => handleLiteratureClick(lit!.id)}
                    >
                      <span className={styles.literatureText}>
                        <span className={styles.literaturePrimary}>{getLiteraturePrimaryTitle(lit!)}</span>
                        <span className={styles.literatureSecondary}>{secondary}</span>
                      </span>
                      <span className={`${styles.status} ${styles[variant]}`}>
                        번역 {percentage}%
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>

      {/* Resizable Hierarchy Navigation */}
      {currentLiterature && (
        <div className={styles.hierarchyWrapper}>
          {/* Resize handle */}
          <div
            className={`${styles.resizeHandle} ${isResizing ? styles.resizing : ''}`}
            onMouseDown={handleResizeStart}
            onTouchStart={handleResizeStart}
            role="separator"
            aria-orientation="horizontal"
            aria-label="목차 크기 조절"
          >
            <div className={styles.resizeGrip} />
          </div>
          {/* Hierarchy Navigation with dynamic height */}
          <div style={{ height: hierarchyHeight, minHeight: MIN_HIERARCHY_HEIGHT, maxHeight: MAX_HIERARCHY_HEIGHT }}>
            <HierarchyNav />
          </div>
        </div>
      )}
      </aside>
    </>
  );
}
