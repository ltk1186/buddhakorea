import json
import os
import logging
from sqlalchemy.orm import Session
from pali.db.models import Literature, Segment

logger = logging.getLogger(__name__)

def import_summaries(db: Session, json_path: str = "/data/source_data/source_summaries_ko.json"):
    """
    Import literature data from source_summaries_ko.json.
    """
    if not os.path.exists(json_path):
        logger.error(f"JSON file not found: {json_path}")
        return

    logger.info(f"Importing data from {json_path}...")

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        summaries = data.get("summaries", {})
        count = 0

        for t_id, info in summaries.items():
            # Check if literature already exists
            existing = db.query(Literature).filter(Literature.id == t_id).first()
            if existing:
                continue

            # Map T-number to Nikaya/Agama grouping
            # Simple heuristic
            if t_id.startswith("T01"):
                nikaya = "dn" # Digha / Dirgha
            elif t_id.startswith("T02") or t_id.startswith("T26"):
                nikaya = "mn" # Majjhima / Madhyama
            elif t_id.startswith("T99") or t_id.startswith("T02"): # T02 overlaps? T99 is Samyukta
                nikaya = "sn" # Samyutta / Samyukta
            elif t_id.startswith("T125"):
                nikaya = "an" # Anguttara / Ekottarika
            else:
                nikaya = "other"

            # Create Literature
            lit = Literature(
                id=t_id,
                name=info.get("title_ko", t_id),
                pali_name=info.get("original_title", t_id), # Using original Chinese title as 'pali_name'
                pitaka="sutta",
                nikaya=nikaya,
                status="translated",
                display_metadata={
                    "brief_summary": info.get("brief_summary"),
                    "author": info.get("author"),
                    "period": info.get("period")
                }
            )
            db.add(lit)
            db.commit() # Commit to get ID

            # Create Segment (One massive segment for the summary)
            # Since we don't have the full text, we use the detailed summary as the "text"
            segment = Segment(
                literature_id=t_id,
                vagga_id=1,
                sutta_id=1,
                paragraph_id=1,
                original_text=info.get("detailed_summary", "") or "내용 없음",
                translation={"summary": info.get("brief_summary", "")},
                is_translated=True
            )
            db.add(segment)
            count += 1
            
            if count % 100 == 0:
                db.commit()
                logger.info(f"Imported {count} literatures...")

        db.commit()
        logger.info(f"Successfully imported {count} literatures from JSON.")

    except Exception as e:
        logger.error(f"Error importing summaries: {e}")
        db.rollback()
