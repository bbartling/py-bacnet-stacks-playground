# Calibrate campaign + client deliverables

Turnkey path from **bill-aligned AMY** to **ASHRAE G14 scorecard** and a
**client handoff package**. Prefer `docker exec vibe20` (image tip) over host
`pip install -e` — see [`AGENT_DOCKER_WORKSPACE.md`](AGENT_DOCKER_WORKSPACE.md).

## When “calibrated” is allowed

Only after monthly utility compare passes G14 (NMBE ±5%, CV(RMSE) ≤15%) with
honest stamps. Chicago TMY screening is **not** calibration.

Required stamps on every run:

| Stamp | Meaning |
| --- | --- |
| `weather_suitability.mode` | `ACTUAL_YEAR_CALIBRATION` (AMY) vs TMY / substitute |
| `prototype_area_scale` | target ft² / ~10k prototype — never scale kWh×N and call it the building without disclosure |
| `sizing_scenario` | `autosize` / `hard_size` / `hard_size_refused` |
| `g14_scale.mode` | `area_scaled_prototype` when absolute kWh G14 multiplies model by scale |

## CLI — `wattlab calibrate-campaign`

```bash
docker exec -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace vibe20 \
  wattlab calibrate-campaign \
  --bundle /data/uploads/dump/enriched_seed_dir \
  --bills /data/uploads/energy/utility_bills.csv \
  --answers /data/reports/answers.json \
  --lat 42.6 --lon -83.15 \
  --cooling-tons 200 --fan-hp 75   # optional; area-aware W3b
```

What it does:

1. Optional `--answers` merges human fields into null dump `model_seed` (non-null only).
   **lat/lon override city label** for weather pin.
2. Derives `data_window` from bill `YYYY-MM` months (first→last) and **replaces**
   any dump telemetry window (stale `span_hours` kept under `dump_data_window`).
3. Fetches Open-Meteo AMY when `weather_observed.csv` is missing **or** does not
   cover the bill window (off-window dump weather is renamed
   `weather_observed_DUMP_STASH_*.csv`). Needs lat/lon. Stamps `epw_bill_overlap`.
4. Runs `run_calibration` with monthly meters, W2b full-day EPW clip via `simulate`,
   optional hard-size (W3b refuse band).
5. Scores dual-fuel monthly G14 with **multi-year-aware** bare-month join
   (Dec’24–Nov’25 bills → expect `months_compared` ≈ 12, not 1). May apply
   `prototype_area_scale` to modeled kWh (stamped — not site CAD).
6. Publishes `runs/calibrate_<id>/` + `calibration_scorecard.json` +
   `campaign_stamp.json`.
7. Builds client package under `.artifacts/deliverable_calibrate_*`.

Image tip: editable `pip install -e ".[studio]"` so `/app/wattlab` is the only
import tree (no dual `/app` vs site-packages drift).

Honest G14 **fail** with full months compared is a valid screening outcome —
do not claim calibrated ROI. For Lower-48 ESCO $/sf screening bands and when
ROI language is allowed vs forbidden, see
[`ESCO_RETROFIT_COST_ROI.md`](ESCO_RETROFIT_COST_ROI.md).

Dry-run: `--dry-run` prints the plan without Docker.

Also: `wattlab calibrate --bundle …` for an already-seeded dump with
`data_window` + `weather_observed.csv`.

## Twin UI — what humans see

1. **Modeled vs actual fuel** — monthly table + chart; NMBE / CV(RMSE) / pass-fail metrics when a scorecard is present (path or autoload from active run).
2. **Client deliverables** — **Build client package**:
   - Report preview (markdown)
   - Optional client DOCX (checkbox defaults on when `python-docx` is available)
   - Downloads: `.md` · `.xlsx` · `.docx` · full `.zip`
3. Zip layout:

```text
01_Report/Energy_Modeling_Report.md
01_Report/Energy_Modeling_Report.docx  # selected client-rendered report
02_Results/Energy_Model_Results.xlsx + calibration_scorecard.json
03_Models/Baseline/Building_Baseline.idf + Weather.epw + README.md
04_Outputs/Baseline/eplustbl.* eplusout.err …
06_Documentation/package_stamp.json + Assumption_Register.csv
```

ECM page can build the same zip from `studio_report` (screening package).
The DOCX is an energy-modeling deliverable, not the separate
`wattlab controls-checklist --docx` output.

## Ladder reminder (sparse sites)

Do **not** jump straight to G14. Follow
[`SPARSE_BUILDING_PLAYBOOK.md`](SPARSE_BUILDING_PLAYBOOK.md): TMY screening →
constrain plant → schedules → **then** AMY + `calibrate-campaign`. Expect
~8–15 published sims when unknowns are high.

## Bugs / honesty (recent)

| Id | Behavior |
| --- | --- |
| W2b | EPW RunPeriod end = last **full** day (max hour ≥ 23) |
| W3b | Nameplate ÷ `prototype_area_scale` when scale > 1.5; refuse freeze outside [0.25, 4.0] |
| Troy | User label `troy` → climate catalog detroit (not silent Madison) |
| DinD | Image includes Docker **CLI**; sock alone is not enough |
| Host drift | Prefer `docker exec vibe20 wattlab …` |
| ARTIFACTS | No inner `ARTIFACTS` re-import in `run_calibration` (UnboundLocalError) |
| G14 year | Cross-year bill windows join all months in `data_window` |
| Dump wx | Off-window `weather_observed.csv` stashed before Open-Meteo |
| Schedule:File | `/work/in/<csv>` + stage sidecar (not absolute `/data` paths) |
| `--answers` | Merge human answers into null dump seed before campaign |
