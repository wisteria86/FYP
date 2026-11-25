@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Hikari virtual environment is missing. Create .venv and install requirements first.
  pause
  exit /b 1
)
rem The venv launcher needs the Python it was created from (see .venv\pyvenv.cfg).
".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
if errorlevel 1 (
  echo Hikari's Python environment cannot find its base Python.
  echo Check the "home" line in .venv\pyvenv.cfg points at an installed Python 3.12.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" run_hikari.py %*
set HIKARI_EXIT=%errorlevel%
rem Keep the window open on failure so a double-clicked shortcut shows the error.
if not "%HIKARI_EXIT%"=="0" pause
exit /b %HIKARI_EXIT%
