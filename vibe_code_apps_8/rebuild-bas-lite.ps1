[CmdletBinding()]
param(
    [switch]$RebuildFrontend,
    [switch]$NoCache,
    [switch]$Logs,
    [switch]$Caddy,
    [string[]]$ComposeFiles = @("docker-compose.yml"),
    [string]$ProjectName = ""
)

$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

# Same idea as Open-FDD bootstrap: avoid indefinite hangs on slow Docker / registry paths.
$env:COMPOSE_HTTP_TIMEOUT = if ($env:COMPOSE_HTTP_TIMEOUT) { $env:COMPOSE_HTTP_TIMEOUT } else { "120" }
$env:DOCKER_CLIENT_TIMEOUT = if ($env:DOCKER_CLIENT_TIMEOUT) { $env:DOCKER_CLIENT_TIMEOUT } else { "180" }

function Run-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )
    Write-Host "==> $Name"
    & $Action
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker command not found."
}

if ($RebuildFrontend) {
    Run-Step -Name "Building React frontend (npm run build)" -Action {
        Push-Location "frontend"
        try {
            npm run build
        }
        finally {
            Pop-Location
        }
    }
    Run-Step -Name "Sync frontend dist into app8 webroot" -Action {
        $target = "volttron_data\ben_bacnet\app8_web_agent\app8_web_agent\webroot"
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Remove-Item -Path "$target\*" -Recurse -Force -ErrorAction SilentlyContinue
        Copy-Item -Recurse -Force "frontend\dist\*" $target
    }
}

$composeArgs = @("compose")
foreach ($f in $ComposeFiles) {
    $composeArgs += @("-f", $f)
}
if ($ProjectName) {
    $composeArgs += @("-p", $ProjectName)
}
if ($Caddy) {
    $composeArgs += @("--profile", "caddy")
}

Run-Step -Name "Stopping stack" -Action { docker @composeArgs down }

Run-Step -Name "Building VOLTTRON runtime image" -Action {
    docker @composeArgs build volttron
}

Run-Step -Name "Starting stack" -Action {
    docker @composeArgs up -d --wait
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "docker compose up --wait failed (Compose <2.29 or healthcheck); retrying without --wait."
        docker @composeArgs up -d
    }
}
Run-Step -Name "Service status" -Action { docker @composeArgs ps }

if ($Logs) {
    Run-Step -Name "Following logs (Ctrl+C to stop)" -Action {
        if ($Caddy) {
            docker @composeArgs logs -f volttron caddy
        }
        else {
            docker @composeArgs logs -f volttron
        }
    }
}

