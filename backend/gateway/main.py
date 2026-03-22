"""
FastAPI gateway: proxies HTTP to ingestion and analytics microservices.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.common.config import get_settings

logger = logging.getLogger(__name__)

# Headers that must not be copied when proxying (connection semantics / length).
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
    },
)


def _forward_headers_for_proxy(request: Request) -> dict[str, str]:
    """
    Build safe request headers for proxying to the ingestion service.

    Multipart form uploads require the exact ``Content-Type`` value (including the
    ``boundary=`` parameter). Hop-by-hop and ``Content-Length`` are omitted so
    httpx can set length or chunked encoding correctly when streaming.

    Args:
        request (Request): Incoming Starlette request.

    Returns:
        dict[str, str]: Header names to values for the outbound httpx call.
    """
    out: dict[str, str] = {}
    for key, value in request.headers.items():
        lk = key.lower()
        if lk in _HOP_BY_HOP:
            continue
        out[key] = value
    return out

app = FastAPI(
    title="Claude Code Analytics Gateway",
    description="Public API surface for the dashboard and operators.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, Any]:
    """
    Aggregate health from ingestion and analytics when reachable.

    Returns:
        dict[str, Any]: Status map per downstream service.
    """
    settings = get_settings()
    out: dict[str, Any] = {"gateway": "ok", "ingestion": None, "analytics": None}
    timeout = httpx.Timeout(5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.get(f"{settings.ingestion_base_url.rstrip('/')}/health")
            out["ingestion"] = "ok" if r.status_code == 200 else r.status_code
        except httpx.HTTPError as exc:
            logger.warning("Ingestion health check failed: %s", exc)
            out["ingestion"] = "unreachable"
        try:
            r = await client.get(f"{settings.analytics_base_url.rstrip('/')}/health")
            out["analytics"] = "ok" if r.status_code == 200 else r.status_code
        except httpx.HTTPError as exc:
            logger.warning("Analytics health check failed: %s", exc)
            out["analytics"] = "unreachable"
    return out


async def _proxy_get(
    client: httpx.AsyncClient,
    base: str,
    path: str,
    request: Request,
) -> Response:
    """
    Forward an HTTP GET with query string to a downstream service.

    Args:
        client (httpx.AsyncClient): Async HTTP client.
        base (str): Downstream base URL.
        path (str): Path on downstream (e.g. /metrics).
        request (Request): Incoming Starlette request.

    Returns:
        Response: Proxied response body and status.
    """
    url = f"{base.rstrip('/')}{path}"
    params = dict(request.query_params)
    try:
        r = await client.get(url, params=params)
    except httpx.HTTPError as exc:
        logger.error("Proxy GET failed url=%s: %s", url, exc)
        return JSONResponse(
            {"detail": "Downstream service unavailable", "target": url},
            status_code=502,
        )
    return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))


@app.get("/metrics")
async def proxy_metrics(request: Request) -> Response:
    """
    Proxy GET /metrics to the analytics service.

    Args:
        request (Request): Incoming request.

    Returns:
        Response: Analytics JSON response.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        return await _proxy_get(client, settings.analytics_base_url, "/metrics", request)


@app.get("/users")
async def proxy_users(request: Request) -> Response:
    """
    Proxy GET /users to the analytics service.

    Args:
        request (Request): Incoming request.

    Returns:
        Response: Analytics JSON response.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        return await _proxy_get(client, settings.analytics_base_url, "/users", request)


@app.get("/sessions")
async def proxy_sessions(request: Request) -> Response:
    """
    Proxy GET /sessions to the analytics service.

    Args:
        request (Request): Incoming request.

    Returns:
        Response: Analytics JSON response.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        return await _proxy_get(client, settings.analytics_base_url, "/sessions", request)


@app.get("/events/summary")
async def proxy_events_summary(request: Request) -> Response:
    """
    Proxy GET /events/summary to the analytics service.

    Args:
        request (Request): Incoming request.

    Returns:
        Response: Analytics JSON response.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        return await _proxy_get(client, settings.analytics_base_url, "/events/summary", request)


@app.api_route("/ingest/{path:path}", methods=["POST", "PUT"])
async def proxy_ingest(path: str, request: Request) -> Response:
    """
    Proxy ingestion routes under /ingest/* to the ingestion service.

    For ``multipart/form-data`` uploads, forwards the raw body stream and all
    non hop-by-hop headers (preserving ``Content-Type`` with boundary). This
    avoids corrupting multipart boundaries that a naive body copy can cause.

    Args:
        path (str): Remainder path after /ingest/.
        request (Request): Incoming request.

    Returns:
        Response: Ingestion service response.
    """
    settings = get_settings()
    url = f"{settings.ingestion_base_url.rstrip('/')}/ingest/{path}"
    headers = _forward_headers_for_proxy(request)
    ct = request.headers.get("content-type", "")
    if "multipart/form-data" in ct.lower() and "boundary=" not in ct.lower():
        logger.error("Invalid multipart Content-Type (missing boundary): %s", ct[:200])
        return JSONResponse(
            {"detail": "Invalid multipart upload: Content-Type must include a boundary"},
            status_code=400,
        )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
            r = await client.request(
                request.method,
                url,
                content=request.stream(),
                headers=headers,
            )
    except httpx.HTTPError as exc:
        logger.error("Proxy ingest failed url=%s: %s", url, exc)
        return JSONResponse(
            {"detail": "Ingestion service unavailable", "target": url},
            status_code=502,
        )
    return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))


@app.api_route("/process/{path:path}", methods=["POST"])
async def proxy_process(path: str, request: Request) -> Response:
    """
    Proxy /process/* (e.g. session rebuild) to ingestion.

    Uses the same streaming and header rules as ingest so JSON or multipart
    bodies (if any) are forwarded correctly.

    Args:
        path (str): Remainder path after /process/.
        request (Request): Incoming request.

    Returns:
        Response: Ingestion response.
    """
    settings = get_settings()
    url = f"{settings.ingestion_base_url.rstrip('/')}/process/{path}"
    headers = _forward_headers_for_proxy(request)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
            r = await client.request(
                "POST",
                url,
                content=request.stream(),
                headers=headers,
            )
    except httpx.HTTPError as exc:
        logger.error("Proxy process failed url=%s: %s", url, exc)
        return JSONResponse(
            {"detail": "Ingestion service unavailable", "target": url},
            status_code=502,
        )
    return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))
