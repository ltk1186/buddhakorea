import { SiteHeader } from '@/components/layout/SiteHeader';
import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '@/api/client';
import styles from './PublishedReader.module.css';

interface Chapter {
    id: number;
    title: string;
    count: number;
    first_verse: number | null;
    last_verse: number | null;
}

interface Book {
    id: string;
    title: string;
    pali_title: string;
    release: string;
    segment_count: number;
    source_url: string | null;
    verse_count: number;
    chapter_label: string;
    description: string | null;
    model: string;
    translation_notice: string;
    chapters: Chapter[];
}

interface Verse {
    key: string;
    chapter: number;
    verse: number | null;
    kind: 'verse' | 'passage' | 'supplement' | 'appendix';
    order: number;
    original_text: string;
    natural_ko: string;
}

interface Translation {
    literal_ko: string;
    terms: { pali: string; ko: string; gloss: string; note: string }[];
    grammar_notes: string[];
    doctrinal_notes: string[];
    uncertainties: string[];
}

function TranslationNotes({ book, verse }: { book: Book; verse: Verse }) {
    const [translation, setTranslation] = useState<Translation | null>(null);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const load = async () => {
        if (loading || translation) return;
        setLoading(true);
        setError('');
        try {
            const result = await apiRequest<{ translation: Translation }>(
                `/literature/${book.id}/reading/detail`,
                { params: { key: verse.key, release: book.release } },
            );
            setTranslation(result.translation);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : '설명을 불러오지 못했습니다.');
        } finally {
            setLoading(false);
        }
    };
    return (
        <details className={styles.notes} onToggle={(event) => { if (event.currentTarget.open) void load(); }}>
            <summary>직역과 해설</summary>
            {loading && <p role="status">설명을 불러오는 중입니다.</p>}
            {error && <p role="alert">{error} <button onClick={() => void load()}>다시 시도</button></p>}
            {translation && <div className={styles.noteBody}>
                <section><h4>직역</h4><p>{translation.literal_ko}</p></section>
                {translation.terms.length > 0 && <section><h4>주요 용어</h4><dl>
                    {translation.terms.map((term, index) => <div key={`${term.pali}-${index}`}>
                        <dt><span lang="pi">{term.pali}</span> · {term.ko}</dt>
                        <dd>{term.note || term.gloss}</dd>
                    </div>)}
                </dl></section>}
                {([
                    ['문법 설명', translation.grammar_notes],
                    ['교리 설명', translation.doctrinal_notes],
                    ['다르게 해석할 수 있는 부분', translation.uncertainties],
                ] as [string, string[]][]).map(([title, notes]) => notes.length > 0 && <section key={title}>
                    <h4>{title}</h4><ul>{notes.map((note, index) => <li key={index}>{note}</li>)}</ul>
                </section>)}
                
            </div>}
        </details>
    );
}

