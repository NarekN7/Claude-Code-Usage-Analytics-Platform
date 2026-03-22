"""
Gateway tests: mock downstream services with respx (no real ingestion/analytics).
"""

from __future__ import annotations

import httpx
import respx
from fastapi.testclient import TestClient

from backend.gateway.main import app


@respx.mock
def test_gateway_health_aggregates_downstream() -> None:
    """
    GET /health calls ingestion and analytics /health and returns gateway + statuses.

    Returns:
        None
    """
    respx.get("http://localhost:8001/health").mock(
        return_value=httpx.Response(200, json={"status": "ok", "service": "ingestion"})
    )
    respx.get("http://localhost:8002/health").mock(
        return_value=httpx.Response(200, json={"status": "ok", "service": "analytics"})
    )
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["gateway"] == "ok"
    assert body["ingestion"] == "ok"
    assert body["analytics"] == "ok"


@respx.mock
def test_gateway_proxy_metrics_forwards_query_params() -> None:
    """
    GET /metrics forwards query string to analytics.

    Returns:
        None
    """
    respx.get("http://localhost:8002/metrics").mock(
        return_value=httpx.Response(200, json={"totals": {"total_events": 1}})
    )
    client = TestClient(app)
    r = client.get("/metrics", params={"practice": "Data Engineering"})
    assert r.status_code == 200
    assert r.json()["totals"]["total_events"] == 1
    assert len(respx.calls) >= 1
    assert respx.calls[0].request.url.params.get("practice") == "Data Engineering"


@respx.mock
def test_gateway_proxy_ingest_post() -> None:
    """
    POST /ingest/telemetry/jsonl forwards body to ingestion service.

    Returns:
        None
    """
    respx.post("http://localhost:8001/ingest/telemetry/jsonl").mock(
        return_value=httpx.Response(
            200,
            json={"lines_read": 1, "rows_attempted": 1, "parse_errors": 0},
        )
    )
    client = TestClient(app)
    files = {"file": ("x.jsonl", b'{"logEvents":[]}\n', "application/octet-stream")}
    r = client.post("/ingest/telemetry/jsonl", files=files)
    assert r.status_code == 200
    assert r.json()["lines_read"] == 1


@respx.mock
def test_gateway_proxy_users() -> None:
    """
    GET /users forwards to analytics.

    Returns:
        None
    """
    respx.get("http://localhost:8002/users").mock(
        return_value=httpx.Response(200, json={"top_users": []})
    )
    client = TestClient(app)
    r = client.get("/users")
    assert r.status_code == 200
    assert r.json()["top_users"] == []


@respx.mock
def test_gateway_proxy_sessions_endpoint() -> None:
    """
    GET /sessions forwards to analytics.

    Returns:
        None
    """
    respx.get("http://localhost:8002/sessions").mock(
        return_value=httpx.Response(200, json={"sessions_by_day": []})
    )
    client = TestClient(app)
    r = client.get("/sessions")
    assert r.status_code == 200
    assert r.json()["sessions_by_day"] == []


@respx.mock
def test_gateway_proxy_events_summary() -> None:
    """
    GET /events/summary forwards to analytics.

    Returns:
        None
    """
    respx.get("http://localhost:8002/events/summary").mock(
        return_value=httpx.Response(200, json={"event_type_distribution": []})
    )
    client = TestClient(app)
    r = client.get("/events/summary")
    assert r.status_code == 200
    assert r.json()["event_type_distribution"] == []


@respx.mock
def test_gateway_proxy_process_sessions() -> None:
    """
    POST /process/sessions forwards to ingestion.

    Returns:
        None
    """
    respx.post("http://localhost:8001/process/sessions").mock(
        return_value=httpx.Response(200, json={"sessions_rebuilt": 3})
    )
    client = TestClient(app)
    r = client.post("/process/sessions")
    assert r.status_code == 200
    assert r.json()["sessions_rebuilt"] == 3
