/**
 * Mobile bottom navigation component
 *
 * Features:
 * - Bottom nav with 3 views: 문헌 (literature list), 원문 (content), 질문 (chat)
 * - Touch-optimized with safe area insets
 * - Haptic feedback on active state
 * - Badge support for notifications
 *
 * Mobile UI Pattern: "One Task, One Screen"
 * Each tab switches to a fullscreen view - no drawers or overlays
 */
import { useUIStore } from '@/store';
import styles from './MobileNav.module.css';

// Could be extended to show unread messages, etc.
interface NavBadges {
  literature?: number;
  original?: number;
  chat?: number;
}

interface MobileNavProps {
  badges?: NavBadges;
}

export function MobileNav({ badges }: MobileNavProps) {
  const { activeMobileView, setMobileView } = useUIStore();

  return (
    <nav className={styles.nav} role="navigation" aria-label="모바일 탐색">
      <button
        className={`${styles.navItem} ${activeMobileView === 'literature' ? styles.active : ''}`}
        onClick={() => setMobileView('literature')}
        aria-label="문헌 목록"
        aria-current={activeMobileView === 'literature' ? 'page' : undefined}
      >
        <span className={styles.iconWrapper}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
          {badges?.literature && badges.literature > 0 && (
            <span className={styles.badge} aria-label={`${badges.literature}개 알림`}>
              {badges.literature > 99 ? '99+' : badges.literature}
            </span>
          )}
        </span>
        <span>목록</span>
      </button>

      <button
        className={`${styles.navItem} ${activeMobileView === 'original' ? styles.active : ''}`}
        onClick={() => setMobileView('original')}
        aria-label="원문 보기"
        aria-current={activeMobileView === 'original' ? 'page' : undefined}
      >
        <span className={styles.iconWrapper}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
          {badges?.original && badges.original > 0 && (
            <span className={styles.badge} aria-label={`${badges.original}개 알림`}>
              {badges.original > 99 ? '99+' : badges.original}
            </span>
          )}
        </span>
        <span>원문</span>
      </button>

      <button
        className={`${styles.navItem} ${activeMobileView === 'chat' ? styles.active : ''}`}
        onClick={() => setMobileView('chat')}
        aria-label="질문하기"
        aria-current={activeMobileView === 'chat' ? 'page' : undefined}
      >
        <span className={styles.iconWrapper}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          {badges?.chat && badges.chat > 0 && (
            <span className={styles.badge} aria-label={`${badges.chat}개 알림`}>
              {badges.chat > 99 ? '99+' : badges.chat}
            </span>
          )}
        </span>
        <span>질문</span>
      </button>
    </nav>
  );
}
