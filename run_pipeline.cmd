@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo FAILED: Project .venv is missing. See README.md for setup.
    exit /b 1
)
".venv\Scripts\python.exe" "src\run_pipeline.py" %*
exit /b %errorlevel%
