import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent } from 'react';
import type { Literature } from '@/types/literature';
import { buildLiteratureSecondaryLine, getLiteraturePrimaryTitle } from '@/utils/literatureDisplay';
import styles from './LiteratureCombobox.module.css';

interface LiteratureComboboxProps {
  literatures: Literature[];
  currentLiterature: Literature | null;
  onSelect: (literatureId: string) => void;
}

const getTranslationPercentage = (lit: Literature): number => {
  if (!lit.total_segments || lit.total_segments === 0) return 0;
  return Math.round((lit.translated_segments / lit.total_segments) * 100);
};

const normalizePitakaLabel = (pitaka: string): string => {
  const normalized = pitaka.trim().toLowerCase();
  if (normalized.includes('sutta')) return 'Sutta';
  if (normalized.includes('vinaya')) return 'Vinaya';
  if (normalized.includes('abhidhamma')) return 'Abhidhamma';
  return pitaka.trim() || 'Other';
};

const normalizeNikayaLabel = (nikaya: string | null): string => {
  const trimmed = nikaya?.trim();
  return trimmed && trimmed.length > 0 ? trimmed : 'Other';
};

const normalizeSearchText = (value: string): string => {
  return value
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '') // strip diacritics
    .replace(/\s+/g, ' ')
    .trim();
};

