/**
 * DpdCard Component
 *
 * Displays DPD dictionary lookup results in the chat stream.
 * Per PHASE0_DECISIONS.md Section 0.7: DPD results appear as system cards.
 */
import type { DpdEntry } from '@/store';
import type { DpdBriefEntry } from '@/types/api';
import styles from './DpdCard.module.css';

interface DpdCardProps {
  word: string;
  status?: 'loading' | 'ok' | 'not_found' | 'suggestions' | 'error';
  entry?: DpdEntry;
  suggestions?: DpdBriefEntry[];
  error?: string;
}

export function DpdCard({ word, status, entry, suggestions, error }: DpdCardProps) {
  const isNotFound = (message: string) =>
    message.includes('404') || message.toLowerCase().includes('not found');

  const resolvedStatus: NonNullable<DpdCardProps['status']> =
    status
      ?? (entry
        ? 'ok'
        : suggestions && suggestions.length > 0
          ? 'suggestions'
          : error
            ? (isNotFound(error) ? 'not_found' : 'error')
            : 'loading');

  if (resolvedStatus === 'loading') {
    return (
      <div className={styles.card}>
        <div className={styles.header}>
          <span className={styles.icon}>📖</span>
          <span className={styles.word}>{word}</span>
        </div>
        <div className={styles.loadingRow}>
          <span className={styles.spinner} aria-hidden="true" />
          <p className={styles.loadingText}>사전 검색 중…</p>
        </div>
      </div>
    );
  }

  if (resolvedStatus === 'suggestions') {
    return (
      <div className={styles.card}>
        <div className={styles.header}>
          <span className={styles.icon}>📖</span>
          <span className={styles.word}>{word}</span>
        </div>
        <p className={styles.notFoundHint}>
          정확히 일치하는 표제어 없음
        </p>
        {suggestions && suggestions.length > 0 ? (
          <div className={styles.suggestionsSection}>
            <p className={styles.suggestionsLabel}>관련 가능한 단어:</p>
            <div className={styles.suggestionsList}>
              {suggestions.map((suggestion, idx) => (
                <div key={idx} className={styles.suggestionItem}>
                  <span className={styles.suggestionHeadword}>{suggestion.headword}</span>
                  {suggestion.grammar && (
                    <span className={styles.suggestionGrammar}>{suggestion.grammar}</span>
                  )}
                  {suggestion.definition && (
                    <p className={styles.suggestionDefinition}>{suggestion.definition}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className={styles.notFound}>
            관련 단어를 찾을 수 없습니다
          </p>
        )}
      </div>
    );
  }

  if (resolvedStatus === 'not_found') {
    return (
      <div className={styles.card}>
        <div className={styles.header}>
          <span className={styles.icon}>📖</span>
          <span className={styles.word}>{word}</span>
        </div>
        <p className={styles.notFound}>
          사전에서 찾을 수 없습니다
        </p>
      </div>
    );
  }

  if (resolvedStatus === 'error') {
    return (
      <div className={styles.card}>
        <div className={styles.header}>
          <span className={styles.icon}>📖</span>
          <span className={styles.word}>{word}</span>
        </div>
        <p className={styles.errorText}>
          조회 중 오류가 발생했습니다
        </p>
      </div>
    );
  }

  if (!entry) {
    return null;
  }

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.icon}>📖</span>
        <span className={styles.headword}>{entry.headword}</span>
        {entry.grammar && (
          <span className={styles.grammar}>{entry.grammar}</span>
        )}
      </div>

      <div className={styles.definition}>
        {entry.definition}
      </div>

      {/* Etymology & Root */}
      {(entry.etymology || entry.root) && (
        <div className={styles.section}>
          {entry.etymology && (
            <div className={styles.etymology}>
              <span className={styles.label}>어원:</span> {entry.etymology}
            </div>
          )}
          {entry.root && entry.base && (
            <div className={styles.root}>
              <span className={styles.label}>어근:</span> {entry.root}
              {entry.base && ` (${entry.base})`}
            </div>
          )}
        </div>
      )}

      {/* Sanskrit */}
      {entry.sanskrit && (
        <div className={styles.section}>
          <span className={styles.label}>산스크리트:</span> {entry.sanskrit}
        </div>
      )}

      {/* Construction */}
      {entry.construction && (
        <div className={styles.section}>
          <span className={styles.label}>구성:</span> {entry.construction}
        </div>
      )}

      {/* Compound info */}
      {entry.compound_type && (
        <div className={styles.section}>
          <span className={styles.label}>복합어:</span> {entry.compound_type}
          {entry.compound_construction && (
            <span className={styles.compoundDetail}>
              {' '}({entry.compound_construction})
            </span>
          )}
        </div>
      )}

      {/* Examples with sources */}
      {entry.examples && entry.examples.length > 0 && (
        <div className={styles.examples}>
          <span className={styles.label}>예문:</span>
          {entry.examples.map((example, idx) => (
            <div key={idx} className={styles.exampleItem}>
              <p
                className={styles.exampleText}
                dangerouslySetInnerHTML={{ __html: example.text }}
              />
              {(example.source || example.sutta) && (
                <p className={styles.exampleSource}>
                  {example.source && <span>{example.source}</span>}
                  {example.source && example.sutta && <span> · </span>}
                  {example.sutta && <span>{example.sutta}</span>}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Commentary */}
      {entry.commentary && (
        <div className={styles.section}>
          <span className={styles.label}>주석:</span>
          <p
            className={styles.commentary}
            dangerouslySetInnerHTML={{ __html: entry.commentary }}
          />
        </div>
      )}

      {/* Synonym & Antonym */}
      {(entry.synonym || entry.antonym) && (
        <div className={styles.section}>
          {entry.synonym && (
            <div className={styles.relatedWords}>
              <span className={styles.label}>유의어:</span> {entry.synonym}
            </div>
          )}
          {entry.antonym && (
            <div className={styles.relatedWords}>
              <span className={styles.label}>반의어:</span> {entry.antonym}
            </div>
          )}
        </div>
      )}

      {/* Notes */}
      {entry.notes && (
        <div className={styles.section}>
          <span className={styles.label}>참고:</span>
          <p className={styles.notes}>{entry.notes}</p>
        </div>
      )}

      {/* Inflection table */}
      {entry.inflections_html && (
        <details className={styles.inflectionDetails}>
          <summary className={styles.inflectionSummary}>굴절표 보기</summary>
          <div
            className={styles.inflectionTable}
            dangerouslySetInnerHTML={{ __html: entry.inflections_html }}
          />
        </details>
      )}
    </div>
  );
}
