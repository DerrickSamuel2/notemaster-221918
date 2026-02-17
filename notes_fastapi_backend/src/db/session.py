import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _get_database_url() -> str:
    """Resolve DATABASE_URL from environment.

    We intentionally keep this private to ensure all callers go through
    the same logic (and to make it easy to improve validation later).
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is required (e.g. postgresql+psycopg2://user:pass@host:5432/dbname)."
        )
    return database_url


# SQLAlchemy engine & session factory
engine = create_engine(
    _get_database_url(),
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a SQLAlchemy session.

    Yields:
        Session: SQLAlchemy session; always closed after request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
