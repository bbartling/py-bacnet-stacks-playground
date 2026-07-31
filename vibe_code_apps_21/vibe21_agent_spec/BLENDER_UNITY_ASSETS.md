# Blender → Unity rooftop assets — Vibe 21

Procedural / Blender-MCP models for **DEMO** roof equipment, plant, and the flyable
drone. Visual toys bound to Twin `entity_id`s — not CAD and not live BAS.

## IDF equipment (Building 100 ops11)

From `assets/twin_b100_ops11/model.idf`:

| Piece | IDF | Unity visual |
| --- | --- | --- |
| `VAV Sys 1/2` | OA mixer → CHW cool → **HW heat** → supply fan (return fan blank) | Cool-focused cutaway: OA/RA mix dampers, CHW coil, **supply + return-path fans**, leave/return/OA ducts. **HW coil omitted** on roof (boiler + zone reheat still in E+) |
| Plant | `Chiller:Electric:EIR`, `CoolingTower:SingleSpeed`, CHW + CW loops | Courtyard chiller + roof tower + **fat** CHW/CW pipes |
| Boiler / zone reheat | Present in IDF | Not shown in this pass |

## Agent workflow

1. Prefer procedural builders: `XrayAhuFactory`, `XrayPlantFactory`, `XrayMepBuilder`, `ProceduralDroneFactory`.
2. Unity MCP: `RoofAssetPlacer.Place()` → `XrayMepBuilder.Build()` → `TwinProxyPlacer.PlaceProxies()`.
3. **`manage_scene` save after every milestone.**

## Play-feel

- Drone SphereCast bounce vs building MeshColliders + terrain; **bonk / scrape** audio; never totalled.
- DR panel: 2-hour event playback in **5 min / 1 min / 30 s**; `chiller_off` stops plant spin/audio and warms DEMO temps.
- `MachineAudioHub`: AHU whoosh, pump, chiller, tower (2D procedural).

## Honesty

Roof AHUs, ducts/pipes, chiller/tower, and the greyscale drone are **illustration / DEMO**.
Geometry massing remains IDF/`unity_geometry.json` only. ML predictions stay on
Flask `POST /api/v1/predict/demand_hourly`.
