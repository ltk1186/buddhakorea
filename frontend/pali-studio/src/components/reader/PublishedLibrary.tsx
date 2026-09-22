import { SiteHeader } from '@/components/layout/SiteHeader';
import { useEffect, useState } from 'react';
import { getLiteratures } from '@/api/literature';
import type { Literature } from '@/types/literature';
import shared from './PublishedReader.module.css';
import styles from './PublishedLibrary.module.css';

export function PublishedLibrary() {
    const [books, setBooks] = useState<Literature[]>([]);
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [retry, setRetry] = useState(0);

    useEffect(() => {
        let cancelled = false;
        document.title = '경전 읽기 — Buddha Korea';
        setLoading(true);
        setError('');
        getLiteratures().then((result) => {
            if (!cancelled) {
                // The API excludes canonical books without a published release.
                setBooks(result.literatures.filter((book) => book.content_type === 'canonical'));
            }
        }).catch((reason) => {
            if (!cancelled) setError(reason instanceof Error ? reason.message : '문헌 목록을 불러오지 못했습니다.');
        }).finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [retry]);

    const search = query.trim().normalize('NFC').toLocaleLowerCase();
    const visible = books.filter((book) => [book.name, book.pali_name, ...(book.display_metadata?.aliases || [])]
        .join(' ').normalize('NFC').toLocaleLowerCase().includes(search));

    return <div className={shared.reader}>
        <a className={shared.skip} href="#library-content">문헌 목록으로 건너뛰기</a>
        <SiteHeader />
        <main id="library-content" className={styles.library}>
            <div className={styles.introduction}>
                
                <h1>경전 읽기</h1>
                <p>빠알리 경전을 한국어로 읽고,<br />원문과 해설을 함께 살펴보세요.</p>
                <p className={styles.accessNote}>로그인 없이 읽을 수 있습니다.</p>
            </div>
            <aside id="translation-guide" className={styles.translationGuide} aria-label="AI 번역 안내"><h2>AI 번역 안내</h2><p>번역과 해설은 AI로 작성했습니다. 오류가 있을 수 있으니 원문과 함께 확인해 주세요.</p></aside>
            <div className={styles.tools}>
                <h2>공개된 문헌 {!loading && !error && <span>{books.length}</span>}</h2>
                <div className={styles.search}>
                    <label htmlFor="book-search">문헌 검색</label>
                    <input id="book-search" type="search" placeholder="한국어·빠알리 제목" value={query} onChange={(event) => setQuery(event.target.value)} />
                </div>
            </div>
            {loading && <p className={shared.status} role="status">문헌 목록을 불러오고 있습니다.</p>}
            {error && <div className={shared.status} role="alert"><p>{error}</p><button onClick={() => setRetry((value) => value + 1)}>다시 불러오기</button></div>}
            {!loading && !error && <>
                <div className={styles.grid}>
                    {visible.map((book) => <a key={book.id} href={`/pali/?lit=${encodeURIComponent(book.id)}`} className={styles.card}>
                        <span className={styles.cardLabel}>한국어 번역</span>
                        <h3>{book.name}</h3>
                        <p className={styles.paliTitle} lang="pi">{book.pali_name}</p>
                        {book.display_metadata?.description && <p className={styles.description}>{book.display_metadata.description}</p>}
                        <div className={styles.cardFooter}><span>{book.translated_segments.toLocaleString()}개 번역 구간</span><span>읽기 시작 <span aria-hidden="true">↗</span></span></div>
                    </a>)}
                </div>
                {visible.length === 0 && <p className={shared.status} role="status">{books.length === 0 ? '공개할 문헌을 준비하고 있습니다.' : '검색 결과가 없습니다. 다른 제목으로 찾아보세요.'}</p>}
                <p className={styles.notice}>번역이 준비된 문헌을 차례로 공개합니다.</p>
            </>}
        </main>
    </div>;
}
