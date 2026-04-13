#Requires -Version 5.1
<#
.SYNOPSIS
  Build documentation.pdf (and .txt) for vibe_code_apps_7 and _8 via Docker image py-bacnet-docs-pdf:local.

.DESCRIPTION
  Run from anywhere; resolves playground repo root from this script location.
  Builds the image if missing (docker build).
#>
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$repoRoot = (Resolve-Path (Join-Path $here "..\..")).Path
$image = "py-bacnet-docs-pdf:local"

Push-Location $repoRoot
try {
    docker image inspect $image 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Building Docker image $image ..."
        docker build -t $image -f scripts/docker-docs-pdf/Dockerfile scripts/docker-docs-pdf
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    $vol = "${repoRoot}:/work"
    Write-Host "Running PDF build in container (mount $repoRoot -> /work)..."
    docker run --rm -v $vol -w /work $image bash scripts/docker-docs-pdf/run.sh
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
