param([string]$Source)

$ErrorActionPreference = "Stop"
$BackendDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtual environment not found. Run: py -3.13 -m venv .venv"
}

Set-Location -LiteralPath $BackendDir
if ($Source) {
    & $Python -m app crawl --source $Source
} else {
    & $Python -m app crawl
}
exit $LASTEXITCODE

