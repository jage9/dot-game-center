$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$wheelDir = Join-Path $PSScriptRoot "vendor/dotpad"
$wheel = Get-ChildItem -Path $wheelDir -Filter "dotpad-*.whl" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $wheel) {
    Write-Error "No dotpad wheel found in $wheelDir. Copy dotpad-*.whl there first."
    exit 1
}

Write-Host "Using DotPad wheel: $($wheel.Name)"

uv sync --no-group build
uv pip install --force-reinstall $wheel.FullName

Write-Host ""
Write-Host "Setup complete."
Write-Host "Run with: uv run dgc"
