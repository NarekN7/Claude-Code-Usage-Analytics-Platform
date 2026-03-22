"""
FastAPI ingestion service: CSV / JSONL batch upload and session rebuild.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, Union

from fastapi import Depends, FastAPI, File, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.common.exceptions import AppException
from db.session import get_db_session
from scripts.etl.load_employees import load_employees_from_csv
from scripts.etl.load_events import ingest_jsonl_path, ingest_jsonl_stream
from scripts.etl.sessionization import rebuild_sessions

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Claude Code Ingestion API",
    description="Batch ingestion for employees CSV and telemetry JSONL.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
    """
    Map AppException to JSON error responses.

    Args:
        request (Request): Incoming request.
        exc (AppException): Application error.

    Returns:
        JSONResponse: Error payload with appropriate status code.
    """
    logger.warning("AppException: %s", exc.message)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


class SessionRebuildResponse(BaseModel):
    """
    Response body after session aggregation.

    Attributes:
        sessions_rebuilt (int): Number of session rows written.
    """

    sessions_rebuilt: int = Field(..., description="Number of rows in sessions table after rebuild")


class IngestSummaryResponse(BaseModel):
    """
    Summary of a JSONL ingest operation.

    Attributes:
        lines_read (int): Lines read from input.
        rows_attempted (int): Rows submitted to insert batches.
        parse_errors (int): Lines that failed JSON parse at root.
    """

    lines_read: int
    rows_attempted: int
    parse_errors: int


@app.get("/health")
def health() -> Dict[str, str]:
    """
    Liveness probe.

    Returns:
        Dict[str, str]: Service status.
    """
    return {"status": "ok", "service": "ingestion"}


@app.post("/ingest/employees/csv", response_model=Dict[str, Union[int, str]])
async def ingest_employees_csv(
    file: UploadFile = File(..., description="employees.csv"),
    session: Session = Depends(get_db_session),
) -> Dict[str, Union[int, str]]:
    """
    Upload employees.csv and upsert into the employees table.

    Args:
        file (UploadFile): CSV file upload.
        session (Session): Database session.

    Returns:
        Dict[str, Union[int, str]]: Rows processed count.

    Raises:
        AppException: If validation fails.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        logger.warning("Rejected employees upload: invalid filename %s", file.filename)
        raise AppException("Expected a .csv file", status_code=400)

    data = await file.read()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        logger.error("Employees CSV is not valid UTF-8")
        raise AppException("File must be UTF-8 encoded", status_code=400) from exc

    with NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".csv", delete=False) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)

    try:
        count = load_employees_from_csv(session, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return {"rows_processed": count, "filename": file.filename}


@app.post("/ingest/telemetry/jsonl", response_model=IngestSummaryResponse)
async def ingest_telemetry_jsonl(
    file: UploadFile = File(..., description="telemetry_logs.jsonl"),
    session: Session = Depends(get_db_session),
) -> IngestSummaryResponse:
    """
    Upload telemetry JSONL (CloudWatch batches per line) and insert events.

    Args:
        file (UploadFile): JSONL upload.
        session (Session): Database session.

    Returns:
        IngestSummaryResponse: Parse and insert statistics.

    Raises:
        AppException: If the file is empty or invalid.
    """
    data = await file.read()
    if not data:
        logger.warning("Empty telemetry upload")
        raise AppException("Empty file", status_code=400)

    stream = io.StringIO(data.decode("utf-8"))
    try:
        summary = ingest_jsonl_stream(session, stream)
    except SQLAlchemyError as exc:
        logger.error("Database error during telemetry ingest: %s", exc)
        raise AppException("Database error during ingest", status_code=500) from exc

    return IngestSummaryResponse(
        lines_read=summary["lines_read"],
        rows_attempted=summary["rows_attempted"],
        parse_errors=summary["parse_errors"],
    )


@app.post("/process/sessions", response_model=SessionRebuildResponse)
def process_sessions(
    session: Session = Depends(get_db_session),
) -> SessionRebuildResponse:
    """
    Rebuild the sessions table from events (full refresh).

    Args:
        session (Session): Database session.

    Returns:
        SessionRebuildResponse: Count of session rows.

    Raises:
        AppException: On database failure.
    """
    try:
        n = rebuild_sessions(session)
    except SQLAlchemyError as exc:
        logger.error("Session rebuild failed: %s", exc)
        raise AppException("Session rebuild failed", status_code=500) from exc

    return SessionRebuildResponse(sessions_rebuilt=n)


@app.post("/ingest/telemetry/jsonl/path", response_model=IngestSummaryResponse)
def ingest_telemetry_from_server_path(
    path: str = Query(..., description="Filesystem path to telemetry_logs.jsonl on the server"),
    session: Session = Depends(get_db_session),
) -> IngestSummaryResponse:
    """
    Ingest JSONL from a path visible to the server (e.g. mounted data/raw).

    Args:
        path (str): Absolute or relative path on the server filesystem.
        session (Session): Database session.

    Returns:
        IngestSummaryResponse: Ingest statistics.

    Raises:
        AppException: If the path is not a file.
    """
    p = Path(path)
    try:
        summary = ingest_jsonl_path(session, p)
    except OSError as exc:
        logger.error("Cannot read telemetry path %s: %s", path, exc)
        raise AppException(f"Cannot read path: {path}", status_code=400) from exc

    return IngestSummaryResponse(
        lines_read=summary["lines_read"],
        rows_attempted=summary["rows_attempted"],
        parse_errors=summary["parse_errors"],
    )
