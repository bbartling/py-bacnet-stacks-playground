# Sparse-building twin playbook

How an AI agent + energy engineer take a **poorly known** existing building from
Fuel evidence to honest EnergyPlus iterations. Practice campuses are examples
only — never invent city / area / HVAC / bills.

**Stack (three layers — do not conflate):**

| Layer | Owns | Does not own |
| --- | --- | --- |
| **EnergyPlus** | Physics engine (loads, HVAC, IdealLoads, tariffs, FuelFactors, tabular CSV/HTML) | UI, smart defaults, calibration judgment |
| **EnergyPlus-MCP** (~35 tools) | Load / validate / inspect / patch / simulate / plot / HVAC topology | TMY vs AMY choice, G14, FDD trust, prototype selection |
| **WattLab + this playbook** | Assumption ledger, peers → ESCO bins → E+, G14, publish `runs/`, honesty stamps | Magical knowledge of the site |

Emulate the disciplined “fast defaults” pattern (simple model form + opinionated
transparent assumption stack), not a magic UI. Prefer:
`prototype/template → assumption engine → IDF patch → MCP validate/sim → report`.

Related: [`TWIN_LOOP.md`](TWIN_LOOP.md) · paste prompt
[`../AGENT_TESTER_PROMPT.md`](../AGENT_TESTER_PROMPT.md) · skills
[`../skills/wattlab-assumptions/SKILL.md`](../skills/wattlab-assumptions/SKILL.md) ·
[`../skills/wattlab-energyplus-mcp/SKILL.md`](../skills/wattlab-energyplus-mcp/SKILL.md).

---

## When little is known — plan ~6–10 published sims, not 3

Minimum QA gate is still **≥3 live** Docker sims with `eplusout.csv`. For sparse
sites (Liberty-class: shared meters, unknown floors, autosize-only plant), expect
**6–10** published `runs/<id>/` before any G14 language — or exit to
**screening + ESCO proxies** if plant/envelope stay contradictory.

**Rule:** one hypothesis per published run. Stamp weather mode, area scale, and
sizing scenario on every report.

### Ladder (recommended order)

| Step | Weather | HVAC sizing | Goal | Stop if… |
| --- | --- | --- | --- | --- |
| 0 | — | — | Bills + campus + peers (Fuel). Dump gaps listed | No bills / no area |
| 1 | TMY / 30-yr typical | Autosize | Order-of-magnitude EUI vs peers | Wild unmet hours / nonsense EUI |
| 2 | Same TMY | Autosize + observe sized tons/CFM/fan kW | Compare to FM nameplate (tons, hp, cfm/ft²) | — |
| 3 | Same TMY | Constrain to reported plant/fans | Unmet hours / saturation = undersized or bad envelope signal | — |
| 4 | Still TMY | One schedule hypothesis (observed AHU vs design) | Biggest free lever when BAS exists | — |
| 5 | AMY / actual (dump weather or Open-Meteo) | Keep constrained (or re-autosize once) | Align calendar to bills | period_mismatch |
| 6–8 | AMY | One FDD knob per run (SAT, SP reset, OA/econ, lockout…) | Move monthly shape toward bills | crosscheck `investigate` |
| 9+ | AMY | Fine multipliers (LPD, people, infil) only after HVAC story holds | Chase G14 | Or declare conceptual-only |

### Ideal Loads vs explicit HVAC

- **Low detail / envelope & schedule questions:** Prefer
  `ZoneHVAC:IdealLoadsAirSystem` (OA, DCV, economizer, HR, humidity still
  expressible) — EnergyPlus’s native “study without full plant” object.
- **HVAC pathway / ECM screening:** Move to a simple explicit seed (today:
  bundled `5ZoneAirCooled.idf` ≈ 10k ft²). **Always** apply
  `prototype_area_scale` or replace with area-true geometry / DOE–PNNL prototype.
- Do **not** call autosized annual kWh “calibrated” from bills alone.

### Assumption hierarchy (agent is the assumption-maker)

1. User / FM explicit facts (`NEEDS_INPUT` — never invent).
2. Uploaded dump / campus / documents (schedules, setpoints, FDD, weather).
3. Nearest archetype / DOE–PNNL prototype by type, size class, code, climate
   (when vendored; else document substitute).
4. Patch only known overrides (fuel, WWR, floors, schedule quirks, HVAC family).
5. Publish an **assumption ledger** (confidence + sensitivity) for occupancy,
   LPD, EPD, ventilation, infiltration, thermostat hours, WWR, HVAC family,
   weather mode, area scale.

Default sources when sparse (log which you used):

- Schedules: ASHRAE Handbook-style archetype defaults (WattLab `defaults`).
- Ventilation: `DesignSpecification:OutdoorAir` (person / area / ACH); EP default
  OA/person ≈ 20 cfm/person — override when FM knows rates.
- Infiltration (no blower door): PNNL commercial guidelines candidate —
  ~0.2016 cfm/ft² above-grade wall from 1.8 cfm/ft² @ 75 Pa leakage; schedule
  fraction 1.0 HVAC-off / 0.25 HVAC-on — **cite and stamp**, do not invent quieter.

### MCP in the campaign

Use EnergyPlus-MCP (when `full_mcp_available`) at least once per **major IDF
change**: validate zones, meters, run period, schedules/loads. WattLab Docker
CLI remains the default simulate path; MCP is the wrench for inspect/modify —
not a calibration coach.

### Studio live loop (required env)

```bash
-e WATTLAB_STUDIO_WORKSPACE=/data \
-e WATTLAB_HOST_WORKSPACE=/home/<user>/wattlab_workspace \
-e WATTLAB_ROOT=/app \
-v /home/<user>/wattlab_workspace:/data \
-v /var/run/docker.sock:/var/run/docker.sock
```

Artifacts under `/data/.artifacts`; `run_energyplus` defaults to `-r` (ReadVars →
`eplusout.csv` for Twin 08 panes).

### What’s still missing (product gaps — be honest in reports)

- Area-true twin (scale factor or real / PNNL geometry) — 5Zone alone ≠ 140k ft².
- First-class “autosize then constrain to FM tons/hp” scenario pack.
- Automated FDD finding → IDF knob ranking beyond measure bridge.
- Full Ideal Loads seed path + DOE–PNNL prototype library vendored.
- Schedule timezone fix (UTC → site TZ) before trusting dump hours in E+.
- Bill↔sim window lock (overlap months or honest `period_mismatch`).

### Exit criteria

| Verdict | When |
| --- | --- |
| **Screening + ESCO proxies** | High unknowns; plant/envelope contradictory; no area-true model |
| **CONCEPTUAL_ONLY** | TMY / substitute climate / unscaled prototype |
| **G14 candidate** | AMY + constrained HVAC story + overlapping bill months + area honesty |

Never publish calibrated ROI without G14 + human confirmation.
