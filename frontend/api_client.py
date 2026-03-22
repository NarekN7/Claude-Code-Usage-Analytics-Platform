"""
HTTP client for the public gateway (no direct database access).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from backend.common.config import get_settings

logger = logging.getLogger(__name__)


def gateway_base_url() -> str:
    """
    Resolve the gateway base URL from environment or settings.

    Returns:
        str: Base URL without trailing slash.
    """
    return os.environ.get("PUBLIC_GATEWAY_URL", get_settings().public_gateway_url).rstrip("/")


def fetch_json(
    path: str,
    params: dict[str, Any] | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """
    GET a JSON document from the gateway.

    Args:
        path (str): Path beginning with ``/`` (e.g. ``/metrics``).
        params (dict[str, Any] | None): Optional query parameters.
        timeout (float): Request timeout in seconds.

    Returns:
        dict[str, Any]: Parsed JSON object.

    Raises:
        httpx.HTTPStatusError: If the response status is not successful.
        httpx.RequestError: On network failure.
    """
    url = f"{gateway_base_url()}{path}"
    logger.info("GET %s params=%s", url, params)
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url, params=params or {})
        response.raise_for_status()
        return response.json()
