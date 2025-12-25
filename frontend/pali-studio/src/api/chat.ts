/**
 * Chat API functions
 */
import { sseRequest, apiRequest } from './client';
import type { ChatRequest } from '@/types/api';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface ChatStreamCallbacks {
  onStart?: (questionId: string) => void;
  onToken?: (content: string) => void;
  onComplete?: (questionId: string, totalTokens?: number) => void;
  onError?: (error: string) => void;
}

/**
 * Send a chat message with streaming response
 */
export async function chatStream(
  request: ChatRequest,
  callbacks: ChatStreamCallbacks,
  sessionId?: string
): Promise<void> {
  await sseRequest(
    '/chat',
    request,
    (event, data) => {
      switch (event) {
        case 'start':
          callbacks.onStart?.((data as { question_id: string }).question_id);
          break;
        case 'token':
          callbacks.onToken?.((data as { content: string }).content);
          break;
        case 'done': {
          const doneData = data as { question_id: string; total_tokens?: number };
          callbacks.onComplete?.(doneData.question_id, doneData.total_tokens);
          break;
        }
        case 'error':
          callbacks.onError?.((data as { error: string }).error);
          break;
      }
    },
    { sessionId }
  );
}

/**
 * Get chat history for current session
 */
export async function getChatHistory(
  sessionId?: string,
  limit: number = 20
): Promise<{ messages: ChatMessage[]; session_id: string | null }> {
  const headers: Record<string, string> = {};
  if (sessionId) {
    headers['X-Session-ID'] = sessionId;
  }

  return apiRequest('/chat/history', {
    params: { limit },
    headers,
  });
}

/**
 * Clear chat history for current session
 */
export async function clearChatHistory(
  sessionId?: string
): Promise<{ status: string; session_id: string | null }> {
  const headers: Record<string, string> = {};
  if (sessionId) {
    headers['X-Session-ID'] = sessionId;
  }

  return apiRequest('/chat/history', {
    method: 'DELETE',
    headers,
  });
}
