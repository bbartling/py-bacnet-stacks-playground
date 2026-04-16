#Requires -Version 5.1
<#
.SYNOPSIS
  HTTP smoke tests for BAS Lite (Caddy + nginx SPA + /app8/api) - pure PowerShell, no WSL.

.DESCRIPTION
  Checks /app8/ shell, Vite entry script URL (not HTML), CSS bundle, /app8/api/health JSON,
  and a few client-side routes (still served as SPA HTML).

.EXAMPLE
  # From repo folder vibe_code_apps_8, after stack is up:
  .\scripts\run-bas-lite.ps1 -ProductionFrontend
  .\scripts\test-bas-lite-http.ps1

.EXAMPLE
  .\scripts\test-bas-lite-http.ps1 -BossPi
  .\scripts\test-bas-lite-http.ps1 -BaseUrl http://192.168.204.12:18080
#>
[CmdletBinding()]
param(
    [string]$BaseUrl = '',
    [switch]$BossPi,
    [string]$PiHost = '192.168.204.12',
    [int]$HttpPort = 18080,
    [int]$HealthWaitSec = 45,
    # Short health wait (for CI / quick checks when the stack is known to be down).
    [switch]$FastFail
)

$ErrorActionPreference = 'Stop'

function Resolve-TestBase {
    if (-not [string]::IsNullOrWhiteSpace($BaseUrl)) {
        return $BaseUrl.TrimEnd('/')
    }
    if ($BossPi) {
        return "http://${PiHost}:${HttpPort}".TrimEnd('/')
    }
    return "http://127.0.0.1:${HttpPort}".TrimEnd('/')
}

function Join-BasePath {
    param([string]$Root, [string]$Rel)
    $r = $Root.TrimEnd('/')
    $p = $Rel.TrimStart('/')
    return "$r/$p"
}

function Write-Pass { param($Message) Write-Host "  [ok] $Message" -ForegroundColor Green }
function Write-Fail { param($Message) Write-Host "  [!!] $Message" -ForegroundColor Red }

$base = Resolve-TestBase
$pageTimeoutSec = if ($FastFail) { 3 } else { 30 }
$failed = $false
function Fail {
    param([string]$Message)
    Write-Fail $Message
    $script:failed = $true
}

Write-Host "=== test-bas-lite-http ($base) ===" -ForegroundColor Cyan
Write-Host ""

# --- /app8/ ---
try {
    $app8 = Join-BasePath $base '/app8/'
    $r = Invoke-WebRequest -UseBasicParsing -Uri $app8 -MaximumRedirection 5 -TimeoutSec $pageTimeoutSec
    if ($r.StatusCode -ne 200) { Fail "GET /app8/ status $($r.StatusCode)" }
    else { Write-Pass "GET /app8/ HTTP 200" }
    $html = $r.Content
    if ($html -notmatch 'id="root"') { Fail '/app8/ HTML missing id="root"' }
    else { Write-Pass '/app8/ contains #root' }
    if ($html -notmatch 'type="module"') { Fail '/app8/ missing type=module script' }
    else { Write-Pass '/app8/ has a module script' }
}
catch {
    Fail "GET /app8/ failed: $($_.Exception.Message)"
    $html = $null
}

$jsPath = $null
if ($html) {
    $m = [regex]::Match($html, 'src="(/app8/assets/[^"]+\.js)"')
    if (-not $m.Success) {
        Fail 'Could not find src="/app8/assets/*.js" in index (wrong Vite base?)'
    }
    else {
        $jsPath = $m.Groups[1].Value
        Write-Pass "Entry script: $jsPath"
    }
}

