/**
 * StreamingMessage component - shows content as it streams
 */
import styles from './StreamingMessage.module.css';

interface StreamingMessageProps {
  content: string;
}

export function StreamingMessage({ content }: StreamingMessageProps) {
  return (
    <div className={styles.container}>
      <div className={styles.avatar}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z" />
          <path d="M12 6v6l4 2" />
        </svg>
      </div>
      <div className={styles.content}>
        <p>{content}<span className={styles.cursor}>|</span></p>
      </div>
    </div>
  );
}
