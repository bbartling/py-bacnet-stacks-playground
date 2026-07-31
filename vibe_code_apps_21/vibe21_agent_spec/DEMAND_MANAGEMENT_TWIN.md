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
Flask /api/v1/predict/demand_hourly
        │
   ┌────┴────┐
React charts   Unity WebGL (massing + DR phase colors)
```

## Out of scope for DM twin v1

- Annual ECM package savings / ESCO cascade
- FDD classifiers as primary product
- Live EnergyPlus on PythonAnywhere
- BAS commanding
- Room-level VAV geometry (Twin is Floor×AHU lumped zones)

## Unity agent needs (checklist)

1. Import `unity_geometry.json` surfaces → mesh (meters → Unity units)
2. Bind `entity_id` on zones / airloops / chiller / plant
3. Visual modes: hourly kW overlay, DR window, precool vs relax phase, plant avail
4. Controls: strategy picker + optional continuous knobs (precool_f, relax_f) → API
5. Do **not** invent geometry beyond IDF; if rooms needed, say `NEEDS_ENH`

## Excel

Demand tab oracle lives in WattLab `ECM_FULL_PARITY.xlsx`.  
Product workbook path = **open-fdd PyPI `ECMJob`** (not long-term vibe builder).
