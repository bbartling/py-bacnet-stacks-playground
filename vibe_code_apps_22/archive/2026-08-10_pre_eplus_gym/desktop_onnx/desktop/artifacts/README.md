# Desktop artifacts (not in git)

Populate by promoting a hybrid ship, or unpack a Drive model pack here:

```powershell
# After train_four_arms (+ E+ delta). Screening farm (<12 pairs) needs smoke flag:
python -u ..\scripts\ship_best_to_desktop.py --no-launch --allow-smoke-promote
# Equivalent: $env:VIBE22_ALLOW_SMOKE_PROMOTE="1"
```

Picks the sklearn arm with lowest **recursive held-out peak MAE** (winter wins
ties; torch never ships), copies baseline into `ml/artifacts/`, promotes the
hybrid walk + ONNX bundle here, and stamps `hybrid_ship_manifest.json`.

Expected after promote (local only): `*.onnx`, feature_meta / model_card JSON,
`hybrid_dsm_96_v1_walk.json`, `hybrid_ship_manifest.json`.

Closeout record: [`../../docs/superpowers/specs/2026-08-09-desktop-ship-closeout.md`](../../docs/superpowers/specs/2026-08-09-desktop-ship-closeout.md).

See [`../ml/artifacts/README.md`](../ml/artifacts/README.md) and [`../../data/DATA.md`](../../data/DATA.md).
