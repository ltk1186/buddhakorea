/**
 * MobileListView - Full-screen literature list view for mobile
 *
 * Purpose: Browse Tripitaka structure and select literature for reading.
 * Reference: ChatGPT conversation list, Claude project selector
 */
import { useLiterature } from '@/hooks';
import { useUIStore } from '@/store';
import { buildLiteratureSecondaryLine, getLiteraturePrimaryTitle } from '@/utils/literatureDisplay';
import type { Literature } from '@/types/literature';
import styles from './MobileListView.module.css';

// Calculate translation percentage
const getTranslationPercentage = (lit: Literature): number => {
  if (!lit.total_segments || lit.total_segments === 0) return 0;
  return Math.round((lit.translated_segments / lit.total_segments) * 100);
};

// Get status variant based on percentage
const getStatusVariant = (percentage: number): 'completed' | 'inProgress' | 'notStarted' => {
  if (percentage === 100) return 'completed';
  if (percentage > 0) return 'inProgress';
  return 'notStarted';
};

export function MobileListView() {
  const { pitakaStructure, literatures, currentLiterature, loadLiterature } = useLiterature();
  const { setMobileView } = useUIStore();

  const getLiteratureByIdList = (ids: string[]) => {
    return ids.map(id => literatures.find(l => l.id === id)).filter(Boolean) as Literature[];
  };

  // Handle literature selection - load and switch to content view
  const handleLiteratureClick = (literatureId: string) => {
    loadLiterature(literatureId);
    setMobileView('original');
  };

  return (
    <div className={styles.view}>
      {/* Header */}
      <header className={styles.header}>
        <h1 className={styles.title}>문헌 목록</h1>
      </header>

      {/* Content */}
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
                  const percentage = getTranslationPercentage(lit);
                  const variant = getStatusVariant(percentage);
                  const secondary = buildLiteratureSecondaryLine(lit);
                  const isActive = currentLiterature?.id === lit.id;
                  return (
                    <li key={lit.id}>
                      <button
                        className={`${styles.literatureItem} ${isActive ? styles.active : ''}`}
                        onClick={() => handleLiteratureClick(lit.id)}
                      >
                        <span className={styles.literatureText}>
                          <span className={styles.literaturePrimary}>{getLiteraturePrimaryTitle(lit)}</span>
                          <span className={styles.literatureSecondary}>{secondary}</span>
                        </span>
                        <span className={`${styles.status} ${styles[variant]}`}>
                          {percentage}%
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
                const percentage = getTranslationPercentage(lit);
                const variant = getStatusVariant(percentage);
                const secondary = buildLiteratureSecondaryLine(lit);
                const isActive = currentLiterature?.id === lit.id;
                return (
                  <li key={lit.id}>
                    <button
                      className={`${styles.literatureItem} ${isActive ? styles.active : ''}`}
                      onClick={() => handleLiteratureClick(lit.id)}
                    >
                      <span className={styles.literatureText}>
                        <span className={styles.literaturePrimary}>{getLiteraturePrimaryTitle(lit)}</span>
                        <span className={styles.literatureSecondary}>{secondary}</span>
                      </span>
                      <span className={`${styles.status} ${styles[variant]}`}>
                        {percentage}%
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
                const percentage = getTranslationPercentage(lit);
                const variant = getStatusVariant(percentage);
                const secondary = buildLiteratureSecondaryLine(lit);
                const isActive = currentLiterature?.id === lit.id;
                return (
                  <li key={lit.id}>
                    <button
                      className={`${styles.literatureItem} ${isActive ? styles.active : ''}`}
                      onClick={() => handleLiteratureClick(lit.id)}
                    >
                      <span className={styles.literatureText}>
                        <span className={styles.literaturePrimary}>{getLiteraturePrimaryTitle(lit)}</span>
                        <span className={styles.literatureSecondary}>{secondary}</span>
                      </span>
                      <span className={`${styles.status} ${styles[variant]}`}>
                        {percentage}%
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
