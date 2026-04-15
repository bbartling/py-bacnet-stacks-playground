#Requires -Version 5.1
<#
.SYNOPSIS
  Compatibility wrapper: sync BAS Lite files to Boss Pi only.

.EXAMPLE
  .\sync-bas-lite-to-bosspi.ps1
  .\sync-bas-lite-to-bosspi.ps1 -Target ben@192.168.204.12
#>
[CmdletBinding()]
param(
    [string]$Target = 'ben@192.168.204.12',
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = 'Stop'

$deployScript = Join-Path $PSScriptRoot 'deploy-app8-to-bosspi.ps1'
if (-not (Test-Path -LiteralPath $deployScript)) {
    throw "Missing deploy script: $deployScript"
}

Write-Host "sync-bas-lite-to-bosspi.ps1 is now a wrapper around deploy-app8-to-bosspi.ps1 -SyncOnly" -ForegroundColor Yellow
& $deployScript -SshTarget $Target -SyncOnly -SkipFrontendBuild:$SkipFrontendBuild
if ($LASTEXITCODE -ne 0) { throw "sync wrapper failed ($LASTEXITCODE)." }
