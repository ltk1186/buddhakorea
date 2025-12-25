"""
Translation API with SSE streaming and DPD hints.
"""
import json
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.models import Segment
from ..deps import get_literature_service, get_gemini_client
from ...services.literature_service import LiteratureService
from ...services.gemini_client import GeminiClient
from ...services.hint_generator import HintGenerator, get_hint_generator
from ...schemas.translate import TranslateRequest, BatchTranslateRequest

router = APIRouter()
logger = logging.getLogger(__name__)


async def generate_translation_stream(
    segment: Segment,
    gemini: GeminiClient,
    service: LiteratureService,
    hint_generator: HintGenerator
):
    """
    Generate SSE stream for translation with DPD hints.
    """
    # Send start event
    yield f"event: start\ndata: {json.dumps({'segment_id': segment.id, 'status': 'translating'})}\n\n"

    try:
        # Generate DPD hints
        hints_text = ""
        try:
            segment_hints = hint_generator.generate_hints(
                str(segment.id),
                segment.original_text
            )
            hints_text = hint_generator.format_single_for_prompt(segment_hints)
        except Exception as e:
            logger.warning(f"Failed to generate hints for segment {segment.id}: {e}")
            # Continue without hints

        full_result = None

        async for chunk in gemini.translate_with_hints_stream(
            segment.original_text,
            hints_text
        ):
            if chunk.get("type") == "token":
                yield f"event: token\ndata: {json.dumps({'content': chunk['content']})}\n\n"
            elif chunk.get("type") == "complete":
                full_result = chunk["data"]
                yield f"event: translation\ndata: {json.dumps(full_result)}\n\n"
            elif chunk.get("type") == "error":
                yield f"event: error\ndata: {json.dumps({'error': chunk['error']})}\n\n"
                return

        # Save translation to database
        if full_result:
            service.update_segment_translation(segment.id, full_result)

        # Send done event
        yield f"event: done\ndata: {json.dumps({'segment_id': segment.id, 'status': 'completed'})}\n\n"

    except Exception as e:
        logger.error(f"Translation error for segment {segment.id}: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


async def generate_batch_translation_stream(
    segments: List[Segment],
    gemini: GeminiClient,
    service: LiteratureService,
    hint_generator: HintGenerator
):
    """
    Generate SSE stream for batch translation with DPD hints.
    """
    segment_ids = [seg.id for seg in segments]

    # Send start event
    yield f"event: start\ndata: {json.dumps({'segment_ids': segment_ids, 'status': 'translating'})}\n\n"

    try:
        # Prepare segments for batch processing
        segment_tuples = [(str(seg.id), seg.original_text) for seg in segments]

        # Generate batch DPD hints
        hints_text = ""
        try:
            batch_hints = hint_generator.generate_batch_hints(segment_tuples)
            hints_text = hint_generator.format_for_prompt(batch_hints)
        except Exception as e:
            logger.warning(f"Failed to generate batch hints: {e}")
            # Continue without hints

        completed_segments = []

        async for chunk in gemini.translate_batch_stream(segment_tuples, hints_text):
            event_type = chunk.get("type")

            if event_type == "token":
                yield f"event: token\ndata: {json.dumps({'content': chunk['content']})}\n\n"

            elif event_type == "parse_complete":
                yield f"event: parse_complete\ndata: {json.dumps({'status': 'parsing'})}\n\n"

            elif event_type == "segment_complete":
                seg_id = chunk.get("segment_id")
                translation = chunk.get("translation")

                logger.info(f"segment_complete event: seg_id={seg_id}, has_translation={translation is not None}")

                # Save to database
                if seg_id and translation:
                    try:
                        # Convert string ID back to int
                        int_seg_id = int(seg_id)
                        logger.info(f"Saving translation for segment {int_seg_id}")
                        service.update_segment_translation(int_seg_id, translation)
                        completed_segments.append(int_seg_id)
                        logger.info(f"Successfully saved segment {int_seg_id}")
                    except Exception as e:
                        logger.error(f"Failed to save translation for segment {seg_id}: {e}")
                else:
                    logger.warning(f"Skipping save: seg_id={seg_id}, translation_present={translation is not None}")

                yield f"event: segment_complete\ndata: {json.dumps({'segment_id': seg_id, 'translation': translation})}\n\n"

            elif event_type == "fallback_start":
                yield f"event: fallback_start\ndata: {json.dumps({'reason': chunk.get('reason', 'unknown')})}\n\n"

            elif event_type == "error":
                error_data = {"error": chunk.get("error", "Unknown error")}
                if "segment_id" in chunk:
                    error_data["segment_id"] = chunk["segment_id"]
                yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

        # Send done event
        yield f"event: done\ndata: {json.dumps({'segment_ids': segment_ids, 'completed': completed_segments, 'status': 'completed'})}\n\n"

    except Exception as e:
        logger.error(f"Batch translation error: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


@router.post("")
async def translate_segment(
    request: TranslateRequest,
    db: Session = Depends(get_db),
    service: LiteratureService = Depends(get_literature_service),
    gemini: GeminiClient = Depends(get_gemini_client)
):
    """
    Translate a segment using Gemini AI with DPD hints.
    Returns SSE stream with translation progress.
    """
    # Get the segment
    segment = service.get_segment_by_id(request.literature_id, request.segment_id)

    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment {request.segment_id} not found"
        )

    # Check if already translated (unless force=True)
    if segment.is_translated and not request.force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Segment is already translated. Use force=true to overwrite."
        )

    hint_generator = get_hint_generator()

    return StreamingResponse(
        generate_translation_stream(segment, gemini, service, hint_generator),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/batch")
async def translate_batch(
    request: BatchTranslateRequest,
    db: Session = Depends(get_db),
    service: LiteratureService = Depends(get_literature_service),
    gemini: GeminiClient = Depends(get_gemini_client)
):
    """
    Translate multiple segments in batch using Gemini AI with DPD hints.
    Returns SSE stream with translation progress.

    Max 5 segments per request.
    """
    # Validate and fetch all segments
    segments = []
    already_translated = []

    for seg_id in request.segment_ids:
        segment = service.get_segment_by_id(request.literature_id, seg_id)

        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Segment {seg_id} not found in literature {request.literature_id}"
            )

        if segment.is_translated and not request.force:
            already_translated.append(seg_id)
        else:
            segments.append(segment)

    # If all segments are already translated (without force)
    if already_translated and not segments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"All segments already translated: {already_translated}. Use force=true to overwrite."
        )

    # Warn about skipped segments
    if already_translated:
        logger.info(f"Skipping already translated segments: {already_translated}")

    if not segments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No segments to translate"
        )

    hint_generator = get_hint_generator()

    return StreamingResponse(
        generate_batch_translation_stream(segments, gemini, service, hint_generator),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/sync")
async def translate_segment_sync(
    request: TranslateRequest,
    service: LiteratureService = Depends(get_literature_service),
    gemini: GeminiClient = Depends(get_gemini_client)
):
    """
    Translate a segment synchronously (non-streaming) with DPD hints.
    Useful for batch processing or when SSE is not supported.
    """
    # Get the segment
    segment = service.get_segment_by_id(request.literature_id, request.segment_id)

    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment {request.segment_id} not found"
        )

    # Check if already translated (unless force=True)
    if segment.is_translated and not request.force:
        return {
            "segment_id": segment.id,
            "status": "already_translated",
            "translation": segment.translation
        }

    # Generate DPD hints
    hint_generator = get_hint_generator()
    hints_text = ""
    try:
        segment_hints = hint_generator.generate_hints(
            str(segment.id),
            segment.original_text
        )
        hints_text = hint_generator.format_single_for_prompt(segment_hints)
    except Exception as e:
        logger.warning(f"Failed to generate hints: {e}")

    # Perform translation with hints
    result = await gemini.translate_with_hints(segment.original_text, hints_text)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Translation failed"
        )

    # Save to database
    service.update_segment_translation(segment.id, result)

    return {
        "segment_id": segment.id,
        "status": "completed",
        "translation": result
    }
