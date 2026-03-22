"""
Load employees.csv into PostgreSQL with upsert semantics.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.common.exceptions import AppException
from db.models import Employee

logger = logging.getLogger(__name__)


def load_employees_from_csv(session: Session, csv_path: Path) -> int:
    """
    Read an employees CSV and upsert rows into the employees table.

    Expected columns: email, full_name, practice, level, location.

    Args:
        session (Session): Active SQLAlchemy session.
        csv_path (Path): Path to employees.csv.

    Returns:
        int: Number of rows processed.

    Raises:
        AppException: If the file is missing or columns are invalid.
        FileNotFoundError: If csv_path does not exist.
    """
    if not csv_path.is_file():
        logger.error("Employees CSV not found: %s", csv_path)
        raise AppException(f"Employees file not found: {csv_path}", status_code=400)

    try:
        df = pd.read_csv(csv_path)
    except pd.errors.EmptyDataError as exc:
        logger.error("Employees CSV is empty: %s", csv_path)
        raise AppException("Employees CSV is empty", status_code=400) from exc

    required = {"email", "full_name", "practice", "level", "location"}
    if not required.issubset(set(df.columns)):
        logger.error("Employees CSV missing columns: got %s", list(df.columns))
        raise AppException(
            f"employees.csv must contain columns: {sorted(required)}",
            status_code=400,
        )

    count = 0
    for _, row in df.iterrows():
        values = {
            "email": str(row["email"]).strip(),
            "full_name": str(row["full_name"]).strip(),
            "practice": str(row["practice"]).strip(),
            "level": str(row["level"]).strip(),
            "location": str(row["location"]).strip(),
        }
        stmt = pg_insert(Employee).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["email"],
            set_={
                "full_name": stmt.excluded.full_name,
                "practice": stmt.excluded.practice,
                "level": stmt.excluded.level,
                "location": stmt.excluded.location,
            },
        )
        session.execute(stmt)
        count += 1

    logger.info("Upserted %s employee rows from %s", count, csv_path)
    return count
