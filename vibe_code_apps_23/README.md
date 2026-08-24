# Vibe 23 — LBNL Building 59 calibrated-model + grid-flex lab

Vibe 23 is the evidence-first path from the public LBNL Building 59 / Shyh Wang Hall dataset to an EnergyPlus baseline and, only after calibration, a transparent grid-flexibility search.

> **Current status: `CALIBRATION_BOOTSTRAP`.** The repository contains the research basis, safe data pipeline, strict Open-FDD bridge, model/calibration contracts, tariff/reward logic, and deterministic grid tooling. It does **not** yet contain a runnable or GL14-calibrated Building 59 IDF, a verified historical Building 59 tariff, or a completed DSM result.

## Delivery snapshot

| Workstream | Implemented now | Remaining proof gate |
| --- | --- | --- |
| Vibe 19–22 skills | All 56 discovered `SKILL.md` sources are mapped in a machine-validated registry; 53 feed 20 shared skills and 3 invalid/archived/UI-only sources are preserved locally | Keep registry validation green as historical skills change |
| Building 59 evidence | Peer-reviewed/official source dossier, machine-readable source manifest, system/topology and regime-change evidence | Resolve geometry/meter scope from the actual package/drawings |
| Data acquisition | Safe nested-ZIP extraction, hashes, API token/URL override, and manual-release fallback | Acquire all four Dryad release files and freeze the local manifest |
| Open-FDD | Explicit point-mapping contract and tested `openfdd_package_v1` ZIP exporter | Bind real columns, run only supported rules, review findings |
| EnergyPlus | Non-runnable seed template, parameter ledger, model/iteration hashing, GL14-style alignment and diagnostics | Author geometry/HVAC, build AMY EPW, run EnergyPlus, iterate and pass gates |
| Tariff/reward | Verified/candidate/illustrative evidence gate, incremental-demand billing, Vibe 22-compatible 2x/3x operator-pay semantics | Prove the account-period tariff or retain scenario-only dollars |
| Grid search | Deterministic finite grid, identical-state contract, paired ranking, pinned upstream inspection | Implement the Building 59 simulator adapter after model/actuator bindings exist |

The full execution and acceptance sequence is in [`docs/VIBE23_CALIBRATED_MODEL_AND_GRID_FLEX_PLAN.md`](docs/VIBE23_CALIBRATED_MODEL_AND_GRID_FLEX_PLAN.md).

## Source of record

- Dryad DOI: [`10.7941/D1N33Q`](https://doi.org/10.7941/D1N33Q)
- Scientific Data paper: [`10.1038/s41597-022-01257-x`](https://doi.org/10.1038/s41597-022-01257-x)
- Published release: `Building_59.zip` plus workbook, metadata document, and README
- Reported data: 27 cleaned CSV files, 337 points, three years, and more than 300 sensors/meters

The publication describes a four-floor, approximately 10,400 m² conditioned building. The monitored two-office-floor scope is reported as 2,325 m² per floor, while a later office HVAC study reports approximately 6,038 m². Vibe 23 records that discrepancy as unresolved; it does not average the numbers or silently choose a model area.

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

# Validate the evidence blockers in the non-calibrated model ledger.
vibe23 validate-model-ledger --ledger model/parameter_ledger.seed.json

# Inspect the researched upstream pin without installing Ray/EnergyPlus extras.
git clone https://github.com/airboxlab/rllib-energyplus ../rllib-energyplus
git -C ../rllib-energyplus checkout a8993f0d87e7d1fbcff0c2593274de2d472aef75
vibe23 inspect-rllib --root ../rllib-energyplus
```

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

vibe23 inspect-tariff --tariff config/examples/tariff.illustrative_zero.json
vibe23 enumerate-grid \
  --grid config/examples/grid.bootstrap.json \
  --out reports/grid/candidates.bootstrap.json
```

The example tariff is intentionally zero-valued and illustrative; it only exercises the evidence contract. The example grid only exercises deterministic enumeration. Neither is a Building 59 economic or control assumption.

Monthly acceptance is `|NMBE| <= 5%` and `CV(RMSE) <= 15%`. Hourly acceptance is `|NMBE| <= 10%` and `CV(RMSE) <= 30%`. Monthly GL14 alone is insufficient for grid flexibility: peak, load shape, end use, zone temperature, control behavior, transient response, and chronological holdout are separate gates.

`vibe23 score` reports standalone numeric diagnostics and always marks the result ineligible for a calibration claim. Claim status comes only from the provenance-bearing scorecard path; monthly promotion also requires at least 12 complete paired months.

## Repository map

| Path | Purpose |
| --- | --- |
| [`docs/research/building59_calibration_evidence_dossier.md`](docs/research/building59_calibration_evidence_dossier.md) | Source-backed building/HVAC/data/weather/tariff findings |
| [`config/evidence_ledger.json`](config/evidence_ledger.json) | Central facts, data-binding requirements, and unresolved issues |
| [`model/b59_seed.idf.template`](model/b59_seed.idf.template) | Intentionally non-runnable provenance template |
| [`model/parameter_ledger.seed.json`](model/parameter_ledger.seed.json) | Explicit model-freeze blockers |
| [`vibe23_agent_spec/OPENFDD_PIPELINE.md`](vibe23_agent_spec/OPENFDD_PIPELINE.md) | Open-FDD contract and handoff |
| [`vibe23_agent_spec/GRID_SEARCH.md`](vibe23_agent_spec/GRID_SEARCH.md) | Vibe 22 reward, tariff, paired-state, and upstream-adapter contract |
| [`../agentic_ai/skills/migration_registry.json`](../agentic_ai/skills/migration_registry.json) | Complete Vibe 19–22 shared-skill migration map |

## Claim boundaries

- Derived monthly meter totals are not utility bills.
- A local PG&E schedule is not Building 59's historical tariff unless account and period evidence prove it.
- A rendered seed or successful EnergyPlus smoke run is not a calibrated model.
- A simulated grid-search result is not a field saving or BACnet authorization.
- The Vibe 22 peak lesson remains open: prior candidates did not verify removal of the approximately 285 kW January peak, and their fast transient response was not validated.
