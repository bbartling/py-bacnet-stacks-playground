<#
.SYNOPSIS
  Launch the Tkinter deploy + .env editor GUI (diy-bas).

.DESCRIPTION
  On Windows, Run Deploy in the GUI invokes the same repo-root deploy_to_pi.ps1 as running
  .\deploy_to_pi.ps1 manually from this directory (tools\ only holds deploy_gui.py, not a second copy of the deploy script).
#>
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$gui = Join-Path (Join-Path $here "tools") "deploy_gui.py"
if (-not (Test-Path $gui)) {
    throw "Missing $gui"
}

$py = $null
foreach ($c in @("py -3", "python3", "python")) {
    $name = ($c -split " ")[0]
    if (Get-Command $name -ErrorAction SilentlyContinue) {
        $py = $c
        break
    }
}
if (-not $py) {
    throw "Python not found on PATH (try py -3, python3, or python)."
}

if ($py -eq "py -3") {
    & py -3 $gui @args
}
else {
    $exe = ($py -split " ")[0]
    & $exe $gui @args
}
