"""
Health endpoints (no database required).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.analytics.main import app as analytics_app
from backend.ingestion.main import app as ingestion_app


def test_analytics_health() -> None:
    """
    GET /health on analytics returns ok.

    Returns:
        None
    """
    client = TestClient(analytics_app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["service"] == "analytics"


def test_ingestion_health() -> None:
    """
    GET /health on ingestion returns ok.

    Returns:
        None
    """
    client = TestClient(ingestion_app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["service"] == "ingestion"
