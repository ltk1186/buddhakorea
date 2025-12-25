/**
 * HierarchyNav - Hierarchical navigation for 품(Vagga)/경(Sutta) selection
 */
import { useState, useEffect } from 'react';
import { useLiteratureStore } from '@/store';
import { apiRequest } from '@/api/client';
import { getHierarchyLabelKo } from '@/utils/hierarchyLabels';
import styles from './HierarchyNav.module.css';

interface Sutta {
  sutta_id: number | null;
  sutta_name: string;
  segment_count: number;
  first_segment_id: number;
  paragraph_range: string;
}

interface Vagga {
  vagga_id: number | null;
  vagga_name: string;
  segment_count: number;
  first_segment_id: number;
  suttas: Sutta[];
}

interface HierarchyResponse {
  literature_id: string;
  hierarchy: Vagga[];
}

export function HierarchyNav() {
  const { currentLiterature, loadSegmentsForLocation, currentVaggaId, currentSuttaId, setCurrentLocation } = useLiteratureStore();
  const [hierarchy, setHierarchy] = useState<Vagga[]>([]);
  const [expandedVagga, setExpandedVagga] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const labels = currentLiterature?.hierarchy_labels || {};
  const level1Label = getHierarchyLabelKo(labels.level_1, '품');
  const level2Label = getHierarchyLabelKo(labels.level_2, '경');

  useEffect(() => {
    if (currentLiterature) {
      loadHierarchy(currentLiterature.id);
    } else {
      setHierarchy([]);
    }
  }, [currentLiterature?.id]);

  const loadHierarchy = async (literatureId: string) => {
    setIsLoading(true);
    try {
      const response = await apiRequest<HierarchyResponse>(`/literature/${literatureId}/hierarchy`);
      setHierarchy(response.hierarchy);
      // Auto-expand first vagga if exists
      if (response.hierarchy.length > 0) {
        setExpandedVagga(response.hierarchy[0].vagga_id);
      }
    } catch (error) {
      console.error('Failed to load hierarchy:', error);
      setHierarchy([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleVaggaClick = (vagga: Vagga) => {
    if (expandedVagga === vagga.vagga_id) {
      setExpandedVagga(null);
    } else {
      setExpandedVagga(vagga.vagga_id);
    }
  };

  const handleSuttaClick = (vagga: Vagga, sutta: Sutta) => {
    setCurrentLocation(vagga.vagga_id, sutta.sutta_id);
    loadSegmentsForLocation(currentLiterature!.id, vagga.vagga_id, sutta.sutta_id);
  };

  const handleVaggaSelect = (vagga: Vagga) => {
    setCurrentLocation(vagga.vagga_id, null);
    loadSegmentsForLocation(currentLiterature!.id, vagga.vagga_id, null);
  };

  if (!currentLiterature) {
    return null;
  }

  if (isLoading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>계층 구조 로딩 중...</div>
      </div>
    );
  }

  if (hierarchy.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.empty}>계층 구조가 없습니다</div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <h3 className={styles.title}>목차</h3>
      <div className={styles.subtitle}>{level1Label} · {level2Label}</div>
      <div className={styles.tree}>
        {hierarchy.map((vagga) => (
          <div key={vagga.vagga_id ?? 'null'} className={styles.vaggaGroup}>
            <div
              className={`${styles.vaggaItem} ${currentVaggaId === vagga.vagga_id ? styles.active : ''}`}
            >
              <button
                className={styles.expandBtn}
                onClick={() => handleVaggaClick(vagga)}
              >
                <svg
                  className={`${styles.arrow} ${expandedVagga === vagga.vagga_id ? styles.expanded : ''}`}
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </button>
              <button
                className={styles.vaggaName}
                onClick={() => handleVaggaSelect(vagga)}
              >
                <span>{vagga.vagga_name}</span>
                <span className={styles.count}>{vagga.segment_count}</span>
              </button>
            </div>

            {expandedVagga === vagga.vagga_id && vagga.suttas.length > 0 && (
              <div className={styles.suttaList}>
                {vagga.suttas.map((sutta) => (
                  <button
                    key={sutta.sutta_id ?? 'null'}
                    className={`${styles.suttaItem} ${
                      currentVaggaId === vagga.vagga_id && currentSuttaId === sutta.sutta_id
                        ? styles.active
                        : ''
                    }`}
                    onClick={() => handleSuttaClick(vagga, sutta)}
                  >
                    <span className={styles.suttaName}>{sutta.sutta_name}</span>
                    <span className={styles.range}>{sutta.paragraph_range}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