export function PublishedReader({ literatureId }: { literatureId: string }) {
    const [book, setBook] = useState<Book | null>(null);
    const [verses, setVerses] = useState<Verse[]>([]);
    const [chapter, setChapter] = useState(1);
    const [showOriginal, setShowOriginal] = useState(false);
    const [fontSize, setFontSize] = useState(20);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [highlight, setHighlight] = useState('');
    const [retry, setRetry] = useState(0);
    const requestNumber = useRef(0);
    const heading = useRef<HTMLHeadingElement>(null);

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            const request = ++requestNumber.current;
            setLoading(true);
            setError('');
            setVerses([]);
            try {
                const nextBook = await apiRequest<Book>(`/literature/${literatureId}/reading`);
                if (cancelled || request !== requestNumber.current) return;
                setBook(nextBook);
                const params = new URLSearchParams(window.location.search);
                const key = params.get('segment');
                let nextChapter = Number(params.get('chapter') ?? params.get('vagga') ?? nextBook.chapters[0]?.id);
                if (key) {
                    const location = await apiRequest<{ chapter: number }>(
                        `/literature/${literatureId}/reading/locate`, { params: { key } },
                    );
                    nextChapter = location.chapter;
                }
                if (!nextBook.chapters.some((item) => item.id === nextChapter)) {
                    throw new Error('해당 목차를 찾을 수 없습니다. 목록에서 다시 선택해 주세요.');
                }
                const nextVerses: Verse[] = [];
                let hasMore = true;
                while (hasMore) {
                    const result = await apiRequest<{ segments: Verse[]; has_more: boolean }>(
                        `/literature/${literatureId}/reading/segments`,
                        { params: { chapter: nextChapter, release: nextBook.release, offset: nextVerses.length } },
                    );
                    if (cancelled || request !== requestNumber.current) return;
                    nextVerses.push(...result.segments);
                    hasMore = result.has_more && result.segments.length > 0;
                }
                if (cancelled || request !== requestNumber.current) return;
                setChapter(nextChapter);
                setVerses(nextVerses);
                setHighlight(key || '');
                setLoading(false);
                document.title = `${nextBook.title} · ${nextBook.chapters.find((item) => item.id === nextChapter)?.title} — Buddha Korea`;
                requestAnimationFrame(() => {
                    if (cancelled || request !== requestNumber.current) return;
                    if (key) document.getElementById(key)?.scrollIntoView({ block: 'center' });
                });
            } catch (reason) {
                if (cancelled || request !== requestNumber.current) return;
                setError(reason instanceof Error ? reason.message : '본문을 불러오지 못했습니다.');
                setLoading(false);
            }
        };
        void load();
        const onPopState = () => { void load(); };
        window.addEventListener('popstate', onPopState);
        return () => { cancelled = true; window.removeEventListener('popstate', onPopState); };
    }, [literatureId, retry]);

    const navigate = (id: number) => {
        const params = new URLSearchParams({ lit: literatureId, chapter: String(id) });
        window.history.pushState({}, '', `${window.location.pathname}?${params}`);
        setNotice('');
        setRetry((value) => value + 1);
        heading.current?.focus();
        window.scrollTo({ top: 0 });
    };
    const copyLink = async (verse: Verse) => {
        const url = new URL(window.location.href);
        url.search = new URLSearchParams({ lit: literatureId, segment: verse.key }).toString();
        try {
            await navigator.clipboard.writeText(url.toString());
            setNotice(verse.verse ? `제${verse.verse}게송 링크를 복사했습니다.` : '이 구간의 링크를 복사했습니다.');
        } catch {
            setNotice(`링크를 복사해 주세요: ${url.toString()}`);
        }
    };
    const chapterLabel = book?.chapter_label || '장';
    const mainChapters = book?.chapters.filter((item) => item.id !== 0) || [];
    const selected = book?.chapters.find((item) => item.id === chapter);
    const chapterIndex = book?.chapters.findIndex((item) => item.id === chapter) ?? 0;

    return (
        <div className={styles.reader}>
            <a className={styles.skip} href="#reading-content">본문으로 건너뛰기</a>
            <SiteHeader />
            <div className={styles.hero}>
                <nav className={styles.breadcrumb} aria-label="현재 위치"><a href="/pali/">경전 읽기</a><span aria-hidden="true">/</span><span aria-current="page">{book?.title || '본문'}</span></nav>
                <h1>{book?.title || '경전 읽기'} {book && <span lang="pi">{book.pali_title}</span>}</h1>
                <p className={styles.intro}>{book?.description || '빠알리 원문과 함께 읽는 한국어 번역.'}</p>
                <div className={styles.metadata}>{book && <><span>{mainChapters.length}개 {chapterLabel}</span><span>{book.verse_count ? `${book.verse_count}개 본문 게송` : `${book.segment_count}개 구간`}</span></>}<span className={styles.badge}>AI 번역</span></div>
            </div>
            <div className={styles.layout}>
                <aside className={styles.sidebar} aria-label={`${book?.title || '문헌'} 목차`}>
                    <div className={styles.tocTitle}>목차 <span>CONTENTS</span></div>
                    <nav aria-label="본문 목차">{book?.chapters.map((item) => <button
                        key={item.id} onClick={() => navigate(item.id)} aria-current={item.id === chapter ? 'page' : undefined}
                        className={item.id === chapter ? styles.selected : ''}
                    ><span className={styles.chapterNumber}>{item.id === 0 ? '＋' : String(item.id).padStart(2, '0')}</span>
                        <span>{item.title}<small>{item.first_verse ? `${item.first_verse}–${item.last_verse}게송` : `${item.count}개 구간`}</small></span>
                    </button>)}</nav>
                </aside>
                <main id="reading-content" className={styles.content}>
                    <div className={styles.mobileSelect}>
                        <label htmlFor="chapter-select">목차</label>
                        <select id="chapter-select" aria-label="목차 선택" value={chapter} onChange={(event) => navigate(Number(event.target.value))}>
                            {book?.chapters.map((item) => <option key={item.id} value={item.id}>{item.id ? `제${item.id}${chapterLabel} · ` : ''}{item.title}</option>)}
                        </select>
                    </div>
                    <div className={styles.toolbar}>
                        <label><input type="checkbox" checked={showOriginal} onChange={(event) => setShowOriginal(event.target.checked)} />빠알리 원문 함께 보기</label>
                        <div className={styles.fontControls}>
                            <button aria-label="글자 작게" disabled={fontSize <= 18} onClick={() => setFontSize((size) => size - 2)}>가−</button>
                            <button aria-label="글자 크게" disabled={fontSize >= 28} onClick={() => setFontSize((size) => size + 2)}>가＋</button>
                        </div>
                    </div>
                    <div className={styles.chapterHeading}>
                        <p>{chapter ? `제${chapter}${chapterLabel}` : '부록'}</p>
                        <h2 ref={heading} tabIndex={-1}>{selected?.title || book?.title || '경전 읽기'}</h2>
                        {selected?.first_verse && <span>제{selected.first_verse}–{selected.last_verse}게송</span>}
                    </div>
                    {loading && <div className={styles.status} role="status">본문을 불러오고 있습니다.</div>}
                    {error && <div className={styles.status} role="alert"><p>{error}</p><button onClick={() => setRetry((value) => value + 1)}>다시 불러오기</button><button onClick={() => navigate(book?.chapters[0]?.id ?? 1)}>처음으로</button></div>}
                    {!loading && !error && book && <div>{verses.map((verse) => <article
                        id={verse.key} key={`${book.release}-${verse.key}`}
                        className={`${styles.verse} ${highlight === verse.key ? styles.highlight : ''}`}
                        aria-label={verse.verse ? `제${verse.verse}게송` : `본문 구간 ${verse.order}`}
                    >
                        <div className={styles.verseTop}>
                            <h3>{verse.verse ? String(verse.verse).padStart(3, '0') : verse.kind === 'passage' ? `본문 ${verse.order}` : verse.kind === 'supplement' ? (book.id === 'vri-romn-s0502m-mul' ? '번호 없는 추가 게송' : '부속 글') : '권말 글'}</h3>
                            <button onClick={() => void copyLink(verse)} aria-label={verse.verse ? `제${verse.verse}게송 링크 복사` : '부속 구간 링크 복사'}>링크 복사 <span aria-hidden="true">↗</span></button>
                        </div>
                        <div className={`${styles.verseText} ${showOriginal ? styles.parallel : ''}`}>
                            {showOriginal && <div className={styles.original}><span>빠알리 원문</span><p lang="pi">{verse.original_text}</p></div>}
                            <p className={styles.translation} style={{ fontSize }}>{verse.natural_ko}</p>
                        </div>
                        <TranslationNotes book={book} verse={verse} />
                    </article>)}</div>}
                    {book && <nav className={styles.chapterNavigation} aria-label="이전 다음 목차">
                        <button disabled={chapterIndex === 0 || loading} onClick={() => navigate(book.chapters[chapterIndex - 1].id)}>← 이전 {chapterLabel}</button>
                        <span>{chapter ? `${mainChapters.findIndex((item) => item.id === chapter) + 1} / ${mainChapters.length}${chapterLabel}` : '권말 부록'}</span>
                        <button disabled={chapterIndex === book.chapters.length - 1 || loading} onClick={() => navigate(book.chapters[chapterIndex + 1].id)}>{book.chapters[chapterIndex + 1]?.id === 0 ? '부록 →' : `다음 ${chapterLabel} →`}</button>
                    </nav>}
                    <footer className={styles.footer}>
                        <details><summary>번역과 출처 안내</summary>
                            <p>빠알리 원문과 한국어 번역을 함께 제공합니다. 한국어 본문은 자연스러운 번역이며, 각 구간에서 직역과 해설을 펼칠 수 있습니다.</p>
                            <p><a href="/pali/#translation-guide">AI 번역 안내</a></p>
                            {book && <>{book.source_url && <a href={book.source_url} target="_blank" rel="noreferrer">원문 출처 · Vipassana Research Institute XML ↗</a>}<p>번역 모델: {book.model}<br />공개본: {book.release}</p></>}
                        </details>
                    </footer>
                </main>
            </div>
            <div className={styles.announcement} role="status" aria-live="polite">{notice}</div>
        </div>
    );
}
