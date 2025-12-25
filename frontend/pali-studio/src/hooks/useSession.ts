/**
 * Session management hook
 */
import { useEffect, useCallback } from 'react';
import { useChatStore } from '@/store';

const SESSION_STORAGE_KEY = 'pali_session_id';

export function useSession() {
  const { sessionId, setSessionId } = useChatStore();

  // Load session ID from localStorage on mount
  useEffect(() => {
    const storedId = localStorage.getItem(SESSION_STORAGE_KEY);
    if (storedId && storedId !== sessionId) {
      setSessionId(storedId);
    } else if (!storedId) {
      localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    }
  }, [sessionId, setSessionId]);

  // Generate a new session
  const newSession = useCallback(() => {
    const newId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(newId);
    localStorage.setItem(SESSION_STORAGE_KEY, newId);
    return newId;
  }, [setSessionId]);

  // Clear session
  const clearSession = useCallback(() => {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    return newSession();
  }, [newSession]);

  return {
    sessionId,
    newSession,
    clearSession,
  };
}
