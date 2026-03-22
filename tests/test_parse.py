"""
Unit tests for JSONL / envelope parsing (no database).
"""

from __future__ import annotations

import json

import pytest

from scripts.etl.parse import (
    iter_events_from_jsonl_line,
    iter_normalized_events_from_record,
)


def test_cloudwatch_batch_logevents_yields_events() -> None:
    """
    CloudWatch-style batch with logEvents[].message JSON string parses to events.

    Returns:
        None
    """
    inner = {
        "body": "claude_code.api_request",
        "attributes": {
            "event.timestamp": "2025-12-03T00:06:00.000Z",
            "session.id": "678c4a9e-4362-404e-89c7-1c8abb91226c",
            "user.email": "user@example.com",
            "input_tokens": "10",
            "output_tokens": "20",
            "model": "claude-sonnet-4-5-20250929",
        },
        "scope": {"name": "com.anthropic.claude_code.events", "version": "2.1.45"},
        "resource": {"host.name": "host"},
    }
    batch = {
        "messageType": "DATA_MESSAGE",
        "logEvents": [
            {
                "id": "657689771374632572378173045471188406392782962573476446469",
                "timestamp": 1764720360000,
                "message": json.dumps(inner),
            }
        ],
    }
    events = list(iter_normalized_events_from_record(batch))
    assert len(events) == 1
    ev = events[0]
    assert ev.event_type == "claude_code.api_request"
    assert ev.user_email == "user@example.com"
    assert ev.session_id == "678c4a9e-4362-404e-89c7-1c8abb91226c"
    assert ev.input_tokens == 10
    assert ev.output_tokens == 20
    assert ev.total_tokens == 30
    assert ev.model == "claude-sonnet-4-5-20250929"


def test_alternate_log_event_message_parsed() -> None:
    """
    Alternate §15-style envelope with log_event.message_parsed is supported.

    Returns:
        None
    """
    record = {
        "batch_envelope": {"messageType": "DATA_MESSAGE"},
        "log_event": {
            "id": "abc",
            "timestamp": 1764720360000,
            "message_parsed": {
                "body": "claude_code.user_prompt",
                "attributes": {
                    "event.timestamp": "2025-12-03T00:06:00.000Z",
                    "session.id": "s1",
                    "user.email": "u@example.com",
                },
                "scope": {},
                "resource": {},
            },
        },
    }
    events = list(iter_normalized_events_from_record(record))
    assert len(events) == 1
    assert events[0].event_type == "claude_code.user_prompt"


def test_jsonl_line_invalid_json_logs_and_skips() -> None:
    """
    Invalid JSONL root line raises JSONDecodeError for caller to handle.

    Returns:
        None
    """
    with pytest.raises(json.JSONDecodeError):
        list(iter_events_from_jsonl_line("not json {{{"))


def test_missing_session_id_skips_event() -> None:
    """
    Events without session.id are skipped (no yield).

    Returns:
        None
    """
    inner = {
        "body": "claude_code.api_request",
        "attributes": {
            "event.timestamp": "2025-12-03T00:06:00.000Z",
            "user.email": "u@example.com",
        },
        "scope": {},
        "resource": {},
    }
    batch = {
        "logEvents": [
            {
                "id": "1",
                "timestamp": 0,
                "message": json.dumps(inner),
            }
        ]
    }
    assert list(iter_normalized_events_from_record(batch)) == []
