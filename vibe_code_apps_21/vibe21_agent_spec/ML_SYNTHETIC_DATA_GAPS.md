# ML synthetic data — gaps for demand-management twin

Seed farm (`july_demand_profiles.json`) proves the **control axes** work on one
hot weekday. That is **not** enough to train a general hourly demand model.

## Have now

- 1 Twin IDF (G14) + AMY EPW
- 1 extreme July weekday + 1 Saturday baseline
- 6 DR strategies on that weekday (shed / DB / plant / HVAC / precool-shift / precool+plant)
- Hourly `Electricity:Facility` kW
- Unity geometry from IDF surfaces

## Missing for a credible DM ML model

### A. Weather / day diversity (highest priority)

| Gap | Why it matters |
| --- | --- |
| Cool / mild / design / extreme summer days | Model must condition on OAT, not memorize one peak day |
| Shoulder + winter electric days | Fans/reheat vs chiller regimes |
| Weekday vs weekend × weather | Occupancy interaction |
| Humidity / enthalpy days | Latent + economizer behavior |

**Farm rule:** sample ≥30–50 distinct calendar days from AMY (stratify by max DB),
run baseline + each strategy (or a designed subset).

### B. Action-space coverage

| Gap | Notes |
| --- | --- |
| Precool depth sweep (−1…−4°F) | Non-linear thermal mass |
| Relax magnitude / duration | 12–16 vs 12–18 vs 14–16 only |
| DAT-only vs zone+DAT | Zone-only was DAT-limited (~0 ΔkW) on this Twin |
| Partial plant (PLR cap) vs hard OFF | Soft DR labels |
| DSP / fan truncate | Fan kW without killing cooling |
| Rebound hours after event | 16–18 spike is an operator KPI |
| Staggered AHU1 vs AHU2 shed | Spatial Unity story |

### C. Labels beyond facility kW

| Gap | Use |
| --- | --- |
| `Cooling:Electricity` hourly | Plant vs fans attribution |
| Fans / pumps end-use if metered | Explainability |
| Max zone temp / unmet hours | Soft vs hard shed safety |
| Comfort violation flag | Unity red/amber |

### D. Feature engineering gaps

| Gap | Rule |
| --- | --- |
| Lagged kW / zone T | Need lookback windows; no future leakage |
| Thermal mass proxy | Morning precool energy → afternoon flexibility |
| `in_dr_window`, `phase∈{precool,relax,recovery}` | Categorical for Unity |
| Group split by `simulation_id` / day | No random hour splits |

### E. Real-BAS validation

Synthetic holdout ≠ building truth. Prefer a few vibe19 historian days with
known DR or natural SP changes for external validation (even if rare).

### F. Unity / architecture honesty

IDF has **12 lumped zones** (Floor×AHU), not rooms. Do not synthesize room
polygons. Optional later: map vibe19 VAV boxes as equipment icons without
fake walls.

## Minimum farm to start training

1. 40 AMY days × baseline  
2. Same 40 × `{precool_shift, deadband_10f, chiller_off}`  
3. 10 days × full strategy set (including HVAC off)  
4. Emit Parquet with schema in `SCHEMAS.md` (`vibe21.dm_hourly_row.v1`)  
5. Train separate models: (a) baseline demand given weather (b) delta-kW given actions — or one model with action features; compare.

## Do not

- Train only on the single hottest day  
- Use annual kWh as the DM twin target  
- Claim DR savings without documenting baseline day + action vector
