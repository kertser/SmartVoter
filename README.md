# SmartVoter

Evidence-based political match web app for Israeli parties.

> This tool compares your policy preferences with parties' observed parliamentary behavior and declared positions. **It does not tell you whom to vote for.**

## Current status

**Phase 1–8 (partial)** — local mock MVP with i18n.

- 5 mock parties, 20 policy items, 40 questions, 10 persons
- Party lineage & candidate volatility examples
- Adaptive questionnaire (8–15 questions)
- Results page with match, confidence, evidence, volatility, lineage
- Admin review panel (password-protected)
- LLM abstraction with mock provider and GPT-4o-mini support
- i18n: English ✓ | Hebrew (UI complete, content needs review) | Russian (UI complete, content needs review)

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
1. Checks prerequisites (uv, Docker)
2. Copies `.env.example → .env` if missing
3. Runs `uv sync` (Python dependencies)
4. Starts PostgreSQL + Redis via Docker Compose
5. Waits for PostgreSQL to become healthy
6. Runs Alembic migrations
7. Seeds mock data (idempotent)
8. Builds and starts the backend and frontend containers
9. Waits for the frontend to compile, then opens the browser

Requires: **Docker Desktop running** and `uv`.

### Manual start

```powershell
# Copy environment config and set your admin password
Copy-Item .env.example .env
# Edit .env → set ADMIN_PASSWORD, SECRET_KEY, optionally OPENAI_API_KEY

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
Copy-Item .env.example .env   # then edit ADMIN_PASSWORD and SECRET_KEY

# Build and start all services
docker compose up --build

# In another terminal, run migrations and seed data
docker compose exec backend uv run alembic upgrade head
docker compose exec backend uv run python -m backend.app.seed.run_seed
```

## Admin panel

Navigate to `http://localhost:3000/admin`. You will be prompted for the admin password.

The password is set via the `ADMIN_PASSWORD` environment variable in `.env`  
(default: `change-me-admin` — **change this before any deployment**).

The password is sent as `X-Admin-Password` header to the backend and is stored  
in `sessionStorage` only — never in cookies or analytics.

Admin capabilities:
- Review and approve / reject / edit LLM-generated questions
- Trigger LLM question generation for policy items
- Browse the full LLM audit log

## Running tests

```powershell
uv run pytest
```

All unit tests cover:
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
| `GET /api/lineage` | Party lineage graph |
| `GET /api/parties/{id}/evidence` | Evidence for a party |
| `GET /api/admin/review/items` | Admin: list questions (🔒 password required) |
| `POST /api/admin/review/{id}/approve` | Admin: approve question (🔒) |
| `POST /api/admin/review/{id}/reject` | Admin: reject question (🔒) |
| `PATCH /api/admin/review/{id}/edit` | Admin: edit question text (🔒) |
| `POST /api/admin/llm/generate-questions` | Admin: generate LLM questions (🔒) |
| `GET /api/admin/llm/outputs` | Admin: LLM audit log (🔒) |

## Internationalisation (i18n)

| Language | Code | Direction | Status |
|---|---|---|---|
| English | `en` | LTR | Complete |
| Hebrew | `he` | RTL | UI translated; question/party content needs native review |
| Russian | `ru` | LTR | UI translated; question/party content needs native review |

Language is stored in `localStorage` key `sv_lang`. The `<html dir>` attribute  
is updated automatically (Hebrew uses `dir="rtl"`).

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://…` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `SECRET_KEY` | `change-me-in-production` | JWT / session signing key |
| `ADMIN_PASSWORD` | `change-me-admin` | Admin panel password |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins (comma-separated) |
| `OPENAI_API_KEY` | *(empty)* | OpenAI key — mock provider used when empty |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |

## Project structure

```
SmartVoter/
  backend/
    app/
      main.py              ← FastAPI app entry point
      config.py            ← Settings (pydantic-settings) including ADMIN_PASSWORD
      db/                  ← SQLAlchemy engine, session, Base
      models/              ← All 18 SQLAlchemy models
      schemas/             ← Pydantic request/response schemas
      api/                 ← FastAPI route handlers
      admin/               ← Password-protected admin review endpoints
      services/
        scoring/           ← Match + confidence scoring engine
        questionnaire/     ← Adaptive next-question selector
        llm/               ← LLM provider abstraction (mock + OpenAI)
        lineage/           ← Lineage prior stub
        volatility/        ← Volatility stub
      seed/                ← Mock data + seed runner
      tests/               ← pytest unit tests
    alembic/               ← DB migrations
    Dockerfile
  frontend/
    app/                   ← Next.js App Router pages
    components/            ← Reusable React components (Tooltip, EvidenceDrawer, charts…)
    lib/
      api.ts               ← Typed API client (includes admin password helpers)
      i18n.tsx             ← I18nProvider, useT(), useLang()
      session.ts           ← Anonymous session management
      utils.ts             ← Helper functions
    locales/               ← en.ts / he.ts / ru.ts / types.ts
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
