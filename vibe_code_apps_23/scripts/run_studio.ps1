# Launch Vibe 23 Studio on a pinned Python 3.12 + Streamlit 1.59.2.
# Hard-refresh the browser (Ctrl+Shift+R) once after switching interpreters.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Pin = "1.59.2"
$Py = $null
try {
    $Py = (py -3.12 -c "import sys; print(sys.executable)").Trim()
} catch {
    Write-Error "Python 3.12 not found via 'py -3.12'. Install 3.12 and retry."
}

$Ver = (& $Py -c "import streamlit; print(streamlit.__version__)").Trim()
if ($Ver -ne $Pin) {
    Write-Host "Installing streamlit==$Pin into $Py ..."
    & $Py -m pip install -r (Join-Path $Root "requirements-studio.txt")
    $Ver = (& $Py -c "import streamlit; print(streamlit.__version__)").Trim()
}
if ($Ver -ne $Pin) {
    Write-Error "Expected streamlit==$Pin, got $Ver from $Py"
}
Write-Host "OK: streamlit $Ver · $Py"

Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

$env:PYTHONPATH = "src"
& $Py -m streamlit run streamlit_app.py --server.headless true --browser.gatherUsageStats false
