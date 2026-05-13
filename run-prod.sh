#!/usr/bin/env bash
set -euo pipefail

echo
echo " =========================================="
echo "   SmartVoter -- Production Start Script"
echo " =========================================="
echo

COMPOSE="docker compose -f docker-compose.prod.yml"

# ── Check Docker ──────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "[ERROR] docker not found."
    exit 1
fi
if ! docker compose version &>/dev/null; then
    echo "[ERROR] 'docker compose' (v2 plugin) not found."
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

# ── Validate required prod variables ──────────────────────────────────────
_get_env() {
    local key="$1" default="${2:-}"
    local val
    val=$(grep -E "^${key}=" .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '[:space:]') || true
    echo "${val:-$default}"
}

_PG_PASSWORD=$(_get_env POSTGRES_PASSWORD "")
_ADMIN_PASSWORD=$(_get_env ADMIN_PASSWORD "")

if [ -z "$_PG_PASSWORD" ] || [ "$_PG_PASSWORD" = "smartvoter" ]; then
    echo "[WARN] POSTGRES_PASSWORD is weak or not set. Set a strong password in .env before going public."
fi
if [ -z "$_ADMIN_PASSWORD" ] || [ "$_ADMIN_PASSWORD" = "admin" ]; then
    echo "[WARN] ADMIN_PASSWORD is weak or not set. Set a strong password in .env before going public."
fi

# ── Pull latest images ────────────────────────────────────────────────────
echo "[1/4] Pulling base images..."
$COMPOSE pull --ignore-buildable 2>/dev/null || true

# ── Build containers ──────────────────────────────────────────────────────
echo "[2/4] Building containers..."
$COMPOSE build

# ── Start infrastructure (postgres, redis) ───────────────────────────────
echo "[3/4] Starting PostgreSQL and Redis..."
$COMPOSE up -d postgres redis

# Wait for postgres
attempts=0
_PG_USER=$(_get_env POSTGRES_USER smartvoter)
_PG_DB=$(_get_env POSTGRES_DB smartvoter)
until $COMPOSE exec -T postgres psql -U "$_PG_USER" -d "$_PG_DB" -c "SELECT 1" &>/dev/null; do
    attempts=$((attempts + 1))
    if [ "$attempts" -gt 30 ]; then
        echo "[ERROR] PostgreSQL did not become ready after 30 seconds."
        exit 1
    fi
    sleep 1
done
echo "      PostgreSQL is ready."

# ── Run migrations + seed ─────────────────────────────────────────────────
echo "      Applying database migrations (inside backend container)..."
$COMPOSE run --rm --no-deps \
    -e DATABASE_URL="postgresql+psycopg://${_PG_USER}:${_PG_PASSWORD}@postgres:5432/${_PG_DB}" \
    backend \
    uv run alembic upgrade head
echo "      Migrations applied."

echo "      Seeding base data (idempotent)..."
$COMPOSE run --rm --no-deps \
    -e DATABASE_URL="postgresql+psycopg://${_PG_USER}:${_PG_PASSWORD}@postgres:5432/${_PG_DB}" \
    backend \
    uv run python -m backend.app.seed.run_seed || true
echo "      Done."

# ── Start all services (backend + frontend + caddy) ───────────────────────
echo "[4/4] Starting backend, frontend and Caddy (HTTPS)..."
$COMPOSE up -d backend frontend caddy
echo "      All services started."

# ── Wait for Caddy to be ready ────────────────────────────────────────────
echo
echo " Waiting for Caddy to obtain TLS certificate (may take ~30 seconds)..."
cw=0
while true; do
    cw=$((cw + 1))
    if [ "$cw" -gt 60 ]; then
        echo " [WARN] Caddy did not respond in 60 seconds. Check: $COMPOSE logs caddy"
        break
    fi
    http_code=$(curl -sk -o /dev/null -w "%{http_code}" "https://localhost" 2>/dev/null || true)
    if [ "$http_code" = "200" ] || [ "$http_code" = "308" ]; then
        break
    fi
    sleep 1
done

# ── Done ──────────────────────────────────────────────────────────────────
DOMAIN=$(_get_env DOMAIN "smartvoter.alpha-numerical.com")
echo
echo " [OK] All services are running:"
echo
echo "       Site      -->  https://${DOMAIN}"
echo "       API docs  -->  https://${DOMAIN}/docs"
echo
echo " To view live logs:"
echo "       $COMPOSE logs -f caddy"
echo "       $COMPOSE logs -f backend"
echo "       $COMPOSE logs -f frontend"
echo
echo " To stop all services:"
echo "       $COMPOSE down"
echo

