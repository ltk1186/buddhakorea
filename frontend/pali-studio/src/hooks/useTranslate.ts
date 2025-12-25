/**
 * Translation hook with SSE streaming
 */
import { useState, useCallback } from 'react';
import { useLiteratureStore } from '@/store';
import { translateSegmentStream, translateSegmentSync } from '@/api/translate';
import type { Translation } from '@/types/literature';

interface UseTranslateReturn {
  isTranslating: boolean;
  streamingContent: string;
  error: string | null;
  translateSegment: (segmentId: number) => Promise<void>;
  translateSegmentNonStream: (segmentId: number) => Promise<Translation | null>;
}

export function useTranslate(): UseTranslateReturn {
  const [isTranslating, setIsTranslating] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [error, setError] = useState<string | null>(null);

  const {
    currentLiterature,
    updateSegmentTranslation,
    startTranslating,
    stopTranslating,
  } = useLiteratureStore();

  const translateSegment = useCallback(async (segmentId: number) => {
    if (!currentLiterature) {
      setError('No literature selected');
      return;
    }

    setIsTranslating(true);
    setStreamingContent('');
    setError(null);
    startTranslating(segmentId);

    try {
      await translateSegmentStream(
        {
          literature_id: currentLiterature.id,
          segment_id: segmentId,
        },
        {
          onStart: () => {
            setStreamingContent('');
          },
          onToken: (content) => {
            setStreamingContent((prev) => prev + content);
          },
          onTranslation: (translation) => {
            updateSegmentTranslation(segmentId, translation);
          },
          onComplete: () => {
            setIsTranslating(false);
            stopTranslating(segmentId);
          },
          onError: (err) => {
            setError(err);
            setIsTranslating(false);
            stopTranslating(segmentId);
          },
        }
      );
    } catch (err) {
      setError((err as Error).message);
      setIsTranslating(false);
      stopTranslating(segmentId);
    }
  }, [currentLiterature, updateSegmentTranslation, startTranslating, stopTranslating]);

  const translateSegmentNonStream = useCallback(async (
    segmentId: number
  ): Promise<Translation | null> => {
    if (!currentLiterature) {
      setError('No literature selected');
      return null;
    }

    setIsTranslating(true);
    setError(null);
    startTranslating(segmentId);

    try {
      const result = await translateSegmentSync({
        literature_id: currentLiterature.id,
        segment_id: segmentId,
      });

      updateSegmentTranslation(segmentId, result.translation);
      setIsTranslating(false);
      stopTranslating(segmentId);
      return result.translation;
    } catch (err) {
      setError((err as Error).message);
      setIsTranslating(false);
      stopTranslating(segmentId);
      return null;
    }
  }, [currentLiterature, updateSegmentTranslation, startTranslating, stopTranslating]);

  return {
    isTranslating,
    streamingContent,
    error,
    translateSegment,
    translateSegmentNonStream,
  };
}
