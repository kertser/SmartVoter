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

# ── Load key variables from .env ─────────────────────────────────────────
# Read individual variables (no shell-substitution in .env values).
# Falls back to sensible defaults if not set.
_get_env() {
    local key="$1" default="$2"
    local val
    val=$(grep -E "^${key}=" .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '[:space:]') || true
    echo "${val:-$default}"
}

_PG_PORT=$(_get_env POSTGRES_PORT 5432)
_FRONTEND_PORT=$(_get_env FRONTEND_PORT 3000)
_BACKEND_PORT=$(_get_env BACKEND_PORT 8001)
_PG_USER=$(_get_env POSTGRES_USER smartvoter)
_PG_PASSWORD=$(_get_env POSTGRES_PASSWORD smartvoter)
_PG_DB=$(_get_env POSTGRES_DB smartvoter)
_APP_ENV=$(_get_env APP_ENV development)
_DOMAIN=$(_get_env DOMAIN "")

# Build a local DATABASE_URL that always points at the Docker-exposed postgres.
# This overrides whatever DATABASE_URL the host .env may contain (which may use
# shell-substitution syntax that dotenv parsers do not expand).
_LOCAL_DB_URL="postgresql+psycopg://${_PG_USER}:${_PG_PASSWORD}@127.0.0.1:${_PG_PORT}/${_PG_DB}"

# ── Python dependencies (for running migrations locally) ──────────────────
echo "[1/5] Syncing Python dependencies..."
uv sync --quiet
echo "      Done."

# ── Start Docker services (postgres + redis) ─────────────────────────────
echo "[2/5] Starting PostgreSQL and Redis via Docker Compose..."
docker compose up -d postgres redis

# ── Wait for postgres to be ready ────────────────────────────────────────
echo "[3/5] Waiting for PostgreSQL to be ready..."
attempts=0
until docker compose exec -T postgres psql -U "$_PG_USER" -d "$_PG_DB" -c "SELECT 1" &>/dev/null; do
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
DATABASE_URL="$_LOCAL_DB_URL" uv run alembic upgrade head
echo "      Migrations applied."

# ── Seed mock data (idempotent) ──────────────────────────────────────────
echo "      Seeding mock data (skipped if already seeded)..."
DATABASE_URL="$_LOCAL_DB_URL" uv run python -m backend.app.seed.run_seed || true
echo "      Done."

# ── Build and start backend + frontend containers ─────────────────────────
echo "[5/5] Building and starting backend and frontend containers..."
docker compose up -d --build backend frontend
echo "      Containers started."

# ── Start Caddy if production or domain is configured ─────────────────────
_USE_CADDY=false
if [ "$_APP_ENV" = "production" ] || [ -n "$_DOMAIN" ]; then
    _USE_CADDY=true
    echo "      Starting Caddy (HTTPS reverse proxy for ${_DOMAIN})..."
    docker compose up -d caddy
    echo "      Caddy started."
fi

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
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${_FRONTEND_PORT}" 2>/dev/null || true)
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
if [ "$_USE_CADDY" = "true" ]; then
    echo "       Site      -->  https://${_DOMAIN}"
    echo "       API docs  -->  https://${_DOMAIN}/docs"
else
    echo "       Frontend  -->  http://localhost:${_FRONTEND_PORT}"
    echo "       Backend   -->  http://localhost:${_BACKEND_PORT}"
    echo "       API docs  -->  http://localhost:${_BACKEND_PORT}/docs"
fi
echo
echo " Tip: for production with HTTPS, use:  ./run-prod.sh"
echo
echo " To view live logs:"
echo "       docker compose logs -f frontend"
echo "       docker compose logs -f backend"
echo
echo " To stop all services:"
echo "       docker compose down"
echo

