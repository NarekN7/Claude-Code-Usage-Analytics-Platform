"""
Parameterized analytics queries against PostgreSQL.

Provides executive, time-based, role-based (practice/level/location), behavioral,
and operational aggregates for the dashboard and /metrics API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalyticsFilters:
    """
    Common filter set for analytics queries.

    Attributes:
        date_from (datetime | None): Inclusive lower bound (UTC).
        date_to (datetime | None): Exclusive upper bound (UTC).
        practice (str | None): Filter by employee practice.
        location (str | None): Filter by employee location.
    """

    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    practice: Optional[str] = None
    location: Optional[str] = None


def _filter_sql(prefix: str = "e") -> str:
    """
    Return SQL fragments for optional filters (timestamp + employee dimensions).

    Args:
        prefix (str): SQL alias for the events table.

    Returns:
        str: SQL AND clauses (possibly empty).
    """
    return """
    AND (:date_from IS NULL OR """ + prefix + """.timestamp >= :date_from)
    AND (:date_to IS NULL OR """ + prefix + """.timestamp < :date_to)
    AND (:practice IS NULL OR emp.practice = :practice)
    AND (:location IS NULL OR emp.location = :location)
    """


def _bind_params(filters: AnalyticsFilters) -> dict[str, Any]:
    """
    Map AnalyticsFilters to SQL bind parameters.

    Args:
        filters (AnalyticsFilters): Active filters.

    Returns:
        dict[str, Any]: Bind parameter dict.
    """
    return {
        "date_from": filters.date_from,
        "date_to": filters.date_to,
        "practice": filters.practice,
        "location": filters.location,
    }


def query_totals(session: Session, filters: AnalyticsFilters) -> dict[str, Any]:
    """
    Compute total distinct users, sessions, events, and token sums.

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Time and dimension filters.

    Returns:
        dict[str, Any]: Keys total_users, total_sessions, total_events, total_tokens, etc.
    """
    sql = text(
        """
        SELECT
            COUNT(DISTINCT e.user_email)::bigint AS total_users,
            COUNT(DISTINCT e.session_id)::bigint AS total_sessions,
            COUNT(*)::bigint AS total_events,
            COALESCE(SUM(e.total_tokens), 0)::bigint AS total_tokens,
            COALESCE(SUM(e.input_tokens), 0)::bigint AS total_input_tokens,
            COALESCE(SUM(e.output_tokens), 0)::bigint AS total_output_tokens
        FROM events e
        LEFT JOIN employees emp ON emp.email = e.user_email
        WHERE 1=1
        """
        + _filter_sql("e"),
    )
    row = session.execute(sql, _bind_params(filters)).mappings().first()
    return dict(row) if row else {}


def query_token_usage_by_practice(session: Session, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    """
    Sum tokens grouped by engineering practice.

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters.

    Returns:
        list[dict[str, Any]]: Rows with practice and token totals.
    """
    sql = text(
        """
        SELECT emp.practice AS practice,
               COALESCE(SUM(e.total_tokens), 0)::bigint AS total_tokens
        FROM events e
        INNER JOIN employees emp ON emp.email = e.user_email
        WHERE 1=1
        """
        + _filter_sql("e")
        + """
        GROUP BY emp.practice
        ORDER BY total_tokens DESC
        """,
    )
    return [dict(r) for r in session.execute(sql, _bind_params(filters)).mappings().all()]


def query_token_usage_by_level(session: Session, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    """
    Sum tokens grouped by seniority level.

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters.

    Returns:
        list[dict[str, Any]]: Rows with level and token totals.
    """
    sql = text(
        """
        SELECT emp.level AS level,
               COALESCE(SUM(e.total_tokens), 0)::bigint AS total_tokens
        FROM events e
        INNER JOIN employees emp ON emp.email = e.user_email
        WHERE 1=1
        """
        + _filter_sql("e")
        + """
        GROUP BY emp.level
        ORDER BY total_tokens DESC
        """,
    )
    return [dict(r) for r in session.execute(sql, _bind_params(filters)).mappings().all()]


def query_token_usage_by_location(session: Session, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    """
    Sum tokens grouped by location.

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters.

    Returns:
        list[dict[str, Any]]: Rows with location and token totals.
    """
    sql = text(
        """
        SELECT emp.location AS location,
               COALESCE(SUM(e.total_tokens), 0)::bigint AS total_tokens
        FROM events e
        INNER JOIN employees emp ON emp.email = e.user_email
        WHERE 1=1
        """
        + _filter_sql("e")
        + """
        GROUP BY emp.location
        ORDER BY total_tokens DESC
        """,
    )
    return [dict(r) for r in session.execute(sql, _bind_params(filters)).mappings().all()]


def query_model_distribution(session: Session, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    """
    Count events by model (non-null models only).

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters.

    Returns:
        list[dict[str, Any]]: model, event_count rows.
    """
    sql = text(
        """
        SELECT e.model AS model,
               COUNT(*)::bigint AS event_count
        FROM events e
        LEFT JOIN employees emp ON emp.email = e.user_email
        WHERE e.model IS NOT NULL AND e.model != ''
        """
        + _filter_sql("e")
        + """
        GROUP BY e.model
        ORDER BY event_count DESC
        """,
    )
    return [dict(r) for r in session.execute(sql, _bind_params(filters)).mappings().all()]


def query_event_type_distribution(session: Session, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    """
    Count events by event_type (body).

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters.

    Returns:
        list[dict[str, Any]]: event_type, event_count rows.
    """
    sql = text(
        """
        SELECT e.event_type AS event_type,
               COUNT(*)::bigint AS event_count
        FROM events e
        LEFT JOIN employees emp ON emp.email = e.user_email
        WHERE 1=1
        """
        + _filter_sql("e")
        + """
        GROUP BY e.event_type
        ORDER BY event_count DESC
        """,
    )
    return [dict(r) for r in session.execute(sql, _bind_params(filters)).mappings().all()]


def query_usage_by_hour(session: Session, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    """
    Aggregate total tokens by hour of day (0-23) in UTC.

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters.

    Returns:
        list[dict[str, Any]]: hour, total_tokens rows.
    """
    sql = text(
        """
        SELECT EXTRACT(HOUR FROM e.timestamp AT TIME ZONE 'UTC')::int AS hour,
               COALESCE(SUM(e.total_tokens), 0)::bigint AS total_tokens
        FROM events e
        LEFT JOIN employees emp ON emp.email = e.user_email
        WHERE 1=1
        """
        + _filter_sql("e")
        + """
        GROUP BY EXTRACT(HOUR FROM e.timestamp AT TIME ZONE 'UTC')
        ORDER BY hour
        """,
    )
    return [dict(r) for r in session.execute(sql, _bind_params(filters)).mappings().all()]


def query_usage_by_dow(session: Session, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    """
    Aggregate total tokens by day of week (0=Sunday .. 6=Saturday) in UTC.

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters.

    Returns:
        list[dict[str, Any]]: dow, total_tokens rows.
    """
    sql = text(
        """
        SELECT EXTRACT(DOW FROM e.timestamp AT TIME ZONE 'UTC')::int AS dow,
               COALESCE(SUM(e.total_tokens), 0)::bigint AS total_tokens
        FROM events e
        LEFT JOIN employees emp ON emp.email = e.user_email
        WHERE 1=1
        """
        + _filter_sql("e")
        + """
        GROUP BY EXTRACT(DOW FROM e.timestamp AT TIME ZONE 'UTC')
        ORDER BY dow
        """,
    )
    return [dict(r) for r in session.execute(sql, _bind_params(filters)).mappings().all()]


def query_usage_by_calendar_day(session: Session, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    """
    Daily token totals for trend charts.

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters.

    Returns:
        list[dict[str, Any]]: day (date), total_tokens rows.
    """
    sql = text(
        """
        SELECT DATE(e.timestamp AT TIME ZONE 'UTC') AS day,
               COALESCE(SUM(e.total_tokens), 0)::bigint AS total_tokens,
               COUNT(*)::bigint AS event_count
        FROM events e
        LEFT JOIN employees emp ON emp.email = e.user_email
        WHERE 1=1
        """
        + _filter_sql("e")
        + """
        GROUP BY DATE(e.timestamp AT TIME ZONE 'UTC')
        ORDER BY day
        """,
    )
    return [dict(r) for r in session.execute(sql, _bind_params(filters)).mappings().all()]


def query_top_users_by_tokens(session: Session, filters: AnalyticsFilters, limit: int = 20) -> list[dict[str, Any]]:
    """
    Rank users by total token consumption.

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters.
        limit (int): Max rows to return.

    Returns:
        list[dict[str, Any]]: user_email, total_tokens, optional practice/location.
    """
    sql = text(
        """
        SELECT e.user_email AS user_email,
               COALESCE(SUM(e.total_tokens), 0)::bigint AS total_tokens,
               MAX(emp.practice) AS practice,
               MAX(emp.location) AS location
        FROM events e
        LEFT JOIN employees emp ON emp.email = e.user_email
        WHERE 1=1
        """
        + _filter_sql("e")
        + """
        GROUP BY e.user_email
        ORDER BY total_tokens DESC
        LIMIT :limit
        """,
    )
    params = {**_bind_params(filters), "limit": limit}
    return [dict(r) for r in session.execute(sql, params).mappings().all()]


def query_session_duration_distribution(session: Session, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    """
    Bucket session durations into histogram bins (minutes).

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters on session time window and employee dims.

    Returns:
        list[dict[str, Any]]: bucket label and session_count.
    """
    sql = text(
        """
        WITH s AS (
            SELECT s.duration_minutes AS duration_minutes
            FROM sessions s
            INNER JOIN employees emp ON emp.email = s.user_email
            WHERE 1=1
            AND (:date_from IS NULL OR s.session_end >= :date_from)
            AND (:date_to IS NULL OR s.session_start < :date_to)
            AND (:practice IS NULL OR emp.practice = :practice)
            AND (:location IS NULL OR emp.location = :location)
        )
        SELECT CASE
            WHEN duration_minutes < 5 THEN '0-5m'
            WHEN duration_minutes < 15 THEN '5-15m'
            WHEN duration_minutes < 30 THEN '15-30m'
            WHEN duration_minutes < 60 THEN '30-60m'
            ELSE '60m+'
        END AS bucket,
        COUNT(*)::bigint AS session_count,
        MIN(duration_minutes) AS bucket_order
        FROM s
        GROUP BY 1
        ORDER BY bucket_order
        """,
    )
    rows = session.execute(sql, _bind_params(filters)).mappings().all()
    out: list[dict[str, Any]] = []
    for r in rows:
        row = dict(r)
        row.pop("bucket_order", None)
        out.append(row)
    return out


def query_sessions_over_time(session: Session, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    """
    Count sessions started per calendar day.

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters.

    Returns:
        list[dict[str, Any]]: day, session_count.
    """
    sql = text(
        """
        SELECT DATE(s.session_start AT TIME ZONE 'UTC') AS day,
               COUNT(*)::bigint AS session_count
        FROM sessions s
        INNER JOIN employees emp ON emp.email = s.user_email
        WHERE 1=1
        AND (:date_from IS NULL OR s.session_end >= :date_from)
        AND (:date_to IS NULL OR s.session_start < :date_to)
        AND (:practice IS NULL OR emp.practice = :practice)
        AND (:location IS NULL OR emp.location = :location)
        GROUP BY DATE(s.session_start AT TIME ZONE 'UTC')
        ORDER BY day
        """,
    )
    return [dict(r) for r in session.execute(sql, _bind_params(filters)).mappings().all()]


def build_metrics_payload(session: Session, filters: AnalyticsFilters) -> dict[str, Any]:
    """
    Assemble the full /metrics response payload.

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters.

    Returns:
        dict[str, Any]: Nested JSON-serializable analytics payload.
    """
    return {
        "filters": {
            "date_from": filters.date_from.isoformat() if filters.date_from else None,
            "date_to": filters.date_to.isoformat() if filters.date_to else None,
            "practice": filters.practice,
            "location": filters.location,
        },
        "totals": query_totals(session, filters),
        "token_usage_by_practice": query_token_usage_by_practice(session, filters),
        "token_usage_by_level": query_token_usage_by_level(session, filters),
        "token_usage_by_location": query_token_usage_by_location(session, filters),
        "model_distribution": query_model_distribution(session, filters),
        "event_type_distribution": query_event_type_distribution(session, filters),
        "usage_by_hour": query_usage_by_hour(session, filters),
        "usage_by_dow": query_usage_by_dow(session, filters),
        "usage_by_day": query_usage_by_calendar_day(session, filters),
        "top_users": query_top_users_by_tokens(session, filters, limit=20),
        "session_duration_buckets": query_session_duration_distribution(session, filters),
        "sessions_by_day": query_sessions_over_time(session, filters),
    }


def build_users_payload(session: Session, filters: AnalyticsFilters) -> dict[str, Any]:
    """
    Build /users-focused payload (breakdowns + top users).

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters.

    Returns:
        dict[str, Any]: User analytics JSON.
    """
    return {
        "filters": {
            "date_from": filters.date_from.isoformat() if filters.date_from else None,
            "date_to": filters.date_to.isoformat() if filters.date_to else None,
            "practice": filters.practice,
            "location": filters.location,
        },
        "token_usage_by_practice": query_token_usage_by_practice(session, filters),
        "token_usage_by_level": query_token_usage_by_level(session, filters),
        "token_usage_by_location": query_token_usage_by_location(session, filters),
        "top_users": query_top_users_by_tokens(session, filters, limit=50),
    }


def build_sessions_payload(session: Session, filters: AnalyticsFilters) -> dict[str, Any]:
    """
    Build /sessions-focused payload.

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters.

    Returns:
        dict[str, Any]: Session analytics JSON.
    """
    return {
        "filters": {
            "date_from": filters.date_from.isoformat() if filters.date_from else None,
            "date_to": filters.date_to.isoformat() if filters.date_to else None,
            "practice": filters.practice,
            "location": filters.location,
        },
        "session_duration_buckets": query_session_duration_distribution(session, filters),
        "sessions_by_day": query_sessions_over_time(session, filters),
    }


def build_events_payload(session: Session, filters: AnalyticsFilters) -> dict[str, Any]:
    """
    Build event- and model-focused payload.

    Args:
        session (Session): Database session.
        filters (AnalyticsFilters): Filters.

    Returns:
        dict[str, Any]: Event analytics JSON.
    """
    return {
        "filters": {
            "date_from": filters.date_from.isoformat() if filters.date_from else None,
            "date_to": filters.date_to.isoformat() if filters.date_to else None,
            "practice": filters.practice,
            "location": filters.location,
        },
        "event_type_distribution": query_event_type_distribution(session, filters),
        "model_distribution": query_model_distribution(session, filters),
    }
