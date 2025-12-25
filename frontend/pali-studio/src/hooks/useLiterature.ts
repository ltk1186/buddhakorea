/**
 * Literature data fetching hook
 */
import { useCallback, useEffect } from 'react';
import { useLiteratureStore } from '@/store';
import {
  getLiteratures,
  getLiterature,
  getSegments,
  getSegment,
} from '@/api/literature';

export function useLiterature() {
  const {
    literatures,
    pitakaStructure,
    currentLiterature,
    segments,
    currentSegment,
    isLoading,
    error,
    totalSegments,
    currentOffset,
    currentLimit,
    setLiteratures,
    selectLiterature,
    setSegments,
    appendSegments,
    selectSegment,
    setLoading,
    setError,
  } = useLiteratureStore();

  // Fetch all literatures
  const fetchLiteratures = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await getLiteratures();
      setLiteratures(data.literatures, data.pitaka_structure);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [setLiteratures, setLoading, setError]);

  // Select and fetch a literature
  const loadLiterature = useCallback(async (literatureId: string) => {
    setLoading(true);
    setError(null);

    try {
      const literature = await getLiterature(literatureId);
      selectLiterature(literature);

      // Fetch initial segments
      const segmentData = await getSegments(literatureId, {
        offset: 0,
        limit: currentLimit,
      });
      setSegments(segmentData.segments, segmentData.pagination.total, 0);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [currentLimit, selectLiterature, setSegments, setLoading, setError]);

  // Load more segments (pagination)
  const loadMoreSegments = useCallback(async () => {
    if (!currentLiterature || isLoading) return;
    if (currentOffset + currentLimit >= totalSegments) return;

    setLoading(true);

    try {
      const data = await getSegments(currentLiterature.id, {
        offset: currentOffset + currentLimit,
        limit: currentLimit,
      });
      appendSegments(data.segments);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [
    currentLiterature,
    isLoading,
    currentOffset,
    currentLimit,
    totalSegments,
    appendSegments,
    setLoading,
    setError,
  ]);

  // Load a specific segment
  const loadSegment = useCallback(async (segmentId: number) => {
    if (!currentLiterature) return;

    try {
      const segment = await getSegment(currentLiterature.id, segmentId);
      selectSegment(segment);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [currentLiterature, selectSegment, setError]);

  // Fetch literatures on mount
  useEffect(() => {
    if (literatures.length === 0) {
      fetchLiteratures();
    }
  }, [fetchLiteratures, literatures.length]);

  return {
    // State
    literatures,
    pitakaStructure,
    currentLiterature,
    segments,
    currentSegment,
    isLoading,
    error,
    totalSegments,
    hasMore: currentOffset + currentLimit < totalSegments,

    // Actions
    fetchLiteratures,
    loadLiterature,
    loadMoreSegments,
    loadSegment,
    selectSegment,
  };
}
