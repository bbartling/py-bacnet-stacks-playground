# Unity MCP workflow — Vibe 21

Agents drive the Liberty 100 Editor project via
[MCP for Unity](https://github.com/CoplayDev/unity-mcp) (CoplayDev), not by inventing
geometry outside the Twin JSON.

## Prerequisites

1. Unity Editor open on `vibe_code_apps_21/unity/liberty_100`.
2. Package `com.coplaydev.unity-mcp` installed; **Window → MCP for Unity** ready.
3. Cursor MCP server `user-unityMCP` connected.
4. Twin SoT: `assets/twin_b100_ops11/unity_geometry.json` + `unity_twin_manifest.json`.

## Hard rules

1. **Do not invent room/VAV polygons.** Massing from Twin surfaces only (now with MeshColliders for drone bounce).
2. AHUs / plant / ducts / sensors are **DEMO / x-ray** — label honesty (cool-focused AHU omits E+ HW coil).
3. **`manage_scene` save after every milestone.**
4. After script edits: wait until compile done, then `read_console`.
5. Unity never trains models — Flask `POST /api/v1/predict/demand_hourly`.

## Milestone save checklist

1. Geometry (+ colliders) / site
2. Cool-focused x-ray AHUs ×2 + greyscale drone (`AirplanePropFactory` blades)
3. Fat **ortho** MEP (`OrthoMepRouter`) + roof chiller/tower + `MepFlowFx` particles
4. Facade sensors outside glass + `GlassUtil` window fix
5. Menu (°C/°F, ~2× UI) / DR playback / procedural motor + machine audio smoke
6. End of session

## Flight controls

| Key | Action |
| --- | --- |
| **W/A/S/D** | Move |
| **E / PageUp** | Climb |
| **Q / PageDown** | Descend |
| **Shift** | Boost |
| **L** | Land (drop, bonk, freeze camera) |
| **R** | Recover (zip back to pre-land hover) |
| **Esc** | Pause menu (large overlay; °C/°F) |

Collision: bounce + bonk/scrape; craft stays flyable. Props are airplane-style blades.
Motor: procedural hum (`MakeHumClip`) after Start Flight.
Zone temps: individual facade sensor labels; visible through glazing / clear air only (occluded by walls).
Roof: x-ray AHUs + ortho MEP + contained flow particles; tower drip/mist white.

## DR panel

- Predict once, or **Run DR Event** for a **2-hour** window compressed to **5 min / 1 min / 30 s**.
- `chiller_off` / `hvac_off`: plant stops, fans idle, DEMO zone/AHU temps rise.
