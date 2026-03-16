"""Shared test fixtures — schema-aware SQLite for testing."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base

SCHEMA = "stock_radar"


@pytest.fixture
def db_engine():
    """In-memory SQLite engine with schema translation.

    SQLite doesn't support schemas, so we translate 'stock_radar.X' → 'X'.
    """
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute(f"ATTACH DATABASE ':memory:' AS \"{SCHEMA}\"")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db(db_engine) -> Session:
    """Yields a single SQLite session for tests that need one."""
    session = sessionmaker(bind=db_engine)()
    yield session
    session.close()


@pytest.fixture
def db_session_factory(db_engine):
    """Returns a session factory for tests that need to create multiple sessions."""
    return sessionmaker(bind=db_engine)
