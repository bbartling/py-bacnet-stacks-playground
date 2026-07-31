# Unity MCP workflow — Vibe 21

Agents drive the Liberty 100 Editor project via
[MCP for Unity](https://github.com/CoplayDev/unity-mcp) (CoplayDev), not by inventing
geometry outside the Twin JSON.

## Prerequisites

1. Unity Editor open on `vibe_code_apps_21/unity/liberty_100` (or `Liberty100`).
2. Package `com.coplaydev.unity-mcp` installed; **Window → MCP for Unity** shows
   **Server ready on http://127.0.0.1:9999**.
3. Cursor MCP server `user-unityMCP` connected (auth if prompted).
4. Twin SoT: `assets/twin_b100_ops11/unity_geometry.json` + `unity_twin_manifest.json`.

## Hard rules for agents

1. **Do not invent room/VAV polygons.** Massing comes only from Twin surfaces.
2. Roof AHU boxes and zone “temp sensors” are **DEMO proxies** — label them.
3. **Save the scene via MCP after every milestone** (`manage_scene` action `save`).
   Unity UI often locks up; MCP save preserves progress when the Editor is wedged.
4. After `create_script` / script edits: wait until `editor_state.is_compiling` is
   false, then `read_console` for errors.
5. Unity never trains models or runs EnergyPlus — call Flask
   `POST /api/v1/predict/demand_hourly` on localhost.

## Milestone save checklist

After each of these, call `manage_scene(action="save")` (and optionally save-as
`Assets/Scenes/Liberty100Twin.unity` once created):

1. Geometry import / massing built (+ E+ fenestration windows)  
2. Free-fly or drone camera + terrain site  
3. DR UI panel wired (large scrubber panel)  
4. Sensor / roof AHU proxies + BAS-style temp glow  
5. Blender FBX AHU/drone import + fan/drone animation hooks  
6. End of session / before Play Mode experiments  

See also `BLENDER_UNITY_ASSETS.md` for rooftop VAV AHU / drone visuals.

## Useful MCP tools

| Tool | Use |
| --- | --- |
| `manage_scene` | `get_active`, `get_hierarchy`, `save`, `create`, `load` |
| `create_script` / `script_apply_edits` | C# under `Assets/` |
| `manage_gameobject` | Create/parent/transform |
| `execute_code` | One-shot Editor C# (build meshes, etc.) |
| `read_console` | Compile / runtime errors |
| `manage_editor` | Play / stop (use sparingly while UI locked) |

## Local demo loop

```text
1. python -m flask_app   # from vibe_code_apps_21, :5050
2. Unity Play Mode — fly + DR scrubbers + window temp glow
3. Optional: Blender MCP for rooftop VAV AHU / drone FBX refresh
   (see BLENDER_UNITY_ASSETS.md)
4. WebGL export later → flask static/unity (not required for Editor demo)
```

## Blender MCP note

Headless `blender -b` can export FBX (`tools/build_twin_roof_assets.py`) but the
addon socket only stays up in GUI. Start Blender, then
`tools/_start_blendermcp.py` or click **Connect to MCP server** on port 9876.
