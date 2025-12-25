/**
 * API-related TypeScript types
 */

export interface HealthResponse {
  status: 'ok' | 'degraded';
  version: string;
  database: string;
  redis: string;
}

export interface ErrorResponse {
  error: string;
  detail?: string;
  code?: string;
}

export interface TranslateRequest {
  literature_id: string;
  segment_id: number;
}

export interface ChatRequest {
  literature_id: string;
  segment_id: number;
  question: string;
}

export interface DpdExample {
  text: string;
  source?: string;
  sutta?: string;
}

export interface DpdEntry {
  headword: string;
  definition: string;
  grammar: string;
  etymology?: string;
  root?: string;
  base?: string;
  construction?: string;
  meaning?: string;
  examples?: DpdExample[];
  compound_type?: string;
  compound_construction?: string;
  // Extended fields
  sanskrit?: string;
  antonym?: string;
  synonym?: string;
  commentary?: string;
  notes?: string;
  inflections_html?: string;
}

export interface DpdBriefEntry {
  headword: string;
  definition: string;
  grammar: string;
}

export interface DpdLookupResponse {
  exact_match: DpdEntry | null;
  suggestions: DpdBriefEntry[];
  query: string;
}
