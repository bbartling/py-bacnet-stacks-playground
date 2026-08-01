# Cannon-style: Unity WebGL → flask_app/webgl → vibe21_pa_bundle.zip
param(
    [string]$UnityEditorPath = $env:UNITY_EDITOR_PATH,
    [switch]$SkipBuild,
    [switch]$ForceZip
)

$ErrorActionPreference = "Stop"
$vibe21 = Split-Path -Parent $PSScriptRoot
$unityProject = Join-Path $vibe21 "unity\liberty_100"
$logs = Join-Path $vibe21 "Logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

if (-not $SkipBuild) {
    if (-not $UnityEditorPath) {
        $versionLine = Get-Content (Join-Path $unityProject "ProjectSettings\ProjectVersion.txt") |
            Where-Object { $_ -like "m_EditorVersion:*" } |
            Select-Object -First 1
        $version = ($versionLine -split ":", 2)[1].Trim()
        $candidate = "C:\Program Files\Unity\Hub\Editor\$version\Editor\Unity.exe"
        if (Test-Path $candidate) { $UnityEditorPath = $candidate }
    }
    if (-not $UnityEditorPath -or -not (Test-Path $UnityEditorPath)) {
        throw "Unity Editor not found. Set UNITY_EDITOR_PATH or pass -UnityEditorPath."
    }

    function Invoke-PatientUnity {
        param([string]$Name, [string[]]$Arguments)
        $log = Join-Path $logs "$Name.log"
        Write-Host "Starting $Name ..."
        $process = Start-Process -FilePath $UnityEditorPath -ArgumentList $Arguments -PassThru -WindowStyle Hidden
        while (-not $process.HasExited) {
            try {
                Wait-Process -Id $process.Id -Timeout 1200 -ErrorAction Stop
            }
            catch {
                Write-Host "$Name still running; last log lines:"
                if (Test-Path $log) { Get-Content $log -Tail 30 }
                $process.Refresh()
            }
        }
        if ($process.ExitCode -ne 0) {
            if (Test-Path $log) { Get-Content $log -Tail 80 }
            throw "$Name failed with exit code $($process.ExitCode)."
        }
    }

    Invoke-PatientUnity -Name "liberty-webgl-build" -Arguments @(
        "-batchmode", "-nographics", "-quit",
        "-projectPath", $unityProject,
        "-executeMethod", "LibertyWebGLBuildPipeline.BuildFromCommandLine",
        "-logFile", (Join-Path $logs "liberty-webgl-build.log")
    )
}

$webglIndex = Join-Path $vibe21 "flask_app\webgl\index.html"
if (-not (Test-Path $webglIndex)) {
    throw "Missing $webglIndex — WebGL build/deploy failed."
}

$packArgs = @()
if ($ForceZip) { $packArgs += "--force" }
python (Join-Path $PSScriptRoot "pack_pa_bundle.py") @packArgs
if ($LASTEXITCODE -ne 0) { throw "pack_pa_bundle.py failed ($LASTEXITCODE)" }

$zip = Join-Path $vibe21 "dist\vibe21_pa_bundle.zip"
$item = Get-Item $zip
Write-Host "PythonAnywhere artifact: $($item.FullName)"
Write-Host ("Artifact size: {0:N2} MiB" -f ($item.Length / 1MB))
