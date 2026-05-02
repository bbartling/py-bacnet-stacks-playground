<#
.SYNOPSIS
  Deploy diy-bas from this script's directory to a Raspberry Pi (zip + ssh).

.DESCRIPTION
  Single Django app deployment (Caddy + diy-bas). After upload, optionally syncs
  bootstrap login values from .env.example into Pi .env, then applies -LoginUsername/-LoginPassword
  and maintenance credentials onto Pi .env (so browser login matches the GUI). With -NtfyPush 1,
  merges DIY_BAS_NTFY_* from -NtfyEnvB64 into Pi .env (same pattern as deploy GUI). Runs bootstrap setup,
  starts docker compose, checks /api/health, and verifies /api/auth/login.
  Runs tools/pi_post_unzip_fix.sh on the Pi so Docker build context can read all files
  (fixes permission denied on bas/templates/bas). Use -VerboseDeploy 1 for plain build logs.
  Switch-like options use 0/1 so GUI and cmd.exe can pass them reliably (not `$true` / `$false` strings).
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$PiHost,
    [Parameter(Mandatory = $true)]
    [string]$PiUser,
    [string]$RemoteDir = "",
    [string]$RemoteBacnetDir = "",
    [ValidateRange(0, 1)]
    [int]$RunBootstrap = 1,
    [ValidateRange(0, 1)]
    [int]$StartApp = 1,
    [ValidateRange(0, 1)]
    [int]$UseDockerStack = 1,
    [ValidateRange(0, 1)]
    [int]$TestLogin = 1,
    [ValidateRange(0, 1)]
    [int]$SyncBootstrapCredentialsFromExample = 1,
    [ValidateRange(0, 1)]
    [int]$DockerMaintenance = 1,
    [string]$LoginUsername = "integrator",
    [string]$LoginPassword = "ChangeMeNow!123",
    [string]$MaintUsername = "maintenance",
    [string]$MaintPassword = "ChangeMeNow!123",
    [ValidateRange(0, 1)]
    [int]$NtfyPush = 0,
    [string]$NtfyEnvB64 = "",
    [ValidateRange(0, 1)]
    [int]$VerboseDeploy = 0,
    [int]$BootstrapLogTail = 80,
    [int]$ComposeLogTail = 50
)

$ErrorActionPreference = "Stop"

function Write-DeployLog([string]$Message) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$ts] [deploy] $Message"
}

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

Write-DeployLog "Staging files from $projectDir ..."
# Exclude .env so the Pi keeps its own secrets (use .env.example + sync tool / bootstrap for keys).
$null = robocopy $projectDir $stagingDir /E /R:1 /W:1 /XD .venv __pycache__ .git data staticfiles /XF *.pyc *.pyo *.sqlite3 *.db .env
$robocopyCode = $LASTEXITCODE
if ($robocopyCode -ge 8) {
    throw "robocopy failed with code $robocopyCode"
}
Write-DeployLog "robocopy exit code: $robocopyCode (0-7 = success with file stats)"

Write-DeployLog "Creating zip: $zipPath ..."
Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipPath -Force
$zipLen = (Get-Item $zipPath).Length
Write-DeployLog "Zip size: $zipLen bytes"

Write-DeployLog "Uploading zip to ${PiUser}@${PiHost}:${remoteZip} ..."
scp $zipPath "${PiUser}@${PiHost}:${remoteZip}" | Out-Host
if ($LASTEXITCODE -ne 0) { throw "scp upload failed with exit code $LASTEXITCODE" }

