# Turnkey: build Lakeside OpenStudio OSM (+ IDF) then optional E+ sim + utility score.
# No Docker. OpenStudio SDK lives under SITE\tools\openstudio\sdk\.
param(
  [switch]$SkipSim,
  [switch]$ScoreUtility,
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$AppRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $AppRoot
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"

$SiteRoot = $env:LAKESIDE_SITE_ROOT
if (-not $SiteRoot) { $SiteRoot = $env:VIBE22_SITE_ROOT }
if (-not $SiteRoot) { $SiteRoot = $env:VIBE22_CREEKSIDE_ROOT }
if (-not $SiteRoot) { $SiteRoot = "C:\Users\ben\OneDrive\Desktop\testing\sp_creekside" }
$env:LAKESIDE_SITE_ROOT = $SiteRoot

if (-not $SkipBuild) {
  Write-Host "== Build OSM =="
  & (Join-Path $PSScriptRoot "run_os_py.ps1") (Join-Path $PSScriptRoot "openstudio_build_lakeside_osm.py")
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if ($SkipSim) {
  Write-Host "SkipSim set - done."
  exit 0
}

$idf = Join-Path $SiteRoot "eplus\models\lakeside_9zone_openstudio.idf"
if (-not (Test-Path $idf)) {
  $idf = Join-Path $SiteRoot "eplus\models\creekside_9zone_openstudio.idf"
}
$epw = Join-Path $SiteRoot "eplus\weather\madison_amy_202508_202607.epw"
$out = Join-Path $SiteRoot "eplus\runs\openstudio_v0\sim"
New-Item -ItemType Directory -Force -Path $out | Out-Null

$sdkRoot = Join-Path $SiteRoot "tools\openstudio\sdk"
$exe = Get-ChildItem -Path $sdkRoot -Recurse -Filter "energyplus.exe" -ErrorAction SilentlyContinue |
  Select-Object -First 1 -ExpandProperty FullName
if (-not $exe) {
  $exe = "C:\EnergyPlusV26-1-0\energyplus.exe"
}
if (-not (Test-Path $exe)) { throw "EnergyPlus not found under $sdkRoot or $exe" }

$pp = Join-Path (Split-Path $exe -Parent) "PostProcess"
if (-not (Test-Path (Join-Path $pp "ReadVarsESO.exe"))) {
  $hostPp = "C:\EnergyPlusV26-1-0\PostProcess"
  if ((Test-Path (Join-Path $hostPp "ReadVarsESO.exe")) -and (-not (Test-Path $pp))) {
    New-Item -ItemType Junction -Path $pp -Target $hostPp | Out-Null
  }
}

Write-Host "== EnergyPlus sim =="
Write-Host "Using: $exe"
& $exe -w $epw -d $out -r $idf
$epCode = $LASTEXITCODE
if ($epCode -ne 0) {
  $ok = (Test-Path (Join-Path $out "eplusmtr.csv")) -or (Test-Path (Join-Path $out "eplusout.sql"))
  if (-not $ok) { exit $epCode }
  Write-Host "EnergyPlus exit $epCode but sim artifacts present; continuing."
}

if ($ScoreUtility) {
  Write-Host "== Score vs utility bills =="
  python -u (Join-Path $PSScriptRoot "score_openstudio_v0.py")
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Done. Site: $SiteRoot"
Write-Host "      OSM/IDF under eplus\models\lakeside_9zone_openstudio.*"
