# Claude Code Usage Analytics Platform

End-to-end analytics for synthetic Claude Code telemetry: **PostgreSQL** warehouse, **ETL** from JSONL/CSV, **FastAPI** microservices (gateway, ingestion, analytics), and a **Streamlit + Plotly** dashboard. Services talk **only over HTTP**; the UI never connects to the database directly.

## Architecture

```text
┌─────────────┐     HTTP      ┌─────────┐     HTTP      ┌───────────┐
│  Streamlit  │ ──────────────► │ Gateway │ ───────────► │ Analytics │
│ (dashboard)│                 │  :8000  │              │   :8002    │
└─────────────┘                 └────┬────┘              └─────┬─────┘
                                   │                         │
                                   │ HTTP                    │ SQL
                                   ▼                         ▼
                            ┌────────────┐            ┌──────────────┐
                            │ Ingestion  │ ──SQL────► │  PostgreSQL  │
                            │   :8001    │            │    :5432     │
                            └────────────┘            └──────────────┘
                                   ▲
                                   │ CLI / batch API
                            ┌──────┴───────┐
                            │ scripts/etl  │
                            └─────────────┘
```

| Layer | Location | Role |
|-------|----------|------|
| Data | `data/raw/` | Place `telemetry_logs.jsonl` and `employees.csv` here (or mount in Docker). |
| DB | `db/` | SQLAlchemy models, Alembic migrations, session helpers. |
| ETL | `scripts/etl/` | Parse JSONL (CloudWatch + alternate envelopes), load employees/events, sessionize. Used by CLI **and** ingestion API. |
| Backend | `backend/gateway/`, `backend/ingestion/`, `backend/analytics/` | Gateway proxies to ingestion + analytics; Pydantic validation on ingest. |
| Frontend | `frontend/streamlit_app.py` | Four pages: Overview, User, Session, Event analytics via gateway. |
| Assignment alias | `app/streamlit_app.py` | Thin shim to `frontend/streamlit_app.py`. |

## Prerequisites

- Python **3.11** (required for type syntax and dependencies; use `python3.11 -m venv .venv` locally)
- **Docker** + Docker Compose (recommended; the `Dockerfile` uses `python:3.11-slim`)
- Optional: local **PostgreSQL** if not using Compose

## Generate sample data

From the repo root:

```bash
python3 claude_code_telemetry2/generate_fake_data.py --num-users 100 --num-sessions 2000 --days 60
```

Copy outputs into the raw data folder:

```bash
mkdir -p data/raw
cp claude_code_telemetry2/output/employees.csv claude_code_telemetry2/output/telemetry_logs.jsonl data/raw/
```

## Configuration

Copy `.env.example` to `.env` and adjust. Important variables:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLAlchemy URL for PostgreSQL (ingestion + analytics). |
| `PUBLIC_GATEWAY_URL` | Base URL the Streamlit app uses (e.g. `http://localhost:8000` or `http://gateway:8000` in Compose). |
| `INGESTION_BASE_URL` / `ANALYTICS_BASE_URL` | Used by the gateway to reach backend services. |
| `DATA_RAW_DIR` | Default directory for the ETL CLI. |

Set `PYTHONPATH` to the repository root for local runs:

```bash
export PYTHONPATH=$(pwd)
```

## Run with Docker Compose

Build and start **postgres**, **pgadmin**, **ingestion**, **analytics**, **gateway**, and **dashboard**:

```bash
docker compose up --build
```

| Service | URL / port |
|---------|------------|
| API gateway | http://localhost:8000 |
| Ingestion API | http://localhost:8001 |
| Analytics API | http://localhost:8002 |
| Streamlit | http://localhost:8501 |
| PostgreSQL | localhost:5432 (`analytics` / `analytics`) |
| pgAdmin | http://localhost:5050 (see compose env for default email/password) |

After containers are up, load data (from your host, with files under `./data/raw`):

```bash
curl -s -X POST "http://localhost:8001/ingest/employees/csv" -F "file=@data/raw/employees.csv"
curl -s -X POST "http://localhost:8001/ingest/telemetry/jsonl" -F "file=@data/raw/telemetry_logs.jsonl"
curl -s -X POST "http://localhost:8001/process/sessions"
```

Or use the gateway (multipart is forwarded correctly):

```bash
curl -s -X POST "http://localhost:8000/ingest/employees/csv" -F "file=@data/raw/employees.csv"
curl -s -X POST "http://localhost:8000/ingest/telemetry/jsonl" -F "file=@data/raw/telemetry_logs.jsonl"
curl -s -X POST "http://localhost:8000/process/sessions"
```

Open the dashboard at **http://localhost:8501**. Optional filters: date range (UTC), practice, location.

### pgAdmin

Add a server: host `postgres` (from your machine use `localhost` if port-forwarded), user `analytics`, password `analytics`, database `analytics`.

## Run locally (without Docker)

1. Start PostgreSQL and create database `analytics` (or set `DATABASE_URL`).
2. Install dependencies: `pip install -r requirements.txt`
3. `export PYTHONPATH=$(pwd)`
4. Migrate: `alembic upgrade head`
5. Terminal A — gateway: `uvicorn backend.gateway.main:app --port 8000`
6. Terminal B — ingestion: `uvicorn backend.ingestion.main:app --port 8001`
7. Terminal C — analytics: `uvicorn backend.analytics.main:app --port 8002`
8. Terminal D — UI: `streamlit run frontend/streamlit_app.py --server.port 8501`

Set `PUBLIC_GATEWAY_URL=http://localhost:8000` for Streamlit.

## ETL CLI (batch pipeline)

Runs the same loaders as the ingestion service:

```bash
export PYTHONPATH=$(pwd)
python -m scripts.etl.run_pipeline
```

Options: `--employees PATH`, `--jsonl PATH`, `--skip-employees`, `--skip-events`, `--skip-sessions`.

## API (via gateway)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/metrics` | Full KPI + breakdown payload (filters: `date_from`, `date_to`, `practice`, `location`). |
| GET | `/users` | User-centric aggregates. |
| GET | `/sessions` | Session duration buckets + sessions per day. |
| GET | `/events/summary` | Event types + model distribution. |
| POST | `/ingest/employees/csv` | Multipart CSV upload. |
| POST | `/ingest/telemetry/jsonl` | Multipart JSONL upload. |
| POST | `/process/sessions` | Rebuild `sessions` from `events`. |

## Git workflow (branch-per-epoch)

Use short-lived branches per milestone (e.g. `epoch/1-db`, `epoch/2-etl`, `epoch/3-backend`, `epoch/4-frontend`, `epoch/5-docker`), merge to `main` after checks, and keep commits small and traceable.

## Coding standards

Python code follows [CODING_GUIDELINES.md](CODING_GUIDELINES.md) (docstrings, logging before raises, typed exceptions).

## License

See [LICENSE](LICENSE) in the repository.
