# Agent tools bin (`/data/tools`)

Shared host folder for **campaign scripts** that are not (yet) product CLIs.
Mounted as `$WATTLAB_HOST_WORKSPACE/tools` ↔ `/data/tools` inside vibe19/vibe20.

Prefer packaged WattLab commands when they cover the job:

| Need | Prefer |
| --- | --- |
| Site-scale massing | `wattlab geo-idf` |
| Lights / equip / infil dial | `wattlab dial-loads` |
| Monthly vs bills score | `wattlab score-monthly` |
| Controls FDD checklist + DOCX | `wattlab controls-checklist` |
| Bills → EUI peer bands | `wattlab benchmark` |

Use `/data/tools/<script>.py` for vintage ladders, gas G14 campaigns, stacked
floor IDFs, HWS peeks, dual-fuel G14 scorecards, or one-off site experiments.
Seed themes: [`examples/workspace_tools/`](../../examples/workspace_tools/).
Human workspace copies often live at `~/wattlab_workspace/tools/` (not in git).

**Twin calibrate dial** (short/long gas & elec, monthly shape): envelope first
(WWR / U / ACH), then banded SAT + VAV min-flow; EnergyPlus stays **autosize**.
Playbook: [`TWIN_DIAL_PLAYBOOK.md`](TWIN_DIAL_PLAYBOOK.md) · skill
`skills/wattlab-twin-calibrate-dial/SKILL.md`.

## Layout

```text
$WATTLAB_HOST_WORKSPACE/
  tools/                 # campaign scripts (this bin)
  tools/TWIN_DIAL_PLAYBOOK.md   # optional live workspace copy of dial playbook
  uploads/dump/          # vibe19 wattlab_dump_*.zip
  uploads/prototypes/    # geo / dial IDFs (+ optional best/ freeze)
  reports/controls_checklist/
  reports/utility_bills*.csv
  runs/<id>/             # Twin publish + calibration_scorecard.json
  .artifacts/<campaign>/
```

## Prefer product CLIs, then tools scripts

```bash
docker exec vibe20 wattlab geo-idf …
docker exec vibe20 wattlab dial-loads …
docker exec vibe20 wattlab score-monthly …
docker exec vibe20 wattlab controls-checklist …
```

```bash
docker exec -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace \
  -e ENERGYPLUS_DOCKER_USER=1000:1000 -e PYTHONUNBUFFERED=1 vibe20 \
  python /data/tools/<script>.py --help
```

Do **not** hardcode client site names into new scripts — pass paths/args.

## Script index (typical workspace bin)

Names below match common `/data/tools` campaigns. Your volume may have a subset;
`--help` before inventing flags.

### Controls (vibe19 dump — no EnergyPlus)

| Script | Role |
| --- | --- |
| `controls_service_checklist.py` | Dump zip → VAV / sensor / hunting checklist (prefer `wattlab controls-checklist`) |
| `analyze_hws_reset.py` | Peek dump HWS vs OAT (ad-hoc boiler reset) |

### Geometry / IDF builders

| Script | Role |
| --- | --- |
| `build_stacked_6floor_idf.py` | N× single-zone stacked floors + HVACTemplate VAV + WC plant |
| `build_geo_idf.py` | DOE Large Office → site-scale (prefer `wattlab geo-idf`) |

### Loads / envelope patches

| Script | Role |
| --- | --- |
| `dial_loads_mcp.py` | MCP lights/equip/infil (prefer `wattlab dial-loads`) |
| `patch_reheat_envelope.py` | Seasonal/flat SAT, window U/SHGC, infil, HW SP |
| `apply_doe_vintage_5a.py` | Post-1980 / Pre-1980 climate fabric + infil + LPD + boiler |

### Score / ladders / weather / Twin publish

| Script | Role |
| --- | --- |
| `score_g14_monthly.py` | Monthly G14 NMBE/CVRMSE for **elec and gas** |
| `write_calibration_scorecard.py` | Map `g14_score.json` → Twin `calibration_scorecard.json` (epoch charts need this shape) |
| `save_best_model.py` | Freeze a Twin run → `uploads/prototypes/best/<label>/` (+ optional `--set-current`) |
| `score_b100_monthly.py` | Site annual score vs bills (prefer `wattlab score-monthly`) |
| `compare_open_meteo_bills.py` | Month-align Open-Meteo AMY vs utility bills |
| `run_gas_g14_ladder.py` | patch → DinD sim → G14 → Twin publish + hypothesis |
| `run_vintage_ladder.py` | Vintage IDFs → sim → G14 → Twin publish |

### Publish chain (Studio G14 charts)

```text
sim → score_g14_monthly → write_calibration_scorecard → publish_run_for_studio
→ optional save_best_model.py --set-current
```

Twin G14 epoch / Inspect metrics read `calibration_scorecard.json` (nested
`utility_bills.stats_electricity` / `stats_natural_gas`). A bare `g14_score.json`
or flat `wattlab_report.g14` blob is **not** enough for the charts.

G14 pass = both fuels \|NMBE\|≤5% **and** CVRMSE≤15% when both exist.
Annual % alone ≠ calibrated.

## Controls checklist + false-positive tuning

```bash
docker exec vibe20 wattlab controls-checklist \
  --dump /data/uploads/dump/wattlab_dump_BUILDING.zip \
  --out-dir /data/reports/controls_checklist \
  --docx \
  --fp-tuning-notes /data/reports/controls_checklist/fp_tuning_log.md
```

If unusual/suspect fault counts look epidemic, agents **must** iterate vibe19
FDD (thresholds / gates / role map), re-export, and record before/after notes
in the MD/DOCX **Agent FDD false-positive tuning** section. Skill:
`skills/wattlab-controls-fdd/SKILL.md`.

Checklist JSON is **detection input**. Client Engineering Findings Report is a
separate vibe19 bridge (`app/reporting/` / Overview **Generate Engineering
Findings Report**) — see vibe19 agent spec skill `vibe19-engineering-report`.

## Dial order (learned from live campaigns)

1. **Geometry lock** — stacked floors or honest `geo-idf`; refuse wrong zoning as “done.”
2. **Annual gas short** → WWR ↑, leaky glass U ↑, infil ACH ↑ (not plant tons).
3. **Annual elec short** → LPD / EPD ↑.
4. **Monthly gas shape** (annual flat, CVRMSE fails) → banded SAT + VAV min-flow + OA hours; read vibe19 DAT first.
5. **Scorecard + publish** — stamp dial knobs on `dial_meta.json` / `run_manifest.json`.

Details: [`TWIN_DIAL_PLAYBOOK.md`](TWIN_DIAL_PLAYBOOK.md).

See also: [`AGENT_DOCKER_WORKSPACE.md`](AGENT_DOCKER_WORKSPACE.md),
[`TWIN_LOOP.md`](TWIN_LOOP.md), [`ESCO_RETROFIT_COST_ROI.md`](ESCO_RETROFIT_COST_ROI.md).
