/**
 * DPD Dictionary API functions
 */
import { apiRequest } from './client';
import type { DpdLookupResponse } from '@/types/api';

/**
 * Look up a Pali word with suggestions fallback
 */
export async function lookupWord(word: string): Promise<DpdLookupResponse> {
  return apiRequest<DpdLookupResponse>(`/dpd/${encodeURIComponent(word)}`);
}

/**
 * Get brief definition of a word
 */
export async function lookupWordBrief(
  word: string
): Promise<{ headword: string; definition: string; grammar: string }> {
  return apiRequest(`/dpd/${encodeURIComponent(word)}/brief`);
}

/**
 * Search for words in the dictionary
 */
export async function searchDictionary(
  query: string,
  limit: number = 20
): Promise<{
  query: string;
  results: Array<{ headword: string; definition: string; grammar: string }>;
  count: number;
}> {
  return apiRequest('/dpd/search', {
    params: { q: query, limit },
  });
}
