"""Read-only content dependencies, independent of Redis and model clients."""

# FastAPI dependency defaults are evaluated by the framework.
# ruff: noqa: B008

from fastapi import Depends
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..services.literature_service import LiteratureService


def get_literature_service(db: Session = Depends(get_db)) -> LiteratureService:
    return LiteratureService(db)
