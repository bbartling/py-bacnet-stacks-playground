# Vendored EnergyPlus-MCP (OpenFDD WattLab)

OpenFDD WattLab uses the [LBNL-ETA/EnergyPlus-MCP](https://github.com/LBNL-ETA/EnergyPlus-MCP) Docker image for EnergyPlus 26.1.0.

- Pin: see `VERSION.txt`
- Local clone: `EnergyPlus-MCP/` (gitignored; re-clone from VERSION.txt)
- Image tag: `energyplus-mcp-dev`

## Build (required build-arg)

Plain `docker build` often leaves `TARGETPLATFORM` empty and the upstream
Dockerfile aborts with `TARGETPLATFORM: parameter not set`. Pass the platform
explicitly:

```bash
# Linux amd64 host / most CI
docker build --build-arg TARGETPLATFORM=linux/amd64 \
  -t energyplus-mcp-dev -f .devcontainer/Dockerfile .devcontainer

# Apple Silicon / linux/arm64
docker build --build-arg TARGETPLATFORM=linux/arm64 \
  -t energyplus-mcp-dev -f .devcontainer/Dockerfile .devcontainer

# Or via buildx
docker buildx build --platform linux/amd64 --load \
  --build-arg TARGETPLATFORM=linux/amd64 \
  -t energyplus-mcp-dev -f .devcontainer/Dockerfile .devcontainer
```

Helper (from `vibe_code_apps_20`):

```bash
bash scripts/build_energyplus_mcp.sh
# PowerShell:
#   .\scripts\build_energyplus_mcp.ps1
```

## Codex / Cursor MCP config

Linux example:

```json
{
  "mcpServers": {
    "energyplus": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/home/ben/py-bacnet-stacks-playground/vibe_code_apps_20/third_party/EnergyPlus-MCP:/workspace",
        "-w", "/workspace/energyplus-mcp-server",
        "energyplus-mcp-dev",
        "uv", "run", "python", "-m", "energyplus_mcp_server.server"
      ]
    }
  }
}
```

Windows path variant (adjust user folder):

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
