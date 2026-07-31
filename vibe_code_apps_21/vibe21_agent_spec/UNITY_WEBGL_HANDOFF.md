# Unity WebGL Handoff — Vibe 21

## Boundary

**DM twin fine-tune:** Unity visualizes Building 100 massing from
`assets/twin_b100_ops11/unity_geometry.json` and overlays hourly demand /
DR phase. Canonical product doc: `DEMAND_MANAGEMENT_TWIN.md`.

Unity work is performed outside the Python Vibe 21 implementation using Unity plus Unity MCP/AI tooling.

The Python/repository agent owns:

- canonical entity IDs;
- JSON schemas;
- Flask APIs;
- model prediction contracts;
- React shell integration;
- deploy-bundle assembly/validation.

The Unity agent owns:

- scene creation/editing;
- GameObjects and visual hierarchy;
- WebGL-compatible interaction logic;
- Unity-to-browser/API calls;
- WebGL build/export;
- Unity build smoke testing.

Unity never becomes the authoritative data store.

---

## Canonical binding

Each visual engineering object maps to one stable backend entity ID.

Example:

```json
{
  "schema_version": "vibe21.unity_binding.v1",
  "unity_object_key": "Building100/Floor2/VAV_7",
  "entity_type": "equipment",
  "entity_id": "equip_vav_7",
  "default_visualization": "predicted_demand_contribution"
}
```

Display names may change; IDs do not.

---

## Unity startup contract

On load Unity should request a small bootstrap/twin manifest containing:

- building ID/name;
- available model versions;
- equipment/zone binding references;
- supported visual modes;
- scenario control schema;
- units;
- safe demo defaults.

Unity should not download the full synthetic training dataset or raw EnergyPlus outputs.

---

## Visual modes

Initial useful modes:

- equipment type;
- current/selected operational status;
- measured vs predicted state;
- predicted building demand;
- zone temperature/comfort;
- fault severity/probability when enabled;
- virtual cooling/heating load;
- scenario annual energy delta;
- scenario peak-demand delta;
- unmet hours;
- data/provenance confidence.

React/Plotly remains the primary surface for exact engineering charts and tables.

---

## Scenario interaction

Unity may expose simple spatial interactions such as selecting an AHU or zone and adjusting an approved scenario value.

The scenario payload goes to Flask:

```text
Unity/React slider
      ↓
POST /api/v1/predict/scenario
      ↓
scenario feature validation
      ↓
approved surrogate models
      ↓
annual kWh + peak kW + gas + comfort
      ↓
Unity color/state + React charts
```

No EnergyPlus process is launched by the deployed app.

---

## Operational prediction interaction

```text
selected timestamp/history fixture or safe live/demo feed
      ↓
POST /api/v1/predict/operational
      ↓
predicted kW
      ↓
derived interval kWh
      ↓
React chart + Unity building state
```

When the deployed demo has no real live BAS connection, the UI must clearly label the data source as replay/demo/simulated.

---

## Browser communication options

Preferred same-origin mechanisms:

- Unity `UnityWebRequest` directly to Flask JSON APIs;
- JavaScript `.jslib` bridge where Unity must communicate with the parent React shell;
- `postMessage` between Unity iframe and React shell when isolated embedding is simpler.

Choose one documented path for the first release and test it end-to-end.

---

## Unity build handoff zip

The Unity agent should export something like:

```text
unity_webgl_build.zip
└── unity/
    ├── index.html
    ├── Build/
    └── TemplateData/
```

The outer Vibe 21 build/packaging step validates expected files and copies the contents into `static/unity/`.

The final deploy bundle must not require Unity Editor on PythonAnywhere.

---

## Build compatibility requirement

For the first PythonAnywhere demo, use a WebGL compression strategy that does not require unavailable server header customization. Prefer Decompression Fallback when using compressed WebGL builds, or disable compression if necessary for compatibility.

The Unity handoff must document:

- Unity version;
- WebGL compression setting;
- decompression fallback setting;
- build hash;
- smoke-test result;
- known browser limitations.
