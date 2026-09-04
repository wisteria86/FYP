@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Hikari virtual environment is missing. Create .venv and install requirements first.
  exit /b 1
)
".venv\Scripts\python.exe" run_hikari.py %*
