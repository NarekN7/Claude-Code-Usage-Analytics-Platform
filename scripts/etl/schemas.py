"""
Pydantic models for validated canonical telemetry rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class NormalizedEvent(BaseModel):
    """
    Canonical row inserted into the events table after parsing raw logs.

    Attributes:
        event_id (str): Unique log event identifier.
        timestamp (datetime): Event time in UTC.
        event_type (str): Telemetry body / event name.
        session_id (str): Session UUID.
        user_email (str): User email from attributes.
        model (Optional[str]): Model identifier when present.
        input_tokens (int): Parsed input token count.
        output_tokens (int): Parsed output token count.
        total_tokens (int): Sum of input and output tokens.
        attributes (dict): Raw attributes object.
        scope (dict): Scope metadata.
        resource (dict): Resource attributes.
    """

    event_id: str = Field(..., min_length=1, max_length=128)
    timestamp: datetime
    event_type: str = Field(..., min_length=1, max_length=256)
    session_id: str = Field(..., min_length=1, max_length=128)
    user_email: str = Field(..., min_length=1, max_length=512)
    model: Optional[str] = Field(default=None, max_length=256)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    scope: Dict[str, Any] = Field(default_factory=dict)
    resource: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("model", mode="before")
    @classmethod
    def empty_model_to_none(cls, v: Optional[str]) -> Optional[str]:
        """
        Normalize blank model strings to None.

        Args:
            v (Optional[str]): Raw model field.

        Returns:
            Optional[str]: None if blank, else stripped string.
        """
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        if isinstance(v, str):
            return v.strip()
        return v
