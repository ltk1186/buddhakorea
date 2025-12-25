/**
 * SSE (Server-Sent Events) streaming hook
 */
import { useState, useCallback, useRef } from 'react';

interface UseSSEOptions {
  onStart?: () => void;
  onMessage?: (content: string) => void;
  onComplete?: () => void;
  onError?: (error: string) => void;
}

interface UseSSEReturn {
  isStreaming: boolean;
  content: string;
  error: string | null;
  startStream: (url: string, body: object, headers?: Record<string, string>) => Promise<void>;
  stopStream: () => void;
  reset: () => void;
}

export function useSSE(options: UseSSEOptions = {}): UseSSEReturn {
  const [isStreaming, setIsStreaming] = useState(false);
  const [content, setContent] = useState('');
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const startStream = useCallback(async (
    url: string,
    body: object,
    headers: Record<string, string> = {}
  ) => {
    // Abort any existing stream
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();
    setIsStreaming(true);
    setContent('');
    setError(null);
    options.onStart?.();

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          ...headers,
        },
        body: JSON.stringify(body),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.error || `HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEvent = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);

              if (currentEvent === 'token' && data.content) {
                setContent((prev) => prev + data.content);
                options.onMessage?.(data.content);
              } else if (currentEvent === 'error') {
                setError(data.error);
                options.onError?.(data.error);
              } else if (currentEvent === 'done') {
                options.onComplete?.();
              }
            } catch {
              // Non-JSON data, append as content
              setContent((prev) => prev + dataStr);
              options.onMessage?.(dataStr);
            }
          }
        }
      }

      setIsStreaming(false);
      options.onComplete?.();
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        // Stream was intentionally stopped
        return;
      }

      const errorMessage = (err as Error).message || 'Stream error';
      setError(errorMessage);
      setIsStreaming(false);
      options.onError?.(errorMessage);
    }
  }, [options]);

  const stopStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const reset = useCallback(() => {
    stopStream();
    setContent('');
    setError(null);
  }, [stopStream]);

  return {
    isStreaming,
    content,
    error,
    startStream,
    stopStream,
    reset,
  };
}
