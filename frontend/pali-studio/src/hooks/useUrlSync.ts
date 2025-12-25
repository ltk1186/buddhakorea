/**
 * URL Sync Hook - Synchronize literature/location state with URL
 *
 * URL Schema: /?lit=<literature_id>&vagga=<id>&sutta=<id>&para=<n>
 */
import { useEffect, useRef } from 'react';
import { useLiteratureStore } from '@/store';
import { useLiterature } from './useLiterature';

export function useUrlSync() {
  const { literatures, loadLiterature } = useLiterature();
  const {
    currentLiterature,
    currentVaggaId,
    currentSuttaId,
    loadSegmentsForLocation,
  } = useLiteratureStore();

  const isInitializedRef = useRef(false);
  const isUpdatingFromUrl = useRef(false);

  // Read URL params and restore state on initial load
  useEffect(() => {
    if (isInitializedRef.current || literatures.length === 0) return;
    isInitializedRef.current = true;

    const params = new URLSearchParams(window.location.search);
    const litId = params.get('lit');
    const vaggaId = params.get('vagga');
    const suttaId = params.get('sutta');

    if (litId) {
      const literature = literatures.find((l) => l.id === litId);
      if (literature) {
        isUpdatingFromUrl.current = true;
        loadLiterature(litId).then(() => {
          if (vaggaId || suttaId) {
            loadSegmentsForLocation(
              litId,
              vaggaId ? parseInt(vaggaId, 10) : null,
              suttaId ? parseInt(suttaId, 10) : null
            );
          }
          isUpdatingFromUrl.current = false;
        });
      }
    }
  }, [literatures, loadLiterature, loadSegmentsForLocation]);

  // Update URL when state changes
  useEffect(() => {
    if (isUpdatingFromUrl.current) return;

    const params = new URLSearchParams();

    if (currentLiterature) {
      params.set('lit', currentLiterature.id);
    }
    if (currentVaggaId !== null) {
      params.set('vagga', currentVaggaId.toString());
    }
    if (currentSuttaId !== null) {
      params.set('sutta', currentSuttaId.toString());
    }

    const newUrl = params.toString()
      ? `${window.location.pathname}?${params.toString()}`
      : window.location.pathname;

    // Only update if URL changed
    if (newUrl !== window.location.pathname + window.location.search) {
      window.history.replaceState({}, '', newUrl);
    }
  }, [currentLiterature, currentVaggaId, currentSuttaId]);

  // Copy link function
  const copyCurrentLink = () => {
    const url = window.location.href;
    navigator.clipboard.writeText(url);
    return url;
  };

  return { copyCurrentLink };
}
