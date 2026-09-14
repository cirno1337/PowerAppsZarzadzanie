# Runs the worker on Windows. Defaults to fully mocked adapters — see
# worker/config.py and docs/WORKER_SETUP.md for real-service configuration.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (Test-Path ".venv\Scripts\Activate.ps1") {
    & ".venv\Scripts\Activate.ps1"
}

if (-not $env:PPDM_POWERPLATFORM_MODE) { $env:PPDM_POWERPLATFORM_MODE = "mock" }
if (-not $env:PPDM_SHAREPOINT_MODE) { $env:PPDM_SHAREPOINT_MODE = "mock" }
if (-not $env:PPDM_COPILOT_MODE) { $env:PPDM_COPILOT_MODE = "mock" }

python -m worker.main @args
