@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto run_setup

".venv\Scripts\python.exe" -c "import dotpad" >nul 2>&1
if errorlevel 1 goto run_setup
goto run_app

:run_setup
echo Running setup...
powershell -NoProfile -ExecutionPolicy Bypass -File ".\setup.ps1"
if errorlevel 1 (
  echo Setup failed.
  exit /b 1
)

:run_app
uv run dgc
if errorlevel 1 exit /b 1
exit /b 0

