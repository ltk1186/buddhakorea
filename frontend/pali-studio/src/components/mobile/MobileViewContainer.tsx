/**
 * MobileViewContainer - Full-screen view switcher for mobile
 *
 * Renders one of three views based on activeMobileView state:
 * - 'literature' (목록): Literature list for browsing
 * - 'original' (원문): Content/segments view
 * - 'chat' (질문): Q&A chat view
 *
 * Only renders on mobile devices (≤768px viewport)
 */
import { useUIStore } from '@/store';
import { useIsMobile } from '@/hooks';
import { MobileListView } from './MobileListView';
import { MobileContentView } from './MobileContentView';
import { MobileChatView } from './MobileChatView';
import styles from './MobileViewContainer.module.css';

export function MobileViewContainer() {
  const isMobile = useIsMobile();
  const { activeMobileView } = useUIStore();

  // Only render on mobile devices
  if (!isMobile) {
    return null;
  }

  return (
    <div className={styles.container}>
      {/* Screen reader announcement for view changes */}
      <div id="sr-live-region" className="sr-only" aria-live="polite" aria-atomic="true" />

      {/* Render active view */}
      <div className={styles.viewWrapper}>
        {activeMobileView === 'literature' && <MobileListView />}
        {activeMobileView === 'original' && <MobileContentView />}
        {activeMobileView === 'chat' && <MobileChatView />}
      </div>
    </div>
  );
}
