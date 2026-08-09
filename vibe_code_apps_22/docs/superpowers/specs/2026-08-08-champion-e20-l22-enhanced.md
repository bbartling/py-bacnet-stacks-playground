# Champion candidate: E20 (enhanced L22)

**Campaign:** `w2a_l22_enhanced_20260808T205123Z`  
**Trial:** `E20_peakplant_eq075_li110_cop120`

## Recipe
| Knob | L22 | E20 |
| --- | ---: | ---: |
| `htg_coil_capacity_mult` | 1.45 | **1.70** |
| `htg_coil_cop_mult` | 1.24 | **1.20** |
| `setback_heat_sp_c` | 7.78 (~46°F) | 7.78 |
| `optimum_start_h` | 3.5 | 3.5 |
| `equip_w_area_mult` | 1.00 | **0.75** (cut plugs after ~285/GL14-fail) |
| `lights_w_area_mult` | 1.00 | **1.10** |

## Metrics (Jan‑26 / monthly utility GL14)
| | L22 | E20 |
| --- | ---: | ---: |
| Overnight 0–4 sim | ~126 kW | ~135 kW |
| Jan‑26 peak | ~261 kW | **~271 kW** |
| NMBE / CVRMSE | −4.4% / 14.9% | **−4.9% / 13.5%** (pass) |

## What Phase A taught
Raising plugs/lights on L22 easily hits **275–294 kW** peak (E01–E10) but **fails monthly GL14** (NMBE −13% to −24%). Overnight stayed mostly ≤140 kW until opt-start 4.0 h pushed baseload up.

## Equip-cut recovery
Cutting `equip_w_area_mult` to 0.70–0.90 while holding fat plant + opt-start recovered GL14 on **E20** and raised peak ~10 kW over L22. Still ~14 kW short of billed **285 kW**. Phase C explores the E20 neighborhood toward 275–285 while holding GL14.

## Fallback
If Phase C does not produce a dual with peak ≥275 and GL14 pass, keep **E20** as enhanced champion (else L22 if E20 overnight gate is unacceptable). Winter overnight *average* observed ~68 kW; Jan‑26 overnight observed is much higher (~161 kW) — design-day overnight is not the winter mean.
