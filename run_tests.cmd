@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Create .venv and install gestureos\requirements.txt first.
    exit /b 1
)

if not exist "test-results" mkdir "test-results"
if not exist ".test-tmp\pytest" mkdir ".test-tmp\pytest"
set "TEMP=%CD%\.test-tmp\pytest"
set "TMP=%TEMP%"
".venv\Scripts\python.exe" -m pytest --basetemp "%TEMP%" %*
if errorlevel 1 exit /b %errorlevel%

echo JUnit report: %CD%\test-results\junit.xml
echo Coverage XML: %CD%\test-results\coverage.xml
echo Coverage HTML: %CD%\test-results\coverage-html\index.html
