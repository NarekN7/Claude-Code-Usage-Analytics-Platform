"""
Application settings loaded from environment variables.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for backend services and scripts.

    Attributes:
        database_url (str): SQLAlchemy URL for PostgreSQL.
        data_raw_dir (Path): Directory for raw CSV/JSONL files.
        ingestion_base_url (str): Base URL for the ingestion service.
        analytics_base_url (str): Base URL for the analytics service.
        gateway_public_url (str): Public gateway URL for documentation/links.
        public_gateway_url (str): URL the Streamlit app uses to call APIs.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg2://analytics:analytics@localhost:5432/analytics",
        alias="DATABASE_URL",
    )
    data_raw_dir: Path = Field(default=Path("data/raw"), alias="DATA_RAW_DIR")
    ingestion_base_url: str = Field(
        default="http://localhost:8001",
        alias="INGESTION_BASE_URL",
    )
    analytics_base_url: str = Field(
        default="http://localhost:8002",
        alias="ANALYTICS_BASE_URL",
    )
    gateway_public_url: str = Field(
        default="http://localhost:8000",
        alias="GATEWAY_PUBLIC_URL",
    )
    public_gateway_url: str = Field(
        default="http://localhost:8000",
        alias="PUBLIC_GATEWAY_URL",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Return cached application settings.

    Returns:
        Settings: Singleton settings instance.
    """
    return Settings()
