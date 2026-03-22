"""
One-shot database seed for Docker: load employees + telemetry + session rebuild when the
warehouse is empty or clearly incomplete (e.g. stray test rows while large JSONL is mounted).

Controlled by env:
  SEED_SKIP_IF_EVENTS_GTE: if event count >= this, do nothing (default 1000).
  SEED_MIN_TELEMETRY_BYTES: telemetry file must exceed this to trigger repair (default 1_000_000).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        logger.error("DATABASE_URL is not set")
        sys.exit(1)
    return url


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_RAW_DIR", "/app/data/raw")).resolve()


def _ingestion_url() -> str:
    return os.environ.get("INGESTION_URL", "http://ingestion:8001").rstrip("/")


def _wait_for_ingestion(timeout_s: float = 120.0) -> None:
    url = f"{_ingestion_url()}/health"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=5.0)
            if r.status_code == 200:
                logger.info("Ingestion is up at %s", url)
                return
        except httpx.HTTPError:
            pass
        time.sleep(2.0)
    logger.error("Timed out waiting for ingestion at %s", url)
    sys.exit(1)


def _event_count() -> int:
    engine = create_engine(_database_url(), pool_pre_ping=True)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT COUNT(*) FROM events")).one()
    engine.dispose()
    return int(row[0])


def _sessions_count() -> int:
    engine = create_engine(_database_url(), pool_pre_ping=True)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT COUNT(*) FROM sessions")).one()
    engine.dispose()
    return int(row[0])


def _truncate_warehouse() -> None:
    engine = create_engine(_database_url(), pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE TABLE sessions, events, employees, ingestion_checkpoints")
        )
    engine.dispose()
    logger.info("Truncated sessions, events, employees, ingestion_checkpoints")


def _resolve_seed_files(data_dir: Path) -> tuple[Path | None, Path | None]:
    emp = data_dir / "employees.csv"
    telem = data_dir / "telemetry_logs.jsonl"
    emp_ok = emp.is_file()
    telem_ok = telem.is_file()
    if not emp_ok:
        logger.warning("Missing %s — cannot seed employees", emp)
    if not telem_ok:
        logger.warning("Missing %s — cannot seed telemetry", telem)
    return (emp if emp_ok else None, telem if telem_ok else None)


def _should_seed_or_repair(event_count: int, telem: Path) -> bool:
    skip_gte = int(os.environ.get("SEED_SKIP_IF_EVENTS_GTE", "1000"))
    min_bytes = int(os.environ.get("SEED_MIN_TELEMETRY_BYTES", "1000000"))

    if event_count >= skip_gte:
        logger.info(
            "Event count %s >= %s — database looks loaded; skipping seed.",
            event_count,
            skip_gte,
        )
        return False

    if event_count == 0:
        logger.info("Event count is 0 — loading seed files.")
        return True

    # Stale / partial: few rows but a large telemetry file is mounted (typical dev mismatch).
    if telem.stat().st_size >= min_bytes:
        logger.info(
            "Event count %s is below %s but large telemetry file is present — repairing.",
            event_count,
            skip_gte,
        )
        return True

    logger.warning(
        "Low event count (%s) but telemetry file is smaller than %s bytes — not auto-repairing.",
        event_count,
        min_bytes,
    )
    return False


def _ingest_employees(client: httpx.Client, csv_path: Path) -> None:
    url = f"{_ingestion_url()}/ingest/employees/csv"
    with csv_path.open("rb") as f:
        r = client.post(url, files={"file": (csv_path.name, f, "text/csv")}, timeout=120.0)
    r.raise_for_status()
    logger.info("Employees ingest: %s", r.text)


def _ingest_telemetry_path(client: httpx.Client, jsonl_path: Path) -> None:
    path_in_container = f"/app/data/raw/{jsonl_path.name}"
    url = f"{_ingestion_url()}/ingest/telemetry/jsonl/path"
    r = client.post(
        url,
        params={"path": path_in_container},
        timeout=httpx.Timeout(3600.0),
    )
    r.raise_for_status()
    logger.info("Telemetry ingest: %s", r.text)


def _rebuild_sessions(client: httpx.Client) -> None:
    url = f"{_ingestion_url()}/process/sessions"
    attempts = int(os.environ.get("SEED_SESSION_REBUILD_ATTEMPTS", "5"))
    pause_s = float(os.environ.get("SEED_SESSION_REBUILD_PAUSE_S", "2.0"))
    for attempt in range(1, attempts + 1):
        r = client.post(url, timeout=httpx.Timeout(600.0))
        r.raise_for_status()
        try:
            body = r.json()
            rebuilt = int(body.get("sessions_rebuilt", 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            rebuilt = 0
        sess = _sessions_count()
        logger.info(
            "Session rebuild attempt %s/%s: sessions_rebuilt=%s rows_in_db=%s body=%s",
            attempt,
            attempts,
            rebuilt,
            sess,
            r.text[:500],
        )
        events_n = _event_count()
        if events_n == 0:
            return
        if rebuilt > 0 or sess > 0:
            return
        if attempt < attempts:
            time.sleep(pause_s)
    if _event_count() > 0 and _sessions_count() == 0:
        logger.error(
            "Sessions table is still empty after %s rebuild attempts — check ingestion / sessionization.",
            attempts,
        )


def main() -> None:
    _wait_for_ingestion()
    data_dir = _data_dir()
    emp_path, telem_path = _resolve_seed_files(data_dir)

    if emp_path is None or telem_path is None:
        logger.warning(
            "Seed files not found under %s — nothing to load. "
            "Copy employees.csv and telemetry_logs.jsonl into data/raw/ on the host.",
            data_dir,
        )
        sys.exit(0)

    try:
        n = _event_count()
    except OSError as exc:
        logger.error("Cannot query database: %s", exc)
        sys.exit(1)

    if not _should_seed_or_repair(n, telem_path):
        sys.exit(0)

    if n > 0:
        _truncate_warehouse()

    with httpx.Client() as client:
        _ingest_employees(client, emp_path)
        _ingest_telemetry_path(client, telem_path)
        _rebuild_sessions(client)

    final = _event_count()
    logger.info("Seed complete. events=%s", final)
    if final < int(os.environ.get("SEED_SKIP_IF_EVENTS_GTE", "1000")):
        logger.warning("Event count still below threshold — check ingestion logs.")
    sys.exit(0)


if __name__ == "__main__":
    main()
