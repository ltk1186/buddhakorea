/**
 * ChatMessage component
 *
 * Renders different message types:
 * - user: User messages
 * - assistant: AI responses
 * - system: System messages (DPD lookup cards)
 */
import type { ChatMessage as ChatMessageType } from '@/store';
import { DpdCard } from './DpdCard';
import styles from './ChatMessage.module.css';

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  // System messages (DPD lookups)
  if (message.role === 'system' && message.metadata?.type === 'dpd_lookup') {
    return (
      <DpdCard
        word={message.metadata.word}
        status={message.metadata.status}
        entry={message.metadata.entry}
        suggestions={message.metadata.suggestions}
        error={message.metadata.error}
      />
    );
  }

  const isUser = message.role === 'user';

  return (
    <div className={`${styles.message} ${isUser ? styles.user : styles.assistant}`}>
      <div className={styles.avatar}>
        {isUser ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z" />
            <path d="M12 6v6l4 2" />
          </svg>
        )}
      </div>
      <div className={styles.content}>
        <p>{message.content}</p>
      </div>
    </div>
  );
}
