/**
 * DPD Dictionary Lookup Hook
 *
 * Provides word lookup functionality with chat stream integration.
 * Per PHASE0_DECISIONS.md: Double-click triggers lookup, results go to chat stream.
 */
import { useCallback, useState } from 'react';
import { lookupWord } from '@/api/dpd';
import { useChatStore, useUIStore, type DpdEntry } from '@/store';
import { normalizeWord, isValidLookupWord } from '@/utils/paliTokenizer';
import type { DpdBriefEntry } from '@/types/api';

interface UseDpdResult {
  lookupAndAddToChat: (word: string) => Promise<void>;
  isLookingUp: boolean;
  lastLookedUpWord: string | null;
}

type FullCacheValue =
  | { status: 'ok'; entry: DpdEntry }
  | { status: 'suggestions'; suggestions: DpdBriefEntry[] }
  | { status: 'error'; message: string };

const fullCache = new Map<string, FullCacheValue>();
const inFlightWords = new Set<string>();

/**
 * Hook for DPD dictionary lookups that add results to chat stream
 */
export function useDpd(): UseDpdResult {
  const [inFlightCount, setInFlightCount] = useState(0);
  const [lastLookedUpWord, setLastLookedUpWord] = useState<string | null>(null);
  const { addMessage, updateMessage } = useChatStore();
  const isLookingUp = inFlightCount > 0;

  const lookupAndAddToChat = useCallback(
    async (word: string) => {
      const normalized = normalizeWord(word);

      // Validate word
      if (!isValidLookupWord(word)) {
        return;
      }

      // Ensure tools/chat panel is visible so results are never "lost"
      const ui = useUIStore.getState();
      if (!ui.showChatPanel) {
        ui.toggleChatPanel();
      }

      setLastLookedUpWord(normalized);

      const cached = fullCache.get(normalized);
      if (cached) {
        if (cached.status === 'ok') {
          addMessage({
            role: 'system',
            content: `📖 ${cached.entry.headword}`,
            metadata: {
              type: 'dpd_lookup',
              word: normalized,
              status: 'ok',
              entry: cached.entry,
            },
          });
          return;
        }

        if (cached.status === 'suggestions') {
          addMessage({
            role: 'system',
            content: `📖 ${normalized}`,
            metadata: {
              type: 'dpd_lookup',
              word: normalized,
              status: 'suggestions',
              suggestions: cached.suggestions,
            },
          });
          return;
        }

        addMessage({
          role: 'system',
          content: `📖 ${normalized}`,
          metadata: {
            type: 'dpd_lookup',
            word: normalized,
            status: 'error',
            error: cached.message,
          },
        });
        return;
      }

      if (inFlightWords.has(normalized)) {
        return;
      }

      inFlightWords.add(normalized);
      setInFlightCount((count) => count + 1);

      const placeholderId = addMessage({
        role: 'system',
        content: `📖 ${normalized}`,
        metadata: {
          type: 'dpd_lookup',
          word: normalized,
          status: 'loading',
        },
      });

      try {
        const response = await lookupWord(normalized);

        if (response.exact_match) {
          fullCache.set(normalized, { status: 'ok', entry: response.exact_match as DpdEntry });
          updateMessage(placeholderId, {
            content: `📖 ${response.exact_match.headword}`,
            metadata: {
              type: 'dpd_lookup',
              word: normalized,
              status: 'ok',
              entry: response.exact_match as DpdEntry,
            },
          });
        } else if (response.suggestions && response.suggestions.length > 0) {
          fullCache.set(normalized, { status: 'suggestions', suggestions: response.suggestions });
          updateMessage(placeholderId, {
            content: `📖 ${normalized}`,
            metadata: {
              type: 'dpd_lookup',
              word: normalized,
              status: 'suggestions',
              suggestions: response.suggestions,
            },
          });
        } else {
          fullCache.set(normalized, { status: 'suggestions', suggestions: [] });
          updateMessage(placeholderId, {
            content: `📖 ${normalized}`,
            metadata: {
              type: 'dpd_lookup',
              word: normalized,
              status: 'suggestions',
              suggestions: [],
            },
          });
        }
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : 'Unknown error';
        fullCache.set(normalized, { status: 'error', message: errorMessage });

        updateMessage(placeholderId, {
          content: `📖 ${normalized}`,
          metadata: {
            type: 'dpd_lookup',
            word: normalized,
            status: 'error',
            error: errorMessage,
          },
        });
      } finally {
        inFlightWords.delete(normalized);
        setInFlightCount((count) => Math.max(0, count - 1));
      }
    },
    [addMessage, updateMessage]
  );

  return {
    lookupAndAddToChat,
    isLookingUp,
    lastLookedUpWord,
  };
}
