# Building 59 EnergyPlus tuning — next-agent handoff

This is the canonical clone-and-resume document for Vibe 23. It records what
was attempted, what the downloaded data mean, what is proven, and the exact
next work. Read `../AGENTS.md` first.

## Current truth

- Status: `CALIBRATION_IN_PROGRESS_BEST_EFFORT`.
- The EnergyPlus 26.1 screening IDF runs with zero warning, severe, and fatal
  diagnostics and produces 8,784 hourly rows with a complete EIO.
- Monthly 2020 score: NMBE **-4.13%**, CV(RMSE) **22.36%**. The monthly
  Guideline-14-style gate (`|NMBE| <= 5%`, `CV(RMSE) <= 15%`) is **not met**.
- January–September: NMBE +1.33%, CV(RMSE) 17.86%. October–December: NMBE
  -33.88%, CV(RMSE) 43.63%. The latter was inspected throughout and is a
  reserved diagnostic slice, not a blind holdout.
- The IDF is `OFFICE_SCREENING_SEED_UNCALIBRATED`. Do not use it for savings,
  tariff settlement, or RL/grid-flexibility claims.

## What was tried

1. Downloaded and hash-inventoried the public B59 clean release.
2. Built a scope-qualified 2020 electrical target from available office meters
   and an 8,784-hour bounded-hybrid actual-year weather file.
3. Authored a runnable two-office-floor, four-RTU, 24-zone UFAD proxy IDF.
4. Ran a deterministic 50-candidate screening campaign.
5. Published progress, monthly comparison, residual, parity, GL14, and end-use
   charts plus hash-bearing scorecards.
6. Re-ran the champion under a strengthened admission gate: clean diagnostics,
   complete EIO, and expected hourly row count.
7. Analyzed occupancy/load timing, RTU feedback and setpoints, zone setpoints,
   UFT points, outdoor-air flow, and plant temperature/flow evidence.
8. Compared those measured values directly with the screening IDF. The result
   shows structural mismatches, so further tuning of the proxy was stopped.

The 50-run outcome is documented in `B59_50_RUN_SCREENING_RESULTS.md`. The
replacement architecture and ordered work packages are in
`B59_AS_OPERATED_MODEL_REVISION_PLAN.md`.

## What the public data represent

Source page: <https://bbd.labworks.org/ds/bbd/lbnlbldg59>. Archived research
release DOI: <https://doi.org/10.7941/D1N33Q>.

Building 59 includes two office floors, a mechanical floor, and a NERSC data
and computing floor. The dataset covers the **two office floors**, not the
whole building. It contains building/office electrical measurements, HVAC and
lighting states, zone/environmental measurements, weather, occupant-camera
counts, and WiFi-device counts.

The clean release has 27 CSVs. Their hashes, date coverage, cadence, modeling
role, and prohibitions are exhaustive in:

- `config/b59_model_data_roles.json`
- `docs/research/b59_all_data_role_matrix.md`

Important scope/time qualifications:

- The BBD page advertises 2018-01-01 through 2021-12-31, while the acquired
  clean release metadata and most files end 2020-12-31 (some use the
  2021-01-01 interval boundary). Re-download and compare hashes before claiming
  2021 observations.
- CSV timestamps are timezone-naive. Keep source-clock results until the BAS
  timezone and DST convention are proven.
- Camera occupancy covers only part of the south office, approximately
  2018-05-22 through 2019-02-21. WiFi is a device proxy and has different
  coverage; neither is a whole-building people count.
- The 2020 scored target is a partial office subtotal:
  `mels_S + mels_N + lig_S + hvac_S + hvac_N`. It omits north lighting and
  does not resolve every load inside the HVAC panels.
- Cleaned files may include curated/imputed values. Fan speed, valve position,
  water flow, and thermal-rate points are evidence but not interchangeable
  proof of electrical power or equipment runtime.

Never commit the 263 MB archive or extracted multi-GB telemetry. They are
intentionally ignored; scripts, manifests, hashes, derived evidence, charts,
and model artifacts are versioned.

The acquired archive is 263,162,077 bytes with SHA-256
`1e224dd7479bb196a8e0368fceb70aa6f699c1d39e1e895ceba7f3b25150b1b4`.
The Zenodo/Dryad transport URL and release version still require reconciliation;
do not infer release identity from the short hash shown here.

## Fresh clone and data acquisition

```bash
git clone https://github.com/bbartling/py-bacnet-stacks-playground.git
cd py-bacnet-stacks-playground
git switch feat/vibe23-lbnl-b59-calibration
cd vibe_code_apps_23
python -m pip install -e '.[dev]'
vibe23 download --data-dir data
```

If automated acquisition is unavailable, download all release files from the
BBD/Dryad links above, extract them locally, and pass the release directory:

```bash
vibe23 download --data-dir data --source-release /absolute/path/to/dryad_release
```

For an authorized API endpoint, set `VIBE23_DRYAD_BEARER_TOKEN` and optionally
`VIBE23_DRYAD_DOWNLOAD_URL`. Do not store credentials in manifests or git.

Expected clean-data root after acquisition:

```text
data/raw/building_59/Bldg59_clean data
```

## Reproduce the operational analytics

