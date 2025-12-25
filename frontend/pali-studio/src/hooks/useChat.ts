/**
 * Chat hook with SSE streaming
 */
import { useCallback } from 'react';
import { useChatStore, useLiteratureStore } from '@/store';
import { chatStream, getChatHistory, clearChatHistory } from '@/api/chat';

export function useChat() {
  const {
    sessionId,
    messages,
    isStreaming,
    streamingContent,
    error,
    contextLiteratureId,
    contextSegmentId,
    setSessionId,
    addMessage,
    appendStreamingContent,
    completeStreaming,
    setStreaming,
    setContext,
    setError,
    clearMessages,
  } = useChatStore();

  const { currentLiterature, currentSegment } = useLiteratureStore();

  // Send a message
  const sendMessage = useCallback(async (question: string) => {
    if (!currentLiterature || !currentSegment) {
      setError('Please select a segment first');
      return;
    }

    // Add user message
    addMessage({
      role: 'user',
      content: question,
      literatureId: currentLiterature.id,
      segmentId: currentSegment.id,
    });

    // Set context
    setContext(currentLiterature.id, currentSegment.id);

    // Start streaming
    setStreaming(true);
    setError(null);

    try {
      await chatStream(
        {
          literature_id: currentLiterature.id,
          segment_id: currentSegment.id,
          question,
        },
        {
          onStart: () => {
            // Streaming started
          },
          onToken: (content) => {
            appendStreamingContent(content);
          },
          onComplete: () => {
            completeStreaming();
          },
          onError: (err) => {
            setError(err);
            setStreaming(false);
          },
        },
        sessionId
      );
    } catch (err) {
      setError((err as Error).message);
      setStreaming(false);
    }
  }, [
    currentLiterature,
    currentSegment,
    sessionId,
    addMessage,
    appendStreamingContent,
    completeStreaming,
    setContext,
    setError,
    setStreaming,
  ]);

  // Load chat history from server
  const loadHistory = useCallback(async () => {
    try {
      const data = await getChatHistory(sessionId);
      if (data.session_id) {
        setSessionId(data.session_id);
      }
      // Note: We could sync messages here if needed
    } catch (err) {
      console.error('Failed to load chat history:', err);
    }
  }, [sessionId, setSessionId]);

  // Clear chat
  const clearChat = useCallback(async () => {
    try {
      await clearChatHistory(sessionId);
      clearMessages();
    } catch (err) {
      console.error('Failed to clear chat history:', err);
      // Still clear local messages
      clearMessages();
    }
  }, [sessionId, clearMessages]);

  return {
    // State
    sessionId,
    messages,
    isStreaming,
    streamingContent,
    error,
    contextLiteratureId,
    contextSegmentId,

    // Computed
    canSendMessage: !!(currentLiterature && currentSegment && !isStreaming),

    // Actions
    sendMessage,
    loadHistory,
    clearChat,
    setError,
  };
}
