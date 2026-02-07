$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Syncing dependencies (including build group)..."
uv sync --group build

$wheel = Get-ChildItem "vendor/dotpad/dotpad-*.whl" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $wheel) {
    throw "No dotpad wheel found in vendor/dotpad. Run setup.ps1 or copy dotpad-*.whl first."
}

Write-Host "Installing dotpad wheel: $($wheel.Name)"
uv pip install "$($wheel.FullName)"

Write-Host "Building DGC executable with PyInstaller..."
uv run --group build pyinstaller `
  --noconfirm `
  --clean `
  --windowed `
  --noconsole `
  --name dgc `
  --paths src `
  --add-data "assets/sounds;assets/sounds" `
  src/dgc/__main__.py

if (Test-Path "dist/dgc") {
    Copy-Item "LICENSE" "dist/dgc/LICENSE" -Force
    Copy-Item "README.md" "dist/dgc/README.md" -Force
}

Write-Host "Build complete: dist/dgc/"
