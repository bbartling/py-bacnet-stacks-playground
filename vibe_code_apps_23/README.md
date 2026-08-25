# Vibe 23 — LBNL Building 59 calibrated-model + grid-flex lab

Vibe 23 is the evidence-first path from the public LBNL Building 59 / Shyh Wang Hall dataset to an EnergyPlus baseline and, only after calibration, a transparent grid-flexibility search.

**Agent takeover:** start with [`docs/B59_AGENT_HANDOFF.md`](docs/B59_AGENT_HANDOFF.md). It contains the exact clone, data-download, analytics, EnergyPlus validation, and next-model steps.

> **Current status: `CALIBRATION_IN_PROGRESS_BEST_EFFORT`.** The repository now contains real B59 telemetry targets, a bounded-hybrid 2020 AMY, a runnable EnergyPlus 26.1 screening IDF, and a reproducible 50-run campaign. All 50 historical runs had zero warning/severe/fatal markers in the scanned EnergyPlus logs; historical R49 had an incomplete ancillary EIO file, while a post-release repeat passed the strengthened complete-EIO gate. Monthly GL14 was **not met** (`NMBE = -4.13%`, `CV(RMSE) = 22.36%`). The model remains `OFFICE_SCREENING_SEED_UNCALIBRATED`; grid-flexibility/DSM claims are blocked.

## Delivery snapshot

| Workstream | Implemented now | Remaining proof gate |
| --- | --- | --- |
| Vibe 19–22 skills | All 56 discovered `SKILL.md` sources are mapped in a machine-validated registry; 53 feed 20 shared skills and 3 invalid/archived/UI-only sources are preserved locally | Keep registry validation green as historical skills change |
| Building 59 evidence | Peer-reviewed/official source dossier, machine-readable source manifest, system/topology and regime-change evidence | Resolve geometry/meter scope from the actual package/drawings |
| Data acquisition | Official Zenodo-mirror fallback, safe nested-ZIP extraction, hashes, 27 real telemetry CSVs, partial seed bindings, a complete 27-file data-role matrix, and 35,136 complete 2020 electrical samples | Finish executable point/unit/time bindings and resolve the electrical panel/end-use boundary |
| Open-FDD | Explicit point-mapping contract and tested `openfdd_package_v1` ZIP exporter | Bind real columns, run only supported rules, review findings |
| EnergyPlus | EnergyPlus 26.1 runtime, 8,784-hour hybrid AMY, runnable two-floor/four-RTU/UFAD **proxy** seed, strict annual-output/sizing gate, and deterministic 50-run harness | Replace the proxy with a data-bound 57-zone/50-UFT/plant model and pass monthly/hourly/physics gates |
| Charts | Published hash-bearing 50-run progress, GL14 scorecard, measured-vs-E+ monthly, residual, parity, and scope/end-use evidence | Add hourly, peak, zone, control, and transient plots after timestamp/point binding |
| Tariff/reward | Verified/candidate/illustrative evidence gate, incremental-demand billing, Vibe 22-compatible 2x/3x operator-pay semantics | Prove the account-period tariff or retain scenario-only dollars |
| Grid search | Deterministic finite grid, identical-state contract, paired ranking, pinned upstream inspection | Implement the Building 59 simulator adapter after model/actuator bindings exist |
| Grid-search **lessons** (ExampleFiles) | Progressive 10-day tutorial under [`lessons/grid_search/`](lessons/grid_search/INDEX.md): pseudocode → fake data → stock E+ models → BESS bonus | Keep educational-only; do not treat as B59 calibration or BACnet authority |

The executed result is in [`docs/B59_50_RUN_SCREENING_RESULTS.md`](docs/B59_50_RUN_SCREENING_RESULTS.md). The full execution and acceptance sequence is in [`docs/VIBE23_CALIBRATED_MODEL_AND_GRID_FLEX_PLAN.md`](docs/VIBE23_CALIBRATED_MODEL_AND_GRID_FLEX_PLAN.md).

## Source of record

