<#
.SYNOPSIS
  Deploy diy-bas from this script's directory to a Raspberry Pi (zip + ssh).

.DESCRIPTION
  Single Django app deployment (Caddy + diy-bas). After upload, optionally syncs
  bootstrap login values from .env.example into Pi .env, runs bootstrap setup,
  starts docker compose, checks /api/health, and verifies /api/auth/login.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$PiHost,
    [Parameter(Mandatory = $true)]
    [string]$PiUser,
    [string]$RemoteDir = "",
    [string]$RemoteBacnetDir = "",
    [bool]$RunBootstrap = $true,
    [bool]$StartApp = $true,
    [bool]$UseDockerStack = $true,
    [bool]$TestLogin = $true,
    [bool]$SyncBootstrapCredentialsFromExample = $true,
    [bool]$DockerMaintenance = $true,
    [string]$LoginUsername = "integrator",
    [string]$LoginPassword = "ChangeMeNow!123"
)

$ErrorActionPreference = "Stop"

function Assert-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

Assert-Command "ssh"
Assert-Command "scp"
Assert-Command "robocopy"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$resolvedRemoteDir = if ($RemoteDir) { $RemoteDir } else { "/home/$PiUser/diy-bas" }
$remoteDataDir = "/var/lib/diy-bas"
$resolvedRemoteBacnetDir = if ($RemoteBacnetDir) { $RemoteBacnetDir } else { "/home/$PiUser/diy-bacnet-server" }
$stagingDir = Join-Path $env:TEMP ("diy-bas-staging-" + [guid]::NewGuid().ToString("N"))
$zipPath = Join-Path $env:TEMP "diy-bas-deploy.zip"
$remoteZip = "/home/$PiUser/diy-bas-deploy.zip"

if (Test-Path $stagingDir) { Remove-Item -Recurse -Force $stagingDir }
New-Item -ItemType Directory -Path $stagingDir | Out-Null
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }

Write-Host "[deploy] Staging files from $projectDir ..."
$null = robocopy $projectDir $stagingDir /E /R:1 /W:1 /XD .venv __pycache__ .git data staticfiles /XF *.pyc *.pyo *.sqlite3 *.db
$robocopyCode = $LASTEXITCODE
if ($robocopyCode -ge 8) {
    throw "robocopy failed with code $robocopyCode"
}

Write-Host "[deploy] Creating zip: $zipPath ..."
Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipPath -Force

Write-Host "[deploy] Uploading zip to $PiUser@$PiHost ..."
scp $zipPath "${PiUser}@${PiHost}:${remoteZip}" | Out-Host

Write-Host "[deploy] Applying uploaded package on Pi ..."
$old = $resolvedRemoteDir
$bak = "${resolvedRemoteDir}.bak"
$rotateBash = "set -e; OLD='$old'; BAK='$bak'; if [ -d `"`$OLD`" ] && [ -f `"`$OLD/docker-compose.yml`" ]; then (cd `"`$OLD`" && docker compose down) 2>/dev/null || true; fi; if [ -d `"`$BAK`" ]; then sudo rm -rf `"`$BAK`" 2>/dev/null || rm -rf `"`$BAK`" || true; fi; if [ -d `"`$OLD`" ]; then mv `"`$OLD`" `"`$BAK`"; fi; mkdir -p `"`$OLD`""
ssh "${PiUser}@${PiHost}" $rotateBash | Out-Host
ssh "${PiUser}@${PiHost}" "sudo mkdir -p '${remoteDataDir}' && sudo chown -R '${PiUser}':'${PiUser}' '${remoteDataDir}'" | Out-Host
ssh "${PiUser}@${PiHost}" "unzip -o '${remoteZip}' -d '${resolvedRemoteDir}' >/dev/null" | Out-Host
ssh "${PiUser}@${PiHost}" "find '${resolvedRemoteDir}' -type f -name '*.sh' -exec sed -i 's/\r$//' {} +; chmod +x '${resolvedRemoteDir}/bootstrap_pi.sh' || true" | Out-Host

if ($RunBootstrap) {
    Write-Host "[deploy] Running bootstrap (setup-only) ..."
    ssh "${PiUser}@${PiHost}" "cd ${resolvedRemoteDir} && export DIY_BACNET_SERVER_DIR='${resolvedRemoteBacnetDir}' && BOOTSTRAP_NO_RUN=1 BOOTSTRAP_MANAGE_BACNET_SERVER=1 bash ./bootstrap_pi.sh" | Out-Host
}

if ($SyncBootstrapCredentialsFromExample) {
    Write-Host "[deploy] Merging bootstrap auth from .env.example into .env ..."
    ssh "${PiUser}@${PiHost}" "cd '${resolvedRemoteDir}' && python3 tools/sync_bootstrap_env_from_example.py" | Out-Host
}

if ($StartApp) {
    if ($UseDockerStack) {
        Write-Host "[deploy] Starting docker stack ..."
        ssh "${PiUser}@${PiHost}" "cd ${resolvedRemoteDir} && export DIY_BACNET_SERVER_DIR='${resolvedRemoteBacnetDir}' && docker compose up -d --build caddy diy-bas" | Out-Host
    }

    Write-Host "[deploy] Waiting for /api/health (up to 45s) ..."
    $healthy = $false
    $healthPath = if ($UseDockerStack) { "http://127.0.0.1/api/health" } else { "http://127.0.0.1:5050/api/health" }
    for ($i = 0; $i -lt 22; $i++) {
        $health = ssh "${PiUser}@${PiHost}" "curl -s --max-time 2 ${healthPath}" 2>$null
        if ($LASTEXITCODE -eq 0 -and $health) {
            $healthy = $true
            Write-Host $health
            break
        }
        Start-Sleep -Seconds 2
    }

    if ($UseDockerStack) {
        Write-Host "[deploy] Recent docker compose logs ..."
        ssh "${PiUser}@${PiHost}" "cd ${resolvedRemoteDir} && docker compose logs --no-color --tail=80 caddy diy-bas" | Out-Host
    }

    if (-not $healthy) {
        throw "App did not become healthy on Pi within timeout."
    }

    if ($TestLogin) {
        $loginUrl = if ($UseDockerStack) { "http://127.0.0.1/api/auth/login" } else { "http://127.0.0.1:5050/api/auth/login" }
        Write-Host "[deploy] Verifying POST /api/auth/login on Pi ($loginUrl) ..."
        Write-Host "[deploy] Login test user: $LoginUsername"
        $loginSpec = @{ url = $loginUrl; username = $LoginUsername; password = $LoginPassword } | ConvertTo-Json -Compress
        $loginSpec | ssh "${PiUser}@${PiHost}" "cd '$resolvedRemoteDir' && python3 tools/pi_verify_login.py" | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw 'Login verification failed on Pi. Verify -LoginUsername/-LoginPassword (or use -TestLogin:$false to skip).'
        }
    }
}

if ($DockerMaintenance -and $StartApp -and $UseDockerStack) {
    Write-Host "[deploy] Docker maintenance: compose down in ~/diy-bas.bak* and prune dangling images ..."
    $maint = 'set -e; shopt -s nullglob 2>/dev/null || true; for d in "$HOME"/diy-bas.bak*; do if [ -d "$d" ] && [ -f "$d/docker-compose.yml" ]; then (cd "$d" && docker compose down --remove-orphans) 2>/dev/null || true; fi; done; docker image prune -f >/dev/null 2>&1 || true'
    ssh "${PiUser}@${PiHost}" $maint | Out-Host
}

Write-Host "[deploy] Done."

Remove-Item -Recurse -Force $stagingDir -ErrorAction SilentlyContinue
Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
