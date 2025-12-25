/**
 * Buddha Korea Site Header
 *
 * Unified navigation header for Buddha Korea platform integration.
 * Shows on scroll-up, hides on scroll-down for minimal distraction.
 */
import { useState, useEffect, useCallback } from 'react';
import styles from './SiteHeader.module.css';

// Buddha Korea logo SVG (simplified lotus)
const BuddhaKoreaLogo = () => (
  <svg width="28" height="28" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="50" cy="50" r="45" fill="var(--sage-pale)" />
    <path
      d="M50 20C50 20 35 35 35 50C35 65 50 80 50 80C50 80 65 65 65 50C65 35 50 20 50 20Z"
      fill="var(--sage-primary)"
      opacity="0.8"
    />
    <circle cx="50" cy="50" r="8" fill="var(--sage-light)" />
  </svg>
);

interface NavItem {
  label: string;
  href: string;
  active?: boolean;
}

const navItems: NavItem[] = [
  { label: '홈', href: '/' },
  { label: 'AI', href: '/gosa-ai/' },
  { label: '빠알리', href: '/pali/', active: true },
  { label: '사경', href: '/sutra-writing.html' },
];

export function SiteHeader() {
  const [isVisible, setIsVisible] = useState(true);
  const [lastScrollY, setLastScrollY] = useState(0);

  const handleScroll = useCallback(() => {
    const currentScrollY = window.scrollY;

    // Always show at top
    if (currentScrollY < 50) {
      setIsVisible(true);
      setLastScrollY(currentScrollY);
      return;
    }

    // Hide when scrolling down, show when scrolling up
    if (currentScrollY > lastScrollY && currentScrollY > 100) {
      setIsVisible(false);
    } else if (currentScrollY < lastScrollY) {
      setIsVisible(true);
    }

    setLastScrollY(currentScrollY);
  }, [lastScrollY]);

  useEffect(() => {
    let ticking = false;

    const onScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          handleScroll();
          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [handleScroll]);

  return (
    <header
      className={`${styles.siteHeader} ${!isVisible ? styles.hidden : ''}`}
      role="banner"
      aria-label="Buddha Korea 사이트 네비게이션"
    >
      <div className={styles.container}>
        {/* Logo */}
        <a href="/" className={styles.logo} aria-label="Buddha Korea 홈">
          <BuddhaKoreaLogo />
          <span className={styles.logoText}>Buddha Korea</span>
        </a>

        {/* Current Section Indicator */}
        <div className={styles.currentSection}>
          <span className={styles.sectionDivider}>|</span>
          <span className={styles.sectionName}>빠알리 스튜디오</span>
        </div>

        {/* Spacer */}
        <div className={styles.spacer} />

        {/* Navigation */}
        <nav className={styles.nav} aria-label="주요 메뉴">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className={`${styles.navLink} ${item.active ? styles.active : ''}`}
              aria-current={item.active ? 'page' : undefined}
            >
              {item.label}
            </a>
          ))}
        </nav>

        {/* User Menu Placeholder */}
        <button
          className={styles.userButton}
          aria-label="사용자 메뉴"
          title="로그인"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 20c0-4 4-6 8-6s8 2 8 6" />
          </svg>
        </button>
      </div>
    </header>
  );
}
