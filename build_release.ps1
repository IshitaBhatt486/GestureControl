$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

& ".\.venv\Scripts\python.exe" -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed; release build stopped." }

& ".\.venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean "GestureOS.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$release = Join-Path $projectRoot "dist\GestureOS.exe"
if (-not (Test-Path -LiteralPath $release)) { throw "Release executable was not created." }
Write-Host "Release created: $release"
