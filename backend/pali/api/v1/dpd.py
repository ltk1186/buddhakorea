"""
DPD (Digital Pali Dictionary) lookup endpoint.
Provides word lookup functionality using the dpd.db SQLite database.

License: DPD data is licensed under CC BY-NC 4.0
Source: https://digitalpalidictionary.github.io/
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query

from ...services.dpd_service import get_dpd_service, DpdService

router = APIRouter()


def get_dpd() -> DpdService:
    """Dependency to get DPD service."""
    try:
        return get_dpd_service()
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"DPD dictionary not available: {str(e)}"
        )


@router.get("/search")
async def search_dictionary(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results")
):
    """
    Search for words in the DPD dictionary.
    Searches headwords and definitions.
    """
    dpd = get_dpd()
    return dpd.search(q, limit)


@router.get("/{word}")
async def lookup_word(word: str):
    """
    Look up a Pali word in the DPD dictionary.

    Returns:
    - exact_match: Full entry if found, null otherwise
    - suggestions: Related words if no exact match
    - query: The original search word

    When exact_match is found, it includes:
    - headword, definition, grammar, etymology, root, base,
    - construction, meaning, examples, compound_type, compound_construction
    """
    dpd = get_dpd()
    result = dpd.lookup_with_suggestions(word)
    return result


@router.get("/{word}/brief")
async def lookup_word_brief(word: str):
    """
    Get brief definition of a Pali word.
    Returns only headword, definition, and grammar.
    """
    dpd = get_dpd()
    entry = dpd.lookup_brief(word)

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Word '{word}' not found in dictionary"
        )

    return entry
