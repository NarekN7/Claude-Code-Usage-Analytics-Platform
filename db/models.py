"""
SQLAlchemy ORM models for the analytics warehouse.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import BigInteger, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Declarative base for all ORM models.

    Attributes:
        metadata: SQLAlchemy MetaData registry.
    """


class Employee(Base):
    """
    Employee directory row keyed by email.

    Attributes:
        email (str): Primary key; corporate email.
        full_name (str): Display name.
        practice (str): Engineering practice.
        level (str): Seniority label (e.g. L5).
        location (str): Country or region.
        events (list[Event]): Related telemetry events (by user_email).
        sessions (list[Session]): Related sessions.
    """

    __tablename__ = "employees"

    email: Mapped[str] = mapped_column(String(512), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False)
    practice: Mapped[str] = mapped_column(String(256), nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    location: Mapped[str] = mapped_column(String(256), nullable=False)


class Event(Base):
    """
    Normalized telemetry event from Claude Code logs.

    Attributes:
        event_id (str): CloudWatch log event id (unique).
        timestamp (datetime): Event time (UTC).
        event_type (str): Maps from message body (e.g. claude_code.api_request).
        session_id (str): Session UUID string.
        user_email (str): User email from attributes.
        model (str | None): LLM model id when applicable.
        input_tokens (int): Input token count (0 if absent).
        output_tokens (int): Output token count (0 if absent).
        total_tokens (int): Sum of input and output when both defined.
        attributes (dict): Raw attributes JSON.
        scope (dict): Instrumentation scope JSON.
        resource (dict): Resource JSON.
    """

    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_email: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    model: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attributes: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    scope: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    resource: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)


class Session(Base):
    """
    Aggregated coding session derived from events.

    Attributes:
        session_id (str): Session identifier (matches events.session_id).
        user_email (str): User for the session.
        session_start (datetime): First event timestamp.
        session_end (datetime): Last event timestamp.
        duration_minutes (float): Wall-clock duration in minutes.
        event_count (int): Number of events in the session.
        total_input_tokens (int): Sum of input tokens.
        total_output_tokens (int): Sum of output tokens.
        total_tokens (int): Sum of total_tokens on events.
        model (str | None): Most frequent non-null model in the session.
    """

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_email: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    session_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    session_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)


class IngestionCheckpoint(Base):
    """
    Checkpoint for incremental file-based ingestion (streaming-ready).

    Attributes:
        source_id (str): Logical source name (e.g. file path or topic).
        last_line_index (int): Last processed 0-based line number in JSONL.
        last_event_timestamp (datetime | None): Optional high-water mark.
        updated_at (datetime): Last update time.
    """

    __tablename__ = "ingestion_checkpoints"

    source_id: Mapped[str] = mapped_column(String(1024), primary_key=True)
    last_line_index: Mapped[int] = mapped_column(BigInteger, nullable=False, default=-1)
    last_event_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
