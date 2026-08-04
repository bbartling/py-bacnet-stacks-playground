# Third-party: OpenStudio MCP

Do **not** vendor the full tree in git (large / fast-moving).

```powershell
cd vibe_code_apps_23
git clone --depth 1 https://github.com/NatLabRockies/openstudio-mcp.git third_party\openstudio-mcp
# or just:
.\openstudio_mcp_bridge\Start-OpenStudioMcp.ps1   # clones + builds if missing
```

Upstream: https://github.com/NatLabRockies/openstudio-mcp  
License: see upstream repo.
