"""
Integration tests against PostgreSQL (skipped when DATABASE_URL / TEST_DATABASE_URL unset).

Run: export DATABASE_URL=postgresql+psycopg2://analytics:analytics@127.0.0.1:5432/analytics
     pytest tests/test_integration_postgres.py -v
"""

from __future__ import annotations

import json
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.analytics.main import app as analytics_app
from backend.analytics.queries import AnalyticsFilters, query_totals
from backend.ingestion.main import app as ingestion_app
from db.session import get_db_session
from scripts.etl.load_employees import load_employees_from_csv
from scripts.etl.load_events import insert_events_batch
from scripts.etl.schemas import NormalizedEvent

pytestmark = pytest.mark.integration


def _session_override_with_commit(session: Session):
    """
    Mimic production get_db_session: yield then commit (or rollback on error).

    Args:
        session (Session): Request-scoped session.

    Returns:
        Callable: Dependency generator function for FastAPI.
    """

    def _override() -> Generator[Session, None, None]:
        try:
            yield session
            session.commit()
        except Exception:  # noqa: BLE001 — mirror production DB dependency teardown in tests
            session.rollback()
            raise

    return _override


@pytest.fixture
def analytics_client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    FastAPI TestClient for analytics with DB session override.

    Args:
        db_session (Session): Shared PostgreSQL session.

    Yields:
        TestClient: Client bound to analytics app.
    """
    analytics_app.dependency_overrides[get_db_session] = _session_override_with_commit(db_session)
    client = TestClient(analytics_app)
    yield client
    analytics_app.dependency_overrides.clear()


@pytest.fixture
def ingestion_client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    FastAPI TestClient for ingestion with DB session override.

    Args:
        db_session (Session): Shared PostgreSQL session.

    Yields:
        TestClient: Client bound to ingestion app.
    """
    ingestion_app.dependency_overrides[get_db_session] = _session_override_with_commit(db_session)
    client = TestClient(ingestion_app)
    yield client
    ingestion_app.dependency_overrides.clear()


def _write_temp_csv(path: Path, content: str) -> None:
    """
    Write CSV content to path.

    Args:
        path (Path): Destination file.
        content (str): UTF-8 CSV text.

    Returns:
        None
    """
    path.write_text(content, encoding="utf-8")


def test_analytics_users_sessions_events_summary_empty_db(analytics_client: TestClient) -> None:
    """
    GET /users, /sessions, /events/summary return 200 with filters envelope on empty DB.

    Args:
        analytics_client (TestClient): Analytics HTTP client.

    Returns:
        None
    """
    for path in ("/users", "/sessions", "/events/summary"):
        r = analytics_client.get(path)
        assert r.status_code == 200, path
        body = r.json()
        assert "filters" in body
        assert body["filters"]["practice"] is None


def test_ingest_employees_csv_multipart(ingestion_client: TestClient) -> None:
    """
    POST /ingest/employees/csv accepts multipart CSV and upserts rows.

    Args:
        ingestion_client (TestClient): Ingestion HTTP client.

    Returns:
        None
    """
    csv_body = (
        "email,full_name,practice,level,location\n"
        "csv-upload@example.com,CSV User,Platform Engineering,L4,Germany\n"
    )
    files = {"file": ("employees.csv", csv_body.encode("utf-8"), "text/csv")}
    r = ingestion_client.post("/ingest/employees/csv", files=files)
    assert r.status_code == 200
    data = r.json()
    assert data["rows_processed"] == 1
    assert "filename" in data


def test_query_totals_empty(db_session: Session) -> None:
    """
    query_totals returns zeros when tables are empty.

    Args:
        db_session (Session): Database session.

    Returns:
        None
    """
    out = query_totals(db_session, AnalyticsFilters())
    assert out.get("total_events", 0) == 0


