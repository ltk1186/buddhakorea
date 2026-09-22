"""
Database connection and session management.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from ..config import settings
from .base import Base

# Create SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create SQLite test tables; PostgreSQL must be provisioned by Alembic."""
    from . import models  # noqa: F401

    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
        return

    inspector = inspect(engine)
    missing = []
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            missing.append(table.name)
            continue
        columns = {column["name"] for column in inspector.get_columns(table.name)}
        missing.extend(
            f"{table.name}.{column.name}" for column in table.columns if column.name not in columns
        )
    if missing:
        raise RuntimeError(
            "Pali database schema is missing: "
            + ", ".join(missing)
            + ". Run the environment's Alembic upgrade head before starting the backend."
        )


def get_db() -> Generator:
    """
    Dependency that provides a database session.
    Ensures proper cleanup after request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