Write-DeployLog "Applying uploaded package on Pi (remote dir: $resolvedRemoteDir) ..."
$old = $resolvedRemoteDir
$bak = "${resolvedRemoteDir}.bak"
$rotateBash = "set -e; OLD='$old'; BAK='$bak'; if [ -d `"`$OLD`" ] && [ -f `"`$OLD/docker-compose.yml`" ]; then (cd `"`$OLD`" && docker compose down) 2>/dev/null || true; fi; if [ -d `"`$BAK`" ]; then sudo rm -rf `"`$BAK`" 2>/dev/null || rm -rf `"`$BAK`" || true; fi; if [ -d `"`$OLD`" ]; then mv `"`$OLD`" `"`$BAK`"; fi; mkdir -p `"`$OLD`""
ssh "${PiUser}@${PiHost}" $rotateBash | Out-Host
ssh "${PiUser}@${PiHost}" "sudo mkdir -p '${remoteDataDir}' && sudo chown -R '${PiUser}':'${PiUser}' '${remoteDataDir}'" | Out-Host
# unzip(1): 0 = normal, 1 = warnings only (e.g. Windows ZIP backslash paths) — files are still extracted. -q reduces noise.
ssh "${PiUser}@${PiHost}" "unzip -q -o '${remoteZip}' -d '${resolvedRemoteDir}'" | Out-Host
$unzipExit = $LASTEXITCODE
if ($unzipExit -eq 1) {
    Write-DeployLog "unzip exited 1 (warnings only); continuing."
}
elseif ($unzipExit -ne 0) {
    throw "remote unzip failed with exit code $unzipExit (see output above; on Pi: unzip -t '$remoteZip')"
}
Write-DeployLog "Unzip finished; normalizing line endings and fixing permissions for Docker build context ..."
ssh "${PiUser}@${PiHost}" "find '${resolvedRemoteDir}' -type f -name '*.sh' -exec sed -i 's/\r$//' {} + 2>/dev/null; chmod +x '${resolvedRemoteDir}/bootstrap_pi.sh' '${resolvedRemoteDir}/docker-entrypoint.sh' '${resolvedRemoteDir}/tools/pi_post_unzip_fix.sh' 2>/dev/null || true" | Out-Null
ssh "${PiUser}@${PiHost}" "bash '${resolvedRemoteDir}/tools/pi_post_unzip_fix.sh' '${resolvedRemoteDir}' '${PiUser}'" | Out-Host

if ($RunBootstrap) {
    Write-DeployLog "Running bootstrap (setup-only); showing last $BootstrapLogTail lines of output ..."
    ssh "${PiUser}@${PiHost}" "cd '${resolvedRemoteDir}' && export DIY_BACNET_SERVER_DIR='${resolvedRemoteBacnetDir}' && BOOTSTRAP_NO_RUN=1 BOOTSTRAP_MANAGE_BACNET_SERVER=1 bash ./bootstrap_pi.sh 2>&1 | tail -n $BootstrapLogTail" | Out-Host
}

if ($SyncBootstrapCredentialsFromExample) {
    Write-DeployLog "Merging bootstrap auth from .env.example into .env ..."
    ssh "${PiUser}@${PiHost}" "cd '${resolvedRemoteDir}' && python3 tools/sync_bootstrap_env_from_example.py" | Out-Host
}

Write-DeployLog "Applying deploy credential overrides to Pi .env (Integrator + Building Operator from this run) ..."
$credObj = @{
    DIY_BAS_ADMIN_USERNAME = $LoginUsername
    DIY_BAS_ADMIN_PASSWORD = $LoginPassword
    DIY_BAS_MAINT_USERNAME = $MaintUsername
    DIY_BAS_MAINT_PASSWORD = $MaintPassword
}
$json = $credObj | ConvertTo-Json -Compress
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
$b64 = [Convert]::ToBase64String($utf8NoBom.GetBytes($json))
ssh "${PiUser}@${PiHost}" "cd '${resolvedRemoteDir}' && printf '%s' '$b64' | base64 -d | python3 tools/apply_deploy_credentials_from_stdin.py" | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "apply_deploy_credentials_from_stdin.py failed on Pi (exit $LASTEXITCODE). Check JSON/base64 pipeline."
}

if ($NtfyPush -eq 1) {
    Write-DeployLog "Applying ntfy settings to Pi .env ..."
    if (-not $NtfyEnvB64) {
        throw "NtfyPush=1 requires NtfyEnvB64 (base64 UTF-8 JSON with DIY_BAS_NTFY_* keys)."
    }
    ssh "${PiUser}@${PiHost}" "cd '${resolvedRemoteDir}' && printf '%s' '$NtfyEnvB64' | base64 -d | python3 tools/apply_ntfy_env_from_stdin.py" | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "apply_ntfy_env_from_stdin.py failed on Pi (exit $LASTEXITCODE)."
    }
}

