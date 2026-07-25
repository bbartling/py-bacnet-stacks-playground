# Agent Docker workspace (vibe19 + vibe20)

Agents use the **running containers** and a **shared host volume** — not a git
clone of this repo on the agent machine. Studio (browser) is the human viewer;
CLI/`docker exec` is the agent surface for this cycle.

Both vibe19 and vibe20 are **native Streamlit apps** (not FastAPI/Flask shells
that embed Streamlit). Optional future: a thin HTTP wrapper around the **same**
workspace contract — that is **not** the current product UI.

## Shared volume layout

On the host (bensbench-style):

```text
$WATTLAB_HOST_WORKSPACE/          # e.g. $HOME/wattlab_workspace
  uploads/                        # WattLab dump zips from vibe19
  runs/                           # published Twin iterations (eplusout.csv, reports)
  reports/                        # CALIBRATE_SESSION.md, capital plans, …
  tools/                          # campaign scripts (/data/tools) — see AGENT_TOOLS.md
  .artifacts/                     # DinD EnergyPlus stage/out (container-managed)
```

Containers typically mount:

| Container | Host path | Container path | Notes |
|-----------|-----------|----------------|-------|
| `vibe19`  | `$HOME/wattlab_workspace` | `/data` (or app workspace) | Export dump zip here |
| `vibe20`  | `$HOME/wattlab_workspace` | `/data` | `WATTLAB_STUDIO_WORKSPACE=/data` |
| both      | `/var/run/docker.sock` | same | DinD EnergyPlus (`energyplus-mcp-dev`) |

vibe20 also needs `WATTLAB_HOST_WORKSPACE` set to the **host** path (sibling
mounts for DinD) and preferably `ENERGYPLUS_DOCKER_USER=1000:1000`.

The vibe20 image ships a **Docker CLI client** (sock alone is not enough). Prefer:

```bash
docker run … \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e WATTLAB_HOST_WORKSPACE="$HOME/wattlab_workspace" \
  -e ENERGYPLUS_DOCKER_USER=1000:1000 \
  ghcr.io/bbartling/vibe20:latest
```

Do **not** rely on host `pip install -e` wattlab — prefer `docker exec vibe20 wattlab …`
so agents match the Studio image (avoids host package drift). If the host git
checkout is on a deleted branch or behind tip, ignore it — use `/app` docs inside
the container and the tip image revision label.

## Uploads path gotchas (Docker GHCR)

Studio process workspace is usually **`/data`** (`WATTLAB_STUDIO_WORKSPACE`).
Cwd is often `/app`. Relative path-box inputs must resolve under `/data`
(fixed BUG-001). Prefer the **file picker**.

| Input | Works? |
| --- | --- |
| File picker → `wattlab_dump_*.zip` | Yes (recommended) |
| `uploads/dump/<file>.zip` | Yes (joins `/data`) |
| `/data/uploads/dump/<file>.zip` | Yes |
| `/home/ben/…` host path | No — not mounted |
| `openfdd_package_v1` / raw OpenFDD zip | No — need vibe19 **WattLab dump** v2/v3 |

Listed dumps appear as absolute `/data/uploads/dump/…` chips on Uploads
(BUG-002). Schema mismatch for OpenFDD packages raises a clear error (BUG-003).

Session log / bug index often lives on the volume as `reports/BUG_REPORT.md`
and `reports/CALIBRATE_SESSION.md` (not always in git).

## Twin dial playbook (short/long fuel)

Envelope first (WWR / leaky glass U / ACH), then LPD/EPD for elec, then banded
SAT + VAV min-flow for monthly gas shape. Autosize plant stays.
See [`TWIN_DIAL_PLAYBOOK.md`](TWIN_DIAL_PLAYBOOK.md),
[`AGENT_TOOLS.md`](AGENT_TOOLS.md), skill `wattlab-twin-calibrate-dial`.

## Schedule:File + DinD (BUG-W-SCHEDULE-FILE-DIND)

EnergyPlus only mounts `__stage_in` → `/work/in` and the out dir → `/work/out`.
`apply_weather_schedule_file` writes File Name as **`/work/in/<basename>`** and
copies the CSV beside the IDF; `run_energyplus` stages that CSV into `__stage_in`.
Do **not** point Schedule:File at absolute `/data/...` host paths (FATAL file not found).

Helpers: `wattlab.existing_building.schedules` + `wattlab.energyplus.patches.weather_schedules`.

## Site-scale geometry + EnergyPlus MCP (required)

Agents use the **same stack as a human in production**:

