#Requires -Version 5.1
<#
.SYNOPSIS
  Local-only BAS Lite test runner for Windows Docker Desktop.

.EXAMPLE
  .\run-bas-lite.ps1
  .\run-bas-lite.ps1 -FollowLogs
  .\run-bas-lite.ps1 -Service api -FollowLogs
#>
[CmdletBinding()]
param(
    [switch]$NoBuild,
    [switch]$DownFirst,
    [switch]$FollowLogs,
    [string]$Service = ''
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker command not found."
}

if ($DownFirst) {
    Write-Host "==> docker compose down" -ForegroundColor Cyan
    docker compose down
    if ($LASTEXITCODE -ne 0) { throw "docker compose down failed ($LASTEXITCODE)." }
}

if (-not $NoBuild) {
    Write-Host "==> docker compose build" -ForegroundColor Cyan
    docker compose build
    if ($LASTEXITCODE -ne 0) { throw "docker compose build failed ($LASTEXITCODE)." }
}
else {
    Write-Host "Skipping build (--NoBuild)." -ForegroundColor Yellow
}

Write-Host "==> docker compose up -d" -ForegroundColor Cyan
docker compose up -d
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed ($LASTEXITCODE)." }

Write-Host "==> docker compose ps" -ForegroundColor Cyan
docker compose ps

Write-Host "==> quick health probe" -ForegroundColor Cyan
try {
    $res = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:18080/app8/api/health" -TimeoutSec 8
    Write-Host "health: HTTP $($res.StatusCode)" -ForegroundColor Green
}
catch {
    Write-Host "health probe failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

if ($FollowLogs) {
    Write-Host "==> docker compose logs -f $Service" -ForegroundColor Cyan
    if ([string]::IsNullOrWhiteSpace($Service)) {
        docker compose logs -f --tail=200
    }
    else {
        docker compose logs -f --tail=200 $Service
    }
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Default UI (see .env for CADDY_HTTP_HOST_PORT):" -ForegroundColor Cyan
Write-Host "  http://127.0.0.1:18080/app8/"
Write-Host "diy-bacnet on host (DIY_BACNET_HOST_PORT):"
Write-Host "  http://127.0.0.1:28090/"
Write-Host ""
Write-Host "Tips:" -ForegroundColor Cyan
Write-Host "  Follow all logs: .\run-bas-lite.ps1 -NoBuild -FollowLogs"
Write-Host "  Follow api only: .\run-bas-lite.ps1 -NoBuild -FollowLogs -Service api"
