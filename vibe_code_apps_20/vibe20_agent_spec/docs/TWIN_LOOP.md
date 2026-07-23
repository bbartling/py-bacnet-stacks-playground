# The twin-iterate loop — human + AI agent protocol

How an AI agent and an energy engineer take **any** building from a vibe19 FDD
dump + energy package to a benchmark-gated capital plan. Practice dumps on a
test bench are examples only — never bake site ids into code or answers.

Every step has a CLI path (agent) and a Studio surface (human). Both share
`wattlab` modules. Any AI agent chats **outside** Streamlit on the workspace folder;
Studio refreshes from `uploads/`, `runs/`, `reports/`. Agents must **publish** each
E+ iteration so Twin 08 panes appear in the browser
(`publish_run_for_studio` / `runs/CURRENT_RUN.txt`).

**Live 08:** DinD writes `progress.json` + `console.log` during the sim; Twin polls
(progress/log live). OA charts update when `eplusout.csv` exists (after ReadVars).
**Building massing** comes from published `model.idf` (BuildingSurface:Detailed) —
unique per run / site. Zone colors apply when CSV zone names match. Not embedded
pyenergyplus / not Flask APIHelper / not hard-coded Liberty footprints.

## Geometry gate (site-scale twins)

Answers `floors` / `wwr` / `sqft` do **not** rebuild the IDF. Default = 5Zone ×
`prototype_area_scale`. For glass multistory offices:

1. `wattlab geo-idf` (DOE Large Office → site-scale; any building via CLI args)
2. `custom_idf` + **`area_scale = 1`**
3. Fuel mix: high elec / low gas → `wattlab dial-loads` (EnergyPlus MCP one-shot)
4. `wattlab score-monthly` — last-12 Monthly meters vs area-weighted bills (never double-half)

Annual simulate = WattLab DinD. MCP = inspect/modify loads only (`simulate_only` tip
does not ship full MCP tools).

Full paste prompt for QA + calibrate sessions:
[`../AGENT_TESTER_PROMPT.md`](../AGENT_TESTER_PROMPT.md).

Sparse / poorly known buildings (TMY→autosize→constrain→AMY→FDD, ~6–10 runs):
[`SPARSE_BUILDING_PLAYBOOK.md`](SPARSE_BUILDING_PLAYBOOK.md).

## Step 0 — Uploads (evidence)

```
wattlab seed dump.zip            # summary
wattlab seed dump.zip --gaps     # what the human still owes
```

Studio: **Uploads**. Load dump v3 + energy package:

- Preferred: `campus.json` + bill CSVs (+ Haystack `column_map` if interval)
- Fallback: monthly Excel → `uploads/energy/derived/` (verify with human)
- Optional: `buildings.json` / dump `model_seed` for ids, area, type, lat/lon

Gap report is the conversation starter. Ask for `required` gaps
(`building_type`, `city`, `floor_area_ft2`) and recommended bills/rates/costs.
**Never invent these.**

## Step 1 — Fuel dashboard (before deep modeling)

Studio: **Fuel dashboard**. Confirm:

- Monthly kWh/gas/demand tables + ≥1 chart (Fuel-ready package)
- Site EUI vs peer band; HDD/CDD + Open-Meteo only when lat/lon present
- Shared-meter allocation scenarios are scenarios, not truth

CLI: `wattlab benchmark campus.json` / `--scenarios`.

If Fuel is empty after Excel load → bug or unmappable workbook; do not proceed
to glossy ROI.

## Step 2 — Resolve the Twin profile

`resolve_profile(minimal)` with provenance. Studio: **Twin / calibrate** form
prefilled from dump/campus — human confirms city, type, area, lat/lon.

## Step 3 — ESCO proxies (screening)

Measure list = catalog + FDD bridge. Bin-method proxies via `wattlab.bench.esco`.
Studio: **ECMs** (and Twin crosscheck when proxies attached).

## Step 4 — Run / iterate the twin (Docker EnergyPlus)

```
wattlab easy-button --profile profile.json --dry-run
wattlab easy-button --profile profile.json
```

Studio Twin:

- Dry-run → `reports/last_dry_run_plan.json`
- Docker run → `runs/<run_id>/` (report, eplusout, manifest); needs
  `WATTLAB_HOST_WORKSPACE` + docker.sock for DinD; `-r` → `eplusout.csv`
