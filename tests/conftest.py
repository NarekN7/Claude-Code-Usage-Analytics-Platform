"""
Shared pytest fixtures: optional PostgreSQL integration, dependency overrides.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Optional

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _postgres_url() -> Optional[str]:
    """
    Resolve PostgreSQL URL for integration tests.

    Returns:
        Optional[str]: URL if set, else None.
    """
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


@pytest.fixture(scope="session")
def postgres_engine() -> Generator[Engine, None, None]:
    """
    Create an engine and apply Alembic migrations once (integration only).

    Yields:
        Engine: SQLAlchemy engine connected to PostgreSQL.

    Raises:
        pytest.skip: If no PostgreSQL URL is set or connection fails.
    """
    url = _postgres_url()
    if not url or "postgresql" not in url:
        pytest.skip("Set TEST_DATABASE_URL or DATABASE_URL to a PostgreSQL URL for integration tests")

    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OSError as exc:
        pytest.skip(f"Cannot connect to PostgreSQL: {exc}")

    env = os.environ.copy()
    env["DATABASE_URL"] = url
    env["PYTHONPATH"] = str(_REPO_ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"alembic upgrade failed: {result.stderr}\n{result.stdout}")

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(postgres_engine: Engine) -> Generator[Session, None, None]:
    """
    Provide a session with empty tables (truncate before each test).

    Args:
        postgres_engine (Engine): Shared test engine.

    Yields:
        Session: SQLAlchemy session.
    """
    factory = sessionmaker(bind=postgres_engine)
    session = factory()
    truncate_all(session)
    try:
        yield session
    finally:
        session.close()


def truncate_all(session: Session) -> None:
    """
    Remove all rows from application tables (integration helper).

    Args:
        session (Session): Active session.

    Returns:
        None
    """
    session.execute(
        text(
            "TRUNCATE TABLE sessions, events, employees, ingestion_checkpoints "
            "RESTART IDENTITY CASCADE"
        )
    )
    session.commit()