def test_load_employees_and_event_then_metrics(
    db_session: Session,
    analytics_client: TestClient,
    tmp_path: Path,
) -> None:
    """
    Load one employee and one event; GET /metrics shows non-zero events.

    Args:
        db_session (Session): Database session.
        analytics_client (TestClient): Analytics HTTP client.
        tmp_path (Path): Pytest temp directory.

    Returns:
        None
    """
    csv_path = tmp_path / "employees.csv"
    _write_temp_csv(
        csv_path,
        "email,full_name,practice,level,location\n"
        "a@example.com,Alice,Data Engineering,L5,United States\n",
    )
    load_employees_from_csv(db_session, csv_path)
    db_session.commit()

    ev = NormalizedEvent(
        event_id="evt-1",
        timestamp=datetime(2025, 12, 3, 12, 0, 0, tzinfo=timezone.utc),
        event_type="claude_code.api_request",
        session_id="sess-1",
        user_email="a@example.com",
        model="claude-haiku-4-5-20251001",
        input_tokens=5,
        output_tokens=5,
        total_tokens=10,
        attributes={"session.id": "sess-1"},
        scope={},
        resource={},
    )
    insert_events_batch(db_session, [ev])
    db_session.commit()

    r = analytics_client.get("/metrics")
    assert r.status_code == 200
    totals = r.json()["totals"]
    assert totals["total_events"] >= 1
    assert totals["total_tokens"] >= 10


def test_sessionization_rebuild(
    db_session: Session,
    ingestion_client: TestClient,
    tmp_path: Path,
) -> None:
    """
    After events exist, POST /process/sessions creates session rows.

    Args:
        db_session (Session): Database session.
        ingestion_client (TestClient): Ingestion HTTP client.
        tmp_path (Path): Pytest temp directory.

    Returns:
        None
    """
    csv_path = tmp_path / "employees.csv"
    _write_temp_csv(
        csv_path,
        "email,full_name,practice,level,location\n"
        "b@example.com,Bob,Backend Engineering,L3,Poland\n",
    )
    load_employees_from_csv(db_session, csv_path)
    ev = NormalizedEvent(
        event_id="evt-2",
        timestamp=datetime(2025, 12, 4, 12, 0, 0, tzinfo=timezone.utc),
        event_type="claude_code.api_request",
        session_id="sess-2",
        user_email="b@example.com",
        model="claude-opus-4-6",
        input_tokens=1,
        output_tokens=2,
        total_tokens=3,
        attributes={},
        scope={},
        resource={},
    )
    insert_events_batch(db_session, [ev])
    db_session.commit()

    r = ingestion_client.post("/process/sessions")
    assert r.status_code == 200
    assert r.json()["sessions_rebuilt"] >= 1

    n = db_session.execute(text("SELECT COUNT(*) FROM sessions WHERE session_id = 'sess-2'")).scalar_one()
    assert n == 1


def test_ingest_jsonl_multipart(ingestion_client: TestClient) -> None:
    """
    POST /ingest/telemetry/jsonl accepts multipart file and inserts rows.

    Args:
        ingestion_client (TestClient): Ingestion HTTP client.

    Returns:
        None
    """
    inner = {
        "body": "claude_code.user_prompt",
        "attributes": {
            "event.timestamp": "2025-12-03T00:06:00.000Z",
            "session.id": "678c4a9e-4362-404e-89c7-1c8abb91226c",
            "user.email": "ingest@example.com",
        },
        "scope": {},
        "resource": {},
    }
    line = json.dumps(
        {
            "logEvents": [
                {
                    "id": "99",
                    "timestamp": 1764720360000,
                    "message": json.dumps(inner),
                }
            ]
        }
    )
    files = {"file": ("t.jsonl", line.encode("utf-8"), "application/octet-stream")}
    r = ingestion_client.post("/ingest/telemetry/jsonl", files=files)
    assert r.status_code == 200
    data = r.json()
    assert data["lines_read"] == 1
    assert data["rows_attempted"] >= 1