- Demo replay → fixture eplusout labeled replay (UI smoke without E+ image)
- **Visualizer panes**: progress + console, outdoor DBT, **IDF 3D massing** from
  `model.idf` (fallback classic 5Zone schematic only when no IDF published)
  heatmap (`wattlab.studio.ep_viz`) — viz patterns only, not host Runtime API

**Order when little is known** (see [`SPARSE_BUILDING_PLAYBOOK.md`](SPARSE_BUILDING_PLAYBOOK.md)):
TMY + autosize → observe sized plant → constrain to FM tons/hp → one schedule
hypothesis → AMY with bill-aligned window → one FDD knob per run. QA floor ≥3
live sims; sparse sites often need **6–10**. Stamp `prototype_area_scale` —
5Zone ≈ 10k ft² is not the site.

**AMY + G14 turnkey** (after TMY screening + plant honesty):

```bash
wattlab calibrate-campaign --bundle dump.zip --bills utility_bills.csv --lat … --lon …
```

See [`CALIBRATE_AND_DELIVERABLES.md`](CALIBRATE_AND_DELIVERABLES.md). Twin UI:
scorecard metrics + **Build client package** (report / xlsx / zip).

DinD: image includes Docker CLI; set `WATTLAB_HOST_WORKSPACE` + sock.
Prefer `docker exec vibe20` — [`AGENT_DOCKER_WORKSPACE.md`](AGENT_DOCKER_WORKSPACE.md).

**W2b:** last full EPW day. **W3b:** area-aware hard-size / refuse band.
**peak_demand_kw** on results. Multi-floor (`floors`≥2) stacked schematic.

Baseline first. With bills (`reports/utility_bills.csv` or dump bills), G14
monthly NMBE ±5% / CV(RMSE) ≤15% before calibrated savings claims — only when
months overlap and scale is honest.

**Human-in-the-loop calibrate:** one hypothesis per run (schedules, setpoints,
capacity, weather EPW from dump/Open-Meteo). New `runs/<id>/` each time. Ask
the engineer when gates fail or crosscheck is `investigate` / `keep_iterating`.

## Step 5 — Crosscheck

| Verdict | Meaning | Action |
| --- | --- | --- |
| `in_line` (0.5–2.0×) | E+ ≈ proxy | proceed |
| `investigate` | outside band | check patch/schedule/sizing; re-run |
| `keep_iterating` | wrong sign / missing | model bug until proven otherwise |

Always area-normalize vs the 5ZoneAirCooled prototype footprint
(`prototype_area_scale`). The prototype name is an EnergyPlus sample, not a site.

## Step 6 — Capital guardrails

`gate_capital_plan` on every plan. Studio **ECMs** capital section. Any hit →
`INVESTIGATE`; human overrides explicitly.

## Workspace paths (shared with Studio)

```
uploads/dump/  uploads/energy/  uploads/energy/derived/
runs/<run_id>/eplusout.csv | model.idf | run_manifest.json | progress.json | report.json
reports/utility_bills.csv | last_dry_run_plan.json | BUG_REPORT.md | CALIBRATE_SESSION.md
```

## Docker turnkey (Studio + EnergyPlus MCP image)

```bash
docker pull ghcr.io/bbartling/vibe20:latest
docker run -d --restart unless-stopped -p 8520:8501 \
  -v "$HOME/wattlab_workspace:/data" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e WATTLAB_STUDIO_WORKSPACE=/data \
  -e WATTLAB_HOST_WORKSPACE="$HOME/wattlab_workspace" \
  -e WATTLAB_ROOT=/app \
  --name vibe20 ghcr.io/bbartling/vibe20:latest
```

**Required for Twin calibrate PASS:** host image `energyplus-mcp-dev` plus a
**multi-run live campaign** (≥3 successful Docker sims published to `runs/<id>/`
for browser 08 panes — baseline + hypotheses; sparse sites → playbook 6–10).
Build image per `third_party/README.md`. Probe:
`wattlab.energyplus.mcp.capability_status()`. Prefer EnergyPlus-MCP inspect when
the vendor tree is cloned. Demo replay ≠ PASS.

Full campaign prompt: [`../AGENT_TESTER_PROMPT.md`](../AGENT_TESTER_PROMPT.md).
