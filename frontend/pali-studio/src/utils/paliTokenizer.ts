/**
 * Pali Text Tokenizer
 *
 * Tokenizes Pali text into words for dictionary lookup.
 * Per PHASE0_DECISIONS.md Section 0.2
 */

// Pali characters including diacritics (uppercase and lowercase)
// NOTE: Keep a non-global regex for `.test()` stability; use a separate global regex for tokenization.
const PALI_WORD_REGEX = /[a-zA-ZāīūṭḍṇṅñṃḷĀĪŪṬḌṆṄÑṂḶ]+/;
const PALI_WORD_REGEX_GLOBAL = new RegExp(PALI_WORD_REGEX.source, 'g');

// Characters that should be trimmed from word boundaries
const TRIM_CHARS = /^[.,;:!?"'()\[\]{}॥।]+|[.,;:!?"'()\[\]{}॥।]+$/g;

export interface Token {
  text: string;
  start: number;
  end: number;
  isWord: boolean;
}

/**
 * Tokenize Pali text into words and non-word segments
 * Returns an array of tokens with position information
 */
export function tokenizePali(text: string): Token[] {
  const tokens: Token[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  // Reset regex state
  PALI_WORD_REGEX_GLOBAL.lastIndex = 0;

  while ((match = PALI_WORD_REGEX_GLOBAL.exec(text)) !== null) {
    // Add non-word segment before this match (if any)
    if (match.index > lastIndex) {
      tokens.push({
        text: text.slice(lastIndex, match.index),
        start: lastIndex,
        end: match.index,
        isWord: false,
      });
    }

    // Add the word token
    tokens.push({
      text: match[0],
      start: match.index,
      end: match.index + match[0].length,
      isWord: true,
    });

    lastIndex = match.index + match[0].length;
  }

  // Add remaining non-word segment (if any)
  if (lastIndex < text.length) {
    tokens.push({
      text: text.slice(lastIndex),
      start: lastIndex,
      end: text.length,
      isWord: false,
    });
  }

  return tokens;
}

/**
 * Normalize a Pali word for dictionary lookup
 * - Lowercase
 * - Trim punctuation
 */
export function normalizeWord(word: string): string {
  return word.toLowerCase().replace(TRIM_CHARS, '').trim();
}

/**
 * Check if a string is a valid Pali word for lookup
 * - Not just numbers
 * - Not empty after normalization
 * - Contains at least one letter
 */
export function isValidLookupWord(word: string): boolean {
  const normalized = normalizeWord(word);
  if (!normalized) return false;
  if (/^\d+$/.test(normalized)) return false;
  return PALI_WORD_REGEX.test(normalized);
}

/**
 * Get the word at a given position in text (for click handling)
 */
export function getWordAtPosition(text: string, position: number): string | null {
  const tokens = tokenizePali(text);
  const token = tokens.find(
    (t) => t.isWord && position >= t.start && position < t.end
  );
  return token ? token.text : null;
}
