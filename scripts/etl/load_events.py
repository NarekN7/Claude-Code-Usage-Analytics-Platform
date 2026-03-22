"""
Bulk insert normalized events with idempotent conflict handling.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import BinaryIO, TextIO

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.common.exceptions import AppException
from db.models import Event
from scripts.etl.parse import iter_events_from_jsonl_line
from scripts.etl.schemas import NormalizedEvent

logger = logging.getLogger(__name__)

_DEFAULT_BATCH = 2000


def _event_row_dict(ev: NormalizedEvent) -> dict:
    """
    Map NormalizedEvent to a dict suitable for SQLAlchemy insert.

    Args:
        ev (NormalizedEvent): Canonical event.

    Returns:
        dict: Column name to value mapping.
    """
    return {
        "event_id": ev.event_id,
        "timestamp": ev.timestamp,
        "event_type": ev.event_type,
        "session_id": ev.session_id,
        "user_email": ev.user_email,
        "model": ev.model,
        "input_tokens": ev.input_tokens,
        "output_tokens": ev.output_tokens,
        "total_tokens": ev.total_tokens,
        "attributes": ev.attributes,
        "scope": ev.scope,
        "resource": ev.resource,
    }


def insert_events_batch(session: Session, events: list[NormalizedEvent]) -> int:
    """
    Insert a batch of events, ignoring duplicate event_id values.

    Args:
        session (Session): Active SQLAlchemy session.
        events (list[NormalizedEvent]): Batch of rows.

    Returns:
        int: Number of rows attempted (PostgreSQL may skip duplicates silently).
    """
    if not events:
        return 0
    rows = [_event_row_dict(e) for e in events]
    stmt = pg_insert(Event).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["event_id"])
    session.execute(stmt)
    return len(rows)


def ingest_jsonl_path(
    session: Session,
    jsonl_path: Path,
    batch_size: int = _DEFAULT_BATCH,
) -> dict[str, int]:
    """
    Stream-parse a JSONL file of telemetry batches and insert events.

    Args:
        session (Session): Active SQLAlchemy session.
        jsonl_path (Path): Path to telemetry_logs.jsonl.
        batch_size (int): Rows per insert batch.

    Returns:
        dict[str, int]: Counts with keys attempted, lines_read, parse_errors.

    Raises:
        AppException: If the file does not exist.
    """
    if not jsonl_path.is_file():
        logger.error("Telemetry JSONL not found: %s", jsonl_path)
        raise AppException(f"Telemetry file not found: {jsonl_path}", status_code=400)

    attempted = 0
    lines_read = 0
    parse_errors = 0
    batch: list[NormalizedEvent] = []

    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            lines_read += 1
            line = line.strip()
            if not line:
                continue
            try:
                for ev in iter_events_from_jsonl_line(line):
                    batch.append(ev)
                    if len(batch) >= batch_size:
                        attempted += insert_events_batch(session, batch)
                        batch = []
            except json.JSONDecodeError as exc:
                parse_errors += 1
                logger.warning("JSON decode error on line %s: %s", lines_read, exc)

    if batch:
        attempted += insert_events_batch(session, batch)

    logger.info(
        "Ingested telemetry lines=%s attempted_batches_rows=%s parse_errors=%s file=%s",
        lines_read,
        attempted,
        parse_errors,
        jsonl_path,
    )
    return {
        "lines_read": lines_read,
        "rows_attempted": attempted,
        "parse_errors": parse_errors,
    }


def ingest_jsonl_stream(
    session: Session,
    stream: BinaryIO | TextIO,
    batch_size: int = _DEFAULT_BATCH,
) -> dict[str, int]:
    """
    Ingest telemetry from a readable stream (e.g. multipart upload).

    Args:
        session (Session): Active SQLAlchemy session.
        stream (BinaryIO | TextIO): UTF-8 text stream.
        batch_size (int): Insert batch size.

    Returns:
        dict[str, int]: lines_read, rows_attempted, parse_errors.
    """
    attempted = 0
    lines_read = 0
    parse_errors = 0
    batch: list[NormalizedEvent] = []

    text_stream: TextIO
    if hasattr(stream, "readline"):
        text_stream = stream  # type: ignore[assignment]
    else:
        raise AppException("Stream must support readline", status_code=400)

    while True:
        line = text_stream.readline()
        if not line:
            break
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        lines_read += 1
        line = line.strip()
        if not line:
            continue
        try:
            for ev in iter_events_from_jsonl_line(line):
                batch.append(ev)
                if len(batch) >= batch_size:
                    attempted += insert_events_batch(session, batch)
                    batch = []
        except json.JSONDecodeError as exc:
            parse_errors += 1
            logger.warning("JSON decode error on streamed line %s: %s", lines_read, exc)

    if batch:
        attempted += insert_events_batch(session, batch)

    logger.info(
        "Stream ingest lines=%s rows_attempted=%s parse_errors=%s",
        lines_read,
        attempted,
        parse_errors,
    )
    return {
        "lines_read": lines_read,
        "rows_attempted": attempted,
        "parse_errors": parse_errors,
    }
