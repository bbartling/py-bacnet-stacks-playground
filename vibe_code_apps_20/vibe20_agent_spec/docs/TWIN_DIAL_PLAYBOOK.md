# Twin dial playbook (EnergyPlus × utility bills)

Living playbook for agents dialing WattLab Studio twins. **Start here (short):**
[`AGENT_CONTEXT.md`](AGENT_CONTEXT.md). Skills:
[`wattlab-twin-calibrate-dial`](../skills/wattlab-twin-calibrate-dial/SKILL.md),
[`wattlab-assumptions`](../skills/wattlab-assumptions/SKILL.md) (§ Short/long fuel).
Tools bin context: [`AGENT_TOOLS.md`](AGENT_TOOLS.md).

Practice campus trajectories (Liberty-style stacked towers) are **labeled
rehearsal evidence** — pass paths/args for any building; never bake site ids
into product defaults.

## Autosize note

Stacked HVACTemplate → ExpandObjects twins use **`autosize`** on coils, fans,
boilers, chillers, and terminal flows. Dialing is **not** about picking tons —
it is envelope / infiltration / internal gains / **as-operated SAT & VAV mins**.

## Ordered phases

### 0. Geometry + weather + bills

- Confirm the twin geometry the human expects (e.g. stacked `Floor_1`…`Floor_N`,
  one zone/floor — **not** DOE mid×4 perimeter-core when they want floor massing).
- AMY EPW overlapping bill months (not TMY screening for G14).
- Bills: correct CSV (shared elec allocation + **that building’s** gas — never
  double-half).
- Builders: `wattlab geo-idf` or `/data/tools/build_stacked_*_idf.py` →
  ExpandObjects → `run_energyplus`.

### 1. Annual gas short → envelope first

| Step | Knob | Typical direction |
| --- | --- | --- |
| 1 | WWR ↑ | toward site curtain-wall reality (often 0.70–0.75) |
| 2 | Window U (leaky) | toward **U-0.80–1.0 IP** (~4.5–5.7 SI), not pretty DOE glass |
| 3 | Infiltration ACH ↑ | ladder until annual gas ~flat |
| 4 | Stop | when \|gas ann\| ≤ ~5% or overshoots |

Do **not** start with plant oversizing when gas is short.

### 2. Annual elec short → plugs/lights

- Raise EPD / LPD (W/m²). Prefer this over random chiller oversizing.
- Hold LPD/EPD steady while chasing gas **shape** once annual elec is near gate.

### 3. Monthly gas shape (CVRMSE) — after annual ~flat

Classic failure: winter/shoulder gas high, summer gas low (annual cancels).

1. Read vibe19 **AHU discharge-air-temp / SP** by month (fan-on) before inventing SAT.
2. Seasonal / **banded** cooling SAT (summer dump often ~50°F where dump shows it;
   winter warmer).
3. **Scheduled VAV min-flow** (higher true summer, lower winter/shoulder).
4. Shorter **winter OA** hours to cut Dec/Jan without killing summer reheat.
5. Soft summer HW OA-reset only if late summer still overshoots with cold dump.

**Trap:** Long cold-dump window (e.g. Apr–Oct @ 50°F) + high constant min-flow →
shoulder months gas +100%+. Cold-dump **peak summer only**; keep shoulders warmer.

**Trap:** Bills may not track HDD (Feb bill ≫ Jan HDD; Oct bill tiny vs HDD).
Residual CVRMSE ~25–30% can remain after honest HVAC banding — **document it**;
do not invent physics to force a 15% CV. Prefer **OA-hours / ops** over more glass
when bills ≠ HDD.

### 4. Monthly elec shape (CVRMSE) — after gas near/pass

Gas shape before elec shape. Once gas is near/pass:

1. Prefer **month-aware light / equipment schedules** (seasonal Schedule:Compact)
   over blunt annual LPD/EPD cuts.
2. Flat annual LPD cuts often trade winter/summer months and can **break a hard-won
   gas pass**.
3. Use Twin monthly ±% chart (over/under by month) to see which seasons elec is wrong.

### 5. Score + publish

```bash
# inside vibe20 (paths are examples)
python /data/tools/score_g14_monthly.py --eplusout … --bills …
python /data/tools/write_calibration_scorecard.py   # Twin G14 charts need this
# publish_run_for_studio / save_best_model.py --set-current
```

Prefer `wattlab score-monthly` when it covers the job; use tools scripts for
dual-fuel ladders and scorecard shape mapping.

G14 pass = \|NMBE\|≤5% **and** CVRMSE≤15% on **both** fuels when both exist.
Stamp WWR / U / ACH / SAT bands / min-flow / OA / hypothesis on
`dial_meta.json` + `run_manifest.json`.

## Studio UX (agent awareness)

- Twin iteration history: chronological **run #** matching G14 epoch chart.
- Inspect: dial/hypothesis knobs table + monthly % off + elec/gas overlays +
  **monthly ±% dial chart** (over/under by month; optional dial-attempt history).
- ECMs: default baseline = best G14 run (`pick_best_g14_run`); human override OK.
- Fuel Weather: reuse Open-Meteo hourly cache for Demand cooling-season avg high.

## Workspace pointers

| Path | Role |
| --- | --- |
| `/data/tools/` | Campaign scripts ([`AGENT_TOOLS.md`](AGENT_TOOLS.md)) |
| `/data/tools/AGENT_CONTEXT.md` | Optional live copy of primary handoff |
| `/data/tools/TWIN_DIAL_PLAYBOOK.md` | Optional live copy of this playbook |
| `/data/reports/CALIBRATE_SESSION.md` | Session narrative (human/agent append) |
| `/data/runs/CURRENT_RUN.txt` | Preferred Twin publish |
| `vibe20_agent_spec/skills/wattlab-twin-calibrate-dial/` | Cursor/agent skill |
