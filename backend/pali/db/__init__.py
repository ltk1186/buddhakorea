"""Database package."""

from .base import Base
from . import publications  # noqa: F401
from .models import Literature, QueryLog, Segment

__all__ = ["Base", "get_db", "engine", "SessionLocal", "Literature", "Segment", "QueryLog"]


def __getattr__(name: str):
    # Migration metadata must not load API settings or create a sync engine.
    if name in {"get_db", "engine", "SessionLocal"}:
        from . import database

        return getattr(database, name)
    raise AttributeError(name)
