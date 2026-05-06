#!/usr/bin/env bash
# SmartVoter — one-shot data initialisation script (Linux / macOS / WSL).
#
# Usage:
#   ./scripts/init-data.sh                     # last 2 Knessets, no LLM
#   LAST_N=4 ./scripts/init-data.sh            # last 4 Knessets
#   LAST_N=2 NO_LLM=false ./scripts/init-data.sh   # with LLM enabled
#   CURRENT_KNESSET=26 ./scripts/init-data.sh  # after a new election
#
# Requires the virtual environment to be activated or uv available in PATH.
# Run from the project root.

set -euo pipefail

LAST_N="${LAST_N:-2}"
NO_LLM="${NO_LLM:-true}"
CURRENT_KNESSET="${CURRENT_KNESSET:-0}"   # 0 = use settings default (currently 26)

BOLD='\033[1m'; CYAN='\033[0;36m'; GREEN='\033[0;32m'; RESET='\033[0m'

step() { echo -e "\n${CYAN}${BOLD}===========================================================${RESET}"; \
         echo -e "${CYAN}${BOLD}  $*${RESET}"; \
         echo -e "${CYAN}${BOLD}===========================================================${RESET}"; }

step "SmartVoter Data Initialisation"
echo "  Last N Knessets : $LAST_N"
echo "  No LLM          : $NO_LLM"
[ "$CURRENT_KNESSET" -gt 0 ] && echo "  Current Knesset : $CURRENT_KNESSET"

# ── 1. Migrations ─────────────────────────────────────────────────────────────
step "1/3  Applying database migrations"
uv run alembic upgrade head

# ── 2. Mock / reference seed data ─────────────────────────────────────────────
step "2/3  Seeding mock/reference data"
uv run python -m backend.app.seed.run_seed

# ── 3. Real Knesset data ──────────────────────────────────────────────────────
step "3/3  Importing Knesset data (last ${LAST_N} Knessets)"

INGEST_ARGS=("--last-n" "$LAST_N")
[ "$NO_LLM" = "true" ]      && INGEST_ARGS+=("--no-llm")
[ "$CURRENT_KNESSET" -gt 0 ] && INGEST_ARGS+=("--current-knesset" "$CURRENT_KNESSET")

uv run python -m backend.app.seed.ingest_knesset "${INGEST_ARGS[@]}"

echo -e "\n${GREEN}${BOLD}===========================================================${RESET}"
echo -e "${GREEN}${BOLD}  ✅  Initialisation complete!${RESET}"
echo -e ""
echo -e "  Next steps:"
echo -e "    • Open http://localhost:3000 to test the questionnaire"
echo -e "    • Visit /admin to review & approve generated questions"
echo -e "    • Set OPENAI_API_KEY in .env and run Admin → Generate"
echo -e "      to enrich questions with LLM if desired."
echo -e "${GREEN}${BOLD}===========================================================${RESET}"

