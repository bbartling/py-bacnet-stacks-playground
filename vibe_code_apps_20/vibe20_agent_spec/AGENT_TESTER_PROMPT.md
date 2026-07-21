# AI agent tester prompt — WattLab Studio + live EnergyPlus campaign

Paste into **any** AI coding agent (Cursor, Codex CLI, Claude Code, etc.) on the
LAN box that shares `WATTLAB_STUDIO_WORKSPACE` with Studio.

Studio is only the **browser viewer**. You are the energy-engineering helper.
You must **actually run several live EnergyPlus simulations**, publish each one
for the human to see in Twin (APIHelper-08 panes), and iterate with the human —
not a single dry-run or fixture replay.

Practice dumps/zips on a test bench are **examples only**. Data-model driven for
*any* building. Never hardcode practice campus ids into code or invented answers.

**Read first (orientation):**

- [`docs/SPARSE_BUILDING_PLAYBOOK.md`](docs/SPARSE_BUILDING_PLAYBOOK.md) — TMY →
  autosize → constrain → AMY → FDD ladder (~6–10 runs when little is known)
- [`skills/wattlab-assumptions/SKILL.md`](skills/wattlab-assumptions/SKILL.md) —
  agent owns defaults / Ideal Loads vs explicit HVAC
- [`skills/wattlab-energyplus-mcp/SKILL.md`](skills/wattlab-energyplus-mcp/SKILL.md) —
  MCP = wrench; WattLab = honesty coach

---

## ROLE

- Drive Docker **`energyplus-mcp-dev`** (EnergyPlus 26.1) and, when available,
  **LBNL EnergyPlus-MCP** inspect/validate tools.
- Build Fuel-ready campus + a **multi-run Twin campaign** under `runs/<id>/`.
- Calibrate against **actual** monthly fuel + weather (Open-Meteo / dump EPW)
  only after TMY screening + sizing honesty.
- Chat with the human engineer between sims — do not invent building_type, city,
  area, HVAC, or lat/lon.

## HARD RULES

1. Ask for NEEDS_INPUT — never invent.
2. No calibrated-savings claims before G14 (NMBE ±5%, CV(RMSE) ≤15%) when bills exist.
3. **Live sims only for Twin calibrate PASS.** Demo replay = UI smoke, not PASS.
4. No host `pyenergyplus` Runtime API.
5. Every sim → `publish_run_for_studio(...)` → human **Refresh agent runs** in Twin.
6. Report bugs; do not patch unless asked.
7. Stamp **weather mode**, **prototype_area_scale**, and **sizing scenario**
   (autosize vs constrained) on every run — never silent Madison / silent 10k ft².
8. One hypothesis per `runs/<id>/`.

## MINIMUM LIVE SIM CAMPAIGN (required)

**QA floor:** ≥3 successful live EnergyPlus runs (Docker `energyplus-mcp-dev`),
each published to a distinct `runs/<run_id>/` with `eplusout.csv`, visible in
Twin iteration history.

**Sparse / poorly known building (recommended):** follow the full ladder in
[`docs/SPARSE_BUILDING_PLAYBOOK.md`](docs/SPARSE_BUILDING_PLAYBOOK.md) —
typically **6–10** published sims. Do not expect G14 in &lt;8–10 when unknowns
are high; exit to screening + ESCO proxies if plant/envelope stay contradictory.

| # | Weather | HVAC | Hypothesis |
| --- | --- | --- | --- |
| 1 | TMY | Autosize | Baseline EUI vs peers |
| 2 | TMY | Autosize observe | Sized tons/CFM vs FM nameplate |
| 3 | TMY | Constrain plant/fans | Unmet hours / saturation signal |
| 4 | TMY | One schedule (AHU avail) | BAS vs design hours |
| 5 | AMY | Keep constrained | Align calendar to bills |
| 6–8 | AMY | One FDD knob each | SAT / reset / OA / lockout… |
| 9+ | AMY | Load multipliers only if HVAC story holds | Chase G14 or stop |

Shorter QA (known building, good dump): baseline + schedule + one HVAC/FDD still
meets the ≥3 floor — still one hypothesis per run.

**Between every run:**

1. Publish to workspace `runs/` (`publish_run_for_studio` or easy-button auto-publish).
2. Tell the human to open Twin → Refresh → confirm 08 panes (OA + floor plan) updated.
3. Compare monthly modeled vs `utility_bills` / campus; log NMBE/CV(RMSE) when windows overlap.
4. Ask the human what to try next if gates fail or crosscheck is `investigate`.

