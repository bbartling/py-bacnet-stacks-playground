#Requires -Version 5.1
<#
.SYNOPSIS
  Push BAS Lite to a Pi: by default full deploy (SD-friendly + PC-built UI).

.DESCRIPTION
  Wraps deploy-app8-to-bosspi.ps1 with beginner-friendly defaults:
  - Runs remote bootstrap (docker compose build/up) unless you pass -SyncOnly.
  - Passes -SdFriendly:$true so bootstrap uses --sd-friendly (trend / agent cadence).
  - Passes -PrebuiltFrontend:$true so the PC runs npm run build and syncs dist (Pi skips Vite in Docker).

  Use -SyncOnly when you only want to copy files and will run bootstrap yourself on the Pi.

.EXAMPLE
  .\sync-bas-lite-to-bosspi.ps1
  .\sync-bas-lite-to-bosspi.ps1 -Target ben@192.168.204.12
  .\sync-bas-lite-to-bosspi.ps1 -SyncOnly
  .\sync-bas-lite-to-bosspi.ps1 -PrebuiltFrontend:$false   # build SPA inside Docker on the Pi
  .\sync-bas-lite-to-bosspi.ps1 -SdFriendly:$false          # omit --sd-friendly on bootstrap
#>
[CmdletBinding()]
param(
    [string]$Target = 'ben@192.168.204.12',
    [switch]$SkipFrontendBuild,
    [switch]$SyncOnly,
    [bool]$SdFriendly = $true,
    [bool]$PrebuiltFrontend = $true
)

$ErrorActionPreference = 'Stop'

$deployScript = Join-Path $PSScriptRoot 'deploy-app8-to-bosspi.ps1'
if (-not (Test-Path -LiteralPath $deployScript)) {
    throw "Missing deploy script: $deployScript"
}

if ($SyncOnly) {
    Write-Host "sync-bas-lite-to-bosspi.ps1 -> deploy -SyncOnly (files only; no remote bootstrap)" -ForegroundColor Yellow
    & $deployScript -SshTarget $Target -SyncOnly -SkipFrontendBuild:$SkipFrontendBuild -SdFriendly:$SdFriendly -PrebuiltFrontend:$PrebuiltFrontend
}
else {
    Write-Host "sync-bas-lite-to-bosspi.ps1 -> full Pi deploy (default: SD-friendly + prebuilt UI)" -ForegroundColor Cyan
    & $deployScript -SshTarget $Target -SyncOnly:$false -SkipFrontendBuild:$SkipFrontendBuild -SdFriendly:$SdFriendly -PrebuiltFrontend:$PrebuiltFrontend
}
if ($LASTEXITCODE -ne 0) { throw "sync wrapper failed ($LASTEXITCODE)." }
