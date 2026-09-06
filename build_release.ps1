$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

& ".\run_tests.cmd" -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed; release build stopped." }

& ".\.venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean "GestureOS.spec"
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Clean build cache removal failed; retrying without deleting the cache."
    & ".\.venv\Scripts\python.exe" -m PyInstaller --noconfirm "GestureOS.spec"
}
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$release = Join-Path $projectRoot "dist\GestureOS.exe"
if (-not (Test-Path -LiteralPath $release)) { throw "Release executable was not created." }

$nsisCandidates = @(
    $env:NSIS_MAKENSIS,
    (Get-Command "makensis.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    "C:\Program Files (x86)\NSIS\makensis.exe",
    "C:\Program Files\NSIS\makensis.exe"
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$makensis = $nsisCandidates | Select-Object -First 1
if (-not $makensis) {
    throw "NSIS was not found. Install it with: winget install --id NSIS.NSIS -e"
}

$version = & ".\.venv\Scripts\python.exe" -c "from gestureos.version import __version__; print(__version__)"
if ($LASTEXITCODE -ne 0 -or -not $version) { throw "Unable to read GestureOS version." }

& $makensis "/DPRODUCT_VERSION=$version" "packaging\GestureOS.nsi"
if ($LASTEXITCODE -ne 0) { throw "NSIS installer build failed." }

$installer = Join-Path $projectRoot "dist\GestureOS-$version-Setup.exe"
if (-not (Test-Path -LiteralPath $installer)) { throw "Installer was not created." }

$checksums = @($release, $installer) | ForEach-Object {
    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_
    "$($hash.Hash.ToLowerInvariant())  $([IO.Path]::GetFileName($_))"
}
$checksums | Set-Content -Encoding ascii -LiteralPath (Join-Path $projectRoot "dist\SHA256SUMS.txt")

Write-Host "Portable executable: $release"
Write-Host "Installer: $installer"
Write-Host "Checksums: $(Join-Path $projectRoot 'dist\SHA256SUMS.txt')"
