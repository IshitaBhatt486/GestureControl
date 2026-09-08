@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_LAUNCHER=py -3.11"
%PYTHON_LAUNCHER% -c "import sys" >nul 2>nul
if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Could not find Python 3.11. Install it from https://www.python.org/downloads/
        echo or via "winget install --id Python.Python.3.11" and re-run setup.cmd.
        exit /b 1
    )
    set "PYTHON_LAUNCHER=python"
)

%PYTHON_LAUNCHER% -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3,11) else 1)" >nul 2>nul
if errorlevel 1 (
    echo Found Python, but it is not 3.11. HandWave requires Python 3.11 specifically.
    echo Install it with "winget install --id Python.Python.3.11" and re-run setup.cmd.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv ...
    %PYTHON_LAUNCHER% -m venv .venv
    if errorlevel 1 (
        echo Failed to create the virtual environment.
        exit /b 1
    )
) else (
    echo Virtual environment already exists at .venv
)

echo Installing dependencies from handwave\requirements.txt ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r handwave\requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies. Check your network connection and try again.
    exit /b 1
)

echo.
echo Setup complete. Next steps:
echo   .\run.cmd          - start HandWave
echo   .\run_tests.cmd -q - run the test suite
