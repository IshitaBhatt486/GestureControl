$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment not found. Create .venv and install gestureos\requirements.txt first."
}

$reportDirectory = Join-Path $projectRoot "test-results"
New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null
$testTemp = Join-Path $projectRoot ".test-tmp\pytest"
New-Item -ItemType Directory -Force -Path $testTemp | Out-Null
$env:TEMP = $testTemp
$env:TMP = $testTemp

& $python -m pytest --basetemp $testTemp @args
if ($LASTEXITCODE -ne 0) {
    throw "Tests or the 80% coverage quality gate failed."
}

Write-Host "JUnit report: $reportDirectory\junit.xml"
Write-Host "Coverage XML: $reportDirectory\coverage.xml"
Write-Host "Coverage HTML: $reportDirectory\coverage-html\index.html"
