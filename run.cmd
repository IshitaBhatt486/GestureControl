@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.cmd first.
    exit /b 1
)

".venv\Scripts\python.exe" -m handwave.main
exit /b %errorlevel%
