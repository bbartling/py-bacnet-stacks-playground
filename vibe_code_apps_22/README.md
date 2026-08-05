# Vibe Code App 22 — Lakeside Elementary School

Unified **code** workspace for Lakeside ES (southern Wisconsin):

- ALC WebCTRL → openfdd package + thermal zones
- EnergyPlus IdealLoads G14 (interval + utility bills)
- Heating DSM ML (sklearn + ONNX) + Excel playground
- OpenStudio OSM authoring (optional)
- Future BACnet live app slot (`bacnet/`)

**Data stays outside git** — set:

```powershell
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
```

```powershell
cd vibe_code_apps_22
pip install -r requirements.txt
python -c "from lakeside.paths import site_root, BUILDING_ID; print(BUILDING_ID, site_root())"
python -u ml\build_bootstrap_dataset.py
jupyter notebook notebooks\lakeside_heating_dsm_sklearn.ipynb
```

See [AGENTS.md](AGENTS.md) for full run order and honesty stamps.

**Not in scope:** Unity digital twin (that is [vibe21](../vibe_code_apps_21)).
