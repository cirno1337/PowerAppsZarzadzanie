# Sets up a local Python environment for offline development on Windows.
# No network access, corporate VPN, or Microsoft account is required.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$venvDir = ".venv"
if (-not (Test-Path $venvDir)) {
    Write-Host "Creating virtual environment in $venvDir..."
    python -m venv --system-site-packages $venvDir
}

& "$venvDir\Scripts\Activate.ps1"

Write-Host "Installing dev dependencies (pytest)..."
python -c "import pytest" 2>$null
if ($LASTEXITCODE -ne 0) {
    pip install --quiet -e ".[dev]"
}

Write-Host ""
Write-Host "Setup complete. Next steps:"
Write-Host "  $venvDir\Scripts\Activate.ps1"
Write-Host "  .\scripts\run-tests.ps1"
Write-Host "  .\scripts\run-worker.ps1"
