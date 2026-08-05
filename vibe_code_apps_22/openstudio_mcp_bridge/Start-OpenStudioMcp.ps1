<#
.SYNOPSIS
  Start OpenStudio-MCP via Docker (stdio).

.NOTES
  Requires Docker Desktop running. Does not register inside Cursor (tool-cap).
#>
param(
  [string]$Image = "openstudio-mcp:dev",
  [string]$Repo = (Join-Path $PSScriptRoot "..\third_party\openstudio-mcp"),
  [string]$Creekside = $env:VIBE23_CREEKSIDE_ROOT
)

if (-not $Creekside) {
  $Creekside = "C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
}

if (-not (Test-Path $Repo)) {
  Write-Host "Cloning NatLabRockies/openstudio-mcp into $Repo ..."
  New-Item -ItemType Directory -Force -Path (Split-Path $Repo) | Out-Null
  git clone --depth 1 https://github.com/NatLabRockies/openstudio-mcp.git $Repo
}

$inputs = Join-Path $Creekside "eplus\models"
$runs = Join-Path $PSScriptRoot "runs"
$measures = Join-Path $PSScriptRoot "measures"
$skills = Join-Path $Repo ".claude\skills"
New-Item -ItemType Directory -Force -Path $runs, $measures | Out-Null

function Dock([string]$p) { return ($p -replace '\\', '/') }

Write-Host "inputs=$inputs"
Write-Host "runs=$runs"
Write-Host "image=$Image"

$images = docker images -q $Image 2>$null
if (-not $images) {
  Write-Host "Building $Image (first time)..."
  Push-Location $Repo
  docker build -t $Image -f docker/Dockerfile .
  Pop-Location
}

docker run --rm -i `
  -v "$(Dock $inputs):/inputs:ro" `
  -v "$(Dock $runs):/runs" `
  -v "$(Dock $measures):/measures" `
  -v "$(Dock $skills):/skills:ro" `
  -e "OPENSTUDIO_MCP_MODE=prod" `
  $Image openstudio-mcp
