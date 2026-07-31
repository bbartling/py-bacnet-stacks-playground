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

Unity visual contract (x-ray pass):

- Exactly **2** roof AHUs via `XrayAhuFactory` (`ahu_proxy_vav_sys_1` / `_2`)
- Cutaway shell: OA → filter → mix → CHW cool → HW heat → supply fan
- Separate world labels: **Leave / Mix / Return** (`AhuAirTempDisplay`)
- Fan spin via `AhuFanSpin` + `SpinUtil` (DEMO load from DR strategy)
- Greyscale **procedural** drone (`ProceduralDroneFactory`) — FBX optional
- `XrayMepBuilder`: blue supply / orange return risers + floor laterals + thin CHW/HW pipes (semi-transparent)
- Zone `ZoneTempSensor`: one short label per zone (`F3 AHU1\n23.1°C`); subtle window tint via MaterialPropertyBlock

## Agent workflow

1. Prefer in-Editor procedural builders (`XrayAhuFactory`, `ProceduralDroneFactory`, `XrayMepBuilder`).
2. Optional: Blender open with **BlenderMCP** for FBX refresh under `Assets/Models/Twin/`.
3. Unity MCP menu / `execute_code`: `RoofAssetPlacer.Place()`, `XrayMepBuilder.Build()`, `TwinProxyPlacer.PlaceProxies()`.
4. **`manage_scene` save after every milestone** (AHUs, MEP, sensors, drone, end).

## Honesty

Roof AHUs, ducts/pipes, and the greyscale drone are **illustration / DEMO**.
Geometry massing remains IDF/`unity_geometry.json` only. ML predictions stay on
Flask `POST /api/v1/predict/demand_hourly`.