```bash
wattlab energyplus-ensure   # clone pin → /data/third_party/EnergyPlus-MCP + build energyplus-mcp-dev
# capability_status()["capability"] must be "ready"
```

- **Annual sims:** WattLab DinD (`run_energyplus`)
- **IDF surgery:** `wattlab dial-loads` / `wattlab mcp-exec -- …` (docker `energyplus-mcp-dev`)

```bash
# Host paths via WATTLAB_HOST_WORKSPACE; tip agents prefer workspace vendor
wattlab mcp-exec -- python -c "import energyplus_mcp_server; print('ok')"
wattlab dial-loads --src /data/uploads/prototypes/geo.idf --dst /data/uploads/prototypes/dialed.idf \
  --lights 4.5 --equip 4.2 --infil-mult 1.4
```

Geometry ladder (any building; CLI args — not site-hardcoded):
`wattlab geo-idf --stories … --wwr … --target-area-ft2 …` → `custom_idf` + `area_scale=1`
→ DinD → `wattlab score-monthly`. Skip vendor `validate_idf` if eppy MSequence errors.

Practice example (Liberty B100 rehearsal only): see campaign notes / `examples/liberty` —
do not reuse B100/B50 numbers as silent defaults.

## G14 calibrate campaign (bill months → Twin)

```bash
docker exec -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace vibe20 \
  wattlab calibrate-campaign \
  --bundle /data/reports/calibrate_seed_dir \
  --bills /data/reports/utility_bills.csv \
  --answers /data/reports/answers_building.json \
  --lat 42.3314 --lon -83.0458 \
  --cooling-tons 200 --fan-hp 75
```

- `--answers` merges human fields into null dump `model_seed` (non-null only).
- **lat/lon beat city label** for weather (metro Troy vs Detroit).
- Off-window dump `weather_observed.csv` is stashed → Open-Meteo for bill months.
- Plan stamps `epw_bill_overlap` — assert before claiming AMY honesty.
- Honest G14 fail with `months_compared` ≈ bill count is a valid screening PASS path.

Publishes `runs/calibrate_*` with scorecard + optional client zip under `.artifacts/deliverable_*`.
In Studio Twin: **Build client package** → download report / xlsx / zip.

Archive root-owned runs when needed:

```bash
docker exec -u 0 vibe20 bash -lc 'mkdir -p /data/runs/_archive && mv /data/runs/<old> /data/runs/_archive/'
```

Studio bootstrap (zero-click Fuel/Twin):

```bash
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data vibe20 \
  wattlab studio-bootstrap \
  --campus /data/uploads/energy/my_campus \
  --dump /data/uploads/dump/wattlab_dump.zip \
  --run-id calibrate_YYYYMMDDTHHMMSSZ \
  --answers /data/reports/answers.json
```

Writes `/data/studio_bootstrap.json` (+ `.last_studio_session.json`). Next Studio
browser session auto-loads Fuel campus + Twin preferred run (sidebar banner).

**Human load path:** browser **page refresh** starts a new Streamlit session (auto-apply once).
If the session is already open and the JSON changed, use sidebar **Re-apply bootstrap**
(or refresh). No HTTP wrapper — file handoff only.

**Publish auto-upsert:** `publish_run_for_studio` / `calibrate-campaign` merge
`preferred_run_id` into `studio_bootstrap.json` (best-effort) and **append** a
timestamp line to `notes` (does not wipe `--notes` text). Explicit
`wattlab studio-bootstrap --campus …` is still useful for campus/dump/answers paths;
run-id alone is often already set after publish.

**Pytest:** runtime `ghcr.io/bbartling/vibe20:latest` does **not** include pytest.
AppTest lives in CI / host: `pip install -e ".[dev]"` then
`python -m pytest tests/test_studio_bootstrap.py -q`. Do not `docker exec … pytest`.

Disable in CI: `WATTLAB_STUDIO_BOOTSTRAP_DISABLE=1`.

## Session status + answers vs dump

```bash
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data vibe20 wattlab studio-status --write
# → /data/reports/session_status.json  (missing | answered | phase2)
# Template: /app/wattlab/studio/templates/answers.schema.template.json
```

Dump `model_seed` may still have null type/city/area while answers are filled —
that is dual-source honesty. Studio softens the NEEDS_INPUT banner when answers
cover required fields. Bootstrap with `answers_path` also builds `studio_profile`
so the ECMs page unlocks without a Twin form click.

## ECM scenario (agent → Easy Buttons)

