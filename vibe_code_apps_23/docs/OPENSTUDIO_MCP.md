# OpenStudio MCP bridge (vibe23)

Upstream: https://github.com/NatLabRockies/openstudio-mcp

## Why a bridge?

OpenStudio-MCP exposes **150+ tools**. Cursor's MCP host has a **~40 tool hard
cap** (documented by upstream). Interactive use belongs in Claude Code / Windsurf
or via **Docker CLI** wrappers here.

## Prerequisites

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) running
2. Vendored tree at `../third_party/openstudio-mcp` (shipped) **or** fresh clone
3. Site models under `VIBE23_CREEKSIDE_ROOT` (IDF/EPW/OSM)

## Build

```powershell
cd ..\third_party\openstudio-mcp
docker build -t openstudio-mcp:dev -f docker/Dockerfile .
```

## Run (stdio MCP)

```powershell
.\Start-OpenStudioMcp.ps1
```

Mounts (defaults):

| Host | Container |
| --- | --- |
| `VIBE23_CREEKSIDE_ROOT\eplus\models` | `/inputs` |
| `vibe_code_apps_23\openstudio_mcp_bridge\runs` | `/runs` |
| `vibe_code_apps_23\openstudio_mcp_bridge\measures` | `/measures` |

## Without Docker

Use native EnergyPlus on the site workspace:

```powershell
python -u $env:VIBE23_CREEKSIDE_ROOT\scripts\eplus_campaign_utility.py
```

Same physics engine; OS-MCP adds OSM authoring / measures / SQL helpers.
