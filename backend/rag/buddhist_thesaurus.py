"""Lightweight thesaurus for Buddhist query expansion.

Used by the retriever to append closely related terms so semantically
similar passages are surfaced even when wording varies.
"""

from typing import Dict, List

# Synonym groups (each term in a group maps to the full group)
SYNONYM_GROUPS: List[List[str]] = [
    ["연기법", "연기", "십이연기", "12연기", "緣起", "인연생기"],
    [
        "상좌부",
        "초기불교",
        "아비담마",
        "남방 불교 4위 82법",
        "남방불교",
        "테라와다",
    ],
    [
        "대승불교",
        "유식학",
        "유가사지론",
        "대승백법명문론의 5위 100법",
        "유가행파",
    ],
    [
        "설일체유부",
        "아비달마대비바사론",
        "아비달마 구사론",
        "북방 불교의 5위 75법",
        "구사파",
    ],
]


def _build_thesaurus(groups: List[List[str]]) -> Dict[str, List[str]]:
    """Create a lookup where each term points to its full synonym group."""
    thesaurus: Dict[str, List[str]] = {}
    for group in groups:
        deduped_group: List[str] = []
        seen = set()
        for term in group:
            if term not in seen:
                deduped_group.append(term)
                seen.add(term)
        for term in deduped_group:
            thesaurus[term] = deduped_group
    return thesaurus


THESAURUS: Dict[str, List[str]] = _build_thesaurus(SYNONYM_GROUPS)


def expand_query(query: str) -> str:
    """Append known synonyms for matched Buddhist terms.

    If no terms are found, the original query is returned unchanged.
    """
    normalized = query.strip()
    if not normalized:
        return query

    lower_query = normalized.lower()
    expansions: List[str] = []

    for term, synonyms in THESAURUS.items():
        if term.lower() in lower_query:
            expansions.extend(synonyms)

    if not expansions:
        return normalized

    # Deduplicate while preserving order
    seen = set()
    deduped: List[str] = []
    for term in expansions:
        if term not in seen:
            deduped.append(term)
            seen.add(term)

    return f"{normalized} {' '.join(deduped)}"
