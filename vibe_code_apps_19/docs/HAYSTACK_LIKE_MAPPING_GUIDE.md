# Haystack-like mapping guide (no RDF)

App 19 uses **Project Haystack–style names** for column maps and for rule inputs
(`siteRef`, `equip`, `device`, `equipType`, `points`). It does **not** run Haystack
RDF / Oxigraph / SPARQL.

Rules read the same point names that appear in `points` (for example
`discharge-air-temp`). There is no second vocabulary.

## IDs

| Entity | Haystack-like key | Example |
|--------|-------------------|---------|
| Site | `siteRef` | `campus_a` |
| Building | `building` (folder name) | `HQ_NORTH` |
| Equipment / device | `equip.<id>` + `device` | `AHU_1`, `VAV_7` |
| Equip type | `equipType` | `ahu`, `vav`, `chwPlant`, `boiler`, `heatPump`, `weather` (`rtu` → `AHU`; unit vent / FCU with supply fan → `ahu`) |
| Point | `points.<haystack-name>` | `discharge-air-temp` |
| Column | CSV header value | `discharge_air_temp_f` |

## Preferred point names

| Haystack point | Typical use |
|----------------|-------------|
| `discharge-air-temp` / `discharge-air-temp-sp` | SAT / SAT SP |
| `mixed-air-temp` / `return-air-temp` / `outside-air-temp` | Mixing envelope |
| `outside-air-damper` | Economizer OA damper % |
| `cooling-valve` / `heating-valve` | Valve % (not mech-cooling OAT-bin proof) |
| `fan-cmd` / `fan-status` | Supply fan |
| `duct-static-pressure` (+ `-sp`) | Duct static |
| `zone-air-temp` / `zone-airflow` / `damper` / `reheat-valve` | VAV / zone |
| `chilled-water-supply-temp` / `chw-pump-status` / `chiller-status` | Plant (pump = motor; `chiller-status` = compressor OAT proof) |
| `compressor-status` / `dx-stage` / `cool-stage` | DX mech-cooling compressor proof |
| `occupied` | Occupancy |
| `web-outside-air-temp` | Open-Meteo / weather CSV (package `weather/history_wide.csv`; never equipment) |
| `ahu-discharge-air-temp` | Parent AHU SAT copied onto VAV (topology) |

## Weather sidecar (any site)

- Path: `{building}/weather/history_wide.csv` — folder name `weather` is **never** equipment.
- Analysis column: `web-outside-air-temp` (°F). Optional humidity/dewpoint; the app may derive wet-bulb.
- Fetch Open-Meteo (or any web source) at **this job’s lat/lon**; interpolate onto the HVAC `timestamp_utc` grid. Do not bake a city into the Streamlit app.
- BAS `outside-air-temp` is often one **site-global** sensor (boiler/plant). Copy it onto AHU frames in the **package** so mixing scatter and OAT-METEO can see both BAS and web.
- `session_config.prefer_web_oat: true` → web OAT is primary for economizer / RCx / physics. OAT-METEO compares BAS vs web **only when both exist**.

## Motor / fan proof (any BAS)

| Have | Map |
| --- | --- |
| Binary fan/pump/tower status | `fan-status` / `chw-pump-status` / `hw-pump-status` |
| VFD speed or analog command only | `fan-cmd` (or pump cmd) **and** a synthetic 0/1 column (`fan_s = speed ≥ threshold`, typically 5%) mapped as `fan-status` |
| Nothing | omit the motor series — never invent hours from leave temperature |

Do not collapse command and status into one role. Do not treat valve % as a motor. Document the synthesis threshold in the **site preprocess repo**, not Vibe19.

## Compressor vs pump vs valve

`chiller-status` / `compressor-status` / verified cmd / amps / power = mech-cooling OAT-bin proof. **CHW pump and AHU `cooling-valve` do not count.** See [`DATA_MODEL_DRIVEN.md`](DATA_MODEL_DRIVEN.md).

## VAV

`zone-airflow` = actual airflow column, **never** the airflow setpoint. Stamp `equipType: vav` even when the folder is not `VAV_1`.

## Mixing scatter

Needs an AHU/RTU with `fan-status` (or cmd-derived status) **on**, plus `outside-air-temp`, `return-air-temp`, `mixed-air-temp`, and enough `|OAT−RAT|≥10°F` samples. Missing any role → skip, don’t crash.

## JSON shape

Single-equip sidecar:

```json
{
  "equipType": "ahu",
  "equipment_type": "AHU",
  "device": "AHU_1",
  "equip": "AHU_1",
  "points": {
    "fan-status": "fan_s",
    "fan-cmd": "supply_fan_speed_pct",
    "mixed-air-temp": "mixed_air_temp_f",
    "return-air-temp": "return_air_temp_f",
    "outside-air-temp": "outside_air_temp_f"
  }
}
```

Values must be exact CSV headers. A string `"equip": "AHU_1"` is a device id, not a nested package `equipment` map.

## Topology

Package `vav_to_ahu_simple.csv` defines **VAV fedBy AHU** / **AHU feeds VAVs**.
Shown on the Data Model **Topology** section — not mixed into point tables.

## Authoring

1. Put a sibling `column_map.json` (or `history_wide.json`) next to each equipment CSV, or one package-root map.
2. Prefer Haystack point names in `points`.
3. Values must be exact CSV headers.
4. Stamp `equipType` so rules/analytics do not guess from folder names.
5. Add `weather/` for web OAT. Synthesize motor/compressor 0/1 columns in the **wide CSV** when the BAS has no binary proof — in the preprocess job, not inside Vibe19.

See also: [`COLUMN_MAP_JSON.md`](COLUMN_MAP_JSON.md), [`DATA_MODEL_DRIVEN.md`](DATA_MODEL_DRIVEN.md), [`PACKAGE_SPEC.md`](PACKAGE_SPEC.md).
