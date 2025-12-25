/**
 * Translation API functions
 */
import { sseRequest, apiRequest } from './client';
import type { TranslateRequest } from '@/types/api';
import type { Translation } from '@/types/literature';

export interface TranslateStreamCallbacks {
  onStart?: (segmentId: number) => void;
  onToken?: (content: string) => void;
  onTranslation?: (translation: Translation) => void;
  onComplete?: (segmentId: number) => void;
  onError?: (error: string) => void;
}

/**
 * Translate a segment with streaming response
 */
export async function translateSegmentStream(
  request: TranslateRequest,
  callbacks: TranslateStreamCallbacks
): Promise<void> {
  await sseRequest('/translate', request, (event, data) => {
    switch (event) {
      case 'start':
        callbacks.onStart?.((data as { segment_id: number }).segment_id);
        break;
      case 'token':
        callbacks.onToken?.((data as { content: string }).content);
        break;
      case 'translation':
        callbacks.onTranslation?.(data as Translation);
        break;
      case 'done':
        callbacks.onComplete?.((data as { segment_id: number }).segment_id);
        break;
      case 'error':
        callbacks.onError?.((data as { error: string }).error);
        break;
    }
  });
}

/**
 * Translate a segment synchronously (non-streaming)
 */
export async function translateSegmentSync(
  request: TranslateRequest
): Promise<{ segment_id: number; status: string; translation: Translation }> {
  return apiRequest('/translate/sync', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export interface BatchTranslateRequest {
  literature_id: string;
  segment_ids: number[];
  force?: boolean;
}

export interface BatchTranslateStreamCallbacks {
  onStart?: (segmentIds: number[]) => void;
  onToken?: (content: string) => void;
  onParseComplete?: () => void;
  onSegmentComplete?: (segmentId: number, translation: Translation) => void;
  onFallbackStart?: (reason: string) => void;
  onComplete?: (segmentIds: number[], completed: number[]) => void;
  onError?: (error: string, segmentId?: number) => void;
}

export interface BatchTranslateOptions {
  signal?: AbortSignal;
}

/**
 * Translate multiple segments in batch with streaming response
 * Max 5 segments per request (server-enforced)
 */
export async function translateBatchStream(
  request: BatchTranslateRequest,
  callbacks: BatchTranslateStreamCallbacks,
  options: BatchTranslateOptions = {}
): Promise<void> {
  await sseRequest('/translate/batch', request, (event, data) => {
    switch (event) {
      case 'start':
        callbacks.onStart?.((data as { segment_ids: number[] }).segment_ids);
        break;
      case 'token':
        callbacks.onToken?.((data as { content: string }).content);
        break;
      case 'parse_complete':
        callbacks.onParseComplete?.();
        break;
      case 'segment_complete': {
        const { segment_id, translation } = data as { segment_id: string; translation: Translation };
        callbacks.onSegmentComplete?.(parseInt(segment_id), translation);
        break;
      }
      case 'fallback_start':
        callbacks.onFallbackStart?.((data as { reason: string }).reason);
        break;
      case 'done': {
        const { segment_ids, completed } = data as { segment_ids: number[]; completed: number[] };
        callbacks.onComplete?.(segment_ids, completed);
        break;
      }
      case 'error': {
        const errorData = data as { error: string; segment_id?: string };
        callbacks.onError?.(errorData.error, errorData.segment_id ? parseInt(errorData.segment_id) : undefined);
        break;
      }
    }
  }, { signal: options.signal });
}
