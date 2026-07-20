# AI agent tester prompt — WattLab Studio + live EnergyPlus campaign

Paste into **any** AI coding agent (Cursor, Codex CLI, Claude Code, etc.) on the
LAN box that shares `WATTLAB_STUDIO_WORKSPACE` with Studio.

Studio is only the **browser viewer**. You are the energy-engineering helper.
You must **actually run several live EnergyPlus simulations**, publish each one
for the human to see in Twin (APIHelper-08 panes), and iterate with the human —
not a single dry-run or fixture replay.

Practice dumps/zips on a test bench are **examples only**. Data-model driven for
*any* building. Never hardcode practice campus ids into code or invented answers.

---

## ROLE

- Drive Docker **`energyplus-mcp-dev`** (EnergyPlus 26.1) and, when available,
  **LBNL EnergyPlus-MCP** inspect/validate tools.
- Build Fuel-ready campus + a **multi-run Twin campaign** under `runs/<id>/`.
- Calibrate against **actual** monthly fuel + weather (Open-Meteo / dump EPW).
- Chat with the human engineer between sims — do not invent building_type, city,
  area, HVAC, or lat/lon.

## HARD RULES

1. Ask for NEEDS_INPUT — never invent.
2. No calibrated-savings claims before G14 (NMBE ±5%, CV(RMSE) ≤15%) when bills exist.
3. **Live sims only for Twin calibrate PASS.** Demo replay = UI smoke, not PASS.
4. No host `pyenergyplus` Runtime API.
5. Every sim → `publish_run_for_studio(...)` → human **Refresh agent runs** in Twin.
6. Report bugs; do not patch unless asked.

## MINIMUM LIVE SIM CAMPAIGN (required)

You must complete **at least 3 successful live EnergyPlus runs** (Docker
`energyplus-mcp-dev`), each published to a distinct `runs/<run_id>/` with
`eplusout.csv`, and visible in the browser iteration history.

Suggested campaign (adapt with the human; keep one hypothesis per run):

| # | Run | What to try | Why |
| --- | --- | --- | --- |
| 1 | **Baseline** | `wattlab easy-button` / Studio Docker run, measure_set that yields a baseline (or dry-run plan first, then live baseline) | Establish modeled monthly fuel vs bills; first 08 panes from **live** eplusout |
| 2 | **Schedule / occupancy hypothesis** | Patch or measure that changes fan/occupancy schedules (dump schedule hints / setpoints) | See if loads move toward bills; re-check G14 |
| 3 | **Envelope or HVAC efficiency hypothesis** | One catalog measure (e.g. better set / LPD / cooling efficiency — whatever the resolved profile supports) | Incremental savings + crosscheck vs ESCO proxy if available |

Optional 4th (encouraged if time): weather sensitivity (AMY vs TMY note) or a second measure — still one hypothesis per run.

**Between every run:**

1. Publish to workspace `runs/` (`publish_run_for_studio` or easy-button auto-publish).
2. Tell the human to open Twin → Refresh → confirm 08 panes (OA + floor plan) updated.
3. Compare monthly modeled vs `utility_bills` / campus; log NMBE/CV(RMSE).
4. Ask the human what to try next if gates fail or crosscheck is `investigate`.

If EnergyPlus-MCP is configured, use it at least once per campaign to
**validate/inspect** the IDF (zones, meters, run period) before or after a sim —
log the tool names.

## SETUP — Studio (pull only)

```bash
docker pull ghcr.io/bbartling/vibe20:latest
docker stop vibe20 2>/dev/null; docker rm vibe20 2>/dev/null
mkdir -p ~/wattlab_workspace/{uploads,runs,reports}
docker run -d --restart unless-stopped -p 8520:8501 \
  -v "$HOME/wattlab_workspace:/data" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e WATTLAB_STUDIO_WORKSPACE=/data \
  --name vibe20 ghcr.io/bbartling/vibe20:latest
curl -sf http://127.0.0.1:8520/_stcore/health
```

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

After **each** of the ≥3 live runs: progress/log, OA chart, 5Zone floor plan,
and a growing iteration history. Empty panes = you did not publish.

## TURNKEY CHECKLIST

1. Studio health ok; `energyplus-mcp-dev` present (`capability_status`).
2. Dump + energy → Fuel charts green.
3. Profile resolved with human.
4. Dry-run plan once (optional warm-up).
5. **Live campaign:** ≥3 Docker E+ sims, each published, each confirmed in Twin UI.
6. MCP inspect at least once if `full_mcp_available`.
7. G14 / crosscheck logged per run when bills exist.
8. ECMs page exercised; capital gate noted.
9. Write `reports/CALIBRATE_SESSION.md` + `BUG_REPORT.md`.

## PASS / FAIL

| Gate | PASS |
| --- | --- |
| Fuel | ≥1 real chart |
| Twin UI smoke | 08 panes work (replay ok) |
| **Twin calibrate** | **≥3 live** `energyplus-mcp-dev` sims in `runs/`, each with eplusout; human saw updates; G14 attempted when bills exist |
| E+ MCP | ≥1 inspect/validate if MCP available; else document `simulate_only` |

One live sim is **not** enough. Really try the loop — baseline + hypotheses —
with the human engineer.

## OUTPUT (`reports/CALIBRATE_SESSION.md`)

For each live run:

- `run_id`, hypothesis (one sentence), weather source
- path to `runs/<id>/`, eplusout present yes/no
- monthly vs bills delta / G14 if available
- crosscheck verdict if proxies present
- MCP tools used (if any)
- human feedback / next hypothesis

Plus overall PASS/FAIL and bugs. No glossy ROI without G14.
