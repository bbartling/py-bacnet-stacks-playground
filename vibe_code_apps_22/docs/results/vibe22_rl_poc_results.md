# Vibe22 RL PoC results (simulation-only)

> The completed RL and exhaustive fixed-policy campaigns were internally paired EnergyPlus screening experiments over December validation weather using OBSERVED_BAS_INCUMBENT_V2. They did not test reduction of the approximately 285 kW January billed-demand event.

Do **not** claim “DQN reduced 285→211 kW” or “grid reduced 285→220 kW”. Those mix January utility/A04-native peaks with December validation peaks under a different baseline contract. See [`docs/audits/2026-08-21-vibe22-baseline-contract-repair.md`](../audits/2026-08-21-vibe22-baseline-contract-repair.md) and the Jan 26 bridge pack under `docs/audits/figures/vibe22_cold_day_bridge/`.

## Honesty

- `SIMULATION-ONLY RL RESEARCH`
- `NOT VALIDATED FOR OPERATIONAL DSM`
- `NO PRISTINE LOCKED TEST`
- `A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION`
- `TOU TARIFF IS ILLUSTRATIVE`
- `CURRENT CAMPAIGNS USED OBSERVED_BAS_INCUMBENT_V2`
- `NO BACNET COMMAND AUTHORITY`
- `NO VERIFIED 285 kW DEMAND REDUCTION CLAIM`
- `RESEARCH POLICY SCREENING ONLY`

## Baseline contract (historical — not retconned)

Both campaigns used **`observed_bas_incumbent_v2`**:

- Scheduled heating approximately **68°F occupied / 64°F unoccupied**
- Scheduled DualSP transitions (not continuous conditioning)
- Cooling approximately **74°F occupied / 85°F unoccupied**

Reported actual BAS configuration may instead use continuous thermostat limits of 68F heating and 74F cooling. That conflict was not resolved before these campaigns.

Do **not** claim the campaign compared against continuous 68°F/74°F.
Do **not** present modeled deltas as verified savings versus actual BAS operation.

## December billing floor disclosure

> Validation demand-cost accounting initialized the December billing floor at zero and may overstate incremental candidate demand charges.

Original validation scores are retained; no offline re-score was possible without arm-specific Dec 1–14 facility series.

## Experiment scale (do not conflate)

| Counter | PRIMARY | SECONDARY |
|---|---:|---:|
| RL transitions per model (PPO/DQN seeds) | 8192 | 8192 |
| Validation arm-days (rows) | 187 | 187 |
| Train days | 44 | 44 |
| Validation calendar days | 17 | 17 |
| Actual EnergyPlus process launches | not recorded | not recorded |
| Elapsed s | 27322.988413899962 | 19035.51828770002 |
| Severe / fatal | 0 / 0 | 0 / 0 |
| BACnet commands | 0 | 0 |

## PRIMARY — FLAT_PLUS_DEMAND

- Validation leader: **`trained_ppo_seed0`** (readiness-constrained; not training mean reward)
- Incumbent total ≈ **$7623.65**
- Leader total ≈ **$7628.91**
- Delta versus incumbent ≈ **$+5.26**
- Incumbent peak ≈ **201.88 kW**; leader peak ≈ **233.77 kW**
- Leader **did not** reduce peak or total modeled cost versus the incumbent.
- Readiness: Ready on 5/5 checked school days; 12 non-school days were not subject to the school-start readiness gate.
- Incumbent readiness: Ready on 0/5 checked school days; 12 non-school days were not subject to the school-start readiness gate.

## SECONDARY — ILLUSTRATIVE_TOU_PLUS_DEMAND

- Validation leader: **`trained_dqn_seed1`**
- Incumbent total ≈ **$7082.56**
- Leader total ≈ **$7019.33**
- Illustrative delta ≈ **$-63.23**
- Incumbent peak ≈ **201.88 kW**; leader peak ≈ **211.51 kW**
- Illustrative savings came from the **TOU energy** component; demand cost and peak **increased**.
- TOU dollars are **illustrative** and **not** verified utility savings.
- Readiness: Ready on 5/5 checked school days; 12 non-school days were not subject to the school-start readiness gate.

**Never compare absolute dollar totals between PRIMARY and SECONDARY as if they were the same tariff.**

## Figures

- `docs/results/figures/cost_decomposition_by_tariff.(png|svg)`
- `docs/results/figures/peak_and_readiness_tradeoff.(png|svg)`
- `docs/results/figures/representative_daily_control_plan.(png|svg)`
- `docs/results/figures/representative_day_outcomes.(png|svg)` (aggregate-from-eval; timestep facility series not retained)

## Exhaustive discrete screen

Status: see [`grid_search/`](grid_search/README.md) — LIVE fixed-policy discrete v3 screen
executed (not the mega Phase 10 scaffold). Daily adaptive branching remains
`NOT_RUN_NO_IDENTICAL_STATE_BRANCHING_CONTRACT`.

## Baseline-contract repair (2026-08-21)

- Audit: [`docs/audits/2026-08-21-vibe22-baseline-contract-repair.md`](../audits/2026-08-21-vibe22-baseline-contract-repair.md)
- A05 decision: [`docs/audits/2026-08-21-vibe22-a05-decision.md`](../audits/2026-08-21-vibe22-a05-decision.md) — **A05 not opened**
- Jan 26 diagnostic bridge: [`docs/audits/figures/vibe22_cold_day_bridge/`](../audits/figures/vibe22_cold_day_bridge/)
- Two-month frozen-policy replay (Dec 2025–Jan 2026): [`two_month_policy_replay/`](two_month_policy_replay/)
- Cold challenge set: [`cold_weather_challenge_set_v1.json`](cold_weather_challenge_set_v1.json) — `RETROSPECTIVE_CONTAMINATED`
- Terminology: `contracts/baseline_terminology_v1.json`; `VERIFIED_BAS_INCUMBENT` **UNRESOLVED**

### Jan 26 bridge peaks (diagnostic, same IDF/EPW/day)

| Arm | Peak kW | Δ vs native | Δ vs obs BAS v2 |
| --- | ---: | ---: | ---: |
| A04 native SCH_HtgSP | 288.15 | 0 | +55.87 |
| observed_bas_incumbent_v2 | 232.29 | −55.87 | 0 |
| continuous 68 heat (unverified sensitivity) | 226.13 | −62.03 | −6.16 |
| grid flat discrete_42 | 238.77 | −49.38 | +6.48 |
| grid TOU discrete_43 | 238.77 | −49.38 | +6.48 |
| deep setback fixed rule | 251.51 | −36.64 | +19.23 |
| frozen PPO (zero-obs probe) | 240.54 | −47.61 | +8.25 |
| frozen DQN (zero-obs probe) | 250.47 | −37.69 | +18.18 |

Deltas vs A04 native are **diagnostic**, not an operational BAS counterfactual. Frozen PPO/DQN actions used a zeroed observation vector (labeled diagnostic).
