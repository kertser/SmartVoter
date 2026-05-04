@echo off
setlocal enabledelayedexpansion

echo.
echo  ==========================================
echo   SmartVoter -- Development Start Script
echo  ==========================================
echo.

:: ── Check uv ──────────────────────────────────────────────────────────────
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] uv not found. Install it from https://github.com/astral-sh/uv
    pause
    exit /b 1
)

:: ── Check Docker ──────────────────────────────────────────────────────────
where docker >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

:: ── Check Node ────────────────────────────────────────────────────────────
where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js not found. Install Node.js 20+ from https://nodejs.org
    pause
    exit /b 1
)

:: ── Copy .env if missing ──────────────────────────────────────────────────
if not exist ".env" (
    echo [INFO] .env not found -- copying from .env.example
    copy ".env.example" ".env" >nul
)

:: ── Python dependencies ───────────────────────────────────────────────────
echo [1/6] Syncing Python dependencies...
uv sync --quiet
if %ERRORLEVEL% neq 0 (
    echo [ERROR] uv sync failed.
    pause
    exit /b 1
)
echo       Done.

:: ── Start Docker services (postgres + redis) ────────────────────────────
echo [2/6] Starting PostgreSQL and Redis via Docker Compose...
docker compose up -d postgres redis
if %ERRORLEVEL% neq 0 (
    echo [ERROR] docker compose up failed. Is Docker Desktop running?
    pause
    exit /b 1
)

:: ── Wait for postgres to be ready ────────────────────────────────────────
echo [3/6] Waiting for PostgreSQL to be ready...
set /a attempts=0
:wait_loop
set /a attempts+=1
if %attempts% gtr 30 (
    echo [ERROR] PostgreSQL did not become ready after 30 seconds.
    pause
    exit /b 1
)
docker compose exec -T postgres pg_isready -U smartvoter -d smartvoter >nul 2>&1
if %ERRORLEVEL% neq 0 (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)
echo       PostgreSQL is ready.

:: ── Run Alembic migrations ────────────────────────────────────────────────
echo [4/6] Running database migrations...
uv run alembic upgrade head
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Alembic migration failed.
    pause
    exit /b 1
)
echo       Migrations applied.

:: ── Seed mock data (idempotent) ──────────────────────────────────────────
echo [5/6] Seeding mock data (skipped if already seeded)...
uv run python -m backend.app.seed.run_seed
echo       Done.

:: ── Frontend dependencies ────────────────────────────────────────────────
echo [6/6] Installing frontend dependencies...
cd frontend
npm install --silent
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npm install failed.
    cd ..
    pause
    exit /b 1
)
cd ..
echo       Done.

:: ── Launch backend in a new window ──────────────────────────────────────
echo.
echo  Starting services...
echo.
start "SmartVoter Backend (http://localhost:8000)" cmd /k "uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000"

:: ── Launch frontend in a new window ─────────────────────────────────────
start "SmartVoter Frontend (http://localhost:3000)" cmd /k "cd frontend && npm run dev"

:: ── Done ─────────────────────────────────────────────────────────────────
echo  [OK] All services started in separate windows:
echo.
echo        Frontend  -->  http://localhost:3000
echo        Backend   -->  http://localhost:8000
echo        API docs  -->  http://localhost:8000/docs
echo.
echo  Close those windows (or Ctrl+C inside them) to stop the servers.
echo  PostgreSQL and Redis continue running in Docker.
echo  To stop Docker:  docker compose down
echo.
pause

