# EnergyPlus execution, validation, and chart publication

Vibe 23 supports the same two execution routes proven in the earlier apps:

1. a native `energyplus` executable; or
2. the Vibe 20 `energyplus-mcp-dev` Docker image, pinned in
   `config/energyplus_engine.json`.

EnergyPlus-MCP is an optional inspection/editing surface around that engine. It
does not replace the IDF, AMY weather, measured targets, calibration loop, or
Guideline 14 gates.

## 1. Preflight

```bash
cd vibe_code_apps_23
vibe23 energyplus-doctor \
  --mcp-vendor ../vibe_code_apps_20/third_party/EnergyPlus-MCP \
  --out reports/runtime/energyplus_capability.json
```

The command does not pull images or alter Docker. A usable path reports
`READY_NATIVE` or `READY_DOCKER`. `BLOCKED_ENGINE_UNAVAILABLE` means this host
cannot run EnergyPlus yet.

The Docker/MCP build remains owned by Vibe 20:

```bash
cd ../vibe_code_apps_20
wattlab energyplus-ensure
```

That command requires Docker plus a daemon/socket and builds the pinned
`energyplus-mcp-dev` image when needed.

## 2. Building 59 calibration-ready smoke gate

Only run this after the Building 59 seed is runnable and the actual-year EPW is
frozen:

```bash
vibe23 run-eplus-smoke \
  --engine docker \
  --idf model/seed/building59_seed.idf \
  --epw weather/b59_2019_amy.epw \
  --output-dir campaigns/runs/smoke_001
```

The command refuses to overwrite a non-empty output directory. It stages the
inputs, runs EnergyPlus with ReadVars, hashes the IDF/EPW and standard outputs,
and writes `run_manifest.json`. `ENGINE_SMOKE_PASS` requires:

- `eplusout.err`, `eplusout.end`, and non-empty `eplusout.csv`;
- the EnergyPlus successful-completion marker;
- process return code zero and consistent totals across `.err`, `.end`, and `console.log`;
- hashed IDF and EPW inputs plus a recorded EnergyPlus version;
- a non-empty `Electricity:Facility` meter column;
- zero warnings under the default strict policy;
- zero severe errors; and
- zero fatal errors.

Existing output folders can be inspected without rerunning:

```bash
vibe23 inspect-eplus-run \
  --run-dir campaigns/runs/smoke_001 \
  --idf model/seed/building59_seed.idf \
  --epw weather/b59_2019_amy.epw \
  --energyplus-version 26.1.0-6f2e40d102 \
  --out reports/runtime/smoke_001_inspection.json
```

An inspection of a separately produced output folder also needs a
`run_manifest.json` whose return code, input hashes, and required output hashes
bind to the artifacts being inspected, and whose EnergyPlus version/engine
identity matches the inspection, or it fails closed because the process outcome
is unknown. The Facility meter must be canonical and unambiguous; values must be
finite/nonnegative and timestamps syntactically valid, unique, and ordered. The gate
records row count but does not claim an annual run period; a GL14 campaign must
separately prove the intended annual coverage, monthly completeness, and
required output intervals. This Facility-meter requirement is a Building 59
calibration gate, not a universal definition of EnergyPlus model validity.
Local hashes provide integrity/repeatability evidence, not third-party
authenticity against an operator who can rewrite both outputs and manifests.

A passing smoke gate is `MODEL_SEED_EVIDENCE_ONLY`. It is not a Guideline 14
result.

## 3. Calibration chart pack

Prepare one quality-controlled, already-aligned CSV:

```csv
timestamp,measured,simulated
2019-01-01T00:00:00-08:00,312.5,305.8
2019-01-01T01:00:00-08:00,298.1,301.2
```

For paired average power:

```bash
vibe23 plot-calibration \
  --csv data/processed/aligned_hourly_kw.csv \
  --data-kind mean_power \
  --timezone America/Los_Angeles \
  --unit kW \
  --energy-unit kWh \
  --output-dir reports/calibration/baseline_001/figures
```

For monthly energy records, use `--data-kind interval_energy --unit kWh`. The
publisher writes PNG and SVG versions of:

- a monthly `|NMBE|` / `CV(RMSE)` scorecard against the 5% / 15% gates;
- monthly measured vs EnergyPlus energy;
- monthly percent residuals;
- paired-interval parity;
- load-duration curves;
- weekday/weekend hourly profiles (hourly inputs); and
- weekday/hour residual heatmap (hourly inputs).

For `mean_power`, monthly energy uses elapsed-time left-hold integration and
the final sample uses the median native interval. Inputs with a gap greater
than four times the shortest paired interval fail closed; quality-control and
document gaps before plotting. `--interval-hours` is an explicit constant-width
override and is recorded in the manifest.

It also writes `monthly_comparison.csv` and `chart_manifest.json`, including the
input/artifact hashes, units, timezone, interval semantics, metric values, and
month-completeness audit. The chart manifest always says
`DIAGNOSTIC_ONLY_NOT_A_CALIBRATION_CLAIM`; claim promotion remains the job of
the provenance-bearing calibration scorecard.

## 4. Iteration-progress plot

Each published calibration iteration belongs in an append-only CSV with these
required columns:

`iteration`, `parameter_family`, `nmbe_pct`, `cvrmse_pct`, `complete_months`,
`idf_sha256`, `epw_sha256`, `target_sha256`.

Then publish the progress plot:

```bash
vibe23 plot-calibration-campaign \
  --campaign-log campaigns/calibration_log.csv \
  --output-dir reports/calibration/campaign_progress
```

The figure shows both monthly metrics and their 5%/15% gates, and marks the
first iteration with 12 complete months that meets both numeric thresholds. Its
status is deliberately `NUMERIC_MONTHLY_GATE_MET_PROVISIONAL`, not
`MONTHLY_CALIBRATED`.

Iterate in engineering order: meter scope/time/weather → schedules/calendar →
plug and lighting loads → occupancy/diversity → HVAC availability/setpoints →
envelope constructions/infiltration/thermal mass → ventilation and air-side
controls → fan/coil/RTU/UFT performance → residuals. Construction materials
are a bounded parameter family, not the first universal knob; this avoids using
envelope changes to hide schedule or base-load errors.

## 5. Evidence ladder

| Evidence | Highest supported statement |
| --- | --- |
| Engine preflight only | execution path available |
| Successful hashed run | `MODEL_SEED_EVIDENCE_ONLY` |
| 12 complete paired months + monthly thresholds + provenance | candidate `MONTHLY_CALIBRATED` |
| Hourly thresholds + peak/end-use/zone/control/transient gates | candidate `HOURLY_CALIBRATED` |
| Untuned chronological holdout passes | candidate `VALIDATED_HOLDOUT` |

The Building 59 status stays `CALIBRATION_BOOTSTRAP` until the real data,
runnable IDF, AMY, and required runs exist.
