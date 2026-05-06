#!/usr/bin/env pwsh
<#
.SYNOPSIS
    SmartVoter — one-shot data initialisation script (Windows / PowerShell).

.DESCRIPTION
    Runs three steps against a RUNNING local stack (postgres + backend must be up):
      1. Apply DB migrations
      2. Seed mock data (topics, parties, questions, simulation data)
      3. Import real Knesset data for the last N Knessets (no LLM by default)

    Run ONCE before first use, or after each election to refresh real data.
    LLM enrichment is OFF by default to avoid API costs.
    Enable it afterwards via Admin → Generate.

.PARAMETER LastN
    Number of most-recent Knessets to import (default: 2 → K24 + K25).

.PARAMETER NoLlm
    Skip LLM enrichment (default: true). Set to $false to enable.

.PARAMETER CurrentKnesset
    Override the most-recent Knesset number (default: from settings, currently 25).

.EXAMPLE
    # Standard initialisation (last 2 Knessets, no LLM):
    .\scripts\init-data.ps1

    # Import last 4 Knessets with LLM enabled:
    .\scripts\init-data.ps1 -LastN 4 -NoLlm:$false

    # After a new election (Knesset 26 just started):
    .\scripts\init-data.ps1 -CurrentKnesset 26 -LastN 2
#>

param(
    [int]    $LastN          = 2,
    [bool]   $NoLlm          = $true,
    [int]    $CurrentKnesset = 0      # 0 = use settings default
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path $PSScriptRoot -Parent

function Step([string]$msg) {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
}

Step "SmartVoter Data Initialisation"
Write-Host "  Last N Knessets : $LastN"
Write-Host "  No LLM          : $NoLlm"
if ($CurrentKnesset -gt 0) { Write-Host "  Current Knesset : $CurrentKnesset" }
Write-Host ""

Push-Location $root

# ── Step 1: Migrations ───────────────────────────────────────────────────────
Step "1/3  Applying database migrations"
uv run alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "alembic upgrade head failed" }

# ── Step 2: Mock seed data ───────────────────────────────────────────────────
Step "2/3  Seeding mock/reference data"
uv run python -m backend.app.seed.run_seed
if ($LASTEXITCODE -ne 0) { throw "run_seed failed" }

# ── Step 3: Real Knesset data ────────────────────────────────────────────────
Step "3/3  Importing Knesset data"

$ingestArgs = @("--last-n", $LastN)
if ($NoLlm)              { $ingestArgs += "--no-llm" }
if ($CurrentKnesset -gt 0) { $ingestArgs += @("--current-knesset", $CurrentKnesset) }

uv run python -m backend.app.seed.ingest_knesset @ingestArgs
if ($LASTEXITCODE -ne 0) { throw "ingest_knesset failed" }

Pop-Location

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Green
Write-Host "  ✅  Initialisation complete!" -ForegroundColor Green
Write-Host "" -ForegroundColor Green
Write-Host "  Next steps:" -ForegroundColor Green
Write-Host "    • Open http://localhost:3000 to test the questionnaire" -ForegroundColor Green
Write-Host "    • Visit /admin to review & approve generated questions" -ForegroundColor Green
Write-Host "    • Set OPENAI_API_KEY in .env and run Admin → Generate" -ForegroundColor Green
Write-Host "      to enrich questions with LLM if desired." -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green

