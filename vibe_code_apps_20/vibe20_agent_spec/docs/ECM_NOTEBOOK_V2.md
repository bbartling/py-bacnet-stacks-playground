# ECM Notebook v2 — polished G36 3-ECM workbook

**Audience:** Cursor / product agents building WattLab ECM Excel notebooks.

**Privacy (hard rule):**
- Never commit `calculators.zip`, client workbooks, client names, or bill CSVs to git / GH.
- Proprietary calculator reference lives at `wattlab_workspace/private/reference/` — **gitignored**.
- Product math is WattLab-owned (`Calc_DSP` / `Calc_SAT` / `Calc_Lockout`) — DP-pump style Inputs | Derived | Notes.

## Primary package

| Id | File | Measures |
|----|------|----------|
| `g36_airside_controls` | `01_G36_DSP_SAT_chiller_lockout.xlsx` | DSP reset, SAT reset, chiller lockout &lt;60°F |

Aliases `controls_first` / `schedules_economizer` resolve to the same workbook.

## Sheet order (engineer → report)

1. **Baseline** — Twin G14 + yellow rates + package `$/ft²` controls + VAV/TAB mechanical
2. **Crosscheck** — ESCO vs Twin `vs_baseline` (primary engineer eval)
3. **Charts** — formula-linked to Crosscheck (report face)
4. **Calc_DSP** / **Calc_SAT** / **Calc_Lockout** — live Excel affinity / plant formulas
5. **Calc_Cost** — package cost; payback/NPV **n/a** when annual $ ≤ 0
6. **Twin_Measures** — independent EnergyPlus deltas
7. Guardrails / Docs

## Savings definition

| Layer | Meaning |
|-------|---------|
| Baseline | G14-calibrated Twin annual |
| Calc_* | WattLab ESCO-style spreadsheet formulas |
| Twin_Measures | `baseline − ECM-on-Twin` (`vs_baseline` only — never progressive) |
| Crosscheck | Calc_* vs Twin |

## Rebuild

```bash
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data vibe20 \
  python /data/tools/agent_build_ecm_packages.py \
    --answers /data/reports/answers_building_100_geo.json \
    --prefix geo_b100 \
    --packages g36_airside_controls,plant_optimization,envelope_code \
    --fan-hp 80 --write-scenario

docker exec vibe20 wattlab notebook cascade-from-twin \
  --twin-run /data/runs/geo_b100_6stack_shape_r56_sched_mild \
  --package g36_airside_controls \
  --answers /data/reports/answers_building_100_geo.json
```

### One-command cascade (BUG-063)

`agent_build_ecm_packages.py` can run the EnergyPlus cascade for you so the
Crosscheck sheet gets real `Twin_Measures` (`vs_baseline`) instead of an
ESCO-only screen:

| Flag | Behavior |
|------|----------|
| *(none)* | ESCO-only build. Always succeeds; `Crosscheck` shows `ESCO_ONLY_NO_EP`. |
| `--cascade` | Force the E+ measure cascade first. Requires `/var/run/docker.sock` and the `energyplus-mcp-dev` image. |
| `--cascade-if-ready` | Run the cascade **only if** `/var/run/docker.sock` exists **and** `docker image inspect energyplus-mcp-dev` succeeds; otherwise print a clear skip reason and continue ESCO-only with the honesty stamp. **Never fails the build.** |

```bash
# Cascade automatically when the environment is ready, else fall back cleanly:
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data vibe20 \
  python /data/tools/agent_build_ecm_packages.py \
    --answers /data/reports/answers_building_100_geo.json \
    --prefix geo_b100 \
    --packages g36_airside_controls,plant_optimization,envelope_code \
    --fan-hp 80 --write-scenario \
    --cascade-if-ready
```

The JSON summary reports `cascade_mode` (`off` / `if_ready` / `forced`),
`cascade_requested`, and `cascade_skip_reason` so agents can see whether the
Compare numbers are twin-backed or ESCO-only. A build is never blocked on the
cascade — a missing image just downgrades to an honest ESCO-only screen.

## Fable gates

1. Only three measures in the G36 workbook.
2. Crosscheck first after Baseline; Charts linked to Crosscheck.
3. Calc_Cost never invents ROI on zero/negative annual $.
4. Twin uses `vs_baseline` only.
5. Proprietary zip never in `git status`.
