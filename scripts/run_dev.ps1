# Start every backend service of the Compliance 360 control tower in its
# own PowerShell window. Run this script from the project root after
# activating the venv and running `pip install -r requirements.txt`.
#
# Usage:
#   .\scripts\run_dev.ps1

$ErrorActionPreference = "Stop"

$root = (Resolve-Path "$PSScriptRoot\..").Path
$python = Join-Path $root "venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "venv not found at $python. Run `python -m venv venv` first."
    exit 1
}

$services = @(
    @{ name = "rag-service";             port = 8001; module = "services.rag_service.app.main:app" },
    @{ name = "doc-analyzer-service";    port = 8002; module = "services.doc_analyzer_service.app.main:app" },
    @{ name = "guardrails-service";      port = 8003; module = "services.guardrails_service.app.main:app" },
    @{ name = "langgraph-agent-service"; port = 8004; module = "services.langgraph_agent_service.app.main:app" },
    @{ name = "orchestrator";            port = 8000; module = "services.orchestrator.app.main:app" }
)

foreach ($svc in $services) {
    $cmd = "cd `"$root`"; & `"$python`" -m uvicorn $($svc.module) --port $($svc.port) --reload"
    Write-Host "Starting $($svc.name) on port $($svc.port)"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd | Out-Null
}

Write-Host ""
Write-Host "All backend services launched. Endpoints:"
foreach ($svc in $services) {
    Write-Host ("  - {0,-26}  http://localhost:{1}/healthz" -f $svc.name, $svc.port)
}
Write-Host ""
Write-Host "Start the dashboard with:  cd webui; npm install; npm run dev"
