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

  Defaults favor Raspberry Pi labs: -SdFriendly:$true (bootstrap --sd-friendly) and
  -PrebuiltFrontend:$true (local npm run build, sync frontend/dist, Pi Docker skips Vite).
  Opt out with -SdFriendly:$false and/or -PrebuiltFrontend:$false (Pi runs npm/vite in Docker).
#>
[CmdletBinding()]
param(
    [string]$SshTarget = 'ben@192.168.204.12',
    [switch]$SkipFrontendBuild,
    [switch]$SyncOnly,
    [bool]$SdFriendly = $true,
    [bool]$PrebuiltFrontend = $true,
    [switch]$GitDeploy,
    [string]$RepoUrl = 'https://github.com/bbartling/py-bacnet-stacks-playground.git',
    [string]$RepoBranch = 'develop'
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

if ($GitDeploy -and $SyncOnly) {
    throw "Use either -GitDeploy or -SyncOnly, not both."
}

# Prebuilt UI is a Windows→SCP path; git-only deploy builds on the Pi instead.
$usePrebuilt = [bool]$PrebuiltFrontend -and -not $GitDeploy
if ($GitDeploy -and $PrebuiltFrontend) {
    Write-Host "Note: -GitDeploy skips prebuilt frontend (no PC dist to sync)." -ForegroundColor Yellow
}

if ($usePrebuilt -and $SkipFrontendBuild) {
    $distIndex = Join-Path $PSScriptRoot 'frontend/dist/index.html'
    if (-not (Test-Path -LiteralPath $distIndex)) {
        throw "-PrebuiltFrontend with -SkipFrontendBuild requires an existing frontend/dist (run npm run build in frontend/ first)."
    }
}

if (-not $SkipFrontendBuild -and -not $GitDeploy) {
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
    if ($usePrebuilt) {
        $distIndex = Join-Path $PSScriptRoot 'frontend/dist/index.html'
        if (-not (Test-Path -LiteralPath $distIndex)) {
            throw "Prebuilt frontend requires frontend/dist after build (missing $distIndex)."
        }
    }
}
else {
    if ($GitDeploy) {
        Write-Host "Skipping local frontend build check in -GitDeploy mode." -ForegroundColor Yellow
    }
    else {
        Write-Host "Skipping frontend build check (--SkipFrontendBuild)." -ForegroundColor Yellow
    }
}

if ($GitDeploy) {
    $bootstrapArgs = @()
    if ($SdFriendly) { $bootstrapArgs += "--sd-friendly" }
    $bootstrapArgString = ($bootstrapArgs -join ' ')
    $remote = @"
set -e
if [ ! -d ~/bas-lite/.git ]; then
  rm -rf ~/bas-lite
  git clone --branch $RepoBranch --depth 1 $RepoUrl ~/bas-lite
fi
cd ~/bas-lite/vibe_code_apps_8
chmod +x ./scripts/bootstrap-bas-lite.sh
if ./scripts/bootstrap-bas-lite.sh --help 2>/dev/null | grep -q -- '--git-update'; then
  ./scripts/bootstrap-bas-lite.sh --git-update $bootstrapArgString
else
  echo "bootstrap script does not support --git-update yet - running fallback path"
  git pull --rebase || git pull || true
  ./scripts/bootstrap-bas-lite.sh $bootstrapArgString
fi
"@
    Write-Host "==> Git-based deploy on $SshTarget (clone/pull + bootstrap)" -ForegroundColor Cyan
    ssh $SshTarget $remote
    if ($LASTEXITCODE -ne 0) { throw "Git-based remote bootstrap failed ($LASTEXITCODE)." }
    Write-Host ""
    Write-Host "Done. Try: http://$($SshTarget.Split('@')[-1]):18080/app8/" -ForegroundColor Green
    exit 0
}

Write-Host "==> Preparing remote directories on $SshTarget" -ForegroundColor Cyan
ssh $SshTarget "mkdir -p ~/bas-lite ~/bas-lite/docker ~/bas-lite/docker/diy-bacnet ~/bas-lite/scripts ~/bas-lite/frontend"
if ($LASTEXITCODE -ne 0) { throw "ssh mkdir failed ($LASTEXITCODE)." }

$files = @(
    'docker-compose.yml',
    'docker-compose.easy-aso-agents.example.yml',
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
    'docker/easy_aso_oat',
    'docker/easy_aso_agent',
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
    # Destination must preserve repo-relative parents (e.g. docker/diy-bacnet), not flatten into ~/bas-lite/.
    $parent = Split-Path -Parent $rel
    if ([string]::IsNullOrEmpty($parent)) {
        throw "Unexpected top-level dir sync: $rel"
    }
    $remoteParent = "~/bas-lite/$($parent -replace '\\', '/')"
    Write-Host "scp -r $rel -> ${SshTarget}:$remoteParent/" -ForegroundColor Cyan
    scp -r $local "${SshTarget}:$remoteParent/"
    if ($LASTEXITCODE -ne 0) { throw "scp -r failed for $rel ($LASTEXITCODE)." }
}

if ($usePrebuilt) {
    $distDir = Join-Path $PSScriptRoot 'frontend/dist'
    if (-not (Test-Path -LiteralPath (Join-Path $distDir 'index.html'))) {
        throw "frontend/dist/index.html missing; run npm run build in frontend/ (or use -PrebuiltFrontend:`$false)."
    }
    Write-Host "scp -r frontend/dist -> ${SshTarget}:~/bas-lite/frontend/dist (prebuilt UI)" -ForegroundColor Cyan
    ssh $SshTarget "mkdir -p ~/bas-lite/frontend"
    if ($LASTEXITCODE -ne 0) { throw "ssh mkdir frontend failed ($LASTEXITCODE)." }
    scp -r $distDir "${SshTarget}:~/bas-lite/frontend/"
    if ($LASTEXITCODE -ne 0) { throw "scp -r frontend/dist failed ($LASTEXITCODE)." }
}

Write-Host "==> Ensure bootstrap script executable" -ForegroundColor Cyan
ssh $SshTarget "chmod +x ~/bas-lite/scripts/bootstrap-bas-lite.sh"
if ($LASTEXITCODE -ne 0) { throw "ssh chmod failed ($LASTEXITCODE)." }

if ($usePrebuilt) {
    Write-Host "==> Pi .env: FRONTEND_SKIP_NODE_BUILD=1 (nginx image uses synced dist, no Vite on Pi)" -ForegroundColor Cyan
    $patchCmd = "cd ~/bas-lite && touch .env && if grep -q '^FRONTEND_SKIP_NODE_BUILD=' .env; then sed -i 's/^FRONTEND_SKIP_NODE_BUILD=.*/FRONTEND_SKIP_NODE_BUILD=1/' .env; else echo FRONTEND_SKIP_NODE_BUILD=1 >> .env; fi"
    ssh $SshTarget $patchCmd
    if ($LASTEXITCODE -ne 0) { throw "ssh .env patch for FRONTEND_SKIP_NODE_BUILD failed ($LASTEXITCODE)." }
}
elseif (-not $SyncOnly) {
    Write-Host "==> Pi .env: FRONTEND_SKIP_NODE_BUILD=0 (Vite/npm build inside Docker on Pi)" -ForegroundColor Cyan
    $patch0 = "cd ~/bas-lite && touch .env && if grep -q '^FRONTEND_SKIP_NODE_BUILD=' .env; then sed -i 's/^FRONTEND_SKIP_NODE_BUILD=.*/FRONTEND_SKIP_NODE_BUILD=0/' .env; else echo FRONTEND_SKIP_NODE_BUILD=0 >> .env; fi"
    ssh $SshTarget $patch0
    if ($LASTEXITCODE -ne 0) { throw "ssh .env patch for FRONTEND_SKIP_NODE_BUILD=0 failed ($LASTEXITCODE)." }
}

if ($SyncOnly) {
    Write-Host ""
    Write-Host "Sync complete (SyncOnly)." -ForegroundColor Green
    $bootHint = "./scripts/bootstrap-bas-lite.sh"
    if ($SdFriendly) {
        $bootHint = "$bootHint --sd-friendly"
    }
    Write-Host "Next on Pi: cd ~/bas-lite && $bootHint"
    Write-Host '  (Layout: same paths as repo, e.g. ~/bas-lite/docker/diy-bacnet/Dockerfile must exist.)'
    if ($usePrebuilt) {
        Write-Host '  Prebuilt frontend: Pi .env has FRONTEND_SKIP_NODE_BUILD=1; docker compose build frontend uses synced dist only.'
    }
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
