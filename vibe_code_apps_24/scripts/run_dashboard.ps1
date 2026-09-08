# Run Vibe 24 dashboard (HTML only; no BACnet bind)
Set-Location $PSScriptRoot\..
python -m pip install -e ".[dev]" -q
vibe24 serve --host 127.0.0.1 --port 8024
