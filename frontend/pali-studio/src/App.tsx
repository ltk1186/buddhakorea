/**
 * Main App component
 *
 * Phase 4: Added accessibility improvements
 * - Skip to main content link
 * - ARIA landmarks (nav, main, aside)
 * Phase 4b: Added DPD hover preview
 * Phase 5: Mobile-first UI with "One Task, One Screen" pattern
 */
import { useCallback, useEffect } from 'react';
import { SiteHeader, Header, Sidebar, MobileNav } from '@/components/layout';
import { LiteraturePanel } from '@/components/literature';
import { ChatPanel } from '@/components/chat';
import { MobileViewContainer } from '@/components/mobile';
import { ResizableDivider, DpdPreview, ToastContainer, ErrorBoundary } from '@/components/common';
import { SettingsPanel } from '@/components/settings';
import { useUIStore } from '@/store';
import { useDpd, useIsDesktop, useIsMobile } from '@/hooks';
import { normalizeWord, isValidLookupWord } from '@/utils/paliTokenizer';
import styles from './App.module.css';

function App() {
  const {
    showChatPanel,
    showSidebar,
    sidebarWidth,
    chatPanelWidth,
    setSidebarWidth,
    setChatPanelWidth,
    dpdPreviewWord,
    dpdPreviewPosition,
    hideDpdPreview
  } = useUIStore();

  const { lookupAndAddToChat } = useDpd();
  const isDesktop = useIsDesktop();
  const isMobile = useIsMobile();

  // On desktop, only show sidebar when showSidebar is true
  const shouldRenderSidebar = showSidebar;

  const handleSidebarResize = useCallback((delta: number) => {
    setSidebarWidth(sidebarWidth + delta);
  }, [sidebarWidth, setSidebarWidth]);

  const handleChatResize = useCallback((delta: number) => {
    setChatPanelWidth(chatPanelWidth - delta);
  }, [chatPanelWidth, setChatPanelWidth]);

  // Handle opening full DPD entry from preview
  const handleOpenFullDpd = useCallback(() => {
    if (dpdPreviewWord) {
      lookupAndAddToChat(dpdPreviewWord);
      hideDpdPreview();
    }
  }, [dpdPreviewWord, lookupAndAddToChat, hideDpdPreview]);

  // Keyboard shortcut: 'd' for DPD lookup of selected text
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Skip if typing in input/textarea or if modifier keys are pressed
      const target = e.target as HTMLElement;
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable ||
        e.ctrlKey ||
        e.metaKey ||
        e.altKey
      ) {
        return;
      }

      // 'd' key for DPD lookup
      if (e.key === 'd' || e.key === 'D') {
        const selection = window.getSelection();
        const selectedText = selection?.toString().trim();

        if (selectedText && isValidLookupWord(selectedText)) {
          e.preventDefault();
          lookupAndAddToChat(normalizeWord(selectedText));
          selection?.removeAllRanges();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [lookupAndAddToChat]);

  return (
    <div className={styles.app}>
      {/* Skip to main content link for keyboard users */}
      <a href="#main-content" className={styles.skipLink}>
        본문으로 건너뛰기
      </a>

      {/* Buddha Korea Site Header - unified platform navigation */}
      <SiteHeader />

      <Header />

      <div className={styles.main}>
        {/* Mobile: Fullscreen view container */}
        {isMobile ? (
          <main
            id="main-content"
            className={styles.content}
            role="main"
            aria-label="모바일 콘텐츠"
          >
            <ErrorBoundary>
              <MobileViewContainer />
            </ErrorBoundary>
          </main>
        ) : (
          /* Desktop: 3-panel layout */
          <>
            {/* Sidebar */}
            {shouldRenderSidebar && (
              <>
                <Sidebar width={sidebarWidth} />
                {isDesktop && <ResizableDivider onResize={handleSidebarResize} direction="horizontal" />}
              </>
            )}

            {/* Main content */}
            <main
              id="main-content"
              className={styles.content}
              role="main"
              aria-label="번역 본문"
            >
              <ErrorBoundary>
                <LiteraturePanel />
              </ErrorBoundary>
            </main>

            {/* Resizable divider */}
            {showChatPanel && (
              <ResizableDivider onResize={handleChatResize} direction="horizontal" />
            )}

            {/* Chat panel */}
            <ErrorBoundary>
              <ChatPanel />
            </ErrorBoundary>
          </>
        )}
      </div>

      {/* Mobile navigation - only on mobile */}
      {isMobile && <MobileNav />}

      {/* Settings Panel (modal) */}
      <SettingsPanel />

      {/* DPD Hover Preview */}
      {dpdPreviewWord && dpdPreviewPosition && (
        <DpdPreview
          word={dpdPreviewWord}
          position={dpdPreviewPosition}
          onClose={hideDpdPreview}
          onOpenFull={handleOpenFullDpd}
        />
      )}

      {/* Toast notifications */}
      <ToastContainer />
    </div>
  );
}

export default App;
