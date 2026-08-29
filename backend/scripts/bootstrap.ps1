$ErrorActionPreference = "Stop"
$BackendDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtual environment not found. Run: py -3.13 -m venv .venv"
}

Set-Location -LiteralPath $BackendDir
& $Python -m app bootstrap
exit $LASTEXITCODE

