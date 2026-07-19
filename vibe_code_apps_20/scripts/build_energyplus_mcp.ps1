# Build the pinned EnergyPlus-MCP image with an explicit TARGETPLATFORM.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PinFile = Join-Path $Root "third_party\VERSION.txt"
$Clone = Join-Path $Root "third_party\EnergyPlus-MCP"
$Commit = (Select-String -Path $PinFile -Pattern '^commit:\s*(\S+)').Matches[0].Groups[1].Value
$Platform = if ($env:TARGETPLATFORM) { $env:TARGETPLATFORM } else { "linux/amd64" }

if (-not (Test-Path (Join-Path $Clone ".git"))) {
  git clone https://github.com/LBNL-ETA/EnergyPlus-MCP.git $Clone
}
git -C $Clone fetch --all --tags
git -C $Clone checkout $Commit

docker build --build-arg "TARGETPLATFORM=$Platform" `
  -t energyplus-mcp-dev `
  -f (Join-Path $Clone ".devcontainer\Dockerfile") `
  (Join-Path $Clone ".devcontainer")

Write-Host "Built energyplus-mcp-dev (TARGETPLATFORM=$Platform, commit=$Commit)"
