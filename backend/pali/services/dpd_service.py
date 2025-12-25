"""
DPD (Digital Pali Dictionary) Service.
Provides lookup functionality for Pali words using the dpd.db SQLite database.
"""
import sqlite3
import os
import re
import json
import logging
from typing import Optional, List, Dict, Any
from functools import lru_cache
from contextlib import contextmanager
from dataclasses import dataclass

from ..config import settings

logger = logging.getLogger(__name__)


# 힌트 제외 대상: 불변화사 (의미가 고정됨)
SKIP_POS = {'ind', 'prefix', 'suffix'}

# 힌트 제외 대상: 일반적인 불변화사들
SKIP_WORDS = {
    'ca', 'eva', 'pi', 'vā', 'hi', 'tu', 'kho', 'nu', 'nanu',
    'atha', 'pana', 'tathā', 'yathā', 'evaṃ', 'idha', 'ettha',
    'tattha', 'iti', 'ti', 'nāma', 'kiṃ', 'na', 'no', 'mā',
}

# 격 변환 매핑 (한국어)
CASE_KOREAN = {
    'nom': '주격', 'acc': '대격', 'ins': '구격',
    'dat': '여격', 'abl': '탈격', 'gen': '속격',
    'loc': '처격', 'voc': '호격'
}

CASE_SUFFIX = {
    'nom': '~은/는', 'acc': '~을/를', 'ins': '~로',
    'dat': '~에게', 'abl': '~로부터', 'gen': '~의',
    'loc': '~에서', 'voc': ''
}


@dataclass
class GrammarInfo:
    """단어의 문법 정보"""
    lemma: str
    pos: str
    gender: str
    case: str
    number: str


