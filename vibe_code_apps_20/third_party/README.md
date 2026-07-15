# Vendored EnergyPlus-MCP (OpenFDD WattLab)

OpenFDD WattLab uses the [LBNL-ETA/EnergyPlus-MCP](https://github.com/LBNL-ETA/EnergyPlus-MCP) Docker image for EnergyPlus 26.1.0.

- Pin: see `VERSION.txt`
- Local clone: `EnergyPlus-MCP/` (gitignored; re-clone from VERSION.txt)
- Image tag: `energyplus-mcp-dev`

Cursor MCP config snippet (adjust the Windows path):

```json
{
  "mcpServers": {
    "energyplus": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "C:\\Users\\ben\\Documents\\py-bacnet-stacks-playground\\vibe_code_apps_20\\third_party\\EnergyPlus-MCP:/workspace",
        "-w", "/workspace/energyplus-mcp-server",
        "energyplus-mcp-dev",
        "uv", "run", "python", "-m", "energyplus_mcp_server.server"
      ]
    }
  }
}
```
