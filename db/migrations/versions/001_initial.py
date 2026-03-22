"""Initial schema: employees, events, sessions, ingestion_checkpoints.

Revision ID: 001
Revises:
Create Date: 2025-03-22

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("email", sa.String(length=512), nullable=False),
        sa.Column("full_name", sa.String(length=512), nullable=False),
        sa.Column("practice", sa.String(length=256), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("location", sa.String(length=256), nullable=False),
        sa.PrimaryKeyConstraint("email"),
    )
    op.create_table(
        "events",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=256), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("user_email", sa.String(length=512), nullable=False),
        sa.Column("model", sa.String(length=256), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resource", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_events_timestamp", "events", ["timestamp"], unique=False)
    op.create_index("ix_events_event_type", "events", ["event_type"], unique=False)
    op.create_index("ix_events_session_id", "events", ["session_id"], unique=False)
    op.create_index("ix_events_user_email", "events", ["user_email"], unique=False)
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("user_email", sa.String(length=512), nullable=False),
        sa.Column("session_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Float(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("total_input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("total_output_tokens", sa.BigInteger(), nullable=False),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False),
        sa.Column("model", sa.String(length=256), nullable=True),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_sessions_user_email", "sessions", ["user_email"], unique=False)
    op.create_table(
        "ingestion_checkpoints",
        sa.Column("source_id", sa.String(length=1024), nullable=False),
        sa.Column("last_line_index", sa.BigInteger(), nullable=False),
        sa.Column("last_event_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("source_id"),
    )


def downgrade() -> None:
    op.drop_table("ingestion_checkpoints")
    op.drop_index("ix_sessions_user_email", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_events_user_email", table_name="events")
    op.drop_index("ix_events_session_id", table_name="events")
    op.drop_index("ix_events_event_type", table_name="events")
    op.drop_index("ix_events_timestamp", table_name="events")
    op.drop_table("events")
    op.drop_table("employees")
