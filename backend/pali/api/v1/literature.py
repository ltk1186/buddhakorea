"""
Literature CRUD endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..deps import get_literature_service
from ...services.literature_service import LiteratureService
from ...schemas.literature import (
    LiteratureResponse, LiteratureListResponse,
    SegmentResponse, SegmentListResponse
)
from ...schemas.common import PaginationMeta

router = APIRouter()


@router.get("", response_model=LiteratureListResponse)
async def list_literatures(
    service: LiteratureService = Depends(get_literature_service)
):
    """
    Get all available literatures with Tripitaka structure.
    """
    literatures = service.get_all_literatures()
    pitaka_structure = service.get_pitaka_structure()

    return LiteratureListResponse(
        literatures=[LiteratureResponse.model_validate(lit) for lit in literatures],
        pitaka_structure=pitaka_structure,
        total_count=len(literatures)
    )


@router.get("/{literature_id}", response_model=LiteratureResponse)
async def get_literature(
    literature_id: str,
    service: LiteratureService = Depends(get_literature_service)
):
    """
    Get a specific literature by ID.
    """
    literature = service.get_literature_by_id(literature_id)
    if not literature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Literature '{literature_id}' not found"
        )

    return LiteratureResponse.model_validate(literature)


@router.get("/{literature_id}/segments", response_model=SegmentListResponse)
async def list_segments(
    literature_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    vagga_id: Optional[int] = Query(default=None),
    sutta_id: Optional[int] = Query(default=None),
    service: LiteratureService = Depends(get_literature_service)
):
    """
    Get segments for a literature with pagination.
    Optionally filter by vagga and/or sutta.
    """
    # Verify literature exists
    literature = service.get_literature_by_id(literature_id)
    if not literature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Literature '{literature_id}' not found"
        )

    segments, total = service.get_segments(
        literature_id=literature_id,
        offset=offset,
        limit=limit,
        vagga_id=vagga_id,
        sutta_id=sutta_id
    )

    return SegmentListResponse(
        segments=[SegmentResponse.model_validate(seg) for seg in segments],
        pagination=PaginationMeta(
            offset=offset,
            limit=limit,
            total=total,
            has_more=(offset + limit) < total
        )
    )


@router.get("/{literature_id}/segments/{segment_id}", response_model=SegmentResponse)
async def get_segment(
    literature_id: str,
    segment_id: int,
    service: LiteratureService = Depends(get_literature_service)
):
    """
    Get a specific segment by ID.
    """
    segment = service.get_segment_by_id(literature_id, segment_id)
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment {segment_id} not found in literature '{literature_id}'"
        )

    return SegmentResponse.model_validate(segment)


@router.get("/{literature_id}/hierarchy")
async def get_literature_hierarchy(
    literature_id: str,
    service: LiteratureService = Depends(get_literature_service)
):
    """
    Get the hierarchical structure (vaggas and suttas) for a literature.
    Returns a tree structure for navigation.
    """
    literature = service.get_literature_by_id(literature_id)
    if not literature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Literature '{literature_id}' not found"
        )

    hierarchy = service.get_literature_hierarchy(literature_id)
    return {
        "literature_id": literature_id,
        "hierarchy": hierarchy
    }


@router.get("/{literature_id}/search")
async def search_in_literature(
    literature_id: str,
    q: str = Query(..., min_length=2),
    limit: int = Query(default=50, ge=1, le=200),
    page: Optional[int] = Query(default=None, ge=0),
    service: LiteratureService = Depends(get_literature_service)
):
    """
    Search for text within a literature.
    """
    # Verify literature exists
    literature = service.get_literature_by_id(literature_id)
    if not literature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Literature '{literature_id}' not found"
        )

    search = service.search_segments_with_stats(
        query=q,
        literature_id=literature_id,
        limit=limit,
        page_number=page,
    )

    return {
        "query": q,
        "page_filter": page,
        "results": [SegmentResponse.model_validate(seg) for seg in search["segments"]],
        "returned_count": search["returned_count"],
        "hit_segments_count": search["hit_segments_count"],
        "total_occurrences": search["total_occurrences"],
        "unknown_page_occurrences": search["unknown_page_occurrences"],
        "pages": search["pages"],
    }
