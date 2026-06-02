# Build and start Layer 3 microservices in Docker, then seed the RAG corpus.
#
# Prerequisites: Docker Desktop running; stop run_dev.ps1 if ports 8001-8004 are in use.
#
# Usage (from repo root):
#   .\scripts\docker_layer3.ps1
#   .\scripts\docker_layer3.ps1 -Down          # stop containers
#   .\scripts\docker_layer3.ps1 -NoSeed        # skip corpus seed

param(
    [switch]$Down,
    [switch]$NoSeed
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..").Path
$composeFile = Join-Path $root "infra\docker-compose.yml"

if ($Down) {
    docker compose -f $composeFile down
    Write-Host "Layer 3 containers stopped."
    exit 0
}

Write-Host "Building and starting Layer 3 services..."
docker compose -f $composeFile up --build -d

Write-Host "Waiting for RAG service (model load may take 1-2 min on first run)..."
$deadline = (Get-Date).AddMinutes(3)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-RestMethod -Uri "http://localhost:8001/healthz" -TimeoutSec 5
        if ($r.status -eq "ok") {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 5
    }
}

if (-not $ready) {
    Write-Warning "RAG health check timed out. Check logs: docker compose -f infra/docker-compose.yml logs rag-service"
} else {
    Write-Host "RAG ready: embedding_backend=$($r.embedding_backend) regulations_indexed=$($r.regulations_indexed)"
}

foreach ($port in @(8002, 8003, 8004)) {
    try {
        $h = Invoke-RestMethod -Uri "http://localhost:$port/healthz" -TimeoutSec 10
        Write-Host "  :$port  $($h.service)  ok"
    } catch {
        Write-Warning "  :$port  health check failed"
    }
}

if (-not $NoSeed -and $ready) {
    $python = Join-Path $root "venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        $python = "python"
    }
    Write-Host "Seeding regulatory corpus via POST /upsert..."
    & $python (Join-Path $root "scripts\seed_regulatory_corpus.py") --remote http://localhost:8001 --reset
}

Write-Host ""
Write-Host "Layer 3 endpoints:"
Write-Host "  http://localhost:8001/healthz  (RAG)"
Write-Host "  http://localhost:8002/healthz  (doc-analyzer)"
Write-Host "  http://localhost:8003/healthz  (guardrails)"
Write-Host "  http://localhost:8004/healthz  (langgraph)"
Write-Host ""
Write-Host "Logs:  docker compose -f infra/docker-compose.yml logs -f"
Write-Host "Stop:  .\scripts\docker_layer3.ps1 -Down"
