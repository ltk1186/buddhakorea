"""Model metadata without application settings or a database connection."""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
