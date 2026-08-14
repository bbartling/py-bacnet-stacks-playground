# Run a Python script with OpenStudio 3.11's embedded interpreter.
# System Python can import openstudio but may crash on Model() (DLL ABI).
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Script,
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ScriptArgs
)

$ErrorActionPreference = "Stop"

# Site data root holds tools/openstudio/sdk (not the vibe22 git tree)
$SiteRoot = $env:LAKESIDE_SITE_ROOT
if (-not $SiteRoot) { $SiteRoot = $env:VIBE22_SITE_ROOT }
if (-not $SiteRoot) { $SiteRoot = $env:VIBE22_CREEKSIDE_ROOT }
if (-not $SiteRoot) { $SiteRoot = "C:\Users\ben\OneDrive\Desktop\testing\sp_creekside" }

$OSROOT = Join-Path $SiteRoot "tools\openstudio\sdk\OpenStudio-3.11.0+241b8abb4d-Windows"
$exe = Join-Path $OSROOT "bin\openstudio.exe"
if (-not (Test-Path $exe)) {
  throw "OpenStudio not found at $exe. Set LAKESIDE_SITE_ROOT to the site data folder."
}
if (-not (Test-Path $Script)) {
  throw "Script not found: $Script"
}

$env:PATH = "$(Join-Path $OSROOT 'bin');$env:PATH"
Push-Location (Join-Path $OSROOT "bin")
try {
  & $exe execute_python_script (Resolve-Path $Script) @ScriptArgs
  exit $LASTEXITCODE
}
finally {
  Pop-Location
}
