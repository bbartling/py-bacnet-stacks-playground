# Easy button: pull newest vibe19 image and recreate the long-running container.
# BUG-061: default bind $HOME/wattlab_workspace -> /data (set DataMount=none to skip).
# Usage:
#   .\scripts\docker_update_vibe19.ps1
#   .\scripts\docker_update_vibe19.ps1 -Tag develop
#   .\scripts\docker_update_vibe19.ps1 -Tag latest -HostPort 8501
#   .\scripts\docker_update_vibe19.ps1 -DataMount "C:\Users\ben\wattlab_workspace:/data"
param(
    [string]$Tag = "latest",
    [string]$Name = "vibe19",
    [int]$HostPort = 8502,
    [string]$DataMount = ""
)

$ErrorActionPreference = "Stop"
$Image = "ghcr.io/bbartling/vibe19:$Tag"
$DefaultHostWs = if ($env:WATTLAB_HOST_WORKSPACE) { $env:WATTLAB_HOST_WORKSPACE } else {
    Join-Path $HOME "wattlab_workspace"
}

if (-not $DataMount) {
    if ($env:DATA_MOUNT) {
        $DataMount = $env:DATA_MOUNT
    } elseif (Test-Path -LiteralPath $DefaultHostWs) {
        $DataMount = "${DefaultHostWs}:/data"
    }
}
if ($DataMount -in @("none", "off", "0")) {
    $DataMount = ""
}

Write-Host "==> Pulling $Image"
docker pull $Image
if ($LASTEXITCODE -ne 0) { throw "docker pull failed" }

Write-Host "==> Recreating container '$Name' on host port $HostPort"
if ($DataMount) {
    Write-Host "    bind: $DataMount"
} else {
    Write-Host "    bind: (none)"
}

docker stop $Name 2>$null | Out-Null
docker rm $Name 2>$null | Out-Null

$runArgs = @(
    "-d", "--restart", "unless-stopped",
    "-p", "${HostPort}:8501",
    "--name", $Name
)
if ($DataMount) {
    $runArgs += @("-v", $DataMount)
}
$runArgs += $Image

docker run @runArgs
if ($LASTEXITCODE -ne 0) { throw "docker run failed" }

Write-Host "==> Running:"
docker ps --filter "name=$Name"
Write-Host "Open http://localhost:${HostPort}  (or http://<host-ip>:${HostPort})"
Write-Host "Note: a running container never auto-updates - re-run this script after GHCR builds."
