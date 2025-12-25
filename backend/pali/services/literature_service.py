"""
Literature service for managing Pali literature data.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Integer

from ..db.models import Literature, Segment


class LiteratureService:
    """Service for literature-related database operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_all_literatures(self) -> List[Literature]:
        """Get all literatures."""
        return self.db.query(Literature).order_by(
            Literature.pitaka,
            Literature.nikaya,
            Literature.name
        ).all()

    def get_literature_by_id(self, literature_id: str) -> Optional[Literature]:
        """Get a literature by ID."""
        return self.db.query(Literature).filter(
            Literature.id == literature_id
        ).first()

    def create_literature(self, data: dict) -> Literature:
        """Create a new literature."""
        literature = Literature(**data)
        self.db.add(literature)
        self.db.commit()
        self.db.refresh(literature)
        return literature

    def update_literature(
        self,
        literature_id: str,
        data: dict
    ) -> Optional[Literature]:
        """Update a literature."""
        literature = self.get_literature_by_id(literature_id)
        if not literature:
            return None

        for key, value in data.items():
            setattr(literature, key, value)

        self.db.commit()
        self.db.refresh(literature)
        return literature

    def delete_literature(self, literature_id: str) -> bool:
        """Delete a literature and all its segments."""
        literature = self.get_literature_by_id(literature_id)
        if not literature:
            return False

        self.db.delete(literature)
        self.db.commit()
        return True

    def get_segments(
        self,
        literature_id: str,
        offset: int = 0,
        limit: int = 50,
        vagga_id: Optional[int] = None,
        sutta_id: Optional[int] = None
    ) -> tuple[List[Segment], int]:
        """
        Get segments for a literature with pagination.
        Returns (segments, total_count).
        """
        query = self.db.query(Segment).filter(
            Segment.literature_id == literature_id
        )

        if vagga_id is not None:
            query = query.filter(Segment.vagga_id == vagga_id)

        if sutta_id is not None:
            query = query.filter(Segment.sutta_id == sutta_id)

        total = query.count()

        segments = query.order_by(
            Segment.vagga_id,
            Segment.sutta_id,
            Segment.paragraph_id
        ).offset(offset).limit(limit).all()

        return segments, total

    def get_segment_by_id(
        self,
        literature_id: str,
        segment_id: int
    ) -> Optional[Segment]:
        """Get a specific segment."""
        return self.db.query(Segment).filter(
            Segment.literature_id == literature_id,
            Segment.id == segment_id
        ).first()

    def create_segment(self, data: dict) -> Segment:
        """Create a new segment."""
        segment = Segment(**data)
        self.db.add(segment)
        self.db.commit()
        self.db.refresh(segment)

        # Update literature segment count
        self._update_literature_counts(segment.literature_id)

        return segment

    def create_segments_bulk(self, segments_data: List[dict]) -> int:
        """
        Create multiple segments in bulk.
        Returns the number of segments created.
        """
        segments = [Segment(**data) for data in segments_data]
        self.db.bulk_save_objects(segments)
        self.db.commit()

        # Update literature counts for all affected literatures
        literature_ids = set(data["literature_id"] for data in segments_data)
        for lit_id in literature_ids:
            self._update_literature_counts(lit_id)

        return len(segments)

    def update_segment_translation(
        self,
        segment_id: int,
        translation: dict
    ) -> Optional[Segment]:
        """Update a segment's translation."""
        segment = self.db.query(Segment).filter(
            Segment.id == segment_id
        ).first()

        if not segment:
            return None

        segment.translation = translation
        segment.is_translated = True
        self.db.commit()
        self.db.refresh(segment)

        # Update literature translated count
        self._update_literature_counts(segment.literature_id)

        return segment

    def _update_literature_counts(self, literature_id: str):
        """Update segment counts for a literature."""
        total = self.db.query(Segment).filter(
            Segment.literature_id == literature_id
        ).count()

        translated = self.db.query(Segment).filter(
            Segment.literature_id == literature_id,
            Segment.is_translated == True
        ).count()

        self.db.query(Literature).filter(
            Literature.id == literature_id
        ).update({
            "total_segments": total,
            "translated_segments": translated,
            "status": "translated" if total == translated and total > 0 else "parsed"
        })
        self.db.commit()

    def get_pitaka_structure(self) -> Dict[str, Any]:
        """
        Get the Tripitaka structure for navigation.
        Groups literatures by pitaka and nikaya.
        """
        literatures = self.get_all_literatures()

        structure = {
            "sutta": {},
            "vinaya": [],
            "abhidhamma": []
        }

        for lit in literatures:
            pitaka = lit.pitaka.lower() if lit.pitaka else ""

            # Flexible matching for pitaka names (handles "Sutta Piṭaka", "Sutta", etc.)
            if "sutta" in pitaka:
                nikaya = lit.nikaya or "Other"
                if nikaya not in structure["sutta"]:
                    structure["sutta"][nikaya] = []
                structure["sutta"][nikaya].append(lit.id)
            elif "vinaya" in pitaka:
                structure["vinaya"].append(lit.id)
            elif "abhidhamma" in pitaka:
                structure["abhidhamma"].append(lit.id)

        return structure

    def get_literature_hierarchy(self, literature_id: str) -> List[Dict[str, Any]]:
        """
        Get the hierarchical structure (vaggas -> suttas -> paragraph count) for a literature.
        Returns a nested structure for navigation.
        """
        # Get all distinct vaggas with their names
        vaggas_query = self.db.query(
            Segment.vagga_id,
            Segment.vagga_name,
            func.count(Segment.id).label('segment_count'),
            func.min(Segment.id).label('first_segment_id')
        ).filter(
            Segment.literature_id == literature_id
        ).group_by(
            Segment.vagga_id,
            Segment.vagga_name
        ).order_by(Segment.vagga_id).all()

        hierarchy = []

        for vagga in vaggas_query:
            vagga_data = {
                "vagga_id": vagga.vagga_id,
                "vagga_name": vagga.vagga_name or f"품 {vagga.vagga_id}" if vagga.vagga_id else "기타",
                "segment_count": vagga.segment_count,
                "first_segment_id": vagga.first_segment_id,
                "suttas": []
            }

            # Get suttas within this vagga
            suttas_query = self.db.query(
                Segment.sutta_id,
                Segment.sutta_name,
                func.count(Segment.id).label('segment_count'),
                func.min(Segment.id).label('first_segment_id'),
                func.min(Segment.paragraph_id).label('first_para'),
                func.max(Segment.paragraph_id).label('last_para')
            ).filter(
                Segment.literature_id == literature_id,
                Segment.vagga_id == vagga.vagga_id
            ).group_by(
                Segment.sutta_id,
                Segment.sutta_name
            ).order_by(Segment.sutta_id).all()

            for sutta in suttas_query:
                sutta_data = {
                    "sutta_id": sutta.sutta_id,
                    "sutta_name": sutta.sutta_name or f"경 {sutta.sutta_id}" if sutta.sutta_id else "기타",
                    "segment_count": sutta.segment_count,
                    "first_segment_id": sutta.first_segment_id,
                    "paragraph_range": f"§{sutta.first_para}-{sutta.last_para}" if sutta.first_para != sutta.last_para else f"§{sutta.first_para}"
                }
                vagga_data["suttas"].append(sutta_data)

            hierarchy.append(vagga_data)

        return hierarchy

    def search_segments(
        self,
        query: str,
        literature_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Segment]:
        """
        Search segments by text content.
        Uses PostgreSQL full-text search.
        """
        search_query = self.db.query(Segment).filter(
            Segment.original_text.ilike(f"%{query}%")
        )

        if literature_id:
            search_query = search_query.filter(
                Segment.literature_id == literature_id
            )

        return search_query.limit(limit).all()

    def search_segments_with_stats(
        self,
        query: str,
        literature_id: str,
        limit: int = 50,
        page_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Search segments with useful summary stats.

        Returns:
            {
              "segments": List[Segment],
              "returned_count": int,
              "hit_segments_count": int,
              "total_occurrences": int,
              "pages": List[{"page_number": int, "occurrences": int}],
              "unknown_page_occurrences": int,
            }
        """
        query = query.strip()

        def escape_like(value: str) -> str:
            return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

        escaped = escape_like(query)
        pattern = f"%{escaped}%"

        base_filters = [
            Segment.literature_id == literature_id,
            Segment.original_text.ilike(pattern, escape="\\"),
        ]

        lower_text = func.lower(Segment.original_text)
        lower_query = query.lower()
        query_len = max(1, len(lower_query))

        occurrences_expr = cast(
            (func.length(lower_text) - func.length(func.replace(lower_text, lower_query, "")))
            / query_len,
            Integer,
        )

        hit_segments_count = (
            self.db.query(func.count(Segment.id))
            .filter(*base_filters)
            .scalar()
            or 0
        )

        total_occurrences = (
            self.db.query(func.coalesce(func.sum(occurrences_expr), 0))
            .filter(*base_filters)
            .scalar()
            or 0
        )

        pages_rows = (
            self.db.query(
                Segment.page_number.label("page_number"),
                func.coalesce(func.sum(occurrences_expr), 0).label("occurrences"),
            )
            .filter(*base_filters, Segment.page_number.isnot(None))
            .group_by(Segment.page_number)
            .order_by(Segment.page_number)
            .all()
        )

        pages = [
            {"page_number": int(row.page_number), "occurrences": int(row.occurrences)}
            for row in pages_rows
            if row.page_number is not None
        ]

        unknown_page_occurrences = (
            self.db.query(func.coalesce(func.sum(occurrences_expr), 0))
            .filter(*base_filters, Segment.page_number.is_(None))
            .scalar()
            or 0
        )

        result_filters = list(base_filters)
        if page_number is not None:
            if page_number == 0:
                result_filters.append(Segment.page_number.is_(None))
            else:
                result_filters.append(Segment.page_number == page_number)

        segments = (
            self.db.query(Segment)
            .filter(*result_filters)
            .order_by(Segment.vagga_id, Segment.sutta_id, Segment.paragraph_id)
            .limit(limit)
            .all()
        )

        return {
            "segments": segments,
            "returned_count": len(segments),
            "hit_segments_count": int(hit_segments_count),
            "total_occurrences": int(total_occurrences),
            "pages": pages,
            "unknown_page_occurrences": int(unknown_page_occurrences),
        }
