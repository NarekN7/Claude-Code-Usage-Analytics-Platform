# Python 3.11 — single image for gateway, ingestion, analytics, and Streamlit.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini pyproject.toml ./
COPY db ./db
COPY backend ./backend
COPY scripts ./scripts
COPY frontend ./frontend
COPY app ./app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
