"""
Unit tests for Pydantic NormalizedEvent.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from scripts.etl.schemas import NormalizedEvent


def test_normalized_event_accepts_optional_model_none() -> None:
    """
    Model field may be omitted or blank and becomes None.

    Returns:
        None
    """
    ev = NormalizedEvent(
        event_id="e1",
        timestamp=datetime.now(timezone.utc),
        event_type="claude_code.x",
        session_id="s",
        user_email="a@b.com",
        model=None,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        attributes={},
        scope={},
        resource={},
    )
    assert ev.model is None


def test_empty_string_model_becomes_none() -> None:
    """
    Validator coerces empty model string to None.

    Returns:
        None
    """
    ev = NormalizedEvent(
        event_id="e1",
        timestamp=datetime.now(timezone.utc),
        event_type="claude_code.x",
        session_id="s",
        user_email="a@b.com",
        model="   ",
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        attributes={},
        scope={},
        resource={},
    )
    assert ev.model is None


def test_event_id_required() -> None:
    """
    Empty event_id fails validation.

    Returns:
        None
    """
    with pytest.raises(ValidationError):
        NormalizedEvent(
            event_id="",
            timestamp=datetime.now(timezone.utc),
            event_type="x",
            session_id="s",
            user_email="a@b.com",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            attributes={},
            scope={},
            resource={},
        )
