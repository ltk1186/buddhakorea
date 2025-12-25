/**
 * MobileChatView - Full-screen chat view for mobile
 *
 * Purpose: Ask questions about selected content, get AI-powered answers.
 * Reference: ChatGPT mobile, Claude mobile, Perplexity
 */
import { useRef, useEffect } from 'react';
import { useChat } from '@/hooks';
import { useLiteratureStore } from '@/store';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { StreamingMessage } from '@/components/chat/StreamingMessage';
import styles from './MobileChatView.module.css';

export function MobileChatView() {
  const { currentSegment } = useLiteratureStore();
  const { messages, isStreaming, streamingContent, canSendMessage, clearChat } = useChat();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  return (
    <div className={styles.view}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerMain}>
          <h1 className={styles.title}>질문하기</h1>
          {messages.length > 0 && (
            <button
              className={styles.clearButton}
              onClick={clearChat}
              aria-label="대화 초기화"
            >
              초기화
            </button>
          )}
        </div>
        {currentSegment && (
          <span className={styles.context}>
            선택: § {currentSegment.paragraph_id}
          </span>
        )}
      </header>

      {/* Messages */}
      <div
        className={styles.messages}
        role="log"
        aria-live="polite"
        aria-label="채팅 메시지"
      >
        {messages.length === 0 && !isStreaming && (
          <div className={styles.empty}>
            <div className={styles.emptyIcon}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <p className={styles.emptyTitle}>세그먼트에 대해 질문하세요</p>
            <p className={styles.emptyHint}>
              {currentSegment
                ? '선택한 세그먼트의 문법, 어휘, 교리적 맥락 등을 물어볼 수 있습니다.'
                : '원문 탭에서 세그먼트를 선택한 후 질문하세요.'}
            </p>
            <ul className={styles.suggestions}>
              <li>문법 구조 설명</li>
              <li>단어 의미 분석</li>
              <li>교리적 맥락</li>
              <li>관련 경전 참조</li>
            </ul>
          </div>
        )}

        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}

        {isStreaming && streamingContent && (
          <StreamingMessage content={streamingContent} />
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className={styles.inputArea}>
        {currentSegment && (
          <div className={styles.contextChip}>
            <span className={styles.contextLabel}>§ {currentSegment.paragraph_id}</span>
          </div>
        )}
        <ChatInput disabled={!canSendMessage} />
        {!currentSegment && (
          <p className={styles.hint}>
            원문에서 세그먼트를 선택하세요
          </p>
        )}
      </div>
    </div>
  );
}
