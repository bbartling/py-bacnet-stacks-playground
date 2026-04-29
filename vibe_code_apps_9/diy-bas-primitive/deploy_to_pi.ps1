param(
    [Parameter(Mandatory = $true)]
    [string]$PiHost,
    [Parameter(Mandatory = $true)]
    [string]$PiUser,
    [string]$RemoteDir = "",
    [string]$RemoteBacnetDir = "",
    [bool]$RunBootstrap = $true,
    [bool]$StartApp = $true,
    [bool]$UseDockerStack = $true
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
$null = robocopy $projectDir $stagingDir /E /R:1 /W:1 /XD .venv __pycache__ .git data /XF *.pyc *.pyo *.sqlite3 *.db
$robocopyCode = $LASTEXITCODE
if ($robocopyCode -ge 8) {
    throw "robocopy failed with code $robocopyCode"
}

Write-Host "[deploy] Creating zip: $zipPath ..."
Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipPath -Force

Write-Host "[deploy] Uploading zip to $PiUser@$PiHost ..."
scp $zipPath "${PiUser}@${PiHost}:${remoteZip}" | Out-Host

Write-Host "[deploy] Applying uploaded package on Pi ..."
ssh "${PiUser}@${PiHost}" "rm -rf '${resolvedRemoteDir}.bak'; if [ -d '${resolvedRemoteDir}' ]; then mv '${resolvedRemoteDir}' '${resolvedRemoteDir}.bak'; fi; mkdir -p '${resolvedRemoteDir}'" | Out-Host
ssh "${PiUser}@${PiHost}" "sudo mkdir -p '${remoteDataDir}' && sudo chown -R '${PiUser}':'${PiUser}' '${remoteDataDir}'" | Out-Host
ssh "${PiUser}@${PiHost}" "unzip -o '${remoteZip}' -d '${resolvedRemoteDir}' >/dev/null" | Out-Host
ssh "${PiUser}@${PiHost}" "find '${resolvedRemoteDir}' -type f -name '*.sh' -exec sed -i 's/\r$//' {} +; chmod +x '${resolvedRemoteDir}/bootstrap_pi.sh' || true; ls -la '${resolvedRemoteDir}/bootstrap_pi.sh'" | Out-Host

if ($RunBootstrap) {
    Write-Host "[deploy] Running bootstrap (setup-only) ..."
    ssh "${PiUser}@${PiHost}" "cd ${resolvedRemoteDir} && export DIY_BACNET_SERVER_DIR='${resolvedRemoteBacnetDir}' && BOOTSTRAP_NO_RUN=1 BOOTSTRAP_MANAGE_BACNET_SERVER=1 bash ./bootstrap_pi.sh" | Out-Host
}

if ($StartApp) {
    if ($UseDockerStack) {
        Write-Host "[deploy] Starting docker stack (Caddy mode) ..."
        ssh "${PiUser}@${PiHost}" "cd ${resolvedRemoteDir} && export DIY_BACNET_SERVER_DIR='${resolvedRemoteBacnetDir}' && docker compose up -d --build caddy diy-bas" | Out-Host
    } else {
        Write-Host "[deploy] Starting app in background (venv mode) ..."
        ssh "${PiUser}@${PiHost}" "pkill -f '${resolvedRemoteDir}/.venv/bin/python run.py' || true; pkill -f 'python run.py' || true; cd ${resolvedRemoteDir} && nohup ./.venv/bin/python run.py > bootstrap_run.log 2>&1 < /dev/null & echo started" | Out-Host
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
        ssh "${PiUser}@${PiHost}" "cd ${resolvedRemoteDir} && docker compose logs --no-color --tail=60 caddy diy-bas" | Out-Host
    } else {
        Write-Host "[deploy] Recent app log tail ..."
        ssh "${PiUser}@${PiHost}" "cd ${resolvedRemoteDir} && tail -n 40 bootstrap_run.log 2>/dev/null || true" | Out-Host
    }
    if (-not $healthy) {
        throw "App did not become healthy on Pi within timeout."
    }
}

Write-Host "[deploy] Done."

Remove-Item -Recurse -Force $stagingDir -ErrorAction SilentlyContinue
Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
