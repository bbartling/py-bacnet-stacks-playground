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
  --bundle /data/uploads/dump/wattlab_dump_BUILDING_100.zip \
  --bills /data/uploads/energy/utility_bills.csv \
  --lat 42.6 --lon -83.15 \
  --cooling-tons 200 --fan-hp 75   # optional; area-aware W3b
```

What it does:

1. Derives `data_window` from bill `YYYY-MM` months (first→last).
2. Fetches Open-Meteo AMY when `weather_observed.csv` is missing (needs lat/lon).
3. Runs `run_calibration` with monthly meters, W2b full-day EPW clip via `simulate`,
   optional hard-size (W3b refuse band).
4. Scores dual-fuel monthly G14; may apply `prototype_area_scale` to modeled kWh
   (stamped — not site CAD).
5. Publishes `runs/calibrate_<id>/` + `calibration_scorecard.json` +
   `campaign_stamp.json`.
6. Builds client package under `.artifacts/deliverable_calibrate_*`.

Dry-run: `--dry-run` prints the plan without Docker.

Also: `wattlab calibrate --bundle …` for an already-seeded dump with
`data_window` + `weather_observed.csv`.

## Twin UI — what humans see

1. **Modeled vs actual fuel** — monthly table + chart; NMBE / CV(RMSE) / pass-fail metrics when a scorecard is present (path or autoload from active run).
2. **Client deliverables** — **Build client package**:
   - Report preview (markdown)
   - Downloads: `.md` · `.xlsx` · full `.zip`
3. Zip layout:

```text
01_Report/Energy_Modeling_Report.md
02_Results/Energy_Model_Results.xlsx + calibration_scorecard.json
03_Models/Baseline/Building_Baseline.idf + Weather.epw + README.md
04_Outputs/Baseline/eplustbl.* eplusout.err …
06_Documentation/package_stamp.json + Assumption_Register.csv
```

ECM page can build the same zip from `studio_report` (screening package).

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
