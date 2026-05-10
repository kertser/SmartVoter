#!/usr/bin/env bash
set -euo pipefail

echo
echo " =========================================="
echo "   SmartVoter -- Development Start Script"
echo " =========================================="
echo

# ── Clear VIRTUAL_ENV so uv always uses the project's .venv ────────────────
unset VIRTUAL_ENV
unset UV_PROJECT_ENVIRONMENT

# ── Check uv ──────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo "[ERROR] uv not found. Install it from https://github.com/astral-sh/uv"
    echo "        curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# ── Check Docker ──────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "[ERROR] docker not found. Install Docker from https://docs.docker.com/get-docker/"
    exit 1
fi

# Verify Docker Compose v2 (plugin) is available
if ! docker compose version &>/dev/null; then
    echo "[ERROR] 'docker compose' (v2 plugin) not found."
    echo "        On older systems try: sudo apt-get install docker-compose-plugin"
    exit 1
fi

# ── Copy .env if missing ──────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "[INFO] .env not found -- copying from .env.example"
        cp ".env.example" ".env"
    else
        echo "[WARN] Neither .env nor .env.example found. Continuing without .env."
    fi
fi

# ── Python dependencies (for running migrations locally) ──────────────────
echo "[1/5] Syncing Python dependencies..."
uv sync --quiet
echo "      Done."

# ── Start Docker services (postgres + redis) ─────────────────────────────
echo "[2/5] Starting PostgreSQL and Redis via Docker Compose..."
docker compose up -d postgres redis

# ── Wait for postgres to be ready ────────────────────────────────────────
# pg_isready only checks if the postmaster is listening; it returns success
# even while the database system is still in startup/recovery.  We run an
# actual query (SELECT 1) to confirm the DB is fully available before
# attempting migrations.
echo "[3/5] Waiting for PostgreSQL to be ready..."
attempts=0
until docker compose exec -T postgres psql -U smartvoter -d smartvoter -c "SELECT 1" &>/dev/null; do
    attempts=$((attempts + 1))
    if [ "$attempts" -gt 30 ]; then
        echo "[ERROR] PostgreSQL did not become ready after 30 seconds."
        exit 1
    fi
    sleep 1
done
echo "      PostgreSQL is ready."

# ── Run Alembic migrations ────────────────────────────────────────────────
echo "[4/5] Running database migrations..."
uv run alembic upgrade head
echo "      Migrations applied."

# ── Seed mock data (idempotent) ──────────────────────────────────────────
echo "      Seeding mock data (skipped if already seeded)..."
uv run python -m backend.app.seed.run_seed || true
echo "      Done."

# ── Build and start backend + frontend containers ─────────────────────────
echo "[5/5] Building and starting backend and frontend containers..."
docker compose up -d --build backend frontend
echo "      Containers started."

# ── Wait for frontend to be ready ────────────────────────────────────────
echo
echo " Waiting for frontend to compile (first startup can take ~60 seconds)..."
fw=0
while true; do
    fw=$((fw + 1))
    if [ "$fw" -gt 90 ]; then
        echo " [WARN] Frontend did not respond within 90 seconds -- continuing anyway."
        break
    fi
    http_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || true)
    if [ "$http_code" = "200" ]; then
        break
    fi
    sleep 1
done
echo " Frontend is ready."

# ── Done ──────────────────────────────────────────────────────────────────
echo
echo " [OK] All services are running in Docker:"
echo
echo "       Frontend  -->  http://localhost:3000"
echo "       Backend   -->  http://localhost:8000"
echo "       API docs  -->  http://localhost:8000/docs"
echo
echo " To view live logs:"
echo "       docker compose logs -f frontend"
echo "       docker compose logs -f backend"
echo
echo " To stop all services:"
echo "       docker compose down"
echo

