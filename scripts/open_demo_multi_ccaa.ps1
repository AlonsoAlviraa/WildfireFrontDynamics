# Rebuild multi-CCAA sales demo and open in default browser (Windows)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "scripts\build_demo_multi_ccaa.py"))) {
  $Root = Get-Location
}
Set-Location $Root
$env:PYTHONPATH = $Root
python scripts\build_demo_multi_ccaa.py
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 2) { exit $LASTEXITCODE }
$portal = Join-Path $Root "outputs\demo_multi_ccaa\index.html"
if (-not (Test-Path $portal)) { Write-Error "Missing $portal"; exit 1 }
Start-Process $portal
Write-Host "Opened $portal"