if ($StartApp) {
    if ($UseDockerStack) {
        Write-DeployLog "Docker: compose directory = $resolvedRemoteDir ; DIY_BACNET_SERVER_DIR = $resolvedRemoteBacnetDir"
        $composeEnv = "cd '${resolvedRemoteDir}' && export DIY_BACNET_SERVER_DIR='${resolvedRemoteBacnetDir}'"
        $dockerQuiet = 'export DOCKER_CLI_HINTS=false'
        if ($VerboseDeploy) {
            Write-DeployLog "Verbose: docker compose build --progress=plain (diy-bas) ..."
            ssh "${PiUser}@${PiHost}" "$composeEnv && $dockerQuiet && docker compose build --progress=plain diy-bas" | Out-Host
            if ($LASTEXITCODE -ne 0) {
                Write-DeployLog "WARN: docker compose build exited $LASTEXITCODE ; collecting diagnostics ..."
                ssh "${PiUser}@${PiHost}" "$composeEnv && docker compose ps -a && ls -la bas/templates/bas 2>&1; id; groups" | Out-Host
                throw "docker compose build failed on Pi (exit $LASTEXITCODE). See logs above; often fixed by: sudo chown -R ${PiUser}:${PiUser} ${resolvedRemoteDir}"
            }
            Write-DeployLog "Starting caddy + diy-bas (no rebuild) ..."
            ssh "${PiUser}@${PiHost}" "$composeEnv && $dockerQuiet && docker compose up -d caddy diy-bas" | Out-Host
        }
        else {
            Write-DeployLog "Starting docker stack (compose up -d --build; pull/build can be chatty) ..."
            ssh "${PiUser}@${PiHost}" "$composeEnv && $dockerQuiet && docker compose up -d --build caddy diy-bas" | Out-Host
            if ($LASTEXITCODE -ne 0) {
                Write-DeployLog "compose up failed (exit $LASTEXITCODE). Diagnostics:"
                ssh "${PiUser}@${PiHost}" "$composeEnv && docker compose ps -a 2>&1; echo '---'; ls -laR bas/templates 2>&1 | head -40" | Out-Host
                throw "docker compose up --build failed on Pi. Re-run with -VerboseDeploy 1 for full build log, or on Pi: sudo chown -R ${PiUser}:${PiUser} ${resolvedRemoteDir}"
            }
        }
    }

    Write-DeployLog "Waiting for /api/health (up to ~44s) ..."
    $healthy = $false
    $healthPath = if ($UseDockerStack) { "http://127.0.0.1/api/health" } else { "http://127.0.0.1:5050/api/health" }
    for ($i = 0; $i -lt 22; $i++) {
        $health = ssh "${PiUser}@${PiHost}" "curl -s --max-time 2 ${healthPath}" 2>$null
        if ($LASTEXITCODE -eq 0 -and $health) {
            $healthy = $true
            Write-DeployLog "Health OK (length $($health.Length) chars)."
            break
        }
        if ($i -eq 0 -or $i -eq 5 -or $i -eq 10) {
            $healthLen = 0
            if ($health) { $healthLen = $health.Length }
            Write-DeployLog "Health poll $i : ssh/curl exit=$LASTEXITCODE bodyLen=$healthLen"
        }
        Start-Sleep -Seconds 2
    }

    if ($UseDockerStack) {
        Write-DeployLog "Recent docker compose logs (caddy, diy-bas) ..."
        ssh "${PiUser}@${PiHost}" "cd '${resolvedRemoteDir}' && docker compose logs --no-color --tail=$ComposeLogTail caddy diy-bas" | Out-Host
    }

    if (-not $healthy) {
        Write-DeployLog "Health check exhausted. Extra diagnostics:"
        ssh "${PiUser}@${PiHost}" "cd '${resolvedRemoteDir}' && docker compose ps -a 2>&1; echo '---'; ls -la bas/templates/bas 2>&1; echo '---'; find bas -maxdepth 4 ! -readable 2>/dev/null | head -20" | Out-Host
        throw "App did not become healthy on Pi within timeout."
    }

    if ($TestLogin) {
        $loginUrl = if ($UseDockerStack) { "http://127.0.0.1/api/auth/login" } else { "http://127.0.0.1:5050/api/auth/login" }
        Write-DeployLog "Verifying POST /api/auth/login on Pi ($loginUrl) ..."
        Write-DeployLog "Login test user: $LoginUsername"
        $loginSpec = @{ url = $loginUrl; username = $LoginUsername; password = $LoginPassword } | ConvertTo-Json -Compress
        $loginSpec | ssh "${PiUser}@${PiHost}" "cd '$resolvedRemoteDir' && python3 tools/pi_verify_login.py" | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw (
                "Login verification failed on Pi. Credentials should match -LoginUsername / -LoginPassword (same as GUI Integrator fields); " +
                "those are written into Pi .env before compose. Pass -TestLogin 0 to skip this check."
            )
        }
    }
}

if ($DockerMaintenance -and $StartApp -and $UseDockerStack) {
    Write-DeployLog "Docker maintenance: compose down in ~/diy-bas.bak* and prune dangling images ..."
    $maint = 'set -e; shopt -s nullglob 2>/dev/null || true; for d in "$HOME"/diy-bas.bak*; do if [ -d "$d" ] && [ -f "$d/docker-compose.yml" ]; then (cd "$d" && docker compose down --remove-orphans) 2>/dev/null || true; fi; done; docker image prune -f >/dev/null 2>&1 || true'
    ssh "${PiUser}@${PiHost}" $maint | Out-Host
}

Write-DeployLog "Done."

Remove-Item -Recurse -Force $stagingDir -ErrorAction SilentlyContinue
Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
