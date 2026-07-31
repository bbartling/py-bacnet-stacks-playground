# Blender → Unity rooftop assets — Vibe 21

Procedural / Blender-MCP models for **DEMO** roof equipment and the flyable
drone. These are visual toys bound to Twin `entity_id`s — not CAD and not live BAS.

## IDF equipment teaser (Building 100 ops11)

From `assets/twin_b100_ops11/model.idf`:

| Air loop | Type (inferred) | Key components |
| --- | --- | --- |
| `VAV Sys 1` | Central **VAV** AHU (west / AHU1 plate) | OA mixer, `Coil:Cooling:Water`, `Coil:Heating:Water`, `Fan:VariableVolume` |
| `VAV Sys 2` | Central **VAV** AHU (east / AHU2 plate) | same stack |
| Plant | `Chiller:Electric:EIR` | CHW source for both AHUs |

Unity visual contract:

- `entity_id` `ahu_proxy_floor_6_ahu1` / `ahu_proxy_floor_6_ahu2` (roof)
- Fan spin rate scales with DEMO zone load / DR strategy (silly but readable)
- Zone `ZoneTempSensor` labels remain DEMO °C proxies

## Agent workflow

1. Blender open with **BlenderMCP** addon listening (see `C:\Users\ben\Documents\blender-mcp`).
2. Cursor MCP server `user-blender` connected.
3. Build / refresh `Assets/Models/Twin/` FBX (or GLB) via Blender MCP.
4. Unity MCP: replace cube AHU proxies, attach `AhuFanSpin` + `DroneVisualBob`.
5. **`manage_scene` save** after import and after animation wiring.

## Honesty

Roof AHUs and the cartoon drone are **illustration**. Geometry massing remains
IDF/`unity_geometry.json` only. ML predictions stay on Flask
`POST /api/v1/predict/demand_hourly`.
