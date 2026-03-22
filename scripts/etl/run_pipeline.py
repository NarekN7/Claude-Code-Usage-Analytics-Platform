"""
CLI orchestrator: load employees, ingest telemetry JSONL, rebuild sessions.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from backend.common.config import get_settings
from backend.common.exceptions import AppException
from db.session import session_scope
from scripts.etl.load_employees import load_employees_from_csv
from scripts.etl.load_events import ingest_jsonl_path
from scripts.etl.sessionization import rebuild_sessions

logger = logging.getLogger(__name__)


def main() -> int:
    """
    Parse CLI arguments and run the ETL pipeline.

    Returns:
        int: Process exit code (0 success, non-zero on failure).
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(description="Claude Code telemetry ETL pipeline")
    parser.add_argument(
        "--employees",
        type=Path,
        help="Path to employees.csv (default: DATA_RAW_DIR/employees.csv)",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        help="Path to telemetry_logs.jsonl (default: DATA_RAW_DIR/telemetry_logs.jsonl)",
    )
    parser.add_argument(
        "--skip-employees",
        action="store_true",
        help="Do not load employees CSV",
    )
    parser.add_argument(
        "--skip-events",
        action="store_true",
        help="Do not ingest JSONL",
    )
    parser.add_argument(
        "--skip-sessions",
        action="store_true",
        help="Do not rebuild sessions",
    )
    args = parser.parse_args()

    settings = get_settings()
    raw = settings.data_raw_dir
    emp_path = args.employees or (raw / "employees.csv")
    jsonl_path = args.jsonl or (raw / "telemetry_logs.jsonl")

    try:
        with session_scope() as session:
            if not args.skip_employees:
                load_employees_from_csv(session, emp_path)
            if not args.skip_events:
                ingest_jsonl_path(session, jsonl_path)
            if not args.skip_sessions:
                rebuild_sessions(session)
    except OSError as exc:
        logger.error("I/O error during pipeline: %s", exc)
        return 1
    except AppException as exc:
        logger.error("Pipeline application error: %s", exc.message)
        return 1
    except SQLAlchemyError as exc:
        logger.error("Database error during pipeline: %s", exc, exc_info=True)
        return 1

    logger.info("Pipeline completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
