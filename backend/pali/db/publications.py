"""Versioned translations, separate from the legacy interactive translator."""

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base

json_type = JSON().with_variant(JSONB, "postgresql")


class CanonicalSource(Base):
    __tablename__ = "canonical_sources"
    stable_key = Column(String(160), primary_key=True)
    segment_id = Column(
        Integer, ForeignKey("segments.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    literature_id = Column(
        String(100), ForeignKey("literatures.id", ondelete="CASCADE"), nullable=False
    )
    source_hash = Column(String(64), nullable=False)
    sort_order = Column(Integer, nullable=False)
    chapter = Column(Integer)
    verse = Column(Integer)
    kind = Column(String(20), nullable=False)
    source_metadata = Column(json_type, nullable=False)
    __table_args__ = (
        UniqueConstraint("literature_id", "sort_order", name="uq_canonical_source_order"),
        CheckConstraint("kind IN ('verse', 'passage', 'supplement', 'appendix')", name="ck_source_kind"),
        Index("ix_canonical_chapter", "literature_id", "chapter", "sort_order"),
    )


class TranslationRelease(Base):
    __tablename__ = "translation_releases"
    id = Column(String(100), primary_key=True)
    literature_id = Column(
        String(100), ForeignKey("literatures.id", ondelete="CASCADE"), nullable=False
    )
    artifact_hash = Column(String(64), nullable=False)
    source_commit = Column(String(64), nullable=False)
    model = Column(String(100), nullable=False)
    prompt_version = Column(String(100), nullable=False)
    segment_count = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        UniqueConstraint("id", "literature_id", name="uq_release_literature"),
        Index("ix_translation_release_literature", "literature_id"),
    )


class ReleasedTranslation(Base):
    __tablename__ = "released_translations"
    release_id = Column(
        String(100), ForeignKey("translation_releases.id", ondelete="CASCADE"), primary_key=True
    )
    source_key = Column(
        String(160),
        ForeignKey("canonical_sources.stable_key", ondelete="CASCADE"),
        primary_key=True,
    )
    source_hash = Column(String(64), nullable=False)
    payload = Column(json_type, nullable=False)
    __table_args__ = (Index("ix_released_translation_source", "source_key"),)


class LiteraturePublication(Base):
    __tablename__ = "literature_publications"
    literature_id = Column(
        String(100), ForeignKey("literatures.id", ondelete="CASCADE"), primary_key=True
    )
    release_id = Column(String(100), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(
            ["release_id", "literature_id"],
            ["translation_releases.id", "translation_releases.literature_id"],
        ),
        Index("ix_publication_release", "release_id", "literature_id"),
    )
