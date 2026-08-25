$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    py -3.14 -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -e ".[dev]"

Write-Host ""
Write-Host "Project setup complete."
Write-Host "Run:"
Write-Host "  .\.venv\Scripts\mvi.exe doctor"
Write-Host "  .\.venv\Scripts\pytest.exe"
