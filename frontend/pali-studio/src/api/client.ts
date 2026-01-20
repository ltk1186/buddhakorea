/**
 * API client configuration
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1/pali';
console.log('API_BASE_URL:', API_BASE_URL);

export interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | undefined>;
}

/**
 * Build URL with query parameters
 */
function buildUrl(path: string, params?: Record<string, string | number | undefined>): string {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.append(key, String(value));
      }
    });
  }

  return url.toString();
}

/**
 * Make an API request
 */
export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, ...fetchOptions } = options;
  const url = buildUrl(path, params);

  const response = await fetch(url, {
    ...fetchOptions,
    headers: {
      'Content-Type': 'application/json',
      ...fetchOptions.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(error.detail || error.error || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Make an SSE streaming request
 */
export async function sseRequest(
  path: string,
  body: object,
  onMessage: (event: string, data: unknown) => void,
  options: { sessionId?: string; signal?: AbortSignal } = {}
): Promise<void> {
  const url = buildUrl(path);

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream',
  };

  if (options.sessionId) {
    headers['X-Session-ID'] = options.sessionId;
  }

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal: options.signal,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(error.detail || error.error || `HTTP ${response.status}`);
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) {
    throw new Error('No response body');
  }

  let buffer = '';

  try {
    while (true) {
      // Check if aborted before reading
      if (options.signal?.aborted) {
        await reader.cancel();
        break;
      }

      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE events from buffer
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep incomplete line in buffer

      let currentEvent = '';

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          const dataStr = line.slice(6);
          try {
            const data = JSON.parse(dataStr);
            onMessage(currentEvent || 'message', data);
          } catch {
            // Non-JSON data
            onMessage(currentEvent || 'message', dataStr);
          }
        }
      }
    }
  } finally {
    // Ensure reader is released
    try {
      await reader.cancel();
    } catch {
      // Ignore cancel errors
    }
  }
}

export { API_BASE_URL };
