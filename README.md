# SmartVoter

Evidence-based political match web app for Israeli parties.

> This tool compares your policy preferences with parties' observed parliamentary behavior and declared positions. **It does not tell you whom to vote for.**

## Current status

**Phase 1** — local mock MVP. 5 mock parties, 20 policy items, 40 questions, 10 persons, party lineage examples, adaptive questionnaire, results page, admin review API.

## Prerequisites

- Windows + PowerShell
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- Python 3.14 (pinned via `.python-version`, managed by uv)
- Node.js 20+
- Docker Desktop (for the full stack via Compose)
- PostgreSQL 16 (locally or via Docker)

## Quick start — local development

### One-command start (recommended)

```powershell
.\run.bat
```

`run.bat` does everything automatically:
1. Checks prerequisites (uv, Docker, Node.js)
2. Copies `.env.example → .env` if missing
3. Runs `uv sync`
4. Starts PostgreSQL + Redis via Docker Compose
5. Runs Alembic migrations
6. Seeds mock data (idempotent)
7. Installs frontend npm packages
8. Opens backend and frontend in separate terminal windows

Requires: **Docker Desktop running**, uv, Node.js 20+.

### Manual start

```powershell
# Copy environment config
Copy-Item .env.example .env

# Install dependencies (creates .venv automatically)
uv sync

# Start PostgreSQL (via Docker is simplest)
docker compose up -d postgres redis

# Apply DB migrations
uv run alembic upgrade head

# Seed mock data (idempotent)
uv run python -m backend.app.seed.run_seed

# Start the FastAPI server (with auto-reload)
uv run uvicorn backend.app.main:app --reload
```

Backend will be available at: http://localhost:8000
API docs: http://localhost:8000/docs

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend will be available at: http://localhost:3000

### 3. Full stack via Docker Compose

```powershell
# First run
Copy-Item .env.example .env

# Build and start all services
docker compose up --build

# In another terminal, run migrations and seed data
docker compose exec backend uv run alembic upgrade head
docker compose exec backend uv run python -m backend.app.seed.run_seed
```

## Running tests

```powershell
uv run pytest
```

All 20 unit tests cover:
- Scoring engine (match score, confidence, coverage, stability)
- Adaptive questionnaire selector (diversity penalty, party separation, stop conditions)

## API endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Health check |
| `GET /api/topics` | List all topics |
| `POST /api/sessions` | Create/get anonymous session |
| `GET /api/questions/next?session_id=...` | Get next adaptive question |
| `POST /api/answers` | Submit an answer |
| `GET /api/results/{session_id}` | Get match results |
| `GET /api/methodology` | Scoring methodology JSON |
| `GET /api/admin/review/items` | Admin: list unreviewed questions |
| `POST /api/admin/review/{id}/approve` | Admin: approve question |
| `POST /api/admin/review/{id}/reject` | Admin: reject question |

## Project structure

```
SmartVoter/
  backend/
    app/
      main.py              ← FastAPI app entry point
      config.py            ← Settings (pydantic-settings)
      db/                  ← SQLAlchemy engine, session, Base
      models/              ← All 18 SQLAlchemy models
      schemas/             ← Pydantic request/response schemas
      api/                 ← FastAPI route handlers
      admin/               ← Admin review endpoints
      services/
        scoring/           ← Match + confidence scoring engine
        questionnaire/     ← Adaptive next-question selector
        llm/               ← LLM provider abstraction (mock for Phase 1)
        lineage/           ← Lineage prior stub
        volatility/        ← Volatility stub
      seed/                ← Mock data + seed runner
      tests/               ← pytest unit tests
    alembic/               ← DB migrations
    Dockerfile
  frontend/
    app/                   ← Next.js App Router pages
    components/            ← Reusable React components
    lib/
      api.ts               ← Typed API client
      session.ts           ← Anonymous session management
      utils.ts             ← Helper functions
    Dockerfile
  docker-compose.yml
  .env.example
  alembic.ini
  pyproject.toml           ← uv-managed Python project
  AGENTS.MD                ← Source of truth for coding agents
```

## Architecture

```
User answers
    ↓
Policy axes (positions on −1 to +1 axes)
    ↓
Party latent positions (inferred from votes, bills, platforms, lineage)
    ↓
Evidence strength weighting (votes > bills > platform > statements)
    ↓
Volatility / uncertainty modeling
    ↓
Transparent probabilistic match + confidence scores
```

See [AGENTS.MD](AGENTS.MD) for full product specification and implementation phases.

