# Vibe 21 — Demand-Management Digital Twin (Unity fine-tune)

**Scope freeze:** Vibe 21 in this package is **demand management only** — not the
full physics-ML + annual-ECM product described in older drafts.

## Product question

> For a chosen **outdoor condition day**, what is the **hourly electric demand**
> when operators play with HVAC (precool, deadband, plant shed, fan off, …)?

Unity visualizes zones/plant and scrubbing those control knobs. Flask serves a
lightweight **hourly demand** surrogate trained on EnergyPlus DR farms. React
shows exact kW charts + provenance.

## Source of truth

| Artifact | Role |
| --- | --- |
| `assets/twin_b100_ops11/model.idf` | BEST G14 Twin (`geo_b100_dual_ahu_shape_ops11`) — geometry + HVAC |
| `assets/twin_b100_ops11/amy.epw` | AMY weather for farm / G14 |
| `assets/twin_b100_ops11/unity_geometry.json` | Zone + surface vertices (m) for Unity massing |
| `assets/twin_b100_ops11/july_demand_profiles.json` | Seed hot-day DR hourly kW portfolio |
| `tools/july_demand_profiles_eplus.py` | Offline DR patch + E+ hourly runner |
| EnergyPlus-MCP | Inspect/modify/validate IDF patches |

## Architecture (narrow)

```text
AMY / selected OA day
        +
G14 Twin IDF
        +
DR action vector (precool, DB, plant, fans, DAT, …)
        │
        ▼
EnergyPlus single-day / multi-day farm  (offline)
        │
        ▼
hourly feature rows → Parquet
        │
        ▼
scikit-learn hourly facility_kw model(s)
        │
        ▼
Flask /api/v1/predict/demand_hourly  (:5050 local)
        │
   ┌────┴────┐
React charts   Unity Editor / WebGL (massing + DR phase colors)
```

Local Editor project: `unity/liberty_100/`. Agents use Unity MCP; see
`UNITY_MCP_WORKFLOW.md`. **Save the scene via MCP after every milestone.**

Honesty: Floor×AHU lumped zones only; roof AHU / plant / zone temp markers are
**DEMO proxies**, not CAD or live BAS. ML status remains **CANDIDATE** /
`ENERGYPLUS_SIMULATED` until BAS-validated.

## Unity Editor twin (current — `unity/liberty_100`)

Shipped visuals / playfeel (see `UNITY_MCP_WORKFLOW.md`, `BLENDER_UNITY_ASSETS.md`):

- Greyscale flyable drone (airplane blades, procedural motor hum, Space land/recover watch mode, bonk/scrape)
- Cool-focused x-ray AHUs ×2 (OA/RA mix, CHW only; HW coil omitted on roof)
- **Ortho** rectangular air ducts (grey-green/amber) + round blue water pipes; distinct air vs liquid particles
- `MepFlowFx` + white tower drip/mist; roof Main Chiller + Cooling Tower
- Facade glass + occluded window zone temps; **Spawn Sensor Badge Kit** for manual placement
- Large pause menu (°C/°F matched toggles); enlarged right DR panel + Land Drone button
- DR 2h playback (5m / 1m / 30s) via Flask `predict/demand_hourly`

## Out of scope for DM twin v1

- Annual ECM package savings / ESCO cascade
- FDD classifiers as primary product
- Live EnergyPlus on PythonAnywhere
- BAS commanding / live historian
- Room-level VAV geometry (Twin is Floor×AHU lumped zones)
- Loading joblib inside Unity

## Unity agent needs (checklist)

1. Import `unity_geometry.json` surfaces → mesh (E+ m → Unity Y-up) + MeshColliders
2. Bind `entity_id` on zones / airloops / chiller / plant
3. Procedural drone + green site (not freefly-only)
4. Visual modes: hourly kW overlay, DR window, plant on/off FX, zone/AHU temps
5. Controls: strategy picker + knobs → Flask `predict/demand_hourly`
6. DEMO roof AHUs / plant / sensors — rebuild via MCP menus in `UNITY_MCP_WORKFLOW.md`
7. Do **not** invent geometry beyond IDF; if rooms needed, say `NEEDS_ENH`
8. MCP `manage_scene` **save** after each milestone above
9. Keep `vibe21_agent_spec/` docs current when Unity/Flask/Blender contracts change

## Excel

Demand tab oracle lives in WattLab `ECM_FULL_PARITY.xlsx`.  
Product workbook path = **open-fdd PyPI `ECMJob`** (not long-term vibe builder).