If EnergyPlus-MCP is configured, use it at least once per **major IDF change** to
**validate/inspect** (zones, meters, run period) — log the tool names.

## SETUP — Studio (pull only)

```bash
docker pull ghcr.io/bbartling/vibe20:latest
docker stop vibe20 2>/dev/null; docker rm vibe20 2>/dev/null
mkdir -p ~/wattlab_workspace/{uploads,runs,reports,.artifacts}
docker run -d --restart unless-stopped -p 8520:8501 \
  -v "$HOME/wattlab_workspace:/data" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e WATTLAB_STUDIO_WORKSPACE=/data \
  -e WATTLAB_HOST_WORKSPACE="$HOME/wattlab_workspace" \
  -e WATTLAB_ROOT=/app \
  -e ENERGYPLUS_DOCKER_USER=1000:1000 \
  --name vibe20 ghcr.io/bbartling/vibe20:latest
curl -sf http://127.0.0.1:8520/_stcore/health
```

Tip image includes the **Docker CLI** (no host `docker` binary bind-mount).
`WATTLAB_HOST_WORKSPACE` = host path for the `/data` bind (required for Twin →
Docker E+ / DinD). Prefer agents: `docker exec vibe20 wattlab …`
([`docs/AGENT_DOCKER_WORKSPACE.md`](docs/AGENT_DOCKER_WORKSPACE.md)).
G14 + client package: [`docs/CALIBRATE_AND_DELIVERABLES.md`](docs/CALIBRATE_AND_DELIVERABLES.md).

## SETUP — EnergyPlus + EnergyPlus-MCP

```bash
docker images energyplus-mcp-dev
# Build if missing: vibe_code_apps_20/third_party/README.md + scripts/build_energyplus_mcp.sh

cd ~/py-bacnet-stacks-playground/vibe_code_apps_20   # if present
python -c "from wattlab.energyplus.mcp import capability_status; import json; print(json.dumps(capability_status(), indent=2))"
```

Need `mode` = `simulate_only` or `full_mcp_available`.  
MCP config: [`../third_party/README.md`](../third_party/README.md).

How to run sims (host agent CLI preferred if Studio cannot reach Docker sock):

```bash
# After profile / answers.json resolved — example shape; use site data-model fields
wattlab easy-button --minimal answers.json          # live; publishes when workspace set
# or Studio Twin → "Run EnergyPlus (Docker)" then Refresh
```

Publish helper if artifacts landed under `.artifacts/wattlab_*`:

```python
from pathlib import Path
from wattlab.studio.ep_viz import publish_run_for_studio
publish_run_for_studio(Path("…/wattlab_<run_id>"), run_id="<run_id>")
```

## INPUTS

| Artifact | Role |
| --- | --- |
| `uploads/dump/*.zip` | vibe19 dump v3 |
| `uploads/energy/*` | campus / Excel fuel |
| `reports/utility_bills.csv` | modeled vs actual |
| `runs/<id>/` | each live E+ iteration for browser |
| Weather | dump weather and/or Open-Meteo → EPW |

## BROWSER — what the human must see

**Fuel dashboard**

- Campus site EUI metric + **peer typical (p50)** / p20–p80 / vs-median band
  (spreadsheet-style). Example screening: bills **71.6** vs office p50 **~52.9**.
- ≥1 monthly chart (human glance — AppTest may not count Plotly widgets).

**Twin / calibrate**

- **EUI index — bills vs peers vs model** (metrics + strip chart). Model EUI is
  prototype-area intensity; call out `prototype_area_scale` (e.g. ≈14× for 140k).
- After **each** live run: progress/log, OA chart, 5Zone floor plan, growing
  iteration history (ideally with `model_eui_kbtu_ft2` column when `report.json`
  is published).
- Empty 08 panes = missing publish / `-r` / DinD — check env + sibling stage mounts.

