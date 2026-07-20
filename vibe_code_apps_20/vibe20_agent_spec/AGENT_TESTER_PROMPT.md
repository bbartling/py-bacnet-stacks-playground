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
  --name vibe20 ghcr.io/bbartling/vibe20:latest
curl -sf http://127.0.0.1:8520/_stcore/health
```

`WATTLAB_HOST_WORKSPACE` = host path for the `/data` bind (required for Twin →
Docker E+ / DinD). Artifacts land under `/data/.artifacts`. Sims use `-r` so
`eplusout.csv` appears for Twin panes. Stage mounts are **siblings** of the
output dir (`…/sim__stage_in` + `…/sim`), never nested `_stage_in` under out.

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

After **each** live run: progress/log, OA chart, 5Zone floor plan,
and a growing iteration history. Empty panes = you did not publish (or missing
`-r` / DinD path — check `WATTLAB_HOST_WORKSPACE`).

## TURNKEY CHECKLIST

1. Studio health ok; `energyplus-mcp-dev` present (`capability_status`).
2. Dump + energy → Fuel charts green.
3. Profile resolved with human (city provenance not Madison-leaked).
4. Dry-run plan once (optional warm-up).
5. **Live campaign:** ≥3 Docker E+ sims (≥6–10 if sparse), each published, each confirmed in Twin UI.
6. MCP inspect at least once if `full_mcp_available`.
7. G14 / crosscheck logged per run when bills exist — or honest period/scale mismatch.
8. Area honesty / `prototype_area_scale` called out (5Zone ≠ site ft²).
9. ECMs page exercised; capital gate noted.
10. Write `reports/CALIBRATE_SESSION.md` + `BUG_REPORT.md`.

## PASS / FAIL

| Gate | PASS |
| --- | --- |
| Fuel | ≥1 real chart |
| Twin UI smoke | 08 panes work (replay ok) |
| **Twin calibrate** | **≥3 live** `energyplus-mcp-dev` sims in `runs/`, each with eplusout; human saw updates; G14 attempted **or** honest mismatch logged when bills exist |
| E+ MCP | ≥1 inspect/validate if MCP available; else document `simulate_only` |
| Honesty | No calibrated ROI without G14 + area + weather stamps |

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