if ($jsPath) {
    $jsUrl = Join-BasePath $base $jsPath
    try {
        $head = Invoke-WebRequest -UseBasicParsing -Uri $jsUrl -Method Head -TimeoutSec $pageTimeoutSec
        $ct = $head.Headers['Content-Type']
        if (-not $ct) { Fail "HEAD $jsPath - no Content-Type" }
        elseif ($ct -match 'text/html') { Fail "HEAD $jsPath is text/html (HTML instead of JS - blank UI symptom)" }
        elseif ($ct -match 'javascript|ecmascript|jscript') { Write-Pass "HEAD entry script Content-Type: $ct" }
        else { Write-Host "  [??] Content-Type: $ct (may still be valid)" -ForegroundColor DarkYellow }
    }
    catch {
        Fail "HEAD entry script failed: $($_.Exception.Message)"
    }

    try {
        $jsGetTimeout = if ($FastFail) { 15 } else { 120 }
        $body = Invoke-WebRequest -UseBasicParsing -Uri $jsUrl -TimeoutSec $jsGetTimeout
        $raw = $body.Content
        if ([string]::IsNullOrEmpty($raw)) { Fail 'GET entry script empty body' }
        elseif ($raw.Substring(0, 1) -eq '<') {
            Fail "GET entry script starts with '<' (HTML body, not JS)"
        }
        else { Write-Pass 'GET entry script body is not HTML' }
    }
    catch {
        Fail "GET entry script failed: $($_.Exception.Message)"
    }
}

$mCss = [regex]::Match($(if ($html) { $html } else { '' }), '/app8/assets/[^"]+\.css')
if ($mCss.Success) {
    $cssPath = $mCss.Value
    $cssUrl = Join-BasePath $base $cssPath
    try {
        $cssTimeout = if ($FastFail) { 5 } else { 60 }
        $cr = Invoke-WebRequest -UseBasicParsing -Uri $cssUrl -TimeoutSec $cssTimeout
        if ($cr.StatusCode -eq 200) { Write-Pass "GET $cssPath HTTP 200" }
        else { Fail "GET $cssPath HTTP $($cr.StatusCode)" }
    }
    catch { Fail "GET stylesheet failed: $($_.Exception.Message)" }
}

Write-Host ""
Write-Host '=== /app8/api/health ===' -ForegroundColor Cyan
$healthUrl = Join-BasePath $base '/app8/api/health'
$healthOk = $false
$deadline = (Get-Date).AddSeconds($HealthWaitSec)
$attempt = 0
$healthTimeout = 15
if ($FastFail) {
    $deadline = (Get-Date).AddSeconds(2)
    $healthTimeout = 2
}
while ((Get-Date) -lt $deadline) {
    $attempt++
    try {
        $hr = Invoke-RestMethod -Uri $healthUrl -TimeoutSec $healthTimeout -Method Get
        if ($hr.status) {
            $healthOk = $true
            Write-Pass "/app8/api/health OK (attempt $attempt); status=$($hr.status)"
            break
        }
    }
    catch {
        # continue
    }
    if (-not $FastFail) {
        Start-Sleep -Seconds 2
    }
    else {
        break
    }
}
if (-not $healthOk) {
    $waitNote = if ($FastFail) { 'short -FastFail window' } else { "${HealthWaitSec}s" }
    Fail "/app8/api/health not OK ($waitNote) - check api + diy-bacnet: docker compose logs api --tail 50"
}

Write-Host ""
Write-Host '=== SPA routes (expect same shell HTML) ===' -ForegroundColor Cyan
foreach ($p in @('/app8/live-points', '/app8/system', '/app8/driver')) {
    try {
        $u = Join-BasePath $base $p
        $sr = Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec $pageTimeoutSec
        if ($sr.StatusCode -eq 200 -and $sr.Content -match 'id="root"') { Write-Pass "GET $p" }
        else { Fail "GET $p - expected 200 + #root" }
    }
    catch { Fail "GET $p : $($_.Exception.Message)" }
}

Write-Host ""
if ($failed) {
    Write-Host "=== FAILED (see [!!] above) ===" -ForegroundColor Red
    exit 1
}
Write-Host "=== All checks passed ===" -ForegroundColor Green
exit 0
