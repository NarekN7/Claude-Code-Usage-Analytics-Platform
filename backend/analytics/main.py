"""
FastAPI read-only analytics service.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.analytics.queries import (
    AnalyticsFilters,
    build_events_payload,
    build_metrics_payload,
    build_sessions_payload,
    build_users_payload,
)
from db.session import get_db_session

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Claude Code Analytics API",
    description="Read-only metrics and aggregates for Claude Code usage telemetry.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _parse_filters(
    date_from: Optional[datetime] = Query(
        default=None,
        description="Inclusive start (UTC), ISO-8601",
    ),
    date_to: Optional[datetime] = Query(
        default=None,
        description="Exclusive end (UTC), ISO-8601",
    ),
    practice: Optional[str] = Query(default=None, description="Filter by employee practice"),
    location: Optional[str] = Query(default=None, description="Filter by employee location"),
) -> AnalyticsFilters:
    """
    Build AnalyticsFilters from query parameters.

    Args:
        date_from (datetime | None): Inclusive lower bound.
        date_to (datetime | None): Exclusive upper bound.
        practice (str | None): Practice filter.
        location (str | None): Location filter.

    Returns:
        AnalyticsFilters: Immutable filter object.
    """
    return AnalyticsFilters(
        date_from=date_from,
        date_to=date_to,
        practice=practice,
        location=location,
    )


@app.get("/health")
def health() -> Dict[str, str]:
    """
    Liveness probe for orchestration.

    Returns:
        dict[str, str]: Service status.
    """
    return {"status": "ok", "service": "analytics"}


@app.get("/metrics")
def get_metrics(
    session: Session = Depends(get_db_session),
    filters: AnalyticsFilters = Depends(_parse_filters),
) -> Dict[str, Any]:
    """
    Return full executive and operational metrics payload.

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Parsed query filters.

    Returns:
        dict: Nested JSON-serializable analytics payload.
    """
    logger.info("metrics request practice=%s location=%s", filters.practice, filters.location)
    return build_metrics_payload(session, filters)


@app.get("/users")
def get_users(
    session: Session = Depends(get_db_session),
    filters: AnalyticsFilters = Depends(_parse_filters),
) -> Dict[str, Any]:
    """
    Return user-centric analytics (practice/level/location, top users).

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Parsed query filters.

    Returns:
        dict: User analytics JSON.
    """
    return build_users_payload(session, filters)


@app.get("/sessions")
def get_sessions(
    session: Session = Depends(get_db_session),
    filters: AnalyticsFilters = Depends(_parse_filters),
) -> Dict[str, Any]:
    """
    Return session-centric analytics (duration buckets, sessions over time).

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Parsed query filters.

    Returns:
        dict: Session analytics JSON.
    """
    return build_sessions_payload(session, filters)


@app.get("/events/summary")
def get_events_summary(
    session: Session = Depends(get_db_session),
    filters: AnalyticsFilters = Depends(_parse_filters),
) -> Dict[str, Any]:
    """
    Return event-type and model distribution summary.

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Parsed query filters.

    Returns:
        dict: Event analytics JSON.
    """
    return build_events_payload(session, filters)
