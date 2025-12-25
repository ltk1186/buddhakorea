/**
 * Literature API functions
 */
import { apiRequest } from './client';
import type {
  Literature,
  Segment,
  LiteratureListResponse,
  SegmentListResponse
} from '@/types/literature';

/**
 * Get all literatures
 */
export async function getLiteratures(): Promise<LiteratureListResponse> {
  return apiRequest<LiteratureListResponse>('/literature');
}

/**
 * Get a specific literature by ID
 */
export async function getLiterature(literatureId: string): Promise<Literature> {
  return apiRequest<Literature>(`/literature/${literatureId}`);
}

/**
 * Get segments for a literature
 */
export async function getSegments(
  literatureId: string,
  options: {
    offset?: number;
    limit?: number;
    vagga_id?: number;
    sutta_id?: number;
  } = {}
): Promise<SegmentListResponse> {
  return apiRequest<SegmentListResponse>(`/literature/${literatureId}/segments`, {
    params: options,
  });
}

/**
 * Get a specific segment
 */
export async function getSegment(
  literatureId: string,
  segmentId: number
): Promise<Segment> {
  return apiRequest<Segment>(`/literature/${literatureId}/segments/${segmentId}`);
}

/**
 * Search segments in a literature
 */
export async function searchSegments(
  literatureId: string,
  query: string,
  options: { limit?: number; page?: number } = {}
): Promise<{
  query: string;
  page_filter: number | null;
  results: Segment[];
  returned_count: number;
  hit_segments_count: number;
  total_occurrences: number;
  unknown_page_occurrences: number;
  pages: Array<{ page_number: number; occurrences: number }>;
}> {
  const { limit = 200, page } = options;
  return apiRequest(`/literature/${literatureId}/search`, {
    params: { q: query, limit, page },
  });
}