```bash
RAW='data/raw/building_59/Bldg59_clean data'

python scripts/analyze_b59_occupancy_loads.py \
  --raw-root "$RAW" \
  --json-out config/b59_occupancy_load_evidence.json \
  --markdown-out docs/research/b59_occupancy_load_evidence.md

python scripts/analyze_b59_hvac_operation.py \
  --raw-root "$RAW" \
  --json-out config/b59_hvac_operating_evidence.json \
  --markdown-out docs/research/b59_hvac_operating_evidence.md

python scripts/compare_b59_measured_to_idf.py \
  --raw-root "$RAW" \
  --json-out config/b59_measured_vs_screening_idf.json \
  --markdown-out docs/research/b59_measured_vs_screening_idf.md
```

The human-readable comparison table is
`docs/research/b59_measured_vs_screening_idf.md`; the JSON is the machine
handoff. Plot pack (CSV + PNG/SVG) from frozen evidence only:

```bash
python scripts/plot_b59_measured_vs_idf.py
# → scorecards/b59_2020_screening/figures/measured_vs_idf/
```

The strongest mismatches are:

Percentiles in the HVAC evidence use deterministic row-stride samples, and
regime summaries pool point samples; they are not equipment- or floor-weighted
statistics.

| Evidence | Measured/public value | Screening IDF | Consequence |
| --- | --- | --- | --- |
| RTU SAT setpoint | medians 65.62–68.00°F | fixed 57.9°F | Replace with dated replay/reset law |
| Per-RTU airflow | published 20,000 cfm | 13,500 cfm | IDF is 32.5% low |
| Per-RTU cooling capacity | published 105.5 kW | 142.4 kW | IDF is 35.0% high |
| Terminals | 51 UFT fan and 44 HW-valve points | no terminal fans; 24 electric reheat proxies | Rebuild terminal topology |
| Plant | chilled/hot-water flow and temperature evidence | no water plant; air-cooled DX/electric reheat | Rebuild plant/topology |
| Monthly GL14 | NMBE -4.13%; CV(RMSE) 22.36% | threshold 5% / 15% | Fail on variability |

## EnergyPlus validation

Use EnergyPlus 26.1.0 (native or the repository's documented Docker path).
Run `vibe23 doctor --repo-root .` to discover available runtimes. The published
proof is `scorecards/b59_2020_screening/postrelease_champion_validation.json`.
It records admission, engine version, hashes, zero diagnostics, complete EIO,
and 8,784 hourly rows.

The historical campaign IDF SHA is
`7096c0ae7a749b800458b420d8936ed2e6146252178c998e9ba6f01b549fffa6`;
the post-release validation IDF SHA is
`3e4407b3cd13f082aaa2da9e4fef620780bdcd77022387d81d173ba011527ef5`
because a stale generator comment was corrected. Physics and hourly output are
unchanged. Only the serial post-release repeat is evidence for the strengthened
complete-EIO gate.

Every new candidate must pass all of these before scoring:

1. EnergyPlus exit code zero.
2. Zero warnings, severe errors, and fatal errors under the declared project gate.
3. EIO contains `End of Data`.
4. Expected annual hourly output count and required variables/meters are present.
5. Model, weather, target, parameter, and output hashes are persisted.

Do not edit `model/b59_screening_champion.generated.idf`; it is historical,
hash-bound campaign evidence. Create a new as-operated model lineage.

## Exact next work

1. Freeze/reconcile the current BBD release, timestamps, units, and meter scope.
2. Map Brick equipment and points into four RTU loops, 50 UFTs/controlled zones,
   plant loops, and meter boundaries; document every unresolved identifier.
3. Run OpenFDD only after roles/units are bound. Use findings as evidence for
   control modes and faults, never as direct IDF parameters.
4. Author the as-operated IDF with measured hydronic fan-powered perimeter
   terminals, water-source RTUs/shared chilled water, hot-water history/change
   regime, correct capacities/flows, and explicit output meters.
5. Replay measured SAT, thermostat, OA, fan-enable, and availability schedules
   for physics calibration. Later infer validated reset laws for control/RL work.
6. Pass design-day and annual clean-engine gates; then add hourly/end-use/zone
   temperature/control-tracking objectives.
7. Run sensitivity screening and a new bounded 50-run campaign. Use a genuinely
   untouched chronological validation period; never relabel Oct–Dec 2020 blind.
8. Only after monthly/hourly/physics/holdout gates pass, freeze the baseline and
   connect real tariff evidence plus `rllib-energyplus` grid-search experiments.

Do not use “ASHRAE 90.1-2015”: no such edition exists. Use measured operation
first; code-era priors are limited to 90.1-2013 or 2015 IECC and must remain
tagged assumptions unless permit/retrofit evidence resolves the applicable code.

## Validation before taking over

From `vibe_code_apps_23`:

```bash
python -m pytest
python -m ruff check src tests scripts
python -m compileall -q src/vibe23 scripts
git diff --check
```

From the repository root:

```bash
python agentic_ai/skills/scripts/validate_registry.py
```

Start the next implementation commit by creating an explicit Brick-to-IDF
topology/point map and a new model generator. Do not start with another blind
parameter sweep of the screening seed.
