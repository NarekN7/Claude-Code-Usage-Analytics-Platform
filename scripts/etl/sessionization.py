"""
Rebuild the sessions table from the events table using SQL aggregates.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


SESSION_INSERT_SQL = """
DELETE FROM sessions;

INSERT INTO sessions (
    session_id,
    user_email,
    session_start,
    session_end,
    duration_minutes,
    event_count,
    total_input_tokens,
    total_output_tokens,
    total_tokens,
    model
)
SELECT
    e.session_id,
    MAX(e.user_email) AS user_email,
    MIN(e.timestamp) AS session_start,
    MAX(e.timestamp) AS session_end,
    EXTRACT(EPOCH FROM (MAX(e.timestamp) - MIN(e.timestamp))) / 60.0 AS duration_minutes,
    COUNT(*)::INTEGER AS event_count,
    COALESCE(SUM(e.input_tokens), 0)::BIGINT AS total_input_tokens,
    COALESCE(SUM(e.output_tokens), 0)::BIGINT AS total_output_tokens,
    COALESCE(SUM(e.total_tokens), 0)::BIGINT AS total_tokens,
    (
        SELECT e2.model
        FROM events e2
        WHERE e2.session_id = e.session_id
          AND e2.model IS NOT NULL
          AND e2.model != ''
        GROUP BY e2.model
        ORDER BY COUNT(*) DESC, e2.model
        LIMIT 1
    ) AS model
FROM events e
GROUP BY e.session_id;
"""


def rebuild_sessions(session: Session) -> int:
    """
    Replace all rows in sessions with aggregates derived from events.

    Args:
        session (Session): Active SQLAlchemy session.

    Returns:
        int: Number of session rows after rebuild (best-effort count).

    Raises:
        sqlalchemy.exc.SQLAlchemyError: On database errors.
    """
    session.execute(text(SESSION_INSERT_SQL))
    result = session.execute(text("SELECT COUNT(*) FROM sessions"))
    row = result.scalar_one()
    logger.info("Sessionization complete: %s sessions", row)
    return int(row)
