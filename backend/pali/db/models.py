"""
SQLAlchemy ORM models for the Pali Translator database.
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Text, Boolean, ForeignKey,
    DateTime, Index, UniqueConstraint, JSON, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .database import Base


class Literature(Base):
    """
    Represents a Pali literature (commentary text).
    Each literature contains multiple segments.
    """
    __tablename__ = "literatures"

    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)  # Korean name
    pali_name = Column(String(255), nullable=False)  # Pali name
    pitaka = Column(String(50), nullable=False)  # Sutta, Vinaya, Abhidhamma
    nikaya = Column(String(100))  # Dighanikaya, Majjhimanikaya, etc.
    status = Column(String(20), default="parsed")  # translated | parsed
    total_segments = Column(Integer, default=0)
    translated_segments = Column(Integer, default=0)
    source_pdf = Column(String(255))
    hierarchy_labels = Column(JSON().with_variant(JSONB, "postgresql"))  # {"level_1": "vagga", "level_2": "sutta"}
    display_metadata = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        # Keep this default cross-dialect for tests (SQLite) while still working on Postgres JSONB.
        server_default=text("'{}'"),
    )  # {"ko_translit": "...", "abbr": "...", "aliases": [...]}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    segments = relationship(
        "Segment",
        back_populates="literature",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    def __repr__(self):
        return f"<Literature(id={self.id}, name={self.name})>"


class Segment(Base):
    """
    Represents a text segment (paragraph) within a literature.
    Contains original Pali text and optional translation.
    """
    __tablename__ = "segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    literature_id = Column(
        String(100),
        ForeignKey("literatures.id", ondelete="CASCADE"),
        nullable=False
    )
    vagga_id = Column(Integer)
    vagga_name = Column(String(255))
    sutta_id = Column(Integer)
    sutta_name = Column(String(255))
    page_number = Column(Integer)
    paragraph_id = Column(Integer, nullable=False)
    original_text = Column(Text, nullable=False)
    translation = Column(JSON().with_variant(JSONB, "postgresql"))  # {sentences: [...], summary: "..."}
    is_translated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    literature = relationship("Literature", back_populates="segments")

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint(
            "literature_id", "vagga_id", "sutta_id", "paragraph_id",
            name="uq_segment_location"
        ),
        Index("idx_segments_literature", "literature_id"),
        Index("idx_segments_location", "literature_id", "vagga_id", "sutta_id"),
        Index("idx_segments_page", "literature_id", "page_number"),
        Index("idx_segments_translated", "is_translated"),
    )

    def __repr__(self):
        return f"<Segment(id={self.id}, literature={self.literature_id}, para={self.paragraph_id})>"


class QueryLog(Base):
    """
    Logs user queries for analytics and debugging.
    """
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100))
    literature_id = Column(
        String(100),
        ForeignKey("literatures.id", ondelete="SET NULL"),
        nullable=True
    )
    segment_id = Column(Integer, nullable=True)
    question = Column(Text, nullable=False)
    answer = Column(Text)
    model = Column(String(50))
    tokens_used = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_query_logs_session", "session_id"),
        Index("idx_query_logs_created", "created_at"),
    )

    def __repr__(self):
        return f"<QueryLog(id={self.id}, session={self.session_id})>"
