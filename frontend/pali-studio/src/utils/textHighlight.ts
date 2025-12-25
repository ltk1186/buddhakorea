/**
 * Text Highlighting Utilities
 *
 * For search result highlighting in Pali text.
 */

/**
 * Escape regex special characters
 */
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Split text into parts with highlighted matches
 */
export interface HighlightPart {
  text: string;
  isMatch: boolean;
}

export function highlightMatches(
  text: string,
  query: string
): HighlightPart[] {
  if (!query.trim()) {
    return [{ text, isMatch: false }];
  }

  const trimmed = query.trim();
  const escapedQuery = escapeRegex(trimmed);
  const regex = new RegExp(`(${escapedQuery})`, 'gi');
  const parts = text.split(regex);
  const normalizedQuery = trimmed.toLowerCase();

  return parts
    .filter((part) => part.length > 0)
    .map((part) => ({
      text: part,
      isMatch: part.toLowerCase() === normalizedQuery,
    }));
}
