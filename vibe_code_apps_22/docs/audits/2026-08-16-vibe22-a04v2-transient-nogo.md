# A04-v2 transient model development — MODEL NO-GO (2026-08-16)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

**Terminal outcome:** `NO_GO_LONG_RL_TRAINING_TRANSIENT_MODEL_NOT_VALIDATED`

Long PPO/DQN training was **not started**. A04 was **not** overwritten. The BAS-informed ramp threshold (`ENGINEERING_MARGIN=3.0`) was **not** weakened.

## Base SHA / stack

| Item | Value |
| --- | --- |
| Branch | `feat/vibe22-a04v2-transient` |
| Base | `a5f6e770` (PR **#97** tip; includes PR **#96**) |
| PRs #96 / #97 | Still **OPEN** on `develop` — this PR is explicitly stacked |
| A04 SHA-256 | `212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683` |
| EPW SHA-256 | `87d7d9bfca7de4ac5b905ec1a65defc7622a78dac9444fc55cdef618ddf91fb2` |
| EnergyPlus | 26.1.0 |

## Phase 0 — frozen A04 failure (reproduced)

| Quantity | Value |
| --- | --- |
| Threshold | ≈ **2.651 °F / 15 min** |
| Incumbent | ≈ **4.616** |
| Low-unocc (68/58) | ≈ **8.203** |
| High-occ | ≈ **3.989** |
| Cause | Evening DualSP 70→65; A04 has **no** CapMult / InternalMass |
| Software recovery-window fix | **Retained** (morning ramp now applies) |

Artifact: [`figures/a04v2/phase0/baseline_manifest.json`](figures/a04v2/phase0/baseline_manifest.json)

## Phase 1 — meter sources (kept separate)

| Source | Role |
| --- | --- |
| **A** Utility bills | Monthly kWh / billed demand; Jan 2026 **284.82 kW** |
| **B** BAS `demand_interval_kw.csv` | Same family as `CS_ELEC_METER` — **not** utility AMI; load shape only |

Jan 2026 interval max ≈ **330 kW** vs billed **284.82 kW** (averaging-window difference).

Ledger: [`figures/a04v2/phase1/meter_source_ledger.md`](figures/a04v2/phase1/meter_source_ledger.md)

## Phase 2 — six-zone temperature folds

Primary aggregation (chosen before trials): six columns already in `real_baseline_15min_v1` from the 67-HP map. Cross-zone std/range published as disagreement proxies.

| Fold | Days |
| --- | ---: |
| train_dev | 233 |
| model_selection_val | 50 |
| heldout_transient | 50 |
| gate_smoke_excluded (Jan 25/26, Mar 16) | 3 |

January is **not** pristine.

## Phase 3–5 — Stage A results (one-factor)

### ZoneCapacitanceMultiplier:ResearchSpecial

| Temp mult | Ramp pass | Inc / Low / High max °F | Inc Jan26 peak kW |
| ---: | --- | --- | ---: |
| 10 | FAIL | 1.68 / 3.22 / 2.83 | 275 |
| 20 | FAIL (low) | 1.57 / 3.20 / 1.72 | 306 |
| 28 | **PASS** | 1.37 / 2.56 / 1.63 | **316** |
| 30 | **PASS** | 1.39 / 2.36 / 1.74 | **324** |
| 40 | **PASS** | 1.37 / 1.77 / 1.46 | **357** |

Frozen peak screen (before selection): **±10% of 284.82 kW** → **[256.3, 313.3] kW**, plus legacy 250–290 band.

**Pareto conflict:** CapMult ≥ ~28 is required for all three ramp arms; CapMult ≥ 28 pushes Jan26 incumbent peak **above** the frozen ±10% band. CapMult=40 also blows January monthly kWh (~+27% vs utility 81491).

### InternalMass furniture (no CapMult)

| Area m²/zone | Ramp pass | Inc / Low / High | Inc peak kW |
| ---: | --- | --- | ---: |
| 500 | FAIL | 4.61 / 8.14 / 4.00 | 243 |
| 1500 | FAIL | 4.59 / 7.98 / 3.98 | 249 |
| 3000 | FAIL | 4.56 / 7.72 / 3.97 | 255 |

InternalMass barely moves evening DualSP tracking; peaks stay near A04.

## Why no champion

A champion must pass **all** required gates (ramp + peak + partial-period monthly GL14-style). No Stage A candidate does.

Capacitance multipliers that fix transients inflate IdealLoads/W2A recovery power. Furniture mass alone does not fix DualSP air-node tracking on this geometry.

A full **Track B** geothermal W2A rebuild (part-load, loop, fans, DOAS) remains future work — not silently labeled A04.

## Long campaign

**Not allowed.** Committed [`figures/postfix/ramp_gate.json`](figures/postfix/ramp_gate.json) remains A04 `passed=false`. Candidate `ramp_gate.json` files under `figures/a04v2/stageA/` that show `passed=true` are CapMult trials that **fail the peak screen** and must not unlock training.

## Reproduction

```powershell
$env:SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
cd vibe_code_apps_22
python scripts/a04v2_phase0_freeze.py
python scripts/a04v2_phase1_meter_ledger.py
python scripts/a04v2_phase2_zone_dataset.py
python scripts/a04v2_build_capmult_candidate.py --temp-mult 28 --run-id capmult_t28
python scripts/reproduce_physics_ramp_gate.py --idf models/eplus/a04v2_candidates/capmult_t28/lakeside_w2a_a04v2_capmult_t28.idf --out docs/audits/figures/a04v2/stageA/capmult_t28 --force
python -m pytest tests -q
```

## Operational recommendation

**NO-GO** for long RL and BACnet. Next scientific step: Track B plant/geometry with mass that does not destroy the January demand anchor — or accept A04 as monthly-only and keep DSM RL blocked.
