<#
.SYNOPSIS
  Build a client-ready ZIP of the Lakeside Heating DSM desktop app + ONNX model.

.DESCRIPTION
  1) cargo build --release
  2) Stage exe + heating_dsm_hourly_v1.{onnx,feature_meta.json} + sample bills
  3) Zip under desktop/dist/

.EXAMPLE
  .\pack_client.ps1
  .\pack_client.ps1 -SkipBuild
#>
[CmdletBinding()]
param(
  [switch]$SkipBuild,
  [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$DesktopRoot = $PSScriptRoot
$Vibe22 = Split-Path $DesktopRoot -Parent
$ExeName = "lakeside-heating-dsm.exe"
$ReleaseExe = Join-Path $DesktopRoot "target\release\$ExeName"
$MlArt = Join-Path $Vibe22 "ml\artifacts"
$Onnx = Join-Path $MlArt "heating_dsm_hourly_v1.onnx"
$Meta = Join-Path $MlArt "heating_dsm_hourly_v1_feature_meta.json"
$SampleCsv = Join-Path $Vibe22 "data\sample\utility_bills_demand_sample.csv"
$SampleMd = Join-Path $Vibe22 "data\sample\UTILITY_BILL_CSV.md"
$E1075Csv = Join-Path $Vibe22 "data\sample\creeksides_e1075_bills.csv"
$Cp2Md = Join-Path $Vibe22 "data\sample\CP2_TARIFF.md"
$ClientReadme = Join-Path $DesktopRoot "CLIENT_README.md"

if (-not $OutDir) {
  $OutDir = Join-Path $DesktopRoot "dist"
}

Write-Host "== Lakeside Heating DSM -- client pack ==" -ForegroundColor Cyan
Write-Host "desktop: $DesktopRoot"

if (-not $SkipBuild) {
  Write-Host "Building release..." -ForegroundColor Yellow
  Push-Location $DesktopRoot
  try {
    cargo build --release
    if ($LASTEXITCODE -ne 0) { throw "cargo build --release failed ($LASTEXITCODE)" }
  } finally {
    Pop-Location
  }
}

foreach ($p in @($ReleaseExe, $Onnx, $Meta, $ClientReadme)) {
  if (-not (Test-Path $p)) {
    throw "Missing required file: $p  (train first: python -u ml\train_heating_dsm.py)"
  }
}

$stamp = Get-Date -Format "yyyyMMdd"
$metaJson = Get-Content $Meta -Raw | ConvertFrom-Json
$champ = if ($metaJson.champion) { [string]$metaJson.champion } else { "model" }
$champSafe = ($champ -replace '[^a-zA-Z0-9_\-]', '_')
$folderName = "lakeside-heating-dsm-windows-$stamp-$champSafe"
$stage = Join-Path $OutDir $folderName
$zipPath = Join-Path $OutDir ($folderName + ".zip")

if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Path $stage | Out-Null

Copy-Item $ReleaseExe (Join-Path $stage $ExeName)
Copy-Item $Onnx (Join-Path $stage "heating_dsm_hourly_v1.onnx")
Copy-Item $Meta (Join-Path $stage "heating_dsm_hourly_v1_feature_meta.json")
Copy-Item $ClientReadme (Join-Path $stage "CLIENT_README.md")
if (Test-Path $SampleCsv) {
  Copy-Item $SampleCsv (Join-Path $stage "utility_bills_demand_sample.csv")
}
if (Test-Path $SampleMd) {
  Copy-Item $SampleMd (Join-Path $stage "UTILITY_BILL_CSV.md")
}
if (Test-Path $E1075Csv) {
  Copy-Item $E1075Csv (Join-Path $stage "creeksides_e1075_bills.csv")
}
if (Test-Path $Cp2Md) {
  Copy-Item $Cp2Md (Join-Path $stage "CP2_TARIFF.md")
}

$manifest = [ordered]@{
  package           = $folderName
  created_utc       = (Get-Date).ToUniversalTime().ToString("o")
  exe               = $ExeName
  model_name        = $metaJson.model_name
  champion          = $metaJson.champion
  training_source   = $metaJson.training_source
  precision_pm_kw   = $metaJson.precision_pm_kw
  cv_metrics        = $metaJson.cv_metrics
  best_params       = $metaJson.best_params
  honesty           = $metaJson.honesty
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $stage "PACKAGE_MANIFEST.json")

$localArt = Join-Path $DesktopRoot "artifacts"
New-Item -ItemType Directory -Path $localArt -Force | Out-Null
Copy-Item $Onnx (Join-Path $localArt "heating_dsm_hourly_v1.onnx") -Force
Copy-Item $Meta (Join-Path $localArt "heating_dsm_hourly_v1_feature_meta.json") -Force

if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path $stage -DestinationPath $zipPath -Force

$need = @(
  $ExeName,
  "heating_dsm_hourly_v1.onnx",
  "heating_dsm_hourly_v1_feature_meta.json",
  "CLIENT_README.md",
  "PACKAGE_MANIFEST.json"
)
foreach ($n in $need) {
  $fp = Join-Path $stage $n
  if (-not (Test-Path $fp)) { throw "Pack smoke failed - missing $n" }
}

$smokePy = Join-Path $env:TEMP "lakeside_dsm_pack_smoke.py"
$env:LAKESIDE_ONNX_DIR = $stage
@(
  "import json, os"
  "from pathlib import Path"
  "import numpy as np"
  "import onnxruntime as ort"
  "d = Path(os.environ['LAKESIDE_ONNX_DIR'])"
  "meta = json.loads((d / 'heating_dsm_hourly_v1_feature_meta.json').read_text(encoding='utf-8'))"
  "assert (d / 'heating_dsm_hourly_v1.onnx').is_file()"
  "assert meta.get('model_name'), 'model_name missing'"
  "sess = ort.InferenceSession(str(d / 'heating_dsm_hourly_v1.onnx'), providers=['CPUExecutionProvider'])"
  "x = np.zeros((1, len(meta['feature_cols'])), np.float32)"
  "y = float(np.asarray(sess.run(None, {'features': x})[0]).reshape(-1)[0])"
  "print('SMOKE_OK', meta.get('model_name'), 'pred0', round(y, 3), 'pm', meta.get('precision_pm_kw'))"
) | Set-Content -Encoding utf8 $smokePy
python $smokePy
if ($LASTEXITCODE -ne 0) { throw "ONNX smoke test failed" }
Remove-Item -Force $smokePy -ErrorAction SilentlyContinue

$sizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 2)
Write-Host ""
Write-Host "OK - client package ready" -ForegroundColor Green
Write-Host ("  folder: {0}" -f $stage)
Write-Host ("  zip:    {0}  ({1} MB)" -f $zipPath, $sizeMb)
Write-Host ("  model:  {0} / {1}" -f $metaJson.model_name, $metaJson.champion)
Write-Host ""
Write-Host ("Send the .zip to the client. They unzip and run {0}." -f $ExeName) -ForegroundColor Cyan
