/**
 * Card component
 */
import { ReactNode, HTMLAttributes } from 'react';
import styles from './Card.module.css';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  children: ReactNode;
}

export function Card({
  hoverable = false,
  padding = 'md',
  className,
  children,
  ...props
}: CardProps) {
  return (
    <div
      className={`
        ${styles.card}
        ${hoverable ? styles.hoverable : ''}
        ${styles[`padding-${padding}`]}
        ${className || ''}
      `}
      {...props}
    >
      {children}
    </div>
  );
}
