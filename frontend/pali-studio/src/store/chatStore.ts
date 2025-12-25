/**
 * Chat state management with Zustand
 */
import { create } from 'zustand';
import type { DpdBriefEntry } from '@/types/api';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  segmentId?: number;
  literatureId?: string;
  // For system messages (e.g., DPD lookup results)
  metadata?: {
    type: 'dpd_lookup';
    word: string;
    status?: 'loading' | 'ok' | 'not_found' | 'suggestions' | 'error';
    entry?: DpdEntry;
    suggestions?: DpdBriefEntry[];
    error?: string;
  };
}

// DPD entry type for dictionary lookups
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

interface ChatState {
  // State
  sessionId: string;
  messages: ChatMessage[];
  isStreaming: boolean;
  streamingContent: string;
  error: string | null;

  // Context
  contextLiteratureId: string | null;
  contextSegmentId: number | null;

  // Actions
  setSessionId: (id: string) => void;
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => string;
  updateMessage: (id: string, patch: Partial<Omit<ChatMessage, 'id' | 'timestamp'>>) => void;
  appendStreamingContent: (content: string) => void;
  completeStreaming: () => void;
  setStreaming: (streaming: boolean) => void;
  setContext: (literatureId: string | null, segmentId: number | null) => void;
  setError: (error: string | null) => void;
  clearMessages: () => void;
  reset: () => void;
}

// Generate a session ID
function generateSessionId(): string {
  return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

const initialState = {
  sessionId: generateSessionId(),
  messages: [],
  isStreaming: false,
  streamingContent: '',
  error: null,
  contextLiteratureId: null,
  contextSegmentId: null,
};

export const useChatStore = create<ChatState>((set) => ({
  ...initialState,

  setSessionId: (sessionId) => set({ sessionId }),

  addMessage: (message) => {
    const id = `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    set((state) => ({
      messages: [
        ...state.messages,
        {
          ...message,
          id,
          timestamp: new Date(),
        },
      ],
    }));
    return id;
  },

  updateMessage: (id, patch) =>
    set((state) => ({
      messages: state.messages.map((message) =>
        message.id === id
          ? {
              ...message,
              ...patch,
              metadata: patch.metadata ?? message.metadata,
            }
          : message
      ),
    })),

  appendStreamingContent: (content) =>
    set((state) => ({
      streamingContent: state.streamingContent + content,
    })),

  completeStreaming: () =>
    set((state) => {
      // Add the streamed content as a complete message
      if (state.streamingContent) {
        return {
          messages: [
            ...state.messages,
            {
              id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              role: 'assistant' as const,
              content: state.streamingContent,
              timestamp: new Date(),
              literatureId: state.contextLiteratureId || undefined,
              segmentId: state.contextSegmentId || undefined,
            },
          ],
          streamingContent: '',
          isStreaming: false,
        };
      }
      return { streamingContent: '', isStreaming: false };
    }),

  setStreaming: (isStreaming) =>
    set({ isStreaming, streamingContent: isStreaming ? '' : '' }),

  setContext: (literatureId, segmentId) =>
    set({
      contextLiteratureId: literatureId,
      contextSegmentId: segmentId,
    }),

  setError: (error) => set({ error }),

  clearMessages: () => set({ messages: [], streamingContent: '' }),

  reset: () => set({ ...initialState, sessionId: generateSessionId() }),
}));