class DpdService:
    """Service for querying the DPD SQLite database."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.DPD_DATABASE_PATH
        # Resolve relative path from backend directory
        if not os.path.isabs(self.db_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, self.db_path)

        self._validate_database()
        self._lookup_available = self._verify_lookup_table()

    def _verify_lookup_table(self) -> bool:
        """lookup 테이블 및 grammar 컬럼 존재 확인."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # 테이블 존재 확인
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='lookup'"
                )
                if not cursor.fetchone():
                    logger.warning("DPD lookup table not found - hints disabled")
                    return False

                # grammar 컬럼 존재 확인
                cursor.execute("PRAGMA table_info(lookup)")
                columns = {row['name'] for row in cursor.fetchall()}
                if 'grammar' not in columns:
                    logger.warning("DPD lookup.grammar column not found - hints disabled")
                    return False

                logger.info("DPD lookup table verified - hints enabled")
                return True
        except Exception as e:
            logger.error(f"Failed to verify lookup table: {e}")
            return False

    @property
    def hints_available(self) -> bool:
        """힌트 기능 사용 가능 여부."""
        return self._lookup_available and settings.HINT_ENABLED

    def _validate_database(self) -> None:
        """Validate that the database file exists."""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"DPD database not found at: {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Get a database connection with read-only mode."""
        # Use URI mode for read-only connection
        conn = sqlite3.connect(
            f"file:{self.db_path}?mode=ro",
            uri=True,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def lookup_word(self, word: str) -> Optional[Dict[str, Any]]:
        """
        Look up a Pali word in the DPD database.

        Lookup strategy:
        1. Direct match on lemma_1
        2. Match with disambiguation suffix (e.g., "buddha" -> "buddha 1")
        3. Lookup table for inflected forms (stores IDs like [48511, 48512])
        """
        normalized = word.lower().strip()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Strategy 1: Try exact match on lemma_1
            row = self._query_headword(cursor, normalized)

            # Strategy 2: Try with " 1" suffix (most common homonym)
            if not row:
                row = self._query_headword(cursor, f"{normalized} 1")

            # Strategy 3: Check lookup table for inflected forms
            if not row:
                cursor.execute("""
                    SELECT headwords FROM lookup
                    WHERE LOWER(lookup_key) = ?
                    LIMIT 1
                """, (normalized,))
                lookup_row = cursor.fetchone()

                if lookup_row and lookup_row['headwords']:
                    # Parse ID from format like "[48511, 48512]" or "[48511]"
                    headwords_str = lookup_row['headwords']
                    try:
                        # Extract first ID from brackets
                        import re
                        ids = re.findall(r'\d+', headwords_str)
                        if ids:
                            first_id = int(ids[0])
                            row = self._query_headword_by_id(cursor, first_id)
                    except (ValueError, IndexError):
                        pass

            if not row:
                return None

            return self._format_entry(dict(row))

    def _query_headword(self, cursor, lemma: str) -> Optional[sqlite3.Row]:
        """Query headword by lemma_1 (case-insensitive)."""
        cursor.execute("""
            SELECT
                h.lemma_1 as headword,
                h.pos,
                h.grammar,
                h.plus_case,
                h.meaning_1,
                h.meaning_2,
                h.meaning_lit,
                h.root_key,
                h.root_base,
                h.construction,
                h.sanskrit,
                h.source_1,
                h.sutta_1,
                h.example_1,
                h.source_2,
                h.sutta_2,
                h.example_2,
                h.compound_type,
                h.compound_construction,
                h.antonym,
                h.synonym,
                h.commentary,
                h.notes,
                h.inflections_html,
                r.root_meaning,
                r.sanskrit_root
            FROM dpd_headwords h
            LEFT JOIN dpd_roots r ON h.root_key = r.root
            WHERE LOWER(h.lemma_1) = ?
            LIMIT 1
        """, (lemma.lower(),))
        return cursor.fetchone()

    def _query_headword_by_id(self, cursor, headword_id: int) -> Optional[sqlite3.Row]:
        """Query headword by ID."""
        cursor.execute("""
            SELECT
                h.lemma_1 as headword,
                h.pos,
                h.grammar,
                h.plus_case,
                h.meaning_1,
                h.meaning_2,
                h.meaning_lit,
                h.root_key,
                h.root_base,
                h.construction,
                h.sanskrit,
                h.source_1,
                h.sutta_1,
                h.example_1,
                h.source_2,
                h.sutta_2,
                h.example_2,
                h.compound_type,
                h.compound_construction,
                h.antonym,
                h.synonym,
                h.commentary,
                h.notes,
                h.inflections_html,
                r.root_meaning,
                r.sanskrit_root
            FROM dpd_headwords h
            LEFT JOIN dpd_roots r ON h.root_key = r.root
            WHERE h.id = ?
            LIMIT 1
        """, (headword_id,))
        return cursor.fetchone()

    def _format_entry(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Format a database row into the DpdEntry structure."""
        # Build definition from meaning_1 and meaning_2
        definitions = []
        if row.get('meaning_1'):
            definitions.append(row['meaning_1'])
        if row.get('meaning_2'):
            definitions.append(row['meaning_2'])
        definition = '; '.join(definitions) if definitions else ''

        # Build grammar string (include plus_case if available)
        grammar_parts = []
        if row.get('pos'):
            grammar_parts.append(row['pos'])
        if row.get('grammar'):
            grammar_parts.append(row['grammar'])
        if row.get('plus_case'):
            grammar_parts.append(row['plus_case'])
        grammar = ', '.join(grammar_parts) if grammar_parts else ''

        # Build etymology from root info
        etymology = None
        if row.get('root_key') and row.get('root_meaning'):
            etymology = f"{row['root_key']} ({row['root_meaning']})"
            if row.get('sanskrit_root'):
                etymology += f" → Skt. {row['sanskrit_root']}"

        # Build examples list with sources
        examples = []
        if row.get('example_1'):
            example_entry = {
                'text': row['example_1'],
                'source': row.get('source_1') or None,
                'sutta': row.get('sutta_1') or None,
            }
            examples.append(example_entry)
        if row.get('example_2'):
            example_entry = {
                'text': row['example_2'],
                'source': row.get('source_2') or None,
                'sutta': row.get('sutta_2') or None,
            }
            examples.append(example_entry)

        return {
            'headword': row.get('headword', ''),
            'definition': definition,
            'grammar': grammar,
            'etymology': etymology,
            'root': row.get('root_key') or None,
            'base': row.get('root_base') or None,
            'construction': row.get('construction') or None,
            'meaning': row.get('meaning_lit') or None,  # literal meaning
            'examples': examples if examples else None,
            # Additional fields for rich display
            'compound_type': row.get('compound_type') or None,
            'compound_construction': row.get('compound_construction') or None,
            # New extended fields
            'sanskrit': row.get('sanskrit') or None,
            'antonym': row.get('antonym') or None,
            'synonym': row.get('synonym') or None,
            'commentary': row.get('commentary') or None,
            'notes': row.get('notes') or None,
            'inflections_html': row.get('inflections_html') or None,
        }

    def lookup_brief(self, word: str) -> Optional[Dict[str, Any]]:
        """Get brief definition (headword, definition, grammar only)."""
        entry = self.lookup_word(word)
        if not entry:
            return None

        return {
            'headword': entry['headword'],
            'definition': entry['definition'],
            'grammar': entry['grammar']
        }

    def lookup_with_suggestions(self, word: str, limit: int = 5) -> Dict[str, Any]:
        """
        Look up a word with fallback suggestions if no exact match.

        Returns:
            {
                "exact_match": {...} or null,
                "suggestions": [...],
                "query": "original word"
            }
        """
        normalized = word.lower().strip()

        # Try exact match first
        exact_match = self.lookup_word(word)
        if exact_match:
            return {
                "exact_match": exact_match,
                "suggestions": [],
                "query": word
            }

        # No exact match - find suggestions
        suggestions = []
        seen_headwords = set()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Strategy 1: Prefix match (e.g., "vessantaraṃtaṃ" -> "vessantaraṃ")
            for prefix_len in range(len(normalized) - 1, 2, -1):
                prefix = normalized[:prefix_len]
                cursor.execute("""
                    SELECT lookup_key, headwords, grammar
                    FROM lookup
                    WHERE LOWER(lookup_key) = ?
                    LIMIT 1
                """, (prefix,))
                row = cursor.fetchone()
                if row and row['headwords']:
                    entry = self._get_suggestion_from_lookup(cursor, row)
                    if entry and entry['headword'] not in seen_headwords:
                        suggestions.append(entry)
                        seen_headwords.add(entry['headword'])
                        break

            # Strategy 2: Suffix match (e.g., "vessantaraṃtaṃ" -> "taṃ")
            # Try from shorter to longer suffixes, prefer longer meaningful ones
            for suffix_start in range(1, len(normalized) - 1):
                suffix = normalized[suffix_start:]
                if len(suffix) < 2:
                    continue
                cursor.execute("""
                    SELECT lookup_key, headwords, grammar
                    FROM lookup
                    WHERE LOWER(lookup_key) = ?
                    LIMIT 1
                """, (suffix,))
                row = cursor.fetchone()
                if row and row['headwords']:
                    entry = self._get_suggestion_from_lookup(cursor, row)
                    if entry and entry['headword'] not in seen_headwords:
                        suggestions.append(entry)
                        seen_headwords.add(entry['headword'])
                        break

            # Strategy 3: Similar words (prefix LIKE search)
            if len(suggestions) < limit and len(normalized) > 3:
                prefix_pattern = f"{normalized[:4]}%"
                cursor.execute("""
                    SELECT DISTINCT lookup_key, headwords, grammar
                    FROM lookup
                    WHERE LOWER(lookup_key) LIKE ?
                    AND headwords IS NOT NULL AND headwords != ''
                    LIMIT ?
                """, (prefix_pattern, limit - len(suggestions)))

                for row in cursor.fetchall():
                    entry = self._get_suggestion_from_lookup(cursor, row)
                    if entry and entry['headword'] not in seen_headwords:
                        suggestions.append(entry)
                        seen_headwords.add(entry['headword'])

        return {
            "exact_match": None,
            "suggestions": suggestions[:limit],
            "query": word
        }

    def _get_suggestion_from_lookup(self, cursor, lookup_row) -> Optional[Dict[str, Any]]:
        """Get brief entry info from lookup row."""
        import re
        headwords_str = lookup_row['headwords']
        ids = re.findall(r'\d+', headwords_str)
        if not ids:
            return None

        first_id = int(ids[0])
        cursor.execute("""
            SELECT lemma_1 as headword, pos, grammar, meaning_1
            FROM dpd_headwords
            WHERE id = ?
            LIMIT 1
        """, (first_id,))
        row = cursor.fetchone()
        if not row:
            return None

        row_dict = dict(row)
        grammar_parts = []
        if row_dict.get('pos'):
            grammar_parts.append(row_dict['pos'])
        if row_dict.get('grammar'):
            grammar_parts.append(row_dict['grammar'])

        return {
            'headword': row_dict.get('headword', ''),
            'definition': row_dict.get('meaning_1', ''),
            'grammar': ', '.join(grammar_parts) if grammar_parts else ''
        }

    # ===== Hint Generation Methods =====

    def lookup_inflection(self, word: str) -> Optional[Dict[str, Any]]:
        """
        lookup 테이블에서 굴절형 조회 (힌트 생성용).

        Returns:
            {
                'grammar_options': [GrammarInfo, ...],
                'meanings': {'lemma': 'meaning', ...}
            }
        """
        if not self._lookup_available:
            return None

        normalized = word.lower().strip()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT headwords, grammar FROM lookup WHERE lookup_key = ?",
                (normalized,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            headwords_str = row['headwords']
            grammar_str = row['grammar']

            if not headwords_str or not grammar_str:
                return None

            try:
                headword_ids = json.loads(headwords_str)
                grammar_data = json.loads(grammar_str)
            except json.JSONDecodeError:
                return None

            if not grammar_data:
                return None

            # 문법 정보 파싱
            grammar_options = []
            for g in grammar_data:
                if len(g) >= 3:
                    lemma, pos, grammar_detail = g[0], g[1], g[2]
                    # grammar_detail 예: "masc dat sg"
                    parts = grammar_detail.split()
                    gender = parts[0] if len(parts) > 0 else ''
                    case = parts[1] if len(parts) > 1 else ''
                    number = parts[2] if len(parts) > 2 else ''

                    grammar_options.append(GrammarInfo(
                        lemma=lemma,
                        pos=pos,
                        gender=gender,
                        case=case,
                        number=number
                    ))

            # 의미 정보 조회
            meanings = {}
            if headword_ids:
                placeholders = ','.join('?' * len(headword_ids))
                cursor.execute(
                    f"SELECT lemma_1, meaning_1, meaning_2 FROM dpd_headwords WHERE id IN ({placeholders})",
                    headword_ids
                )
                for mrow in cursor.fetchall():
                    lemma = mrow['lemma_1'].split()[0]  # "dhamma 1.01" -> "dhamma"
                    meaning = mrow['meaning_1'] or mrow['meaning_2'] or ''
                    if lemma not in meanings and meaning:
                        meanings[lemma] = meaning

            return {
                'grammar_options': grammar_options,
                'meanings': meanings
            }

    def _has_case_ambiguity(self, grammar_options: List[GrammarInfo]) -> bool:
        """격(case)이 다른 해석이 2개 이상인지 확인."""
        cases = set()
        for g in grammar_options:
            if g.case:
                cases.add(g.case)
        return len(cases) > 1

    def should_provide_hint(self, word: str) -> bool:
        """
        이 단어에 힌트를 제공해야 하는지 판단.

        Returns:
            True: 힌트 제공 필요 (모호한 격 변화)
            False: 힌트 불필요 (불변화사, 의미 고정)
        """
        if not self.hints_available:
            return False

        # 일반 불변화사는 스킵
        if word.lower() in SKIP_WORDS:
            return False

        result = self.lookup_inflection(word)
        if not result:
            return False

        grammar_options = result['grammar_options']

        # 불변화사 품사는 스킵
        all_pos = set(g.pos for g in grammar_options)
        if all_pos.issubset(SKIP_POS):
            return False

        # 문법적 모호성이 있으면 힌트 필요
        return self._has_case_ambiguity(grammar_options)

    def get_hint(self, word: str, compact: bool = True) -> Optional[Dict[str, Any]]:
        """
        단어에 대한 힌트 생성.

        Args:
            word: 빠알리 단어
            compact: True면 간결한 형식 (토큰 절약)

        Returns:
            compact=True:
            {
                "word": "dhammassa",
                "lemma": "dhamma",
                "opts": ["여격: ~에게", "속격: ~의"]
            }

            compact=False:
            {
                "word": "dhammassa",
                "options": [
                    {"grammar": "명사, 남성, 여격, 단수", "meaning": "법에게"},
                    ...
                ]
            }
        """
        if not self.should_provide_hint(word):
            return None

        result = self.lookup_inflection(word)
        if not result:
            return None

        grammar_options = result['grammar_options']
        meanings = result['meanings']

        # 격별로 그룹화
        case_options = {}
        lemma_found = None

        for g in grammar_options:
            if g.case and g.case not in case_options:
                lemma_found = g.lemma
                if compact:
                    case_korean = CASE_KOREAN.get(g.case, g.case)
                    case_suffix = CASE_SUFFIX.get(g.case, '')
                    case_options[g.case] = f"{case_korean}: {case_suffix}"
                else:
                    meaning = meanings.get(g.lemma, '')
                    suffix = CASE_SUFFIX.get(g.case, '')
                    # Build full grammar string
                    pos_map = {
                        'noun': '명사', 'adj': '형용사', 'verb': '동사',
                        'pron': '대명사', 'pp': '과거분사', 'prp': '현재분사',
                    }
                    gender_map = {'masc': '남성', 'fem': '여성', 'nt': '중성'}
                    number_map = {'sg': '단수', 'pl': '복수'}

                    grammar_parts = []
                    if g.pos:
                        grammar_parts.append(pos_map.get(g.pos, g.pos))
                    if g.gender:
                        grammar_parts.append(gender_map.get(g.gender, g.gender))
                    if g.case:
                        grammar_parts.append(CASE_KOREAN.get(g.case, g.case))
                    if g.number:
                        grammar_parts.append(number_map.get(g.number, g.number))

                    case_options[g.case] = {
                        "grammar": ', '.join(grammar_parts),
                        "meaning": f"{meaning}{suffix}" if suffix else meaning
                    }

        if not case_options:
            return None

        if compact:
            return {
                "word": word,
                "lemma": lemma_found or '',
                "opts": list(case_options.values())
            }
        else:
            return {
                "word": word,
                "options": list(case_options.values())
            }

    def search(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """
        Search for words matching the query.
        Searches headwords and definitions.
        """
        normalized = f"%{query.lower().strip()}%"

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    lemma_1 as headword,
                    pos,
                    grammar,
                    meaning_1,
                    meaning_2
                FROM dpd_headwords
                WHERE LOWER(lemma_1) LIKE ?
                   OR LOWER(meaning_1) LIKE ?
                   OR LOWER(meaning_2) LIKE ?
                LIMIT ?
            """, (normalized, normalized, normalized, limit))

            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                definitions = []
                if row_dict.get('meaning_1'):
                    definitions.append(row_dict['meaning_1'])
                if row_dict.get('meaning_2'):
                    definitions.append(row_dict['meaning_2'])

                grammar_parts = []
                if row_dict.get('pos'):
                    grammar_parts.append(row_dict['pos'])
                if row_dict.get('grammar'):
                    grammar_parts.append(row_dict['grammar'])

                results.append({
                    'headword': row_dict.get('headword', ''),
                    'definition': '; '.join(definitions) if definitions else '',
                    'grammar': ', '.join(grammar_parts) if grammar_parts else ''
                })

            return {
                'query': query,
                'results': results,
                'count': len(results)
            }


# Singleton instance
@lru_cache()
def get_dpd_service() -> DpdService:
    """Get cached DPD service instance."""
    return DpdService()
