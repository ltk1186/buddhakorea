/**
 * ErrorMessage Component
 *
 * Displays inline error messages with retry functionality.
 * Phase 6: Accessibility & User Feedback
 */
import styles from './ErrorMessage.module.css';

interface ErrorMessageProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  variant?: 'inline' | 'card' | 'banner';
}

export function ErrorMessage({
  title,
  message,
  onRetry,
  variant = 'card'
}: ErrorMessageProps) {
  return (
    <div
      className={`${styles.container} ${styles[variant]}`}
      role="alert"
      aria-live="polite"
    >
      <div className={styles.iconWrapper}>
        <svg
          className={styles.icon}
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>

      <div className={styles.content}>
        {title && <h3 className={styles.title}>{title}</h3>}
        <p className={styles.message}>{message}</p>
      </div>

      {onRetry && (
        <button
          className={styles.retryButton}
          onClick={onRetry}
          type="button"
          aria-label="다시 시도"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path d="M1 4v6h6" />
            <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
          </svg>
          <span>다시 시도</span>
        </button>
      )}
    </div>
  );
}
