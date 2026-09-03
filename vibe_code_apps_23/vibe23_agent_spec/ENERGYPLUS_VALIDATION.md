# EnergyPlus validation — residential

- Engine: native `energyplus.exe` (default `C:\EnergyPlusV26-1-0`)
- Soft gate for demos: returncode 0, 0 fatal, `eplusout.csv` present
- Inventory severe warnings; do not require zero warnings for DR/grid demos
- MCP (`EnergyPlus-MCP`) is optional engineering assist only

Always inspect `eplusout.err` after model changes.
