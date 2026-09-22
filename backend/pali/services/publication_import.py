"""Validate and atomically import completed artifacts. No model clients."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import Literature, Segment
from ..db.publications import (
    CanonicalSource,
    LiteraturePublication,
    ReleasedTranslation,
    TranslationRelease,
)
from ..schemas.published import PublishedTranslation

LITERATURE_ID = "vri-romn-s0502m-mul"
SOURCE_COMMIT = "49bc86914748589a2501b548cc6b3e97a8abe018"
RELEASE_ID = "dhp-ko-20260907-v22"
CHAPTER_ENDS = [
    20,
    32,
    43,
    59,
    75,
    89,
    99,
    115,
    128,
    145,
    156,
    166,
    178,
    196,
    208,
    220,
    234,
    255,
    272,
    289,
    305,
    319,
    333,
    359,
    382,
    423,
]


@dataclass(frozen=True)
class Artifact:
    digest: str
    summary: dict
    items: list[dict]
    literature: dict | None = None
    locations: dict | None = None


def location(source: dict) -> tuple[int | None, int | None, str]:
    match = re.fullmatch(r"kn2_(\d+):(\d+)", source["canonical_ref"])
    if match:
        # The source XML reuses kn2_2 for chapter 9. Use the parsed heading
        # position and verified verse ranges, never the XML div ID as chapter.
        verse = int(match.group(2))
        chapter = source["vagga_id"]
        expected_chapter = next((i + 1 for i, end in enumerate(CHAPTER_ENDS) if verse <= end), None)
        if chapter != expected_chapter or int(source["paragraph_number"]) != verse:
            raise ValueError("Source chapter/verse mismatch")
        return chapter, verse, "verse"
    return source["vagga_id"], None, "supplement" if source["vagga_id"] else "appendix"


def validate_artifact(path: Path) -> Artifact:
    raw = path.read_bytes()
    data = json.loads(raw)
    items, summary = data["items"], data["summary"]
    if len(items) != 438 or summary["count"] != 438:
        raise ValueError("Expected all 438 translated XML segments")
    if summary["source_commit"] != SOURCE_COMMIT:
        raise ValueError("Unexpected source edition")
    keys, orders, verses, chapters = set(), set(), set(), set()
    for item in items:
        source, result = item["source"], item["result"]
        key = source["stable_segment_key"]
        if key in keys or source["sort_order"] in orders:
            raise ValueError("Duplicate source key or order")
        keys.add(key)
        orders.add(source["sort_order"])
        if source["literature_id"] != LITERATURE_ID or source["source_commit"] != SOURCE_COMMIT:
            raise ValueError("Artifact mixes literature or source editions")
        digest = hashlib.sha256(source["normalized_text"].encode()).hexdigest()
        if (
            digest != source["source_text_hash"]
            or source["original_text"] != source["normalized_text"]
        ):
            raise ValueError("Source text hash mismatch")
        if result["stable_segment_key"] != key or result["source_text_hash"] != digest:
            raise ValueError("Translation/source pairing mismatch")
        if result["status"] != "succeeded" or result["schema_valid"] is not True:
            raise ValueError("Artifact contains unsuccessful translations")
        PublishedTranslation.model_validate(result["parsed_translation_json"])
        chapter, verse, _ = location(source)
        if verse is not None:
            if verse in verses:
                raise ValueError("Duplicate canonical verse")
            verses.add(verse)
            chapters.add(chapter)
    if (
        orders != set(range(1, 439))
        or verses != set(range(1, 424))
        or chapters != set(range(1, 27))
    ):
        raise ValueError("Incomplete chapter, verse, or source order coverage")
    return Artifact(
        hashlib.sha256(raw).hexdigest(),
        summary,
        sorted(items, key=lambda i: i["source"]["sort_order"]),
    )


def import_release(db: Session, artifact: Artifact, release_id: str) -> dict:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", release_id):
        raise ValueError("Invalid release ID")
    metadata = artifact.literature or {
        "id": LITERATURE_ID,
        "name": "법구경",
        "pali_name": "Dhammapadapāḷi",
        "pitaka": "sutta",
        "nikaya": "Khuddakanikāye",
        "display_metadata": {"description": "빠알리 원전에서 옮긴 법구경 본문"},
    }
    literature_id = metadata["id"]
    expected_count = len(artifact.items)
    # Serialize imports and publication changes for this literature on PostgreSQL.
    if db.bind.dialect.name == "postgresql":
        db.execute(select(func.pg_advisory_xact_lock(func.hashtext(literature_id))))
    release = db.get(TranslationRelease, release_id)
    if release:
        if release.artifact_hash != artifact.digest or release.literature_id != literature_id:
            raise ValueError("Release ID already belongs to a different artifact")
        count = db.query(ReleasedTranslation).filter_by(release_id=release_id).count()
        if count != expected_count:
            raise ValueError("Existing release is incomplete")
        return {
            "status": "unchanged",
            "release_id": release_id,
            "count": count,
            "artifact_hash": artifact.digest,
        }
    literature = db.get(Literature, literature_id)
    if literature and literature.content_type != "canonical":
        raise ValueError("Cannot replace a legacy literature")
    if not literature:
        literature = Literature(
            **metadata,
            content_type="canonical",
            status="translated",
            total_segments=expected_count,
            translated_segments=expected_count,
        )
        db.add(literature)
        db.flush()
    release = TranslationRelease(
        id=release_id,
        literature_id=literature_id,
        artifact_hash=artifact.digest,
        source_commit=artifact.summary["source_commit"],
        model=artifact.summary["model"],
        prompt_version=artifact.summary["prompt_version"],
        segment_count=expected_count,
    )
    db.add(release)
    db.flush()
    existing_sources = {
        row.stable_key: row
        for row in db.query(CanonicalSource).filter_by(literature_id=literature_id)
    }
    incoming_keys = {item["source"]["stable_segment_key"] for item in artifact.items}
    if existing_sources and set(existing_sources) != incoming_keys:
        raise ValueError(
            "New releases must preserve the complete source set; use a new literature ID for a new edition"
        )
    for item in artifact.items:
        src, result = item["source"], item["result"]
        key = src["stable_segment_key"]
        existing = existing_sources.get(key)
        if existing:
            position = artifact.locations[key] if artifact.locations is not None else location(src)
            if (
                existing.source_hash != src["source_text_hash"]
                or existing.source_metadata != src
                or (existing.chapter, existing.verse, existing.kind) != position
            ):
                raise ValueError("Existing source identity has changed; use a new source edition")
        else:
            chapter, verse, kind = (
                artifact.locations[key] if artifact.locations is not None else location(src)
            )
            segment = Segment(
                literature_id=literature_id,
                vagga_id=chapter,
                vagga_name=src["vagga_name"],
                paragraph_id=src["sort_order"],
                original_text=src["original_text"],
                is_translated=True,
            )
            db.add(segment)
            db.flush()
            db.add(
                CanonicalSource(
                    stable_key=key,
                    segment_id=segment.id,
                    literature_id=literature_id,
                    source_hash=src["source_text_hash"],
                    sort_order=src["sort_order"],
                    chapter=chapter,
                    verse=verse,
                    kind=kind,
                    source_metadata=src,
                )
            )
            db.flush()
        db.add(
            ReleasedTranslation(
                release_id=release_id,
                source_key=key,
                source_hash=src["source_text_hash"],
                payload=result["parsed_translation_json"],
            )
        )
    db.flush()
    return {
        "status": "imported",
        "release_id": release_id,
        "count": expected_count,
        "artifact_hash": artifact.digest,
    }


def publish_release(db: Session, release_id: str) -> dict:
    release = db.get(TranslationRelease, release_id)
    if not release:
        raise ValueError("Release not found")
    if db.bind.dialect.name == "postgresql":
        db.execute(select(func.pg_advisory_xact_lock(func.hashtext(release.literature_id))))
    count = (
        db.query(ReleasedTranslation)
        .join(CanonicalSource, CanonicalSource.stable_key == ReleasedTranslation.source_key)
        .filter(
            ReleasedTranslation.release_id == release_id,
            CanonicalSource.literature_id == release.literature_id,
            CanonicalSource.source_hash == ReleasedTranslation.source_hash,
        )
        .count()
    )
    if count != release.segment_count:
        raise ValueError("Release is incomplete or source hashes do not match")
    publication = db.get(LiteraturePublication, release.literature_id)
    if publication:
        publication.release_id = release_id
        publication.published_at = datetime.now(timezone.utc)
    else:
        db.add(LiteraturePublication(literature_id=release.literature_id, release_id=release_id))
    db.flush()
    return {"status": "published", "release_id": release_id, "count": count}