export function LiteratureCombobox({ literatures, currentLiterature, onSelect }: LiteratureComboboxProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);

  const dedupedLiteratures = useMemo(() => {
    const seen = new Set<string>();
    const unique: Literature[] = [];
    for (const lit of literatures) {
      if (!lit?.id) continue;
      if (seen.has(lit.id)) continue;
      seen.add(lit.id);
      unique.push(lit);
    }
    return unique;
  }, [literatures]);

  const grouped = useMemo(() => {
    const collator = new Intl.Collator('ko');
    const pitakaOrder: Record<string, number> = { Sutta: 0, Vinaya: 1, Abhidhamma: 2, Other: 9 };
    const groups = new Map<string, { pitaka: string; nikaya: string; items: Literature[] }>();

    for (const lit of dedupedLiteratures) {
      const pitaka = normalizePitakaLabel(lit.pitaka);
      const nikaya = normalizeNikayaLabel(lit.nikaya);
      const key = `${pitaka} - ${nikaya}`;
      const group = groups.get(key);
      if (group) group.items.push(lit);
      else groups.set(key, { pitaka, nikaya, items: [lit] });
    }

    for (const group of groups.values()) {
      group.items.sort((a, b) =>
        collator.compare(getLiteraturePrimaryTitle(a), getLiteraturePrimaryTitle(b))
      );
    }

    return Array.from(groups.values()).sort((a, b) => {
      const pitakaDiff = (pitakaOrder[a.pitaka] ?? 9) - (pitakaOrder[b.pitaka] ?? 9);
      if (pitakaDiff !== 0) return pitakaDiff;
      const nikayaDiff = collator.compare(a.nikaya, b.nikaya);
      if (nikayaDiff !== 0) return nikayaDiff;
      return collator.compare(
        getLiteraturePrimaryTitle(a.items[0]),
        getLiteraturePrimaryTitle(b.items[0])
      );
    });
  }, [dedupedLiteratures]);

  const searchableItems = useMemo(() => {
    return grouped.map((g) => ({
      ...g,
      items: g.items.map((lit) => {
        const meta = lit.display_metadata ?? {};
        const aliases = Array.isArray(meta.aliases) ? meta.aliases.join(' ') : '';
        const searchKey = normalizeSearchText(
          [
            lit.id,
            lit.name,
            lit.pali_name,
            meta.ko_translit,
            meta.abbr,
            aliases,
            lit.pitaka,
            lit.nikaya ?? '',
          ]
            .filter(Boolean)
            .join(' ')
        );
        return { lit, searchKey };
      }),
    }));
  }, [grouped]);

  const filteredGroups = useMemo(() => {
    const q = normalizeSearchText(query);
    if (!q) {
      return searchableItems.map((g) => ({
        pitaka: g.pitaka,
        nikaya: g.nikaya,
        items: g.items.map((i) => i.lit),
      }));
    }

    return searchableItems
      .map((g) => ({
        pitaka: g.pitaka,
        nikaya: g.nikaya,
        items: g.items.filter((i) => i.searchKey.includes(q)).map((i) => i.lit),
      }))
      .filter((g) => g.items.length > 0);
  }, [searchableItems, query]);

  const flatOptions = useMemo(() => {
    const out: Literature[] = [];
    for (const group of filteredGroups) {
      for (const lit of group.items) out.push(lit);
    }
    return out;
  }, [filteredGroups]);

  const activeLiterature = flatOptions[activeIndex];

  const open = useCallback(() => {
    setIsOpen(true);
    setQuery('');
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
    setQuery('');
    requestAnimationFrame(() => triggerRef.current?.focus());
  }, []);

  const selectLiterature = useCallback(
    (literatureId: string) => {
      onSelect(literatureId);
      close();
    },
    [onSelect, close]
  );

  // Keep active index aligned to current selection when opening.
  useEffect(() => {
    if (!isOpen) return;
    const currentId = currentLiterature?.id;
    if (!currentId) {
      setActiveIndex(0);
      return;
    }
    const idx = flatOptions.findIndex((l) => l.id === currentId);
    setActiveIndex(idx >= 0 ? idx : 0);
  }, [isOpen, currentLiterature?.id, flatOptions]);

  // Scroll active option into view (keyboard navigation).
  useEffect(() => {
    if (!isOpen) return;
    const el = document.getElementById(`literature-option-${activeLiterature?.id}`);
    if (el) el.scrollIntoView({ block: 'nearest' });
  }, [isOpen, activeLiterature?.id]);

  // Close on outside click.
  useEffect(() => {
    if (!isOpen) return;
    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (!containerRef.current?.contains(target)) {
        close();
      }
    };
    document.addEventListener('mousedown', onMouseDown);
    return () => document.removeEventListener('mousedown', onMouseDown);
  }, [isOpen, close]);

  // Global shortcut: Ctrl/Cmd+K opens the picker.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== 'k') return;
      const target = e.target as HTMLElement | null;
      const isTextInput =
        target?.tagName === 'INPUT' || target?.tagName === 'TEXTAREA' || target?.isContentEditable;
      if (isTextInput) return;
      e.preventDefault();
      if (!isOpen) open();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [isOpen, open]);

  const handleTriggerClick = () => {
    if (isOpen) close();
    else open();
  };

  const handleInputKeyDown = (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((prev) => Math.min(prev + 1, flatOptions.length - 1));
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((prev) => Math.max(prev - 1, 0));
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      if (activeLiterature) selectLiterature(activeLiterature.id);
    }
  };

  const handleOptionClick = (lit: Literature) => {
    selectLiterature(lit.id);
  };

  const triggerSecondary = currentLiterature ? buildLiteratureSecondaryLine(currentLiterature) : '';
  const triggerProgress = currentLiterature ? getTranslationPercentage(currentLiterature) : null;

  return (
    <div className={styles.container} ref={containerRef}>
      <button
        type="button"
        ref={triggerRef}
        className={`${styles.trigger} ${isOpen ? styles.triggerOpen : ''}`}
        onClick={handleTriggerClick}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label="문헌 선택"
      >
        <div className={styles.triggerInner}>
          <div className={styles.triggerText}>
            {currentLiterature ? (
              <>
                <div className={styles.primary}>{getLiteraturePrimaryTitle(currentLiterature)}</div>
                {triggerSecondary && <div className={styles.secondary}>{triggerSecondary}</div>}
              </>
            ) : (
              <div className={styles.placeholder}>문헌 선택…</div>
            )}
          </div>
          <div className={styles.rightMeta}>
            {typeof triggerProgress === 'number' && (
              <span className={styles.progress}>번역 {triggerProgress}%</span>
            )}
            <svg
              className={`${styles.chevron} ${isOpen ? styles.chevronOpen : ''}`}
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </div>
        </div>
      </button>

      {isOpen && (
        <div className={styles.popover} role="dialog" aria-label="문헌 검색">
          <div className={styles.searchRow}>
            <svg className={styles.searchIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <path d="M21 21l-4.35-4.35" />
            </svg>
            <input
              ref={inputRef}
              className={styles.searchInput}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder="문헌 검색 (한글/원문/음역/약어)…"
              role="combobox"
              aria-expanded="true"
              aria-controls="literature-combobox-list"
              aria-activedescendant={activeLiterature ? `literature-option-${activeLiterature.id}` : undefined}
            />
            <span className={styles.kbd} title="단축키">
              ⌘/Ctrl K
            </span>
          </div>

          <div className={styles.hint}>↑↓ 이동 · Enter 선택 · Esc 닫기</div>

          <div className={styles.list} id="literature-combobox-list" role="listbox" ref={listRef}>
            {filteredGroups.length === 0 && <div className={styles.empty}>검색 결과가 없습니다</div>}

            {filteredGroups.map((group) => (
              <div key={`${group.pitaka}-${group.nikaya}`}>
                <div className={styles.groupLabel}>{group.pitaka} · {group.nikaya}</div>
                {group.items.map((lit) => {
                  const isSelected = currentLiterature?.id === lit.id;
                  const isActive = activeLiterature?.id === lit.id;
                  const progress = getTranslationPercentage(lit);
                  return (
                    <button
                      key={lit.id}
                      id={`literature-option-${lit.id}`}
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      className={`${styles.option} ${isActive ? styles.optionActive : ''} ${isSelected ? styles.optionSelected : ''}`}
                      onMouseEnter={() => {
                        const idx = flatOptions.findIndex((o) => o.id === lit.id);
                        if (idx >= 0) setActiveIndex(idx);
                      }}
                      onClick={() => handleOptionClick(lit)}
                    >
                      <div className={styles.optionText}>
                        <div className={styles.optionPrimary}>{getLiteraturePrimaryTitle(lit)}</div>
                        <div className={styles.optionSecondary}>{buildLiteratureSecondaryLine(lit)}</div>
                      </div>
                      <div className={styles.optionMeta}>
                        <span className={styles.progress}>번역 {progress}%</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
