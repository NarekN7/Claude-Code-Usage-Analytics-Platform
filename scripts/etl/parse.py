"""
Parse CloudWatch-style JSONL batches and alternate envelope formats into NormalizedEvent rows.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Iterator

from scripts.etl.schemas import NormalizedEvent

logger = logging.getLogger(__name__)


def _parse_iso_ts(value: str | None) -> datetime | None:
    """
    Parse an ISO-8601 timestamp string to UTC datetime.

    Args:
        value (str | None): Timestamp string, possibly with Z suffix.

    Returns:
        datetime | None: UTC-aware datetime, or None if parsing fails.
    """
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        logger.warning("Could not parse ISO timestamp: %s", value[:64])
        return None


def _ms_to_dt(ms: int | float | None) -> datetime | None:
    """
    Convert epoch milliseconds to UTC datetime.

    Args:
        ms (int | float | None): Milliseconds since Unix epoch.

    Returns:
        datetime | None: UTC datetime, or None if invalid.
    """
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc)
    except (OSError, ValueError, OverflowError):
        logger.warning("Invalid epoch milliseconds for timestamp: %s", ms)
        return None


def _safe_int_token(raw: Any) -> int:
    """
    Coerce token-like values from JSON (often strings) to non-negative int.

    Args:
        raw (Any): Raw attribute value.

    Returns:
        int: Parsed integer, or 0 on failure.
    """
    if raw is None:
        return 0
    try:
        if isinstance(raw, bool):
            return 0
        if isinstance(raw, int):
            return max(0, raw)
        return max(0, int(float(str(raw).strip())))
    except (ValueError, TypeError):
        return 0


def _inner_from_message_dict(
    inner: dict[str, Any],
    event_id: str,
    fallback_ts_ms: int | float | None,
) -> NormalizedEvent | None:
    """
    Build a NormalizedEvent from a parsed message dict (body/attributes/scope/resource).

    Args:
        inner (dict[str, Any]): Parsed message object.
        event_id (str): External log event id.
        fallback_ts_ms (int | float | None): Epoch ms if attribute timestamp missing.

    Returns:
        NormalizedEvent | None: Validated row, or None if required fields are missing.
    """
    body = inner.get("body")
    if not body or not isinstance(body, str):
        logger.warning("Skipping event %s: missing body", event_id[:32])
        return None

    attributes = inner.get("attributes")
    if not isinstance(attributes, dict):
        attributes = {}
    scope = inner.get("scope")
    if not isinstance(scope, dict):
        scope = {}
    resource = inner.get("resource")
    if not isinstance(resource, dict):
        resource = {}

    session_id = attributes.get("session.id")
    user_email = attributes.get("user.email")
    if not session_id or not isinstance(session_id, str):
        logger.warning("Skipping event %s: missing session.id", event_id[:32])
        return None
    if not user_email or not isinstance(user_email, str):
        logger.warning("Skipping event %s: missing user.email", event_id[:32])
        return None

    ts_raw = attributes.get("event.timestamp")
    ts = _parse_iso_ts(ts_raw) if isinstance(ts_raw, str) else None
    if ts is None:
        ts = _ms_to_dt(fallback_ts_ms)
    if ts is None:
        logger.warning("Skipping event %s: no valid timestamp", event_id[:32])
        return None

    model_raw = attributes.get("model")
    model: str | None
    if model_raw is None or (isinstance(model_raw, str) and model_raw.strip() == ""):
        model = None
    elif isinstance(model_raw, str):
        model = model_raw.strip()
    else:
        model = str(model_raw)

    input_tokens = _safe_int_token(attributes.get("input_tokens"))
    output_tokens = _safe_int_token(attributes.get("output_tokens"))
    total_tokens = input_tokens + output_tokens

    return NormalizedEvent(
        event_id=str(event_id)[:128],
        timestamp=ts,
        event_type=body[:256],
        session_id=session_id[:128],
        user_email=user_email[:512],
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        attributes=attributes,
        scope=scope,
        resource=resource,
    )


def _parse_message_string(message: str, event_id: str, fallback_ts_ms: int | float | None) -> NormalizedEvent | None:
    """
    Parse the CloudWatch log event message JSON string.

    Args:
        message (str): JSON string for one event.
        event_id (str): Log event id.
        fallback_ts_ms (int | float | None): Epoch ms fallback.

    Returns:
        NormalizedEvent | None: Parsed row, or None on error.
    """
    try:
        inner = json.loads(message)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid JSON in message for event %s: %s", event_id[:32], exc)
        return None
    if not isinstance(inner, dict):
        logger.warning("Message JSON is not an object for event %s", event_id[:32])
        return None
    return _inner_from_message_dict(inner, event_id, fallback_ts_ms)


def iter_normalized_events_from_record(record: dict[str, Any]) -> Iterator[NormalizedEvent]:
    """
    Yield NormalizedEvent instances from one top-level JSON object (one JSONL line).

    Supports:
    - CloudWatch batch: logEvents[].message
    - Alternate: log_event.message_parsed or log_event with message string
    - Single inner object with body/attributes/scope/resource

    Args:
        record (dict[str, Any]): Parsed JSON root object.

    Yields:
        NormalizedEvent: Zero or more validated events.
    """
    if "logEvents" in record and isinstance(record["logEvents"], list):
        for le in record["logEvents"]:
            if not isinstance(le, dict):
                continue
            eid = le.get("id", "")
            if not eid:
                eid = "unknown"
            ts_ms = le.get("timestamp")
            msg = le.get("message")
            if not isinstance(msg, str):
                logger.warning("logEvents entry missing string message: %s", str(eid)[:32])
                continue
            parsed = _parse_message_string(msg, str(eid), ts_ms)
            if parsed is not None:
                yield parsed
        return

    if "log_event" in record and isinstance(record["log_event"], dict):
        le = record["log_event"]
        eid = le.get("id", "unknown")
        ts_ms = le.get("timestamp")
        if "message_parsed" in le and isinstance(le["message_parsed"], dict):
            ev = _inner_from_message_dict(le["message_parsed"], str(eid), ts_ms)
            if ev is not None:
                yield ev
            return
        msg = le.get("message")
        if isinstance(msg, str):
            parsed = _parse_message_string(msg, str(eid), ts_ms)
            if parsed is not None:
                yield parsed
        return

    if "message_parsed" in record and isinstance(record["message_parsed"], dict):
        ev = _inner_from_message_dict(record["message_parsed"], str(record.get("id", "unknown")), None)
        if ev is not None:
            yield ev
        return

    if "body" in record and isinstance(record.get("body"), str):
        ev = _inner_from_message_dict(record, str(record.get("event_id", "inline")), None)
        if ev is not None:
            yield ev


def iter_events_from_jsonl_line(line: str) -> Iterator[NormalizedEvent]:
    """
    Parse one non-empty JSONL line and yield normalized events.

    Args:
        line (str): Single line from a JSONL file.

    Yields:
        NormalizedEvent: Parsed events from the line.

    Raises:
        json.JSONDecodeError: If the line is not valid JSON at the root (caller may catch).
    """
    line = line.strip()
    if not line:
        return
    record = json.loads(line)
    if not isinstance(record, dict):
        logger.warning("JSONL root is not an object; skipping line")
        return
    yield from iter_normalized_events_from_record(record)
