/**
 * ChatPanel - right panel for Q&A
 *
 * Phase 4: Added ARIA attributes for accessibility
 */
import { useRef, useEffect } from 'react';
import { useChat } from '@/hooks';
import { useLiteratureStore, useUIStore } from '@/store';
import { ChatInput } from './ChatInput';
import { ChatMessage } from './ChatMessage';
import { StreamingMessage } from './StreamingMessage';
import styles from './ChatPanel.module.css';

export function ChatPanel() {
  const { showChatPanel, chatPanelWidth } = useUIStore();
  const { currentSegment } = useLiteratureStore();
  const { messages, isStreaming, streamingContent, canSendMessage } = useChat();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  if (!showChatPanel) return null;

  return (
    <aside
      className={styles.panel}
      style={{ width: chatPanelWidth }}
      role="complementary"
      aria-label="질문 및 사전 조회"
    >
      <div className={styles.header}>
        <h3 className={styles.title}>질문하기</h3>
        {currentSegment && (
          <span className={styles.context}>
            선택됨: § {currentSegment.paragraph_id}
          </span>
        )}
      </div>

      <div
        className={styles.messages}
        role="log"
        aria-live="polite"
        aria-label="채팅 메시지"
      >
        {messages.length === 0 && !isStreaming && (
          <div className={styles.empty}>
            <p>세그먼트를 선택하고 텍스트에 대해 질문하세요.</p>
            <p>번역이 있는 세그먼트는 번역도 함께 참고합니다.</p>
            <ul>
              <li>문법 설명</li>
              <li>단어 의미</li>
              <li>교리적 맥락</li>
              <li>관련 참조</li>
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

      <div className={styles.inputArea}>
        <ChatInput disabled={!canSendMessage} />
        {!currentSegment?.is_translated && currentSegment && (
          <p className={styles.hint}>
            미번역 세그먼트입니다. 원문 기반으로 답변합니다.
          </p>
        )}
        <p className={styles.disclaimer}>
          AI 생성 답변은 오류가 있을 수 있으니 검토가 필요합니다.
        </p>
      </div>
    </aside>
  );
}
