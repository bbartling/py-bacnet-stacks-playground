# Desktop artifacts (not in git)

Populate by promoting a hybrid ship, or unpack a Drive model pack here:

```powershell
$env:VIBE22_ALLOW_CLI_TRAIN="1"
$env:VIBE22_ALLOW_SMOKE_PROMOTE="1"   # screening farm only
python -u ..\scripts\ship_best_to_desktop.py --no-launch
```

Expected after promote (local only): `*.onnx`, feature_meta / model_card JSON, `hybrid_dsm_96_v1_walk.json`, `hybrid_ship_manifest.json`.

See [`../ml/artifacts/README.md`](../ml/artifacts/README.md) and [`../../data/DATA.md`](../../data/DATA.md).
