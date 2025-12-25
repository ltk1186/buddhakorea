/**
 * Server-Sent Events TypeScript types
 */

export interface SSEStartEvent {
  segment_id?: number;
  question_id?: string;
  status: string;
}

export interface SSETokenEvent {
  content: string;
}

export interface SSETranslationEvent {
  sentences: Array<{
    original_pali: string;
    grammatical_analysis: string;
    literal_translation: string;
    free_translation: string;
    explanation: string;
  }>;
  summary?: string;
}

export interface SSEDoneEvent {
  segment_id?: number;
  question_id?: string;
  status?: string;
  total_tokens?: number;
}

export interface SSEErrorEvent {
  error: string;
  detail?: string;
}

export type SSEEventType =
  | 'start'
  | 'token'
  | 'translation'
  | 'sentence_complete'
  | 'done'
  | 'error';

export interface ParsedSSEEvent {
  type: SSEEventType;
  data: SSEStartEvent | SSETokenEvent | SSETranslationEvent | SSEDoneEvent | SSEErrorEvent;
}
