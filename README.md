# SmartVoter

> **Evidence-based political match web app for Israeli parliamentary parties.**
>
> *"This tool compares your policy preferences with parties' observed parliamentary behavior and declared positions. It does not tell you whom to vote for."*

---

## What is SmartVoter?

SmartVoter is a civic analytics platform — not a political quiz. It uses real Knesset voting records, sponsored bills, party platforms, candidate histories, and LLM-assisted classification to compute a **transparent, probabilistic similarity score** between a user's stated policy preferences and each party's observed behavior.

Key principles:
- **Evidence first**: parliamentary votes outweigh platform declarations.
- **Confidence is separate from match**: a 78% match with low confidence is shown differently from a 72% match with high confidence.
- **New parties are not excluded**: they get lower-confidence scores based on candidate history, lineage, and declared positions.
- **Uncertainty is always visible**: sparse evidence, high volatility, and new-party status are shown explicitly.
- **No voting advice**: the app shows similarity, disagreement, evidence, and uncertainty — never "vote for this party".

---

## Current status

**Phases 1–8 and 14B complete. Phase 14C (privacy, accessibility, auditing) partially implemented.**

| Feature | Status |
|---|---|
| Adaptive questionnaire | ✅ Phase-based, convergence-driven (8–40 questions) |
| Party match scoring | ✅ Match + confidence + evidence + volatility |
| Party lineage & candidate volatility | ✅ Mock data with real-data import support |
| Results visualisations | ✅ Radar chart, heatmap, evidence bars, lineage timeline |
| Knesset seat simulation | ✅ Monte Carlo, threshold risk, coalition scenarios |
| Live poll refresh via OpenAI | ✅ Web search on startup (daily, optional) |
| Real Knesset data ingestion | ✅ Knessets 1–24 votes, bills, persons, factions |
| LLM pipeline (questions, positions, lineage) | ✅ Mock provider + OpenAI GPT-4o-mini |
| Admin review panel | ✅ Password-protected, full audit trail |
| i18n: English / Hebrew / Russian | ✅ UI complete; question content needs native review |
| Privacy (anonymous sessions, delete-session) | ✅ |
| Accessibility | 🔄 WCAG AA target, partial |

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| [uv](https://github.com/astral-sh/uv) | latest | Python package manager — replaces pip/poetry |
| Python | 3.14 | Pinned via `.python-version`; managed by `uv` |
| Node.js | 20+ | For the Next.js frontend |
| Docker Desktop | latest | Runs PostgreSQL, Redis, backend, frontend |
| PowerShell | 7+ (`pwsh`) | Windows development shell |

---

## Quick start

### Option A — one-command (recommended)

```powershell
.\run.bat
```

`run.bat` automatically:
1. Checks prerequisites (uv, Docker)
2. Copies `.env.example → .env` if missing
3. Runs `uv sync` (installs Python dependencies into `.venv`)
4. Starts PostgreSQL + Redis via Docker Compose
5. Waits for PostgreSQL to become healthy
6. Runs Alembic migrations (`upgrade head`)
7. Seeds mock data (idempotent — safe to re-run)
8. Builds and starts the backend and frontend containers
9. Opens the browser at `http://localhost:3000`

**Requires Docker Desktop to be running.**

---

### Option B — manual (backend only, no Docker for services)

```powershell
# 1. Copy and configure environment
Copy-Item .env.example .env
# Edit .env → set ADMIN_PASSWORD, SECRET_KEY, DATABASE_URL, optionally OPENAI_API_KEY

# 2. Install Python dependencies
uv sync

# 3. Start PostgreSQL and Redis (Docker is simplest)
docker compose up -d postgres redis

# 4. Apply DB migrations
uv run alembic upgrade head

# 5. Seed mock data
uv run python -m backend.app.seed.run_seed

# 6. Start the FastAPI backend
uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend: **http://localhost:8000** | API docs: **http://localhost:8000/docs**

```powershell
# 7. Start the Next.js frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Frontend: **http://localhost:3000**

---

### Option C — full Docker Compose stack

```powershell
# First run: copy and configure .env
Copy-Item .env.example .env   # then edit ADMIN_PASSWORD and SECRET_KEY

# Build and start all services (postgres + redis + backend + frontend)
docker compose up --build

# First-time data initialisation (run once in a separate terminal)
docker compose --profile init up data-init
```

The `data-init` service applies migrations and seeds mock data automatically.

---

## Importing real Knesset data

Real data can be imported from the Knesset OData API via the admin panel or the CLI.

**Notes on data availability (as of May 2026):**
- **Votes**: available for Knessets 1–24 only (`Votes.svc`). Knessets 25–26 return empty results.
- **Bills, persons, factions**: available for all Knessets via `ParliamentInfo.svc`.

```powershell
# Probe vote availability for a specific Knesset number
# GET /api/admin/ingest/probe-votes/{knesset_number}

# Trigger ingestion via HTTP (or use the Admin → Knesset Ingestion tab in the UI)
# POST /api/admin/ingest/knesset
# Body: {"knesset_number": 24, "limit": 1000, "votes_only": false, "bills_only": false, "no_llm": true}
```

---

## Live polling (OpenAI web search)

When `OPENAI_API_KEY` is configured, the app automatically refreshes Israeli opinion polls on startup (at most once per day) using the OpenAI Responses API with `web_search_preview`.

- Results are stored in `polls` / `poll_party_results` tables
- Used by the simulation engine as the primary polling input
- To refresh manually: `POST /api/admin/polling/refresh` (admin auth required)
- To disable: leave `OPENAI_API_KEY` empty — mock seed polls are used instead

---

## Admin panel

Navigate to **http://localhost:3000/admin**. Enter the admin password set in `.env`.

The password is sent as the `X-Admin-Password` HTTP header and stored in `sessionStorage` only — never in cookies or analytics.

| Admin capability | Description |
|---|---|
| Review queue | Approve / reject / edit LLM-generated questions |
| Generate questions | Trigger LLM question generation per policy item or batch |
| Generate root questions | Create one broad survey question per topic |
| LLM audit log | Full history of every LLM call with inputs, outputs, confidence |
| Knesset ingestion | Import real votes, bills, persons, factions from OData API |
| Full pipeline | Multi-Knesset import + analysis pipeline wizard |
| Available data summary | Shows what Knessets are already in the DB |
| Database backup / restore | Download / upload full JSON snapshot |
| Polling refresh | Manually trigger live poll update via OpenAI web search |

---

## Adaptive questionnaire

The questionnaire uses a **phase-based convergence model** — not a fixed question count.

### Phase 1 — Survey (breadth)
Covers all 15 topics with exactly one question each. Root questions (broad, topic-level) are served first. Topics not yet covered get near-infinite priority, enforcing breadth before depth.

### Phase 2 — Depth (salience-driven)
Follows the user's expressed interest (salience). Topics marked "Very important" get up to 2× more follow-up questions. Topics marked "Not important" are deprioritised. Re-asking the same *policy item* is blocked unless the user rated it Very Important.

### Stopping conditions
- **Minimum**: 8 questions answered
- **Soft stop**: convergence banner shown when ranking stability ≥ 80% AND all topics covered → user chooses "see results" or "keep going"
- **Hard maximum**: 40 questions (server-enforced)

The progress bar shows:
- **Survey phase** (brand blue): topics covered / total
- **Depth phase** (indigo): answered count / hard max
- **Convergence stability** percentage in real time

---

## Scoring model

### Match score
```
distance        = |user_position − party_position|    ∈ [0, 2]
similarity      = 1 − distance / 2                    ∈ [0, 1]
weighted_sim    = similarity × user_salience × evidence_strength
match_score     = Σ(weighted_sim) / Σ(user_salience × evidence_strength)
```

### Confidence score
```
confidence = evidence_strength × coverage_score × (1 − volatility_penalty) × answer_stability
```

### Evidence reliability priors

| Source | Weight |
|---|---|
| Parliamentary vote | 1.00 |
| Sponsored bill | 0.80 |
| Committee behavior | 0.70 |
| Candidate past vote | 0.55 |
| Party lineage | 0.50 |
| Coalition agreement | 0.45 |
| Party platform | 0.35 |
| Public statement | 0.25 |
| Media interview | 0.20 |

### New-party position formula
```
position = 0.45 × candidate_history
         + 0.25 × party_lineage_prior
         + 0.20 × official_platform
         + 0.10 × public_statements
```
New parties always display a low-confidence warning.

---

## Knesset simulation (Phase 14B)

The **Election Simulator** (`/simulation`) is a separate analytical tool — independent from personal matching.

- **Monte Carlo**: 5,000 iterations by default, samples vote shares from polling distributions
- **Threshold filtering**: configurable electoral threshold (currently 3.25%)
- **Seat allocation**: D'Hondt method (simplified)
- **Uncertainty intervals**: p10 / p25 / p50 / p75 / p90 for each party
- **Threshold-pass probability**: per small party
- **Coalition scenarios**: viable coalitions (≥ 61 seats) scored by feasibility, stability, ideological coherence
- **Party lineage**: renames, mergers, splits handled via `party_lineage_edges`
- **Volatility widening**: volatile and new parties get wider forecast intervals

Visual components:
- Knesset semicircle chart (120 seats)
- Seat distribution bars with uncertainty bands
- Threshold risk panel
- Coalition scenario cards with member breakdown
- Assumptions and data-cutoff drawer

---

## Running tests

```powershell
uv run pytest
```

| Test file | Coverage |
|---|---|
| `test_scoring.py` | Match score, confidence, coverage, answer stability |
| `test_questionnaire.py` | Phase selection, salience follow-up, convergence, stop conditions, values-discovery scenarios (39 tests) |
| `test_seat_allocator.py` | D'Hondt allocation, threshold edge cases, near-threshold parties |
| `test_pipelines.py` | LLM pipeline integration stubs |

---

## API reference

### Public API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/topics` | List all topics |
| `POST` | `/api/sessions` | Create / get anonymous session |
| `GET` | `/api/questions/next?session_id=…` | Next adaptive question (with convergence metadata) |
| `POST` | `/api/answers` | Submit an answer |
| `GET` | `/api/results/{session_id}` | Full match results with evidence |
| `DELETE` | `/api/sessions/{session_id}` | Delete session (privacy) |
| `GET` | `/api/methodology` | Scoring methodology JSON |
| `GET` | `/api/lineage` | Party lineage graph |
| `GET` | `/api/parties` | List parties |
| `GET` | `/api/parties/{id}` | Party detail + positions + lineage |
| `GET` | `/api/parties/{id}/evidence` | Evidence items for a party |
| `GET` | `/api/persons` | List persons/candidates |
| `GET` | `/api/persons/{id}` | Person detail + membership history |
| `GET` | `/api/votes` | List votes (filterable by Knesset) |
| `GET` | `/api/votes/{id}` | Vote detail + MK-level results |
| `GET` | `/api/bills` | List bills |
| `GET` | `/api/bills/{id}` | Bill detail |
| `GET` | `/api/simulation/latest` | Latest simulation run |
| `POST` | `/api/simulation/run` | Trigger new simulation |
| `GET` | `/api/simulation/knesset/current` | Current Knesset seat composition |
| `POST` | `/api/simulation/coalition/evaluate` | Evaluate a custom coalition |

### Admin API (🔒 requires `X-Admin-Password` header)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/admin/review/items` | List questions pending review |
| `POST` | `/api/admin/review/{id}/approve` | Approve a question |
| `POST` | `/api/admin/review/{id}/reject` | Reject a question |
| `PATCH` | `/api/admin/review/{id}/edit` | Edit question text |
| `POST` | `/api/admin/review/bulk-approve` | Bulk approve by status filter |
| `GET` | `/api/admin/policy-items` | List policy items |
| `POST` | `/api/admin/llm/generate-questions` | Generate questions for policy items |
| `POST` | `/api/admin/llm/generate-root-question` | Generate root question for a topic |
| `POST` | `/api/admin/llm/generate-all-root-questions` | Batch root question generation (background job) |
| `GET` | `/api/admin/llm/generate-all-root-questions/status/{job_id}` | Job status |
| `GET` | `/api/admin/llm/outputs` | LLM audit log |
| `POST` | `/api/admin/ingest/knesset` | Trigger Knesset data ingestion (background job) |
| `GET` | `/api/admin/ingest/status/{job_id}` | Check ingestion job status |
| `GET` | `/api/admin/ingest/jobs` | List recent ingestion jobs |
| `GET` | `/api/admin/ingest/available-data` | Summary of what data is in the DB |
| `POST` | `/api/admin/ingest/full-pipeline` | Multi-Knesset full pipeline |
| `GET` | `/api/admin/ingest/probe-votes/{knesset_number}` | Check vote availability |
| `POST` | `/api/admin/polling/refresh` | Refresh live polls via OpenAI web search |
| `GET` | `/api/admin/topics/with-root-questions` | Topics + root question status |
| `POST` | `/api/admin/questions/manual` | Create a question manually |
| `GET` | `/api/admin/db/backup` | Download full DB backup (JSON) |
| `POST` | `/api/admin/db/restore` | Restore from backup file |

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://smartvoter:smartvoter@localhost:5432/smartvoter` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis (rate limiting) |
| `SECRET_KEY` | `change-me-in-production` | Session signing key |
| `ADMIN_PASSWORD` | `change-me-admin` | Admin panel password — **change before deployment** |
| `APP_ENV` | `development` | `development` or `production` |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins (comma-separated) |
| `OPENAI_API_KEY` | *(empty)* | OpenAI key — mock provider used when empty |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model for LLM pipeline |
| `CURRENT_KNESSET` | `26` | Current Knesset number |
| `LAST_KNESSET_WITH_VOTES` | `24` | Last Knesset with votes data in OData API |

Copy `.env.example` to `.env` and fill in the values before starting.

---

## Internationalisation

| Language | Code | Direction | Status |
|---|---|---|---|
| English | `en` | LTR | ✅ Complete |
| Hebrew | `he` | RTL | ✅ UI translated; question/party content needs native review |
| Russian | `ru` | LTR | ✅ UI translated; question/party content needs native review |

- Language preference stored in `localStorage` key `sv_lang`
- `<html lang>` and `<html dir>` updated automatically; Hebrew uses `dir="rtl"`
- Tailwind logical properties (`ms-`, `me-`, `ps-`, `pe-`) used in place of `ml-`/`mr-`
- All UI strings live in `frontend/locales/{en,he,ru}.ts` — never hardcoded in components
- Politically sensitive terms use `frontend/locales/glossary.ts` for consistent translation

---

## Project structure

```
SmartVoter/
├── backend/
│   ├── app/
│   │   ├── main.py                  ← FastAPI app, lifespan, rate limiting, startup poll refresh
│   │   ├── config.py                ← Settings (pydantic-settings), reads .env
│   │   ├── admin/__init__.py        ← All admin endpoints (password-protected)
│   │   ├── api/                     ← Public API routers
│   │   │   ├── answers.py  questions.py  sessions.py  results.py
│   │   │   └── topics.py  simulation.py  lineage.py  methodology.py  public.py
│   │   ├── db/                      ← SQLAlchemy engine, session, Base
│   │   ├── models/                  ← 18+ SQLAlchemy Mapped models
│   │   ├── schemas/                 ← Pydantic request/response schemas
│   │   └── services/
│   │       ├── scoring/engine.py    ← Match + confidence scoring (pure functions)
│   │       ├── questionnaire/       ← Phase-based adaptive selector + convergence tracking
│   │       ├── llm/                 ← Provider abstraction (mock + OpenAI + fallback + audit)
│   │       ├── ingestion/           ← Knesset OData importers, LLM analysis pipelines
│   │       ├── simulation/          ← Monte Carlo simulator, seat allocator, coalition engine
│   │       ├── polling/             ← OpenAI web search poll aggregator
│   │       ├── lineage/             ← Lineage prior computation
│   │       └── volatility/          ← Party and candidate volatility scoring
│   ├── seed/
│   │   ├── run_seed.py              ← Seeds mock data (idempotent)
│   │   └── data/                    ← JSON: topics, parties, questions, polls, persons, etc.
│   ├── tests/                       ← pytest unit tests
│   └── alembic/versions/            ← 5 DB migrations applied
├── frontend/
│   ├── app/                         ← Next.js App Router pages
│   │   ├── page.tsx                 ← Onboarding / home
│   │   ├── questionnaire/           ← Adaptive questionnaire with convergence UX
│   │   ├── results/                 ← Match results + visualisations
│   │   ├── simulation/              ← Knesset seat simulation
│   │   ├── methodology/             ← Methodology explanation
│   │   ├── admin/                   ← Admin review panel
│   │   └── parties/ persons/ votes/ bills/  ← Public evidence browser
│   ├── components/
│   │   ├── NavHeader.tsx  EvidenceDrawer.tsx  CoalitionBuilder.tsx
│   │   ├── LanguageSwitcher.tsx  PrivacyBanner.tsx  Tooltip.tsx
│   │   └── charts/
│   │       ├── TopicRadarChart.tsx  PartyPolicyHeatmap.tsx
│   │       ├── EvidenceCompositionBar.tsx  ConfidenceBreakdownBar.tsx
│   │       ├── PartyLineageTimeline.tsx  SeatDistributionChart.tsx
│   │       ├── KnessetSemicircleChart.tsx  KnessetSpectrumBar.tsx
│   │       └── MatchScoreRing.tsx
│   ├── lib/
│   │   ├── api.ts                   ← Typed API client (all public + admin endpoints)
│   │   ├── i18n.tsx                 ← I18nProvider, useT(), useLang()
│   │   ├── session.ts               ← Anonymous session management
│   │   └── utils.ts                 ← Shared helpers
│   └── locales/
│       ├── types.ts                 ← Shared Translations TypeScript interface
│       ├── en.ts  he.ts  ru.ts      ← Full locale files
│       └── glossary.ts              ← Political/legal term translations
├── alembic/                         ← Root-level Alembic config (mounted by Docker)
├── docs/                            ← Methodology, data sources, scoring docs
├── docker-compose.yml               ← Dev stack (postgres + redis + backend + frontend + data-init)
├── docker-compose.prod.yml          ← Production variant
├── pyproject.toml                   ← uv-managed Python 3.14 project
├── alembic.ini
├── .env.example                     ← Copy to .env and configure
├── run.bat                          ← Windows one-command launcher
└── AGENTS.MD                        ← Source of truth for coding agents
```

---

## Data model

| Table | Purpose |
|---|---|
| `political_brands` | Long-lived political identity (not tied to election cycle) |
| `party_instances` | Concrete party/list in a specific Knesset or election |
| `party_lineage_edges` | Rename / split / merger / successor relationships with continuity weights |
| `persons` | MKs, candidates, ministers, founders |
| `person_party_memberships` | Party membership over time with role and confidence |
| `bills` | Legislative initiatives with LLM summaries |
| `votes` | Plenary votes with importance and signal-quality scores |
| `vote_results` | Per-MK vote values (for / against / abstain / absent) |
| `topics` | 15 policy topic areas |
| `policy_items` | Normalised positions on directional axes (−1 to +1) |
| `party_positions` | Party position per policy item with evidence and uncertainty |
| `questions` | Questionnaire questions with review status |
| `user_sessions` | Anonymous session UUIDs |
| `user_answers` | Per-question responses with salience |
| `recommendation_runs` | Scored result snapshots per session |
| `llm_audit` | Full LLM input/output audit trail (model, prompt version, input hash, confidence) |
| `polls` / `poll_party_results` | Current opinion polls (live web search or seeded) |
| `simulation_runs` / `simulation_party_results` | Monte Carlo seat forecast outputs |
| `coalition_scenarios` / `coalition_scenario_members` | Viable coalition candidates |

---

## Architecture

```
User answers
    ↓
Policy axes  (positions on −1 … +1 per policy item)
    ↓
Party latent positions  (weighted aggregate of votes, bills, candidate history, lineage, platform)
    ↓
Evidence strength weighting  (votes=1.0 … media interviews=0.2)
    ↓
Volatility & uncertainty modeling  (candidate turnover, party splits, new-party penalty)
    ↓
match_score + confidence_score  per party
    ↓
Results page: ranked parties, evidence drawer, representation gap, strategic context
```

Simulation engine (runs independently):

```
Live polls (OpenAI web search) + historical election results
    ↓
Weighted poll aggregate  (recency decay, sample-size weighting, pollster reliability)
    ↓
Monte Carlo sampling  (Normal / Dirichlet vote-share draws × 5,000 iterations)
    ↓
Threshold filtering + D'Hondt seat allocation  (per iteration)
    ↓
p10/p25/p50/p75/p90 seat distributions + coalition feasibility scores
```

---

## Contributing

1. Read [`AGENTS.MD`](AGENTS.MD) — it is the authoritative specification for all coding agents and contributors.
2. Run `uv run pytest` before submitting changes — all 39+ tests must pass.
3. All UI strings must be added to `locales/types.ts`, `en.ts`, `he.ts`, and `ru.ts`.
4. Never hardcode political claims in UI components — all claims must trace to DB records.
5. All LLM outputs must be stored with prompt version, input hash, model, and confidence.
6. Questions must have `human_review_status = approved` before appearing in the public questionnaire.
7. Use `uv add <package>` to add dependencies — do not use `pip` directly.

---

## License

Private repository — all rights reserved. Not licensed for redistribution or public deployment without explicit permission.

---

*See [AGENTS.MD](AGENTS.MD) for the full product specification, data model, scoring formulas, LLM pipeline, simulation model, and implementation phase plan.*
