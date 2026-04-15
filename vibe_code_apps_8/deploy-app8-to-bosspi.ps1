#Requires -Version 5.1
<#
.SYNOPSIS
  Single-script deploy for BAS Lite to Boss Pi.

.DESCRIPTION
  This is the one script to push files from Windows -> Boss Pi.
  It can:
    1) run local frontend build check,
    2) sync all required stack files to ~/bas-lite,
    3) run remote bootstrap to build/up containers.

  Use -SyncOnly if you only want to copy files.
#>
[CmdletBinding()]
param(
    [string]$SshTarget = 'ben@192.168.204.12',
    [switch]$SkipFrontendBuild,
    [switch]$SyncOnly,
    [switch]$SdFriendly
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Assert-Cmd([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name command not found in PATH."
    }
}

Assert-Cmd ssh
Assert-Cmd scp

if (-not $SkipFrontendBuild) {
    Write-Host "==> Frontend build check (npm run build)" -ForegroundColor Cyan
    Push-Location (Join-Path $PSScriptRoot 'frontend')
    try {
        if (-not (Test-Path -LiteralPath 'node_modules')) {
            npm install
            if ($LASTEXITCODE -ne 0) { throw "npm install failed ($LASTEXITCODE)." }
        }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed ($LASTEXITCODE)." }
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "Skipping frontend build check (--SkipFrontendBuild)." -ForegroundColor Yellow
}

Write-Host "==> Preparing remote directories on $SshTarget" -ForegroundColor Cyan
ssh $SshTarget "mkdir -p ~/bas-lite ~/bas-lite/docker ~/bas-lite/scripts ~/bas-lite/frontend"
if ($LASTEXITCODE -ne 0) { throw "ssh mkdir failed ($LASTEXITCODE)." }

$files = @(
    'docker-compose.yml',
    '.env.example',
    '.dockerignore',
    'bosspi.env',
    'run-bas-lite.ps1',
    'scripts/bootstrap-bas-lite.sh',
    'docker/Dockerfile.frontend'
)

$dirs = @(
    'docker/bas_lite_api',
    'docker/caddy',
    'docker/diy-bacnet',
    'docker/nginx',
    'frontend/src'
)

$frontendRootFiles = @(
    'frontend/package.json',
    'frontend/package-lock.json',
    'frontend/tsconfig.json',
    'frontend/tsconfig.app.json',
    'frontend/tsconfig.node.json',
    'frontend/vite.config.ts',
    'frontend/index.html',
    'frontend/eslint.config.js',
    'frontend/components.json'
)

foreach ($rel in $files + $frontendRootFiles) {
    $local = Join-Path $PSScriptRoot $rel
    if (-not (Test-Path -LiteralPath $local)) {
        throw "Missing required path: $local"
    }
    Write-Host "scp $rel -> ${SshTarget}:~/bas-lite/$rel" -ForegroundColor Cyan
    scp $local "${SshTarget}:~/bas-lite/$rel"
    if ($LASTEXITCODE -ne 0) { throw "scp failed for $rel ($LASTEXITCODE)." }
}

foreach ($rel in $dirs) {
    $local = Join-Path $PSScriptRoot $rel
    if (-not (Test-Path -LiteralPath $local)) {
        throw "Missing required directory: $local"
    }
    Write-Host "scp -r $rel -> ${SshTarget}:~/bas-lite/" -ForegroundColor Cyan
    scp -r $local "${SshTarget}:~/bas-lite/"
    if ($LASTEXITCODE -ne 0) { throw "scp -r failed for $rel ($LASTEXITCODE)." }
}

Write-Host "==> Ensure bootstrap script executable" -ForegroundColor Cyan
ssh $SshTarget "chmod +x ~/bas-lite/scripts/bootstrap-bas-lite.sh"
if ($LASTEXITCODE -ne 0) { throw "ssh chmod failed ($LASTEXITCODE)." }

if ($SyncOnly) {
    Write-Host ""
    Write-Host "Sync complete (SyncOnly)." -ForegroundColor Green
    Write-Host "Next on Pi: cd ~/bas-lite && ./scripts/bootstrap-bas-lite.sh"
    exit 0
}

$bootstrapCmd = "cd ~/bas-lite && ./scripts/bootstrap-bas-lite.sh"
if ($SdFriendly) {
    $bootstrapCmd = "$bootstrapCmd --sd-friendly"
}

Write-Host "==> Running remote bootstrap on $SshTarget" -ForegroundColor Cyan
ssh $SshTarget $bootstrapCmd
if ($LASTEXITCODE -ne 0) { throw "Remote bootstrap failed ($LASTEXITCODE)." }

Write-Host ""
Write-Host "Done. Try: http://$($SshTarget.Split('@')[-1]):18080/app8/" -ForegroundColor Green
