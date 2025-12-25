/**
 * Literature and Segment TypeScript types
 */

export interface Literature {
  id: string;
  name: string;
  pali_name: string;
  pitaka: string;
  nikaya: string | null;
  status: 'translated' | 'parsed';
  total_segments: number;
  translated_segments: number;
  source_pdf: string | null;
  hierarchy_labels: Record<string, string> | null;
  display_metadata: LiteratureDisplayMetadata | null;
  created_at: string;
  updated_at: string;
}

export interface LiteratureDisplayMetadata {
  ko_translit?: string;
  abbr?: string;
  aliases?: string[];
  description?: string;
}

export interface TranslationSentence {
  original_pali: string;
  grammatical_analysis: string;
  literal_translation: string;
  free_translation: string;
  explanation: string;
}

export interface Translation {
  sentences: TranslationSentence[];
  summary?: string;
}

export interface Segment {
  id: number;
  literature_id: string;
  vagga_id: number | null;
  vagga_name: string | null;
  sutta_id: number | null;
  sutta_name: string | null;
  page_number: number | null;
  paragraph_id: number;
  original_text: string;
  translation: Translation | null;
  is_translated: boolean;
  created_at: string;
  updated_at: string;
}

export interface PaginationMeta {
  offset: number;
  limit: number;
  total: number;
  has_more: boolean;
}

export interface LiteratureListResponse {
  literatures: Literature[];
  pitaka_structure: PitakaStructure;
  total_count: number;
}

export interface SegmentListResponse {
  segments: Segment[];
  pagination: PaginationMeta;
}

export interface PitakaStructure {
  sutta: Record<string, string[]>;
  vinaya: string[];
  abhidhamma: string[];
}

export interface VaggaInfo {
  vagga_id: number;
  vagga_name: string;
  sutta_count: number;
}
