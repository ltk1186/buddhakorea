"""Public reading endpoints, backed exclusively by stored translations."""

# FastAPI dependency defaults are evaluated by the framework.
# ruff: noqa: B008

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.models import Literature, Segment
from ...db.publications import (
    CanonicalSource,
    LiteraturePublication,
    ReleasedTranslation,
    TranslationRelease,
)
from ...schemas.published import PublishedTranslation

router = APIRouter()
DHAMMAPADA_CHAPTER_TITLES = [
    "쌍의 품",
    "방일하지 않음의 품",
    "마음의 품",
    "꽃의 품",
    "어리석은 자의 품",
    "현명한 자의 품",
    "아라한의 품",
    "천의 품",
    "악의 품",
    "폭력의 품",
    "늙음의 품",
    "자기의 품",
    "세상의 품",
    "부처님의 품",
    "행복의 품",
    "사랑하는 것의 품",
    "분노의 품",
    "때의 품",
    "법에 머무는 자의 품",
    "길의 품",
    "여러 가지의 품",
    "지옥의 품",
    "코끼리의 품",
    "갈애의 품",
    "비구의 품",
    "바라문의 품",
]


def current_release(db: Session, literature_id: str, expected: str | None = None):
    row = (
        db.query(Literature, TranslationRelease)
        .join(LiteraturePublication, LiteraturePublication.literature_id == Literature.id)
        .join(TranslationRelease, TranslationRelease.id == LiteraturePublication.release_id)
        .filter(Literature.id == literature_id, Literature.content_type == "canonical")
        .first()
    )
    if not row:
        raise HTTPException(404, "공개된 번역을 찾을 수 없습니다.")
    if expected and row[1].id != expected:
        raise HTTPException(409, "새 번역이 공개되었습니다. 화면을 다시 불러와 주세요.")
    return row


def translated_rows(db: Session, release: TranslationRelease):
    return (
        db.query(CanonicalSource, Segment, ReleasedTranslation)
        .join(Segment, Segment.id == CanonicalSource.segment_id)
        .join(ReleasedTranslation, ReleasedTranslation.source_key == CanonicalSource.stable_key)
        .filter(
            CanonicalSource.literature_id == release.literature_id,
            ReleasedTranslation.release_id == release.id,
            ReleasedTranslation.source_hash == CanonicalSource.source_hash,
        )
    )


@router.get("/{literature_id}/reading")
def book(literature_id: str, response: Response, db: Session = Depends(get_db)):
    literature, release = current_release(db, literature_id)
    is_dhammapada = literature_id == "vri-romn-s0502m-mul"
    chapter_label = "품" if is_dhammapada else "장"
    groups = (
        db.query(
            CanonicalSource.chapter,
            func.count(CanonicalSource.stable_key),
            func.min(CanonicalSource.verse),
            func.max(CanonicalSource.verse),
            func.min(Segment.vagga_name),
            func.count(CanonicalSource.verse),
        )
        .join(Segment, Segment.id == CanonicalSource.segment_id)
        .filter(CanonicalSource.literature_id == literature_id)
        .group_by(CanonicalSource.chapter)
        .order_by(CanonicalSource.chapter.asc().nulls_last())
        .all()
    )
    chapters = [
        {
            "id": chapter or 0,
            "title": (
                "권말 부록"
                if not chapter
                else DHAMMAPADA_CHAPTER_TITLES[chapter - 1]
                if is_dhammapada and 1 <= chapter <= len(DHAMMAPADA_CHAPTER_TITLES)
                else name or f"제{chapter}{chapter_label}"
            ),
            "count": count,
            "first_verse": first,
            "last_verse": last,
        }
        for chapter, count, first, last, name, _ in groups
    ]
    source = (
        db.query(CanonicalSource)
        .filter(CanonicalSource.literature_id == literature_id)
        .order_by(CanonicalSource.sort_order)
        .first()
    )
    metadata = source.source_metadata if source else {}
    source_url = None
    if metadata.get(
        "source_repo"
    ) == "https://github.com/VipassanaTech/tipitaka-xml" and metadata.get("source_path"):
        source_url = (
            "https://github.com/VipassanaTech/tipitaka-xml/blob/"
            f"{quote(release.source_commit, safe='')}/{quote(metadata['source_path'], safe='/')}"
        )
    response.headers["Cache-Control"] = "no-cache"
    return {
        "id": literature.id,
        "title": literature.name,
        "pali_title": literature.pali_name,
        "format": "natural_ko_v2_2",
        "release": release.id,
        "segment_count": release.segment_count,
        "verse_count": sum(group[5] for group in groups),
        "chapter_label": chapter_label,
        "description": (literature.display_metadata or {}).get("description"),
        "chapters": chapters,
        "source_url": source_url,
        "model": release.model,
        "translation_notice": "AI 번역 · 빠알리 원문과 함께 읽을 수 있습니다.",
    }


@router.get("/{literature_id}/reading/segments")
def segments(
    literature_id: str,
    response: Response,
    chapter: int = Query(1, ge=0),
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=200),
    release: str | None = None,
    db: Session = Depends(get_db),
):
    _, current = current_release(db, literature_id, release)
    if (
        not db.query(CanonicalSource.stable_key)
        .filter(
            CanonicalSource.literature_id == literature_id,
            CanonicalSource.chapter == (chapter or None),
        )
        .first()
    ):
        raise HTTPException(404, "해당 목차를 찾을 수 없습니다.")
    rows = (
        translated_rows(db, current)
        .filter(CanonicalSource.chapter == (chapter or None))
        .order_by(CanonicalSource.sort_order)
        .offset(offset)
        .limit(limit + 1)
        .all()
    )
    response.headers["Cache-Control"] = "no-cache"
    return {
        "release": current.id,
        "chapter": chapter,
        "has_more": len(rows) > limit,
        "segments": [
            {
                "key": source.stable_key,
                "chapter": source.chapter or 0,
                "verse": source.verse,
                "kind": source.kind,
                "order": source.sort_order,
                "original_text": segment.original_text,
                "natural_ko": translation.payload["natural_ko"],
            }
            for source, segment, translation in rows[:limit]
        ],
    }


@router.get("/{literature_id}/reading/detail")
def detail(
    literature_id: str,
    key: str,
    response: Response,
    release: str | None = None,
    db: Session = Depends(get_db),
):
    _, current = current_release(db, literature_id, release)
    row = translated_rows(db, current).filter(CanonicalSource.stable_key == key).first()
    if not row:
        raise HTTPException(404, "해당 구간을 찾을 수 없습니다.")
    response.headers["Cache-Control"] = "no-cache"
    return {
        "key": key,
        "release": current.id,
        "translation": PublishedTranslation.model_validate(row[2].payload).model_dump(),
    }


@router.get("/{literature_id}/reading/locate")
def locate(literature_id: str, key: str, response: Response, db: Session = Depends(get_db)):
    _, current = current_release(db, literature_id)
    row = translated_rows(db, current).filter(CanonicalSource.stable_key == key).first()
    if not row:
        raise HTTPException(404, "공유 링크의 구간을 찾을 수 없습니다.")
    response.headers["Cache-Control"] = "no-cache"
    return {"key": key, "chapter": row[0].chapter or 0, "verse": row[0].verse}
