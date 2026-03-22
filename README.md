# Claude Code Usage Analytics Platform

End-to-end analytics for Claude Code–style telemetry: **PostgreSQL** warehouse, **ETL** from JSONL/CSV, **FastAPI** microservices (gateway, ingestion, analytics), and a **Streamlit + Plotly** dashboard. The UI talks only to the **gateway** over HTTP; it never connects to the database directly.

**Run the app:** [From clone to Streamlit (Docker)](#from-clone-to-streamlit-docker) · **Verify it:** [How to test that everything works](#how-to-test-that-everything-works) · **LLM usage:** [LLM usage log](#llm-usage-log)

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

## LLM usage log

This section documents how **generative AI** was used to build and refine this project, per the assignment deliverables: **which tools**, **representative prompts**, and **how outputs were validated**.

### Tools and workflow

| Tool / mode | How it was used |
|-------------|------------------|
| **Cursor — Planning / Agent mode** | **Primary driver** for structuring the work: breaking the assignment into layers (database, ETL, APIs, gateway, Streamlit, Docker), sequencing tasks, and keeping the codebase aligned with a consistent architecture. Used heavily for scaffolding, refactors, and cross-cutting fixes (e.g. ingestion, analytics, dashboard wiring). |
| **Chat-style assistance** | Ad-hoc questions, debugging, README and documentation drafting, and clarifying behavior of libraries (Streamlit, FastAPI, SQLAlchemy). |
| *(add others if applicable: e.g. Claude web, Copilot, …)* | *(short note)* |

The **planning-oriented agent workflow** was the main lever to **structure the project end-to-end** (what to build first, how services talk, and where code should live) rather than only one-off completions.

### Example prompts

Three representative prompts below cover **initial architecture**, **synthetic data verification**, and **pipeline debugging**. The first prompt suggested a generic `src/` / `app/` layout; the implemented repository uses `backend/`, `frontend/`, `scripts/`, and `db/` instead (see [Architecture](#architecture)).

#### Prompt 1 — “Initial architecture / plan”

```
You are a senior data engineer and full-stack developer.

Your task is to build a complete end-to-end analytics platform called:

"Claude Code Usage Analytics Platform"

Follow these requirements strictly and generate production-quality code with clean architecture.


====================================================
1. OVERVIEW
====================================================

We have synthetic telemetry data generated from a script:
- telemetry_logs.jsonl
- employees.csv

The goal is to:
- ingest and process telemetry data
- store it in PostgreSQL
- build analytics queries
- expose results in a Streamlit dashboard
- optionally expose API endpoints (FastAPI)

Use Docker Compose for orchestration.

====================================================
2. TECH STACK (MANDATORY)
====================================================

- Python 3.11
- PostgreSQL
- Docker Compose
- SQLAlchemy (preferred) or psycopg2
- Pandas for ETL
- Streamlit for dashboard
- Plotly for charts
- FastAPI (bonus API)

====================================================
3. PROJECT STRUCTURE (STRICT)
====================================================

Create this structure:

project/
├── data/
│   └── raw/
├── src/
│   ├── ingestion/
│   ├── processing/
│   ├── db/
│   ├── analytics/
│   ├── api/
├── app/
│   └── streamlit_app.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── README.md

====================================================
4. DATABASE DESIGN
====================================================

Create PostgreSQL tables:

1. employees
- email (PK)
- full_name
- practice
- level
- location

2. events
- event_id (PK)
- timestamp
- event_type
- session_id
- user_email
- model
- input_tokens
- output_tokens
- total_tokens
- attributes (JSON)
- scope (JSON)
- resource (JSON)

3. sessions (derived)
- session_id (PK)
- user_email
- session_start
- session_end
- duration_minutes
- event_count
- total_input_tokens
- total_output_tokens
- total_tokens
- model

====================================================
5. DATA INGESTION (VERY IMPORTANT)
====================================================

Implement ETL pipeline:

- Read employees.csv into employees table
- Read telemetry_logs.jsonl line-by-line

Each JSON line contains:
{
  "logEvents": [
    {
      "message": "{...JSON STRING...}"
    }
  ]
}

For each logEvent:
- parse message JSON string
- extract:
  - body → event_type
  - attributes
  - scope
  - resource

Flatten into rows and insert into events table.

Handle:
- invalid JSON safely
- missing fields
- type conversions

====================================================
6. SESSIONIZATION
====================================================

Create logic to aggregate events into sessions:

Group by session_id:
- min(timestamp) → session_start
- max(timestamp) → session_end
- duration
- event_count
- sum tokens

Insert into sessions table.

====================================================
7. ANALYTICS LAYER
====================================================

Implement queries/functions:

- total users, sessions, events, tokens
- token usage by practice / level / location
- model usage distribution
- event type distribution
- usage by hour/day
- top users by tokens
- session duration distribution

====================================================
8. STREAMLIT DASHBOARD
====================================================

Create app with 4 pages:

1. Overview
- KPIs
- trends

2. User Analytics
- usage by practice/level/location
- top users

3. Session Analytics
- session duration
- sessions over time

4. Event Analytics
- event types
- model usage

Include:
- filters (date, practice, location)
- Plotly charts

====================================================
9. DOCKER SETUP
====================================================

Create docker-compose.yml with:

- postgres
- pgadmin
- streamlit app

Ensure:
- proper ports
- volumes
- environment variables

Also create Dockerfile for Python app.

====================================================
10. API (BONUS)
====================================================

Create FastAPI service with endpoints:

- /metrics
- /users
- /sessions

====================================================
11. CODE QUALITY
====================================================

- modular code
- clear functions
- comments where needed
- no hardcoding paths
- use environment variables

====================================================
12. README
====================================================

Generate a professional README including:
- architecture
- setup steps
- data generation command
- how to run docker
- how to run pipeline
- dashboard access URLs

====================================================
13. IMPORTANT
====================================================

- PostgreSQL as analytical source
- Docker Compose as execution standard
- Streaming-ready incremental ingestion design
- Strict frontend-backend-database separation
- API-driven loosely coupled architecture
- Microservice architecture is required: gateway, ingestion, analytics, and dashboard services must be independently implemented and orchestrated via Docker Compose. Services must communicate only through well-defined APIs. Ingestion must support batch APIs (JSON/CSV) and be designed for future streaming. Events must be normalized into a canonical relational model with Pydantic-based validation. Analytics must cover executive, time-based, role-based, behavioral, and operational insights.

- Make code runnable
- Do NOT skip implementation details
- Prefer clarity over complexity
- Use best practices
- Assume real-world usage
- Follow the CODING_GUIDELINES.md

====================================================
14. GIT STRATEGY & WORKFLOW DISCIPLINE
====================================================

- Branch-per-epoch development model
- Feature branches per implementation phase
- Commit history must reflect incremental evolution
- Merge to main only after validation
- Maintain a clear, traceable development timeline


====================================================
15. ONE OBSERVATION FROM DATA
====================================================

{
  "batch_envelope": {
    "messageType": "DATA_MESSAGE",
    "owner": "123456789012",
    "logGroup": "/claude-code/telemetry",
    "logStream": "otel-collector",
    "subscriptionFilters": [
      "logs-to-s3"
    ],
    "year": 2025,
    "month": 12,
    "day": 3
  },
  "log_event": {
    "id": "657689771374632572378173045471188406392782962573476446469",
    "timestamp": 1764720360000,
    "message_parsed": {
      "body": "claude_code.user_prompt",
      "attributes": {
        "event.timestamp": "2025-12-03T00:06:00.000Z",
        "organization.id": "27d80e08-3d7f-4b6a-a457-5cc58629ce8b",
        "session.id": "678c4a9e-4362-404e-89c7-1c8abb91226c",
        "terminal.type": "vscode",
        "user.account_uuid": "f0af77a2-8307-4b95-b5f9-e99f6ce34b26",
        "user.email": "blake.patel@example.com",
        "user.id": "4ba41b6cc8bf83a2096c4bcd7c735f5dc746824a6153f5e0f9b359f3ee50b7a7",
        "event.name": "user_prompt",
        "prompt": "<REDACTED>",
        "prompt_length": "420"
      },
      "scope": {
        "name": "com.anthropic.claude_code.events",
        "version": "2.1.45"
      },
      "resource": {
        "host.arch": "x86_64",
        "host.name": "Blakes-MacBook-Pro.local",
        "os.type": "linux",
        "os.version": "6.1.0",
        "service.name": "claude-code-None",
        "service.version": "2.1.45",
        "user.email": "",
        "user.practice": "Frontend Engineering",
        "user.profile": "patel",
        "user.serial": "WN2Y8FV2BC"
      }
    }
  }
}

====================================================
OUTPUT FORMAT
====================================================

Generate:
- all files
- full code
- docker config
- ETL scripts
- dashboard
- API

Everything should be ready to run.
```

#### Prompt 2 — *Data generation and verification*

```
Please follow these steps carefully and provide clear, structured output.

1. Review the project documentation located at:
   claude_code_telemetry2/README.md (from the repository root)

   The README contains instructions for generating synthetic telemetry data using the script:
   generate_fake_data.py

2. Execute the data generation script using the recommended parameters:
   --num-users 100
   --num-sessions 5000
   --days 60

   Ensure the data is successfully generated before proceeding.

3. After generation, load the produced dataset and extract a single complete record.

4. Present the record in a clean, human-readable, fully formatted JSON structure:
   - Do NOT redact or replace any fields with placeholders
   - Preserve all nested structure and attributes exactly as generated
   - Format the output for readability (proper indentation, key ordering if applicable)

5. The goal is to inspect and understand the schema and structure of the telemetry events, so ensure the output is accurate and complete.

Return only:
- Confirmation that data generation succeeded
- One fully formatted example record
```

*For comparison: [From clone to Streamlit](#from-clone-to-streamlit-docker) uses `--num-sessions 2000` for a quicker first run; this prompt used `--num-sessions 5000` for a larger verification sample.*

#### Prompt 3 — *Example of Debugging the error cause*

```
We are observing a critical data inconsistency in the analytics dashboard.

Current state:
- Distinct users: 1
- Sessions: 1
- Events: 1
- Total tokens: 0

This indicates a systemic issue in the data pipeline rather than a UI problem.

====================================================
OBJECTIVE
====================================================

Identify and permanently resolve the root cause across the full data flow:

ingestion → normalization → persistence → analytics → API → dashboard

The fix must address the underlying issue, not just patch symptoms.

====================================================
INVESTIGATION REQUIREMENTS
====================================================

Perform a structured, end-to-end validation of the pipeline:

1. Data Generation
   - Verify that synthetic data contains diverse users, sessions, and token values
   - Confirm that generated records are non-trivial and correctly distributed

2. Ingestion Layer
   - Ensure all records are being read (not overwritten or truncated)
   - Validate parsing logic for nested JSON (logEvents.message)
   - Confirm batch ingestion processes all events, not just one

3. Normalization & Validation
   - Check field extraction (user_email, session_id, tokens, timestamps)
   - Verify type conversions (strings → numeric fields)
   - Ensure no silent failures or dropped records
   - Validate Pydantic schemas are correctly applied

4. Database Layer (PostgreSQL)
   - Inspect raw and normalized tables
   - Confirm row counts match expected ingestion volume
   - Validate token fields are populated and not defaulting to zero
   - Check for accidental overwrites or primary key collisions

5. Analytics Layer
   - Validate aggregation queries (GROUP BY, SUM, COUNT)
   - Ensure filters and joins are correct
   - Confirm queries return realistic distributions

6. API Layer (Gateway → Analytics Service)
   - Verify endpoints return correct aggregated data
   - Inspect responses for incorrect defaults or truncation

7. Dashboard Layer
   - Confirm API responses are rendered correctly
   - Ensure no client-side filtering reduces dataset unintentionally

====================================================
EXPECTED OUTCOME
====================================================

- Correct counts for users, sessions, and events
- Non-zero and realistic token values
- Proper distributions across time, roles, and sessions
- Dashboard reflecting actual underlying data

====================================================
IMPORTANT
====================================================

- Do not apply superficial fixes at the UI layer
- Root cause must be identified and resolved at the correct layer
- Add logging and validation checks where needed
- Ensure the fix is robust and prevents regression

Return:
- Root cause analysis
- Specific fixes applied
- Verification results after correction
```

### How AI-generated output was validated

| Validation | What we did |
|------------|-------------|
| **Automated tests** | `pytest` (unit + mocked gateway; optional PostgreSQL integration). See [How to test that everything works](#how-to-test-that-everything-works). |
| **Manual / smoke** | Docker Compose stack, health endpoints, `/metrics`, and Streamlit UI checks documented in the same testing section. |
| **Code review** | Human review of diffs before merge; alignment with [CODING_GUIDELINES.md](CODING_GUIDELINES.md). |
| **Iterative fixes** | When behavior was wrong (e.g. empty KPIs, session rebuild), we reproduced the issue, adjusted prompts or code, and re-ran tests and containers until checks passed. |

---

## Git workflow (optional)

Short-lived feature branches, merge to `main` after checks; keep commits small and traceable.

---

## Coding standards

See [CODING_GUIDELINES.md](CODING_GUIDELINES.md).

---

## License

See [LICENSE](LICENSE).
