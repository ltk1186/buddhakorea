"""
Admin API endpoints for PDF parsing and data management.
Protected by admin token authentication.
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...db.database import get_db
from ..deps import verify_admin_token, get_literature_service
from ...services.literature_service import LiteratureService
from ...services.pdf_parser import PdfParser
from ...schemas.literature import LiteratureCreate
from ...db.models import Segment

router = APIRouter()


class ParsePdfRequest(BaseModel):
    """Request schema for PDF parsing."""
    pdf_path: str
    literature_id: str
    name: str
    pali_name: str
    pitaka: str
    nikaya: str = None
    max_pages: int = None


class ParsePdfResponse(BaseModel):
    """Response schema for PDF parsing."""
    status: str
    literature_id: str
    segments_count: int


@router.post("/parse-pdf", response_model=ParsePdfResponse)
async def parse_pdf(
    request: ParsePdfRequest,
    db: Session = Depends(get_db),
    service: LiteratureService = Depends(get_literature_service),
    _: bool = Depends(verify_admin_token)
):
    """
    Parse a PDF file and load it into the database.
    Requires admin authentication.
    """
    # Verify PDF exists
    if not os.path.exists(request.pdf_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF file not found: {request.pdf_path}"
        )

    # Check if literature already exists
    existing = service.get_literature_by_id(request.literature_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Literature '{request.literature_id}' already exists"
        )

    try:
        # Parse the PDF
        parser = PdfParser(request.pdf_path)
        segments = parser.parse(max_pages=request.max_pages)

        # Create the literature record
        literature = service.create_literature({
            "id": request.literature_id,
            "name": request.name,
            "pali_name": request.pali_name,
            "pitaka": request.pitaka,
            "nikaya": request.nikaya,
            "source_pdf": request.pdf_path,
            "hierarchy_labels": parser.hierarchy_labels,
            "status": "parsed"
        })

        # Create segments in bulk
        segments_data = [
            {"literature_id": request.literature_id, **seg}
            for seg in parser.to_dict_list(segments)
        ]
        service.create_segments_bulk(segments_data)

        return ParsePdfResponse(
            status="success",
            literature_id=request.literature_id,
            segments_count=len(segments)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error parsing PDF: {str(e)}"
        )


class ImportJsonRequest(BaseModel):
    """Request schema for importing existing JSON translation."""
    json_path: str
    literature_id: str
    name: str
    pali_name: str
    pitaka: str
    nikaya: str = None


@router.post("/import-json")
async def import_json_translation(
    request: ImportJsonRequest,
    db: Session = Depends(get_db),
    service: LiteratureService = Depends(get_literature_service),
    _: bool = Depends(verify_admin_token)
):
    """
    Import an existing JSON translation file into the database.
    Supports both array format and {_metadata, segments} format.
    """
    import json

    # Verify file exists
    if not os.path.exists(request.json_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"JSON file not found: {request.json_path}"
        )

    # Check if literature already exists
    existing = service.get_literature_by_id(request.literature_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Literature '{request.literature_id}' already exists"
        )

    try:
        # Load JSON file
        with open(request.json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Determine format and extract segments
        if isinstance(data, list):
            # Array format
            raw_segments = data
            hierarchy_labels = None
        elif isinstance(data, dict) and "segments" in data:
            # {_metadata, segments} format
            raw_segments = data["segments"]
            hierarchy_labels = data.get("_metadata", {}).get("hierarchy_labels")
        else:
            raise ValueError("Unsupported JSON format")

        # Create the literature record
        literature = service.create_literature({
            "id": request.literature_id,
            "name": request.name,
            "pali_name": request.pali_name,
            "pitaka": request.pitaka,
            "nikaya": request.nikaya,
            "hierarchy_labels": hierarchy_labels,
            "status": "translated"
        })

        # Transform and create segments
        segments_data = []
        for seg in raw_segments:
            page_number = seg.get("page_number", seg.get("page"))
            segments_data.append({
                "literature_id": request.literature_id,
                "vagga_id": seg.get("vagga_id"),
                "vagga_name": seg.get("vagga_name"),
                "sutta_id": seg.get("sutta_id"),
                "sutta_name": seg.get("sutta_name"),
                "page_number": page_number,
                "paragraph_id": seg.get("paragraph_id", 0),
                "original_text": seg.get("original_text", ""),
                "translation": seg.get("translation"),
                "is_translated": seg.get("translation") is not None
            })

        service.create_segments_bulk(segments_data)

        return {
            "status": "success",
            "literature_id": request.literature_id,
            "segments_count": len(segments_data),
            "translated_count": sum(1 for s in segments_data if s["is_translated"])
        }

    except Exception as e:
        # Rollback by deleting the literature if it was created
        if service.get_literature_by_id(request.literature_id):
            service.delete_literature(request.literature_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error importing JSON: {str(e)}"
        )


class BackfillPageNumbersRequest(BaseModel):
    """Request schema for backfilling page numbers on existing segments."""

    literature_id: str
    pdf_path: Optional[str] = None
    max_pages: Optional[int] = None
    dry_run: bool = False


@router.post("/backfill-page-numbers")
async def backfill_page_numbers(
    request: BackfillPageNumbersRequest,
    service: LiteratureService = Depends(get_literature_service),
    _: bool = Depends(verify_admin_token),
):
    """
    Backfill `page_number` for an existing literature by reparsing its source PDF.
    Does not modify translations.
    """
    literature = service.get_literature_by_id(request.literature_id)
    if not literature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Literature '{request.literature_id}' not found",
        )

    pdf_path = request.pdf_path or literature.source_pdf
    if not pdf_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="pdf_path is required (literature.source_pdf is empty)",
        )

    if not os.path.exists(pdf_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF file not found: {pdf_path}",
        )

    parser = PdfParser(pdf_path)
    parsed_segments = parser.parse(max_pages=request.max_pages)

    def norm_id(value):
        return int(value) if value is not None else 0

    page_map = {
        (norm_id(s.vagga_id), norm_id(s.sutta_id), int(s.paragraph_id)): int(s.page_number)
        for s in parsed_segments
    }

    db = service.db
    db_segments = (
        db.query(Segment)
        .filter(Segment.literature_id == request.literature_id)
        .all()
    )

    matched = 0
    updated = 0
    missing = 0

    for seg in db_segments:
        key = (norm_id(seg.vagga_id), norm_id(seg.sutta_id), int(seg.paragraph_id))
        page_number = page_map.get(key)
        if page_number is None:
            missing += 1
            continue
        matched += 1
        if seg.page_number != page_number:
            seg.page_number = page_number
            updated += 1

    if not request.dry_run:
        db.commit()

    return {
        "status": "success",
        "literature_id": request.literature_id,
        "pdf_path": pdf_path,
        "parsed_segments_count": len(parsed_segments),
        "db_segments_count": len(db_segments),
        "matched": matched,
        "missing": missing,
        "updated": updated,
        "dry_run": request.dry_run,
    }


class UpdateLiteratureRequest(BaseModel):
    """Request schema for updating literature metadata."""
    name: str = None
    pali_name: str = None
    pitaka: str = None
    nikaya: str = None


@router.put("/literature/{literature_id}")
async def update_literature(
    literature_id: str,
    request: UpdateLiteratureRequest,
    service: LiteratureService = Depends(get_literature_service),
    _: bool = Depends(verify_admin_token)
):
    """
    Update literature metadata.
    Requires admin authentication.
    """
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    literature = service.update_literature(literature_id, update_data)
    if not literature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Literature '{literature_id}' not found"
        )

    return {
        "status": "updated",
        "literature_id": literature_id,
        "updated_fields": list(update_data.keys())
    }


@router.delete("/literature/{literature_id}")
async def delete_literature(
    literature_id: str,
    service: LiteratureService = Depends(get_literature_service),
    _: bool = Depends(verify_admin_token)
):
    """
    Delete a literature and all its segments.
    Requires admin authentication.
    """
    success = service.delete_literature(literature_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Literature '{literature_id}' not found"
        )

    return {"status": "deleted", "literature_id": literature_id}
