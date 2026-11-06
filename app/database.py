"""Database engine, session dependency, and SQLite hardening.

Changes vs. the original:
- ``echo=True`` removed (prevents SQL leakage in production).
- ``PRAGMA journal_mode = WAL`` for safer concurrent reads.
- ``PRAGMA foreign_keys = ON`` to enforce FK / CASCADE constraints.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Enable WAL journal mode and foreign-key enforcement on every connect."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
