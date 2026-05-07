@echo off
setlocal enabledelayedexpansion

echo.
echo  ==========================================
echo   SmartVoter -- Development Start Script
echo  ==========================================
echo.

:: ── Clear VIRTUAL_ENV so uv always uses the project's .venv ────────────────
:: Without this, an activated external venv in the shell (e.g. "(venv)") causes
:: the warning: VIRTUAL_ENV=venv does not match project environment path .venv
set VIRTUAL_ENV=
set UV_PROJECT_ENVIRONMENT=

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

:: ── Copy .env if missing ──────────────────────────────────────────────────
if not exist ".env" (
    echo [INFO] .env not found -- copying from .env.example
    copy ".env.example" ".env" >nul
)

:: ── Python dependencies (for running migrations locally) ──────────────────
echo [1/5] Syncing Python dependencies...
uv sync --quiet
if %ERRORLEVEL% neq 0 (
    echo [ERROR] uv sync failed.
    pause
    exit /b 1
)
echo       Done.

:: ── Start Docker services (postgres + redis) ─────────────────────────────
echo [2/5] Starting PostgreSQL and Redis via Docker Compose...
docker compose up -d postgres redis
if %ERRORLEVEL% neq 0 (
    echo [ERROR] docker compose up failed. Is Docker Desktop running?
    pause
    exit /b 1
)

:: ── Wait for postgres to be ready ────────────────────────────────────────
echo [3/5] Waiting for PostgreSQL to be ready...
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
echo [4/5] Running database migrations...
uv run alembic upgrade head
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Alembic migration failed.
    pause
    exit /b 1
)
echo       Migrations applied.

:: ── Seed mock data (idempotent) ──────────────────────────────────────────
echo       Seeding mock data (skipped if already seeded)...
uv run python -m backend.app.seed.run_seed
echo       Done.

:: ── Build and start backend + frontend containers ─────────────────────────
echo [5/5] Building and starting backend and frontend containers...
docker compose up -d --build backend frontend
if %ERRORLEVEL% neq 0 (
    echo [ERROR] docker compose up failed for backend/frontend.
    pause
    exit /b 1
)
echo       Containers started.

:: ── Wait for frontend to be ready, then open browser ─────────────────────
echo.
echo  Waiting for frontend to compile (first startup can take ~30 seconds)...
set /a fw=0
:wait_frontend
set /a fw+=1
if %fw% gtr 90 goto open_browser
timeout /t 1 /nobreak >nul
curl.exe -s -o nul -w "%%{http_code}" http://localhost:3000 2>nul | findstr /r "^200$" >nul 2>&1
if %ERRORLEVEL% equ 0 goto open_browser
goto wait_frontend

:open_browser
echo  Frontend is ready.

:: ── Done ─────────────────────────────────────────────────────────────────
echo.
echo  [OK] All services are running in Docker:
echo.
echo        Frontend  --^>  http://localhost:3000
echo        Backend   --^>  http://localhost:8000
echo        API docs  --^>  http://localhost:8000/docs
echo.
echo  To view live logs:
echo        docker compose logs -f frontend
echo        docker compose logs -f backend
echo.
echo  To stop all services:
echo        docker compose down
echo.
echo  Opening browser...
start "" "http://localhost:3000"
echo.
pause
