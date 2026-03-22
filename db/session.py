"""
SQLAlchemy engine and session factory.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.common.config import get_settings
from backend.common.exceptions import AppException

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine():
    """
    Lazily create and return the SQLAlchemy engine.

    Returns:
        sqlalchemy.Engine: Bound engine for the configured DATABASE_URL.

    Raises:
        sqlalchemy.exc.ArgumentError: If the database URL is invalid.
    """
    global _engine
    if _engine is None:
        url = get_settings().database_url
        logger.info("Creating database engine for configured DATABASE_URL host")
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """
    Return a session factory bound to the shared engine.

    Returns:
        sessionmaker: Factory producing new Session instances.
    """
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _SessionLocal


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Provide a transactional scope around a series of operations.

    Yields:
        Session: SQLAlchemy session.

    Raises:
        Exception: Re-raised after rollback on failure.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except (SQLAlchemyError, AppException, OSError, ValueError) as exc:
        logger.error("Session rollback due to exception: %s", exc, exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session.

    Yields:
        Session: Request-scoped SQLAlchemy session.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except (SQLAlchemyError, AppException, OSError, ValueError) as exc:
        logger.error("Request-scoped session rollback: %s", exc, exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()
