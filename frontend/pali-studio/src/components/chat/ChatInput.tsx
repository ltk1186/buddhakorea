/**
 * ChatInput component
 */
import { useState, KeyboardEvent } from 'react';
import { useChat } from '@/hooks';
import { Button } from '@/components/common';
import styles from './ChatInput.module.css';

interface ChatInputProps {
  disabled?: boolean;
}

export function ChatInput({ disabled = false }: ChatInputProps) {
  const [input, setInput] = useState('');
  const { sendMessage, isStreaming } = useChat();

  const handleSubmit = async () => {
    if (!input.trim() || disabled || isStreaming) return;

    const question = input.trim();
    setInput('');
    await sendMessage(question);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className={styles.container} role="search">
      <textarea
        className={styles.input}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={disabled ? '세그먼트를 선택하세요...' : '질문을 입력하세요...'}
        disabled={disabled || isStreaming}
        rows={2}
        aria-label="질문 입력"
        aria-describedby="chat-input-hint"
      />
      <span id="chat-input-hint" className={styles.srOnly}>
        Enter 키를 눌러 전송, Shift+Enter로 줄바꿈
      </span>
      <Button
        variant="primary"
        size="sm"
        onClick={handleSubmit}
        disabled={!input.trim() || disabled || isStreaming}
        loading={isStreaming}
        aria-label="질문 전송"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      </Button>
    </div>
  );
}
