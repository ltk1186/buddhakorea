/**
 * UI state management with Zustand
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type PanelView = 'literature' | 'original' | 'chat';
type FontSize = 'small' | 'medium' | 'large' | 'xlarge' | 'xxlarge';
type ReadingMode = 'compact' | 'comfortable' | 'spacious';
type PaliFont = 'gentium' | 'noto-serif' | 'crimson';
type KoreanFont = 'pretendard' | 'noto-sans' | 'noto-serif-kr';

interface UIState {
  // Panel visibility (desktop)
  showSidebar: boolean;
  showChatPanel: boolean;

  // Panel sizes
  sidebarWidth: number;
  chatPanelWidth: number;

  // Mobile navigation
  activeMobileView: PanelView;

  // Segment display options
  showGrammar: boolean;
  showLiteralTranslation: boolean;
  showFreeTranslation: boolean;
  showExplanation: boolean;
  showSummary: boolean;
  contentMaxWidth: number;

  // Search
  searchQuery: string;
  isSearching: boolean;

  // Font Size (legacy - kept for compatibility)
  fontSize: FontSize;

  // Typography Settings
  paliFont: PaliFont;
  koreanFont: KoreanFont;
  readingMode: ReadingMode;
  showSettingsPanel: boolean;

  // DPD Settings
  enableDpdHoverPreview: boolean;  // Show preview on hover (300ms delay)
  dpdHoverDelay: number;           // Delay in ms before showing preview

  // DPD Preview State
  dpdPreviewWord: string | null;
  dpdPreviewPosition: { x: number; y: number } | null;

  // DPD Popup (legacy - kept for chat panel)
  dpdWord: string | null;
  dpdPosition: { x: number; y: number } | null;

  // Keyboard Navigation
  keyboardFocusedSegmentId: number | null;
  isKeyboardNavigating: boolean;

  // Actions
  toggleSidebar: () => void;
  toggleChatPanel: () => void;
  setSidebarWidth: (width: number) => void;
  setChatPanelWidth: (width: number) => void;
  setMobileView: (view: PanelView) => void;
  toggleDisplayOption: (option: keyof Pick<UIState,
    'showGrammar' | 'showLiteralTranslation' | 'showFreeTranslation' |
    'showExplanation' | 'showSummary'
  >) => void;
  setSearchQuery: (query: string) => void;
  setSearching: (searching: boolean) => void;
  setFontSize: (size: FontSize) => void;
  setPaliFont: (font: PaliFont) => void;
  setKoreanFont: (font: KoreanFont) => void;
  setReadingMode: (mode: ReadingMode) => void;
  toggleSettingsPanel: () => void;
  setEnableDpdHoverPreview: (enabled: boolean) => void;
  showDpdPreview: (word: string, position: { x: number; y: number }) => void;
  hideDpdPreview: () => void;
  showDpdPopup: (word: string, position: { x: number; y: number }) => void;
  hideDpdPopup: () => void;
  setKeyboardFocusedSegmentId: (segmentId: number | null) => void;
  setIsKeyboardNavigating: (isNavigating: boolean) => void;
  setContentMaxWidth: (width: number) => void;
  reset: () => void;
}

const initialState = {
  showSidebar: true,
  showChatPanel: true,
  sidebarWidth: 320,
  chatPanelWidth: 360,
  activeMobileView: 'literature' as PanelView,
  showGrammar: true,
  showLiteralTranslation: true,
  showFreeTranslation: true,
  showExplanation: true,
  showSummary: true,
  searchQuery: '',
  isSearching: false,
  contentMaxWidth: 800,
  fontSize: 'medium' as FontSize,
  paliFont: 'gentium' as PaliFont,
  koreanFont: 'pretendard' as KoreanFont,
  readingMode: 'comfortable' as ReadingMode,
  showSettingsPanel: false,
  enableDpdHoverPreview: false,
  dpdHoverDelay: 150,
  dpdPreviewWord: null,
  dpdPreviewPosition: null,
  dpdWord: null,
  dpdPosition: null,
  keyboardFocusedSegmentId: null,
  isKeyboardNavigating: false,
};

// Font size CSS variable mapping (legacy)
const fontSizeMap: Record<FontSize, { base: string; pali: string; translation: string; lineHeight: string }> = {
  // Keep UI stable: base stays constant; scale reading content (Pali more than translation).
  small: { base: '16px', pali: '1.05rem', translation: '0.95rem', lineHeight: '1.8' },
  medium: { base: '16px', pali: '1.15rem', translation: '1.0rem', lineHeight: '1.9' },
  large: { base: '16px', pali: '1.3rem', translation: '1.1rem', lineHeight: '2.0' },
  xlarge: { base: '16px', pali: '1.45rem', translation: '1.2rem', lineHeight: '2.1' },
  xxlarge: { base: '16px', pali: '1.6rem', translation: '1.3rem', lineHeight: '2.2' },
};

// Reading mode presets
const readingModeMap: Record<ReadingMode, { fontSize: string; lineHeight: string; paragraphSpacing: string }> = {
  compact: { fontSize: '0.875rem', lineHeight: '1.6', paragraphSpacing: 'var(--space-sm)' },
  comfortable: { fontSize: '1rem', lineHeight: '1.8', paragraphSpacing: 'var(--space-md)' },
  spacious: { fontSize: '1.125rem', lineHeight: '2.2', paragraphSpacing: 'var(--space-lg)' },
};

// Pali font families
const paliFontMap: Record<PaliFont, string> = {
  'gentium': "'Gentium Plus', 'Noto Serif', serif",
  'noto-serif': "'Noto Serif', 'Gentium Plus', serif",
  'crimson': "'Crimson Pro', 'Gentium Plus', serif",
};

// Korean font families
const koreanFontMap: Record<KoreanFont, string> = {
  'pretendard': "'Pretendard Variable', 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif",
  'noto-sans': "'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif",
  'noto-serif-kr': "'Noto Serif KR', 'KoPub Batang', serif",
};

const applyFontSize = (size: FontSize) => {
  const root = document.documentElement;
  const sizes = fontSizeMap[size];
  root.style.setProperty('--font-size-base', sizes.base);
  root.style.setProperty('--font-size-pali', sizes.pali);
  root.style.setProperty('--font-size-translation', sizes.translation);
  root.style.setProperty('--line-height-base', sizes.lineHeight);
};

const applyPaliFont = (font: PaliFont) => {
  const root = document.documentElement;
  root.style.setProperty('--font-pali', paliFontMap[font]);
};

const applyKoreanFont = (font: KoreanFont) => {
  const root = document.documentElement;
  root.style.setProperty('--font-main', koreanFontMap[font]);
};

const applyReadingMode = (mode: ReadingMode) => {
  const root = document.documentElement;
  const settings = readingModeMap[mode];
  root.style.setProperty('--reading-font-size', settings.fontSize);
  root.style.setProperty('--reading-line-height', settings.lineHeight);
  root.style.setProperty('--reading-paragraph-spacing', settings.paragraphSpacing);
};

const applyContentMaxWidth = (width: number) => {
  const root = document.documentElement;
  root.style.setProperty('--content-max-width', `${width}px`);
};

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      ...initialState,

      toggleSidebar: () =>
        set((state) => ({ showSidebar: !state.showSidebar })),

      toggleChatPanel: () =>
        set((state) => ({ showChatPanel: !state.showChatPanel })),

      setSidebarWidth: (sidebarWidth) =>
        set({ sidebarWidth: Math.max(200, Math.min(500, sidebarWidth)) }),

      setChatPanelWidth: (chatPanelWidth) =>
        set({ chatPanelWidth: Math.max(280, Math.min(1200, chatPanelWidth)) }),

      setMobileView: (activeMobileView) => set({ activeMobileView }),

      toggleDisplayOption: (option) =>
        set((state) => ({ [option]: !state[option] })),

      setSearchQuery: (searchQuery) => set({ searchQuery }),

      setSearching: (isSearching) => set({ isSearching }),

      setFontSize: (fontSize) => {
        applyFontSize(fontSize);
        set({ fontSize });
      },

      setPaliFont: (paliFont) => {
        applyPaliFont(paliFont);
        set({ paliFont });
      },

      setKoreanFont: (koreanFont) => {
        applyKoreanFont(koreanFont);
        set({ koreanFont });
      },

      setReadingMode: (readingMode) => {
        applyReadingMode(readingMode);
        set({ readingMode });
      },

      toggleSettingsPanel: () =>
        set((state) => ({ showSettingsPanel: !state.showSettingsPanel })),

      setEnableDpdHoverPreview: (enableDpdHoverPreview) =>
        set({ enableDpdHoverPreview }),

      showDpdPreview: (dpdPreviewWord, dpdPreviewPosition) =>
        set({ dpdPreviewWord, dpdPreviewPosition }),

      hideDpdPreview: () =>
        set({ dpdPreviewWord: null, dpdPreviewPosition: null }),

      showDpdPopup: (dpdWord, dpdPosition) => set({ dpdWord, dpdPosition }),

      hideDpdPopup: () => set({ dpdWord: null, dpdPosition: null }),

      setKeyboardFocusedSegmentId: (keyboardFocusedSegmentId) =>
        set({ keyboardFocusedSegmentId, isKeyboardNavigating: keyboardFocusedSegmentId !== null }),

      setIsKeyboardNavigating: (isKeyboardNavigating) =>
        set({ isKeyboardNavigating }),

      setContentMaxWidth: (width) => {
        applyContentMaxWidth(width);
        set({ contentMaxWidth: width });
      },

      reset: () => set(initialState),
    }),
    {
      name: 'pali-ui-storage',
      version: 2,
      migrate: (persistedState: unknown) => {
        const state = persistedState as Partial<UIState> | undefined;
        if (!state) return persistedState as UIState;

        // Default hover preview to OFF for everyone; users can explicitly enable it again.
        return {
          ...state,
          enableDpdHoverPreview: false,
        } as UIState;
      },
      partialize: (state) => ({
        showGrammar: state.showGrammar,
        showLiteralTranslation: state.showLiteralTranslation,
        showFreeTranslation: state.showFreeTranslation,
        showExplanation: state.showExplanation,
        showSummary: state.showSummary,
        sidebarWidth: state.sidebarWidth,
        chatPanelWidth: state.chatPanelWidth,
        fontSize: state.fontSize,
        paliFont: state.paliFont,
        koreanFont: state.koreanFont,
        readingMode: state.readingMode,
        contentMaxWidth: state.contentMaxWidth,
        enableDpdHoverPreview: state.enableDpdHoverPreview,
      }),
      onRehydrateStorage: () => (state) => {
        // Apply persisted settings on app load
        if (state?.fontSize) {
          applyFontSize(state.fontSize);
        }
        if (state?.paliFont) {
          applyPaliFont(state.paliFont);
        }
        if (state?.koreanFont) {
          applyKoreanFont(state.koreanFont);
        }
        if (state?.readingMode) {
          applyReadingMode(state.readingMode);
        }
        if (state?.contentMaxWidth) {
          applyContentMaxWidth(state.contentMaxWidth);
        }
      },
    }
  )
);

// Export types for use in components
export type { PaliFont, KoreanFont, ReadingMode, FontSize };
