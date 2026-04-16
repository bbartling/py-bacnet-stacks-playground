#Requires -Version 5.1
<#
.SYNOPSIS
  Local BAS Lite on Windows Docker Desktop (compose from stack root next to scripts/).

.DESCRIPTION
  Sets working directory to the parent of scripts/ (where docker-compose.yml lives).

  Use -ProductionFrontend to match the Pi: npm run build with VITE_BASE_PATH=/app8, then
  FRONTEND_SKIP_NODE_BUILD=1 for docker compose so the nginx image uses frontend/dist
  (same pattern as deploy to Boss Pi).

.EXAMPLE
  cd vibe_code_apps_8   # parent of scripts/
  .\scripts\run-bas-lite.ps1
  .\scripts\run-bas-lite.ps1 -ProductionFrontend
  .\scripts\run-bas-lite.ps1 -ProductionFrontend -NoBuild -FollowLogs
  .\scripts\run-bas-lite.ps1 -DownFirst -ProductionFrontend
#>
[CmdletBinding()]
param(
    [switch]$NoBuild,
    [switch]$DownFirst,
    [switch]$FollowLogs,
    [string]$Service = '',
    [switch]$ProductionFrontend
)

$ErrorActionPreference = "Stop"
$StackRoot = Split-Path -Path $PSScriptRoot -Parent
Set-Location -Path $StackRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker command not found."
}

if ($ProductionFrontend -and $NoBuild) {
    $distIndex = Join-Path $StackRoot 'frontend/dist/index.html'
    if (-not (Test-Path -LiteralPath $distIndex)) {
        throw "-ProductionFrontend with -NoBuild requires frontend/dist (run once without -NoBuild, or npm run build in frontend/)."
    }
}

if ($ProductionFrontend -and -not $NoBuild) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm not found; install Node.js or run without -ProductionFrontend."
    }
    Write-Host "==> Pi-like frontend: npm run build (VITE_BASE_PATH=/app8)" -ForegroundColor Cyan
    Push-Location (Join-Path $StackRoot 'frontend')
    try {
        $oldViteBase = $env:VITE_BASE_PATH
        $env:VITE_BASE_PATH = "/app8"
        if (-not (Test-Path -LiteralPath 'node_modules')) {
            npm install
            if ($LASTEXITCODE -ne 0) { throw "npm install failed ($LASTEXITCODE)." }
        }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed ($LASTEXITCODE)." }
    }
    finally {
        if ($null -eq $oldViteBase) {
            Remove-Item Env:VITE_BASE_PATH -ErrorAction SilentlyContinue
        }
        else {
            $env:VITE_BASE_PATH = $oldViteBase
        }
        Pop-Location
    }
}

$oldSkip = $env:FRONTEND_SKIP_NODE_BUILD
try {
    if ($ProductionFrontend) {
        $env:FRONTEND_SKIP_NODE_BUILD = '1'
        Write-Host "==> compose: FRONTEND_SKIP_NODE_BUILD=1 (prebuilt dist in frontend image)" -ForegroundColor Cyan
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
    $healthUri = "http://127.0.0.1:18080/app8/api/health"
    $maxWaitSec = 45
    $deadline = (Get-Date).AddSeconds($maxWaitSec)
    $attempt = 0
    $ok = $false
    while ((Get-Date) -lt $deadline) {
        $attempt += 1
        try {
            $res = Invoke-WebRequest -UseBasicParsing -Uri $healthUri -TimeoutSec 6
            if ($res.StatusCode -eq 200) {
                Write-Host "health: HTTP $($res.StatusCode) (attempt $attempt)" -ForegroundColor Green
                $ok = $true
                break
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    if (-not $ok) {
        Write-Host "health probe failed after ${maxWaitSec}s: $healthUri" -ForegroundColor Yellow
        Write-Host "Tip: run .\scripts\run-bas-lite.ps1 -NoBuild -FollowLogs -Service api" -ForegroundColor Yellow
    }
}
finally {
    if ($null -eq $oldSkip) {
        Remove-Item Env:FRONTEND_SKIP_NODE_BUILD -ErrorAction SilentlyContinue
    }
    else {
        $env:FRONTEND_SKIP_NODE_BUILD = $oldSkip
    }
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
Write-Host "  (No port means Windows IIS/local web server, not this stack; use :18080)" -ForegroundColor DarkGray
Write-Host "diy-bacnet on host (DIY_BACNET_HOST_PORT):"
Write-Host "  http://127.0.0.1:28090/"
Write-Host ""
Write-Host "HTTP smoke tests (Pi-style UI checks):" -ForegroundColor Cyan
Write-Host "  .\scripts\test-bas-lite-http.ps1"
Write-Host ""
Write-Host "Tips:" -ForegroundColor Cyan
Write-Host "  Pi-like prebuilt UI: .\scripts\run-bas-lite.ps1 -ProductionFrontend"
Write-Host "  Follow all logs: .\scripts\run-bas-lite.ps1 -NoBuild -FollowLogs"
Write-Host "  Follow api only: .\scripts\run-bas-lite.ps1 -NoBuild -FollowLogs -Service api"
Write-Host "  Test Boss Pi: .\scripts\test-bas-lite-http.ps1 -BossPi"
