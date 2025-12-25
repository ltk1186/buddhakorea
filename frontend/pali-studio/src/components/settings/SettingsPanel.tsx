/**
 * SettingsPanel - Typography and reading settings
 */
import { useUIStore, type PaliFont, type KoreanFont, type ReadingMode } from '@/store/uiStore';
import styles from './SettingsPanel.module.css';

interface FontOption<T> {
  id: T;
  name: string;
  preview: string;
}

const paliFontOptions: FontOption<PaliFont>[] = [
  { id: 'gentium', name: 'Gentium Plus', preview: 'Dhammapada' },
  { id: 'noto-serif', name: 'Noto Serif', preview: 'Dhammapada' },
  { id: 'crimson', name: 'Crimson Pro', preview: 'Dhammapada' },
];

const koreanFontOptions: FontOption<KoreanFont>[] = [
  { id: 'pretendard', name: 'Pretendard', preview: '법구경 해설' },
  { id: 'noto-sans', name: 'Noto Sans KR', preview: '법구경 해설' },
  { id: 'noto-serif-kr', name: 'Noto Serif KR', preview: '법구경 해설' },
];

const readingModeOptions: { id: ReadingMode; name: string; description: string }[] = [
  { id: 'compact', name: '빽빽하게', description: '좁은 줄간격' },
  { id: 'comfortable', name: '편안하게', description: '기본 설정' },
  { id: 'spacious', name: '여유롭게', description: '넓은 줄간격' },
];

export function SettingsPanel() {
  const {
    paliFont,
    koreanFont,
    readingMode,
    showSettingsPanel,
    enableDpdHoverPreview,
    setPaliFont,
    setKoreanFont,
    setReadingMode,
    setEnableDpdHoverPreview,
    toggleSettingsPanel,
  } = useUIStore();

  if (!showSettingsPanel) return null;

  return (
    <>
      {/* Backdrop */}
      <div className={styles.backdrop} onClick={toggleSettingsPanel} />

      {/* Panel */}
      <div className={styles.panel} role="dialog" aria-label="읽기 설정">
        <div className={styles.header}>
          <h2 className={styles.title}>읽기 설정</h2>
          <button
            className={styles.closeButton}
            onClick={toggleSettingsPanel}
            aria-label="닫기"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className={styles.content}>
          {/* Reading Mode */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>읽기 모드</h3>
            <div className={styles.modeOptions}>
              {readingModeOptions.map((option) => (
                <button
                  key={option.id}
                  className={`${styles.modeOption} ${readingMode === option.id ? styles.active : ''}`}
                  onClick={() => setReadingMode(option.id)}
                >
                  <span className={styles.modeName}>{option.name}</span>
                  <span className={styles.modeDescription}>{option.description}</span>
                </button>
              ))}
            </div>
          </section>

          {/* Pali Font */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>빠알리어 글꼴</h3>
            <div className={styles.fontOptions}>
              {paliFontOptions.map((option) => (
                <button
                  key={option.id}
                  className={`${styles.fontOption} ${paliFont === option.id ? styles.active : ''}`}
                  onClick={() => setPaliFont(option.id)}
                  style={{ fontFamily: getFontFamily('pali', option.id) }}
                >
                  <span className={styles.fontName}>{option.name}</span>
                  <span className={styles.fontPreview}>{option.preview}</span>
                </button>
              ))}
            </div>
          </section>

          {/* Korean Font */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>한글 글꼴</h3>
            <div className={styles.fontOptions}>
              {koreanFontOptions.map((option) => (
                <button
                  key={option.id}
                  className={`${styles.fontOption} ${koreanFont === option.id ? styles.active : ''}`}
                  onClick={() => setKoreanFont(option.id)}
                  style={{ fontFamily: getFontFamily('korean', option.id) }}
                >
                  <span className={styles.fontName}>{option.name}</span>
                  <span className={styles.fontPreview}>{option.preview}</span>
                </button>
              ))}
            </div>
          </section>

          {/* DPD Dictionary Settings */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>사전 설정</h3>
            <label className={styles.toggleOption}>
              <span className={styles.toggleLabel}>
                <span className={styles.toggleName}>호버 미리보기</span>
                <span className={styles.toggleDescription}>
                  빠알리어 단어에 마우스를 올리면 간단한 정의를 표시합니다
                </span>
              </span>
              <button
                role="switch"
                aria-checked={enableDpdHoverPreview}
                className={`${styles.toggle} ${enableDpdHoverPreview ? styles.toggleOn : ''}`}
                onClick={() => setEnableDpdHoverPreview(!enableDpdHoverPreview)}
              >
                <span className={styles.toggleThumb} />
              </button>
            </label>
            <p className={styles.keyboardHint}>
              <kbd>d</kbd> 키로 선택한 텍스트를 사전에서 바로 검색할 수 있습니다
            </p>
          </section>

          {/* Preview */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>미리보기</h3>
            <div className={styles.preview}>
              <p className={styles.previewPali}>
                Sabbe dhammā nālaṃ abhinivesāya.
              </p>
              <p className={styles.previewKorean}>
                모든 법은 집착할 만한 것이 아닙니다.
              </p>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}

// Helper to get font family for preview
function getFontFamily(type: 'pali' | 'korean', id: string): string {
  const paliFonts: Record<string, string> = {
    'gentium': "'Gentium Plus', serif",
    'noto-serif': "'Noto Serif', serif",
    'crimson': "'Crimson Pro', serif",
  };

  const koreanFonts: Record<string, string> = {
    'pretendard': "'Pretendard Variable', sans-serif",
    'noto-sans': "'Noto Sans KR', sans-serif",
    'noto-serif-kr': "'Noto Serif KR', serif",
  };

  return type === 'pali' ? paliFonts[id] : koreanFonts[id];
}