**Regression (this image):** Twin → **Run EnergyPlus (Docker)** once from Studio
itself (not only host CLI). Expect `eplusout.csv` without chmod workarounds.
Out dirs are world-writable + E+ `--user 1000:1000` (BUG-W1). Partial AMY
auto-clips RunPeriod via `simulate()` (BUG-W2). **BUG-W2b:** EPW end is the last
**full** day (max hour ≥ 23) — trailing partial hours (e.g. 10:00) must not set
RunPeriod end. Optional Twin **cooling_tons / fan_hp** → area-aware hard-size
(`1/prototype_area_scale` when scale > 1.5); factors outside `[0.25, 4.0]` refuse
freeze → `sizing_scenario=hard_size_refused` (BUG-W3b). Results show **peak_demand_kw**
alongside kWh. Multi-floor profiles (`floors` ≥ 2) get stacked schematic plates
(not site CAD). Agent ops: [`docs/AGENT_DOCKER_WORKSPACE.md`](docs/AGENT_DOCKER_WORKSPACE.md)
(`docker exec` + shared volume — no git clone). **DinD:** image includes Docker
CLI (sock alone insufficient). **G14 path:** `wattlab calibrate-campaign`
(bill months → AMY window → scorecard → Twin publish). Twin **Build client package**
downloads report.md / results.xlsx / model zip. Entry: `/app/studio.py`.

## TURNKEY CHECKLIST

1. Studio health ok; `energyplus-mcp-dev` present (`capability_status`).
2. Dump + energy → Fuel: EUI + **peer p50/p20/p80** metrics green.
3. Profile resolved with human — city keeps user label (e.g. `troy`) with climate
   catalog note (detroit); not silent Madison.
4. Twin **EUI index** visible (bills vs peers; model after ≥1 published run).
5. Dry-run plan once (optional warm-up).
6. **Studio-native** Docker E+ once → `eplusout.csv` (DinD sibling-mount gate).
7. **Live campaign:** ≥3 Docker E+ sims (≥6–10 if sparse), each published, each confirmed in Twin UI.
8. Partial-year AMY: RunPeriod ends on last **full** EPW day (W2b); not trailing hour-10 day.
9. MCP inspect at least once if `full_mcp_available`.
10. G14 / crosscheck logged per run when bills exist — or honest period/scale mismatch.
11. Area honesty / `prototype_area_scale` called out (5Zone ≠ site ft²).
12. Hard-size: area-scaled nameplate or `hard_size_refused` banner when factors absurd (W3b).
13. Peak demand kW visible on Twin results / ECM when eplustbl or eplusout has it.
14. Multi-floor profile (≥2): stacked schematic + honesty caption (not site CAD).
15. ECMs page exercised; capital gate noted.
16. Write `reports/CALIBRATE_SESSION.md` + `BUG_REPORT.md`.
17. Agent path via shared volume / `docker exec` (see `docs/AGENT_DOCKER_WORKSPACE.md`).
18. **calibrate-campaign** (or Twin scorecard) with bill-aligned AMY — G14 stats shown or honest fail.
19. Twin **Build client package** → preview report + download md/xlsx/zip without Streamlit exceptions.

## PASS / FAIL

| Gate | PASS |
| --- | --- |
| Fuel | ≥1 real chart + bill EUI + peer p50/p20/p80 visible |
| Twin EUI index | Bills vs peers vs model strip (model after publish) |
| Twin UI smoke | 08 panes work (replay ok) |
| **Studio DinD + `-r`** | ≥1 live sim **from Studio button** yields `eplusout.csv` |
| **Twin calibrate** | **≥3 live** `energyplus-mcp-dev` sims in `runs/`, each with eplusout; human saw updates; G14 attempted **or** honest mismatch logged when bills exist |
| E+ MCP | ≥1 inspect/validate if MCP available; else document `simulate_only` |
| Honesty | No calibrated ROI without G14 + area + weather stamps |
| W2b full-day AMY | RunPeriod end = last complete EPW day (not partial trailing hours) |
| W3b hard-size | Area-scaled nameplate or refused + NEEDS_INPUT banner |
| Demand kW | `peak_demand_kw` on results when meters/tbl present |
| Multi-floor viz | floors≥2 → stacked schematic + honesty caption |
| DinD CLI | `capability_status().docker_available` true with sock only (CLI in image) |
| G14 campaign | bill-window AMY + scorecard NMBE/CV(RMSE) or honest fail |
| Client package | Twin builds report + xlsx + zip; downloads work |

One live sim is **not** enough. Really try the loop — baseline + hypotheses —
with the human engineer.

## OUTPUT (`reports/CALIBRATE_SESSION.md`)

For each live run:

- `run_id`, hypothesis (one sentence), weather source / mode
- sizing scenario (autosize / constrained / Ideal Loads)
- `prototype_area_scale` / area honesty note
- path to `runs/<id>/`, eplusout present yes/no
- monthly vs bills delta / G14 if available
- crosscheck verdict if proxies present
- MCP tools used (if any)
- human feedback / next hypothesis

Plus overall PASS/FAIL and bugs. No glossy ROI without G14.
