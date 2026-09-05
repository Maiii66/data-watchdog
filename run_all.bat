@echo off
REM Data Watchdog - one-command launcher.
REM Drop you in the project folder and run the full test + start the dashboard.
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo ERROR: venv\Scripts\python.exe not found. Run: python -m venv venv ^&^& pip install -r requirements.txt
    exit /b 1
)

echo Running full Data Watchdog test, then starting the dashboard...
"venv\Scripts\python.exe" run_all.py