Write `/data/reports/ecm_scenario.json`:

```json
{
  "version": 3,
  "selected_ecm_ids": ["ECM-AHU-SCHED-ALIGN", "ECM-OCC-STANDBY-DCV"],
  "measure_set": "best",
  "sort_preference": "implementation_complexity",
  "package_hints": ["esco-top15"],
  "notebook_package_id": "controls_first",
  "notebook_path": "/data/reports/notebooks/controls_first.xlsx",
  "input_overrides": {"elec_rate": 0.14},
  "proxy_defaults": {},
  "roi_param_hints": {},
  "notes": "from chat",
  "recommendations": ["ECM-CHILLER-LOCKOUT"]
}
```

Prefer building the Excel notebook for deliverables:

```bash
wattlab notebook build --package controls_first --out /data/reports/notebooks/ \
  --answers /data/reports/answers.json --from-run /data/runs/<id>
```

Human Re-apply / open ECMs → notebook package + Easy Buttons prefilled. Studio
**Save to ecm_scenario.json** writes back. Optional bootstrap key: `ecm_scenario_path`.

## Twin iteration dashboard + client package

Twin **Iteration history** shows run_id, hypothesis, weather, status, eplusout,
elapsed (from `run_manifest.json`). **Build client package** can include the
14-section `01_Report/Energy_Modeling_Report.docx` alongside report.md,
workbook.xlsx, and the full zip (`05_Source_Data` included when answers/bills
are present). The Studio checkbox defaults on when `python-docx` is installed.

Fuel **Portfolio** peer metrics have `?` help text + “How buildings are benchmarked”.

## DinD live progress → APIHelper-08 panes

While EnergyPlus runs in `energyplus-mcp-dev`, WattLab streams console lines into
`runs/<id>/console.log` and updates `runs/<id>/progress.json` (percent + status).
Studio Twin polls that folder (fragment / live status box) — **not** embedded
`pyenergyplus`. OA / floor-plan charts appear after `eplusout.csv` (ReadVars `-r`).

Agent path publishes the same files; human **Refresh agent runs** or leave Twin open.

## studio-bootstrap --ecm-scenario (merge-safe)

```bash
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data vibe20 \
  wattlab studio-bootstrap \
  --run-id calibrate_… \
  --ecm-scenario /data/reports/ecm_scenario.json
```

Rewrites **merge** existing `studio_bootstrap.json` keys (campus/dump/answers/ecm)
so a partial CLI call does not drop `ecm_scenario_path`.

`wattlab studio-status` fills `twin.g14` from scorecard / campaign_stamp, marks
`utility_bills` answered from answers array or `reports/utility_bills.csv`, and
normalizes `ecm_scenario.status` when ids are selected.

## Agent flow (no git)

```text
docker exec vibe19 … agent_api / agent_afdd
        │
        ▼  WattLab dump zip
shared wattlab_workspace/uploads/
        │
        ▼
docker exec vibe20 wattlab twin | easy-button | calibrate
        │
        ▼  Docker sock → energyplus-mcp-dev
runs/<id>/eplusout.csv + wattlab_report.json
        │
        ▼
Human opens Studio Twin (browser) — Refresh agent runs
```

### Examples

```bash
# 1) vibe19 — produce dump into shared uploads (exact CLI depends on image entrypoints)
docker exec vibe19 python -m openfdd_vibe ...   # or agent_api / agent_afdd docs in vibe19

# 2) vibe20 — easy-button / twin from a profile under /data
docker exec vibe20 wattlab easy-button --building /data/uploads/.../building_profile.json

# 3) Confirm publish
docker exec vibe20 ls -la /data/runs
```

EnergyPlus itself runs in `energyplus-mcp-dev` via the mounted docker socket
(DinD). Do **not** expect host `pyenergyplus` or a live Flask mid-run server.

## Equal look-and-feel (ops)

| Concern | vibe19 | vibe20 |
|---------|--------|--------|
| Workspace | shared volume | same shared volume |
| Agent entry | `docker exec` + agent API/AFDD | `docker exec` + `wattlab` CLI |
| Human UI | Streamlit | Streamlit Studio Twin |
| Secrets / code | image + volume | image + volume (no clone) |

Cross-links:

- vibe19 README — Docker/GHCR + dump handoff
- [`AGENT_TESTER_PROMPT.md`](../AGENT_TESTER_PROMPT.md) — browser gates (W2b/W3b, demand kW, multi-floor)
- [`TWIN_LOOP.md`](TWIN_LOOP.md) — calibrate iteration contract