- Dryad DOI: [`10.7941/D1N33Q`](https://doi.org/10.7941/D1N33Q)
- Scientific Data paper: [`10.1038/s41597-022-01257-x`](https://doi.org/10.1038/s41597-022-01257-x)
- Published release: `Building_59.zip` plus workbook, metadata document, and README
- Reported data: 27 cleaned CSV files, 337 points, three years, and more than 300 sensors/meters

The publication describes a four-floor, approximately 10,400 m² conditioned building. The monitored two-office-floor scope is reported as 2,325 m² per floor, while a later office HVAC study reports approximately 6,038 m². Vibe 23 records that discrepancy as unresolved; it does not average the numbers or silently choose a model area.

The current BBD catalog page advertises data through 2021-12-31, but the
acquired cleaned package generally ends at 2020-12-31 or the 2021-01-01
interval boundary. Vibe 23 does not claim that 2021 telemetry is present until
the current BBD release is separately downloaded, inventoried, and hash-frozen.

## Quick start

```bash
cd vibe_code_apps_23
python -m pip install -e ".[dev]"

# The public Dryad endpoint may reject automated clients. Either use the API...
vibe23 download --data-dir data

# ...or download all four release files manually and stage their directory.
vibe23 download --data-dir data --source-release /path/to/dryad_release

# Inventory real files/headers before authoring any executable point map.
vibe23 inventory \
  --root data/raw/building_59 \
  --out data/processed/inventory.csv

# Build the exact 2020 derived-office-subtotal target.
python scripts/build_b59_targets.py \
  --raw-root 'data/raw/building_59/Bldg59_clean data' \
  --out-dir scorecards/b59_2020_screening/source_targets

# Reproduce source-clock occupancy/load and HVAC/setpoint evidence.
python scripts/analyze_b59_occupancy_loads.py \
  --raw-root 'data/raw/building_59/Bldg59_clean data' \
  --output config/b59_occupancy_load_evidence.json
python scripts/analyze_b59_hvac_operation.py \
  --raw-root 'data/raw/building_59/Bldg59_clean data' \
  --json-out config/b59_hvac_operating_evidence.json \
  --markdown-out docs/research/b59_hvac_operating_evidence.md

# Prepare saved weather inputs and reproduce the bounded-hybrid EPW.
python scripts/prepare_b59_weather_inputs.py --help
python scripts/build_b59_2020_epw.py \
  --manifest-out data/processed/b59_weather/b59_2020_epw_manifest.json

# Validate the evidence blockers in the non-calibrated model ledger.
vibe23 validate-model-ledger --ledger model/parameter_ledger.seed.json

# Check whether this host can run native or Docker EnergyPlus (no pull/build).
vibe23 energyplus-doctor --out reports/runtime/energyplus_capability.json

# Inspect the researched upstream pin without installing Ray/EnergyPlus extras.
git clone https://github.com/airboxlab/rllib-energyplus ../rllib-energyplus
git -C ../rllib-energyplus checkout a8993f0d87e7d1fbcff0c2593274de2d472aef75
vibe23 inspect-rllib --root ../rllib-energyplus
```

With an explicit EnergyPlus 26.1 executable, run the bounded release workflow:

```bash
python scripts/run_b59_50_campaign.py \
  --energyplus /path/to/EnergyPlus-26.1.0/energyplus \
  --epw weather/b59_2020_bounded_hybrid_amy.epw \
  --measured-monthly scorecards/b59_2020_screening/source_targets/b59_2020_monthly_records.csv \
  --run-root campaigns/runs/b59_2020_screening \
  --publish-dir scorecards/b59_2020_screening \
  --champion-idf model/b59_screening_champion.generated.idf \
  --workers 4
```

This is a screening campaign, not a command that promotes the model. The
published champion fails monthly variability and reserved validation, contains
large offsetting end-use errors, and is not ready for RL/grid search.

For authorized API access, set `VIBE23_DRYAD_BEARER_TOKEN`. A custom authorized endpoint can be supplied with `--download-url` or `VIBE23_DRYAD_DOWNLOAD_URL`. Credentials are never written to the acquisition manifest.

## From measured data to Open-FDD evidence

Do not copy the example mapping into a campaign unchanged. Replace every placeholder only after reviewing the extracted data dictionary, Brick metadata, and inventory.

```bash
cp config/examples/openfdd_mapping.template.json config/b59_openfdd_mapping.json

vibe23 export-openfdd \
  --mapping config/b59_openfdd_mapping.json \
  --raw-root data/raw/building_59 \
  --out data/processed/LBNL_B59_openfdd.zip \
  --report reports/openfdd/adapter_report.json
```

The exporter does not infer names, convert units, fill gaps, or invent weather/topology. Open-FDD findings can support schedules, runtime, economizer/SAT behavior, sensor exclusions, and operational constraints. They cannot establish geometry, equipment performance, tariff assignment, or calibration by themselves.

## Calibration and grid contracts

After positively binding a measured power channel:

```bash
vibe23 aggregate-power \
  --csv path/to/verified_source.csv \
  --timestamp-column VERIFIED_TIMESTAMP \
  --value-column VERIFIED_POWER_KW \
  --rule 1h \
  --out data/processed/measured_hourly.csv

vibe23 score \
  --csv reports/calibration/measured_vs_simulated_monthly.csv \
  --interval monthly \
  --out reports/calibration/monthly_gl14.json

vibe23 plot-calibration \
  --csv reports/calibration/measured_vs_simulated_hourly.csv \
  --data-kind mean_power --unit kW --energy-unit kWh \
  --output-dir reports/calibration/baseline_001/figures

vibe23 plot-calibration-campaign \
  --campaign-log campaigns/calibration_log.csv \
  --output-dir reports/calibration/campaign_progress

vibe23 inspect-tariff --tariff config/examples/tariff.illustrative_zero.json
vibe23 enumerate-grid \
  --grid config/examples/grid.bootstrap.json \
  --out reports/grid/candidates.bootstrap.json
```

The example tariff is intentionally zero-valued and illustrative; it only exercises the evidence contract. The example grid only exercises deterministic enumeration. Neither is a Building 59 economic or control assumption.

Monthly acceptance is `|NMBE| <= 5%` and `CV(RMSE) <= 15%`. Hourly acceptance is `|NMBE| <= 10%` and `CV(RMSE) <= 30%`. Monthly GL14 alone is insufficient for grid flexibility: peak, load shape, end use, zone temperature, control behavior, transient response, and chronological holdout are separate gates.

`vibe23 score` reports standalone numeric diagnostics and always marks the result ineligible for a calibration claim. Claim status comes only from the provenance-bearing scorecard path; monthly promotion also requires at least 12 complete paired months.

EnergyPlus engine/MCP preparation, the non-overwriting smoke runner, existing-run
inspection, and chart input semantics are documented in
[`vibe23_agent_spec/ENERGYPLUS_VALIDATION.md`](vibe23_agent_spec/ENERGYPLUS_VALIDATION.md).

## Repository map

| Path | Purpose |
| --- | --- |
| [`docs/research/building59_calibration_evidence_dossier.md`](docs/research/building59_calibration_evidence_dossier.md) | Source-backed building/HVAC/data/weather/tariff findings |
| [`docs/B59_AS_OPERATED_MODEL_REVISION_PLAN.md`](docs/B59_AS_OPERATED_MODEL_REVISION_PLAN.md) | Telemetry-first replacement architecture, revised 50-run budget, and promotion gates |
| [`docs/research/b59_all_data_role_matrix.md`](docs/research/b59_all_data_role_matrix.md) | Audited disposition for every one of the 27 cleaned CSVs |
| [`docs/research/b59_code_era_modeling_basis.md`](docs/research/b59_code_era_modeling_basis.md) | 2015-vintage code-era guardrails; no nonexistent “90.1-2015” label |
| [`docs/research/b59_occupancy_load_evidence.md`](docs/research/b59_occupancy_load_evidence.md) | Reproducible camera/Wi-Fi/electrical schedule evidence and scope/clock caveats |
| [`docs/research/b59_hvac_operating_evidence.md`](docs/research/b59_hvac_operating_evidence.md) | Reproducible runtime, SAT, thermostat, OA, UFT, and regime analytics |
| [`docs/B59_50_RUN_SCREENING_RESULTS.md`](docs/B59_50_RUN_SCREENING_RESULTS.md) | Executed 50-run outcome, failed gates, compensating-error audit, and next actions |
| [`config/evidence_ledger.json`](config/evidence_ledger.json) | Central facts, data-binding requirements, and unresolved issues |
| [`scorecards/b59_2020_screening/`](scorecards/b59_2020_screening/) | Hash-bearing targets, campaign ledger/results, scope audit, and PNG/SVG evidence |
| [`model/b59_screening_champion.generated.idf`](model/b59_screening_champion.generated.idf) | Exact executed screening champion; explicitly not calibrated/as-built |
| [`weather/b59_2020_epw_manifest.json`](weather/b59_2020_epw_manifest.json) | Portable provenance/hash for the ignored generated EPW |
| [`model/b59_seed.idf.template`](model/b59_seed.idf.template) | Intentionally non-runnable provenance template |
| [`model/parameter_ledger.seed.json`](model/parameter_ledger.seed.json) | Explicit model-freeze blockers |
| [`vibe23_agent_spec/OPENFDD_PIPELINE.md`](vibe23_agent_spec/OPENFDD_PIPELINE.md) | Open-FDD contract and handoff |
| [`vibe23_agent_spec/ENERGYPLUS_VALIDATION.md`](vibe23_agent_spec/ENERGYPLUS_VALIDATION.md) | Native/Docker/MCP preflight, smoke/artifact gates, and chart publication |
| [`vibe23_agent_spec/GRID_SEARCH.md`](vibe23_agent_spec/GRID_SEARCH.md) | Vibe 22 reward, tariff, paired-state, and upstream-adapter contract |
| [`../agentic_ai/skills/migration_registry.json`](../agentic_ai/skills/migration_registry.json) | Complete Vibe 19–22 shared-skill migration map |

## Claim boundaries

- Derived monthly meter totals are not utility bills.
- A local PG&E schedule is not Building 59's historical tariff unless account and period evidence prove it.
- A rendered seed or successful EnergyPlus smoke run is not a calibrated model.
- A near-zero annual bias with failed CV(RMSE), monthly shape, end uses, or reserved validation is not calibration.
- A simulated grid-search result is not a field saving or BACnet authorization.
- The Vibe 22 peak lesson remains open: prior candidates did not verify removal of the approximately 285 kW January peak, and their fast transient response was not validated.
