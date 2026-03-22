# Claude Code Usage Analytics Platform

End-to-end analytics for Claude Code–style telemetry: **PostgreSQL** warehouse, **ETL** from JSONL/CSV, **FastAPI** microservices (gateway, ingestion, analytics), and a **Streamlit + Plotly** dashboard. The UI talks only to the **gateway** over HTTP; it never connects to the database directly.

**Run the app:** [From clone to Streamlit (Docker)](#from-clone-to-streamlit-docker) · **Verify it:** [How to test that everything works](#how-to-test-that-everything-works)

---

## What you get

| Piece | What it does |
|-------|----------------|
| **PostgreSQL** | Stores employees, events, sessions, ingestion checkpoints. |
| **Ingestion API** (`:8001`) | Upload CSV/JSONL, ingest from server path, rebuild sessions. |
| **Analytics API** (`:8002`) | Read-only metrics, filters, aggregates. |
| **Gateway** (`:8000`) | Single public API: proxies to ingestion + analytics. |
| **Streamlit** (`:8501`) | Four-page dashboard (Overview, User, Session, Event analytics). |
| **Seed (one-shot)** | On startup, loads `data/raw/` into Postgres when the DB is empty or incomplete. |
| **pgAdmin** (`:5050`, optional) | Web UI to inspect Postgres. |

---

## What you need installed

| Tool | Why |
|------|-----|
| **Git** | Clone this repository. |
| **Docker Desktop** (or Docker Engine + Compose v2) | Run the full stack with one command. |
| **Python 3.11+** | Only for **generating** sample `employees.csv` + `telemetry_logs.jsonl` on your machine (Step 2 below). Docker images use Python 3.11 internally. |

No Docker? See [Run without Docker (advanced)](#run-without-docker-advanced).

---

## From clone to Streamlit (Docker)

Run every step in a terminal. Working directory must be the **repository root** (the folder that contains `docker-compose.yml`).

### Step 0 — Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd Claude-Code-Usage-Analytics-Platform
```

Confirm you are in the right place:

```bash
ls docker-compose.yml README.md
```

---

### Step 1 — Create sample data under `data/raw/`

The stack expects **`data/raw/employees.csv`** and **`data/raw/telemetry_logs.jsonl`**. Generate them with the bundled script (requires Python 3.11+ on your host):

```bash
mkdir -p data/raw
python3 claude_code_telemetry2/generate_fake_data.py --num-users 100 --num-sessions 2000 --days 60
cp claude_code_telemetry2/output/employees.csv claude_code_telemetry2/output/telemetry_logs.jsonl data/raw/
```

**If you already have** compatible files, copy them into `data/raw/` instead of running the generator.

---

### Step 2 — Build images and start **all** services

This starts **PostgreSQL**, **pgAdmin**, **ingestion**, **analytics**, **gateway**, runs **seed** once, then starts **Streamlit**.

```bash
docker compose up --build -d
```

First run builds images (may take a few minutes). Subsequent runs are faster.

---

### Step 3 — Wait until **seed** finishes

Loading a large JSONL can take **about 1–2 minutes**. Streamlit will **not** start until `seed` exits successfully.

```bash
docker compose logs -f seed
```

Press **Ctrl+C** when you see log lines like `Seed complete` or the `seed` container stops. If `seed` fails, read the error in that log.

---

### Step 4 — Verify every microservice (health checks)

Run these from your machine. Each should return JSON with `"status": "ok"` (gateway aggregates downstream services).

```bash
curl -s http://localhost:8000/health
```

```bash
curl -s http://localhost:8001/health
```

```bash
curl -s http://localhost:8002/health
```

Quick check that **analytics** has data (non‑tiny `total_events` after seed):

```bash
curl -s http://localhost:8000/metrics | python3 -c "import sys,json; print(json.load(sys.stdin)['totals'])"
```

Check Streamlit responds:

```bash
curl -s -o /dev/null -w "Streamlit HTTP %{http_code}\n" http://localhost:8501/
```

You should see `Streamlit HTTP 200`.

---

### Step 5 — Open the dashboard

In a browser, open:

**http://localhost:8501**

Use the sidebar: filters (date, practice, location), API base caption, and four pages (Overview, User analytics, Session analytics, Event analytics).

---

### Step 6 — If KPIs look empty or stuck at “1 / 1 / 1”

Re-run the loader (same logic as startup `seed`), then refresh the browser:

```bash
docker compose run --rm seed
```

If it still fails, confirm Step 1 files exist and you did **not** wipe the database with `docker compose down -v` unless you intend to reload from scratch.

---

### Step 7 — (Optional) pgAdmin

| Field | Value |
|-------|--------|
| URL | http://localhost:5050 |
| Email | `admin@example.com` |
| Password | `admin` (from `docker-compose.yml`) |

Register a server: host **`localhost`**, port **5432**, user **`analytics`**, password **`analytics`**, database **`analytics`**.

---

### Stop the stack

```bash
docker compose down
```

Keep your data: **do not** add `-v` unless you want to **delete** the Postgres volume.

```bash
docker compose down -v
```

---

## Service reference (ports after `docker compose up`)

| Service | Port | Role |
|---------|------|------|
| **Gateway** | 8000 | Public API for dashboard and operators. |
| **Ingestion** | 8001 | CSV/JSONL ingest, session rebuild. |
| **Analytics** | 8002 | Metrics and aggregates. |
| **Streamlit** | 8501 | Interactive dashboard. |
| **PostgreSQL** | 5432 | Database (`analytics` / `analytics`). |
| **pgAdmin** | 5050 | DB admin UI (optional). |

---

## Run without Docker (advanced)

Use when you cannot run Docker but have PostgreSQL locally. You need **five terminals** from the repo root.

### 1) Install Python deps and apply migrations

```bash
pip install -r requirements.txt
export PYTHONPATH=$(pwd)
alembic upgrade head
```

Set `DATABASE_URL` if Postgres is not the default in `backend/common/config.py`.

### 2) Start each API (three terminals)

```bash
uvicorn backend.gateway.main:app --host 0.0.0.0 --port 8000
```

```bash
uvicorn backend.ingestion.main:app --host 0.0.0.0 --port 8001
```

```bash
uvicorn backend.analytics.main:app --host 0.0.0.0 --port 8002
```

### 3) Start Streamlit (fourth terminal)

```bash
export PUBLIC_GATEWAY_URL=http://localhost:8000
streamlit run frontend/streamlit_app.py --server.port 8501
```

### 4) Load data

With APIs running, either:

```bash
export PYTHONPATH=$(pwd)
python -m scripts.etl.run_pipeline
```

(uses defaults under `data/raw/` when files exist), **or** use the **Manual ingest** commands in [Manual ingest via `curl`](#manual-ingest-via-curl).

---

## Manual ingest via `curl`

Use when `seed` did not run or you need to reload. Put files under `data/raw/` on the host (Compose mounts them at `/app/data/raw/` in the **ingestion** container).

**Gateway (8000)** — good for CSV and multipart JSONL:

```bash
curl -s -X POST "http://localhost:8000/ingest/employees/csv" -F "file=@data/raw/employees.csv"
curl -s -X POST "http://localhost:8000/ingest/telemetry/jsonl" -F "file=@data/raw/telemetry_logs.jsonl"
curl -s -X POST "http://localhost:8000/process/sessions"
```

**Ingestion (8001)** — use **path ingest** for large JSONL (no multi‑hundred‑MB upload through `curl`):

```bash
curl -s -X POST "http://localhost:8001/ingest/employees/csv" -F "file=@data/raw/employees.csv"
curl -s -X POST "http://localhost:8001/ingest/telemetry/jsonl/path?path=/app/data/raw/telemetry_logs.jsonl"
curl -s -X POST "http://localhost:8001/process/sessions"
```

Or multipart only on **8001**:

```bash
curl -s -X POST "http://localhost:8001/ingest/telemetry/jsonl" -F "file=@data/raw/telemetry_logs.jsonl"
curl -s -X POST "http://localhost:8001/process/sessions"
```

---

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
| Data | `data/raw/` | `telemetry_logs.jsonl`, `employees.csv` (not committed if large; see `.gitignore`). |
| DB | `db/` | SQLAlchemy models, Alembic migrations. |
| ETL | `scripts/etl/` | JSONL parsing, loaders, sessionization; used by CLI and ingestion API. |
| Backend | `backend/` | Gateway, ingestion, analytics, shared config. |
| Frontend | `frontend/streamlit_app.py` | Dashboard entry. |
| Alias | `app/streamlit_app.py` | Shim to `frontend/streamlit_app.py`. |

---

## Configuration

Copy `.env.example` to `.env` if you need overrides.

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL URL for services and Alembic. |
| `PUBLIC_GATEWAY_URL` | Base URL Streamlit uses (`http://localhost:8000` locally, `http://gateway:8000` in Compose). |
| `INGESTION_BASE_URL` / `ANALYTICS_BASE_URL` | Gateway → backends. |

Local Python tools:

```bash
export PYTHONPATH=$(pwd)
```

---

## ETL CLI (same loaders as the ingestion API)

```bash
export PYTHONPATH=$(pwd)
python -m scripts.etl.run_pipeline
```

Options: `--employees PATH`, `--jsonl PATH`, `--skip-employees`, `--skip-events`, `--skip-sessions`.

---

## API (via gateway on port 8000)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Gateway + downstream liveness. |
| GET | `/metrics` | KPIs + breakdowns (`date_from`, `date_to`, `practice`, `location`). |
| GET | `/users` | User-centric aggregates. |
| GET | `/sessions` | Session duration + sessions per day. |
| GET | `/events/summary` | Event types + model distribution. |
| POST | `/ingest/employees/csv` | Multipart CSV. |
| POST | `/ingest/telemetry/jsonl` | Multipart JSONL. |
| POST | `/process/sessions` | Rebuild `sessions` from `events`. |

Ingestion-only routes (e.g. `/ingest/telemetry/jsonl/path`) are available on **:8001**; the gateway forwards `/ingest/*` when proxied accordingly.

---

## How to test that everything works

Use **automated tests** for CI-style checks, then **manual smoke tests** when the Docker stack is up. All commands below assume the **repository root** and (for Python) **`PYTHONPATH`**.

### A) Install test dependencies

```bash
pip install -r requirements-dev.txt
export PYTHONPATH=$(pwd)
```

---

### B) Fast automated tests (no PostgreSQL, no Docker)

Runs unit tests, parsers, schemas, mocked gateway, and in-process health checks — **no live database**.

```bash
pytest tests -v -m "not integration"
```

Expect **all tests passed** (the suite skips integration tests).

---

### C) Full automated tests (includes PostgreSQL integration)

Integration tests live in `tests/test_integration_postgres.py` and need a **reachable Postgres** with the same schema (Alembic migrations applied).

**Option 1 — Postgres already running (e.g. Docker Compose):**

```bash
docker compose up -d postgres
```

Wait until Postgres is healthy, then:

```bash
export DATABASE_URL=postgresql+psycopg2://analytics:analytics@127.0.0.1:5432/analytics
pytest tests -v
```

**Option 2 — only integration file:**

```bash
export DATABASE_URL=postgresql+psycopg2://analytics:analytics@127.0.0.1:5432/analytics
pytest tests/test_integration_postgres.py -v
```

You can use `TEST_DATABASE_URL` instead of `DATABASE_URL` if you prefer a dedicated test database.

**Important:** Do **not** point `DATABASE_URL` at the same database while you are **also** using the full app and expecting seeded data — integration tests **truncate** tables. Use a separate DB, or run integration tests **before** loading production-like data, or stop the stack first.

---

### D) What the test suite covers

| Area | Files |
|------|--------|
| JSONL parse / Pydantic | `test_parse.py`, `test_schemas.py` |
| `/health` on ingestion & analytics | `test_health_endpoints.py` |
| Gateway → downstream (mocked HTTP) | `test_gateway_respx.py` |
| Postgres + ingest + metrics + sessionization | `test_integration_postgres.py` (needs live DB) |

---

### E) Manual smoke test (full Docker stack)

After **Steps 2–4** in [From clone to Streamlit (Docker)](#from-clone-to-streamlit-docker) (stack is up and health checks pass), confirm:

| Check | Command or action |
|-------|-------------------|
| Gateway health | `curl -s http://localhost:8000/health` — `ingestion` and `analytics` should be `"ok"`. |
| Ingestion health | `curl -s http://localhost:8001/health` |
| Analytics health | `curl -s http://localhost:8002/health` |
| Metrics payload | `curl -s http://localhost:8000/metrics \| python3 -c "import sys,json; print(json.load(sys.stdin)['totals'])"` — expect non‑tiny `total_events` after seed. |
| Streamlit | Open http://localhost:8501 — four pages load; KPIs and charts populate (no filters excluding all data). |
| Optional | `curl -s "http://localhost:8000/users?limit=3"` and similar for `/sessions`, `/events/summary`. |

If any step fails, follow **Step 6** in the same section (re-run `seed`) and inspect `docker compose logs` for `gateway`, `ingestion`, `analytics`, `seed`, `dashboard`.

---

## Git workflow (optional)

Short-lived feature branches, merge to `main` after checks; keep commits small and traceable.

---

## Coding standards

See [CODING_GUIDELINES.md](CODING_GUIDELINES.md).

---

## License

See [LICENSE](LICENSE).
