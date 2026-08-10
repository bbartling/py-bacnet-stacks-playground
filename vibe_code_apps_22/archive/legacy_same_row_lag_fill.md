# Archived: same-row lag fill (DEF-STEP0-LAG) — DO NOT IMPORT

Historical bug (pre 2026-08-10 contract rebuild):

```python
feat[c] = feat[c].fillna(feat[TARGET_COL])  # facility_kw_lag*
out[lag] = out[lag].fillna(out[c])          # zone temp lags
```

This copied y[q0] into features for q0. Replaced by:

- `ml/real_store/build.py` — causal cross-midnight `.shift(1)` on wall time
- `ml/feature_compile_15min.py` — dropna only; no same-row target fill
- `ml/train_eplus_delta_15min.py` — Δ lags `fillna(0.0)` at intervention start
- `ml/feature_compile_heating_dsm.py` — causal shift only

See `docs/audits/lag_train_serve_parity.md`.
