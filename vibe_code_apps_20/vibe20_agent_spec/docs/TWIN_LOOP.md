# The twin-iterate loop — human + AI agent protocol

How an AI agent and an energy engineer take a building from vibe19 FDD dump to
a benchmark-gated capital plan. Every step has a CLI path (agent) and a Studio
page (human); both share the same `wattlab` modules, so numbers never diverge.

## Step 0 — Ingest the evidence

```
wattlab seed dump.zip            # summary
wattlab seed dump.zip --gaps     # what the human still owes
```

Studio: **Ingest** page. The gap report is the conversation starter: the agent
asks the human for `required` gaps (building type, city, floor area) and
`recommended` ones (bills, WWR, rates, measure costs). Never invent these.

## Step 1 — Benchmark the bills (before any model!)

```
wattlab benchmark campus.json                # annual EUIs + peer bands
wattlab benchmark campus.json --scenarios    # shared-meter splits side-by-side
```

Studio: **Benchmark** page. Questions to answer *before* modeling:

- Is site EUI inside the peer band? Way below p20 with big savings claims
  coming → something is wrong (area? allocation? vacancy?).
- Does gas track heating degree days? Summer gas ≠ 0 → DHW/reheat baseload
  the model must include.
- Shared meters: which allocation scenario is being used, and does the story
  change if you switch? If yes, flag it — don't pick silently.

## Step 2 — Resolve the profile

`resolve_profile(minimal)` fills archetype gaps with provenance
(`field_sources`). Studio: **Model** page. The human confirms geometry and
rates; everything defaulted stays visibly labeled as a default.

## Step 3 — Price measures with ESCO proxies

Measure list = catalog measure set + FDD-suggested (bridge). Each measure gets
a bin-method proxy estimate (`wattlab.bench.esco`) — screening-grade,
spreadsheet-auditable. Studio: **Measures** page (editable costs).
Agent: `wattlab bench` with explicit inputs.

## Step 4 — Run the twin

```
python -m wattlab.easy_button --profile profile.json --dry-run   # plan only
python -m wattlab.easy_button --profile profile.json             # Docker E+
```

Baseline first. If bills exist, the baseline must pass ASHRAE G14 monthly
gates (NMBE ±5%, CV(RMSE) ≤15%) before any savings claim is "calibrated" —
otherwise iterate: schedules from the dump, setpoints from `setpoints.csv`,
envelope/LPD knobs from defaults, weather from the AMY EPW.

Then measures run progressively; `savings_by_measure[].vs_previous` is each
measure's incremental effect.

## Step 5 — Crosscheck (the referee)

Automatic when the profile carries `proxy_savings`; standalone:
`wattlab crosscheck --report wattlab_report.json --proxies proxies.json`.

| Verdict | Meaning | Agent action |
| --- | --- | --- |
| `in_line` (0.5–2.0×) | E+ and bin method agree | proceed |
| `investigate` | outside band | check patch applied, schedule overlap, sizing; re-run |
| `keep_iterating` | wrong sign / zero proxy vs big E+ | model bug until proven otherwise |

The spreadsheet method is the trust anchor: when they disagree, suspect the
model first, then the proxy inputs, then (rarely) the method.

**Area normalization (learned live on Liberty):** the bundled 5ZoneAirCooled
prototype is only ~10k ft², so raw E+ kWh for a 140k ft² profile under-reports
~14× and every verdict comes back `investigate` for the wrong reason. The
crosscheck now auto-scales via `prototype_area_scale` (target ft² / model ft²
from the baseline record's `building_area_m2`) and reports both raw and
scaled values plus the `area_scale` used. G14 comparisons scale the modeled
monthly series the same way. When the scaled ratio is *still* outside the
band, the disagreement is real — schedule assumptions, W/cfm, kW/ton — not
geometry. The long-term fix is a right-sized prototype; the scale factor is
the honest screening bridge until then.

**Monthly data prerequisite:** the G14 gate only fires when the baseline
record has a `monthly` series. `easy_button` now patches monthly
`Output:Meter,Electricity:Facility` / `NaturalGas:Facility` into every
prototype (`apply_monthly_energy_tables`) and, because EnergyPlus 26.1 still
writes no monthly tabular section for this prototype, results parsing falls
back to `eplusout.mtr` (`parse_monthly_from_mtr`). If `monthly` is empty,
fix the outputs — don't skip the gate.

Full rehearsal of steps 1–7 against the Liberty campus (real Docker E+ runs):
`python scripts/agent_twin_demo.py --measure-set best`.

## Step 6 — Capital plan + benchmark gate

`wattlab.finance.capital_plan` rolls up payback/ROI/NPV. Then — mandatory —
`gate_capital_plan` (see [BENCHMARK_GOVERNANCE.md](BENCHMARK_GOVERNANCE.md)).
Studio: **Capital plan** page shows `PUBLISH` / `INVESTIGATE` with the check
table. An agent must never present ROI output from an `INVESTIGATE` plan
without surfacing the failed checks verbatim.

## Step 7 — Report ranges, not points

Cost and savings statements carry range + basis + confidence, e.g. "major
HVAC retrofit: reference band ~$3.8–7.0/ft² (median $4.6/ft², 2009$, adjust
for market)". Single-point promises are an anti-pattern this tool exists to
prevent.

## Iteration bookkeeping

Every E+ run writes `run_manifest.json` (model SHA, weather SHA, image pin).
Studio Twin loop shows the last 10. Never compare savings across runs with
different weather or prototype hashes.

## School 30-year rehearsal

`examples/school_30yr/` is a fictional 100,000 ft² K-12 school with twelve
repository-authored 2025 bills labeled `synthetic_rehearsal`. It contains no
measured or transformed customer, district, contractor, or utility data.

Before network or simulation work, strict Pydantic contracts reject extra
fields, invalid coordinates/date order, incomplete EPW variables, bad
fuel-unit pairs, duplicate or non-consecutive bills, mixed fuels/units, and
scenarios without unique measures or an explicit conceptual-surrogate flag.
The Open-Meteo archive flow uses request-keyed atomic caching, source SHA and
download provenance, bounded retries for timeout/429/5xx only, declared-unit
and physical-bound validation, consecutive timestamps, and exact full-year
coverage (8,760 rows; 8,784 in leap years).

Open-Meteo archive rows arrive in UTC. A full-year frame must be rotated and
restamped to the site's **local standard time** before EPW generation, with
the same fixed UTC offset in the LOCATION header. DST is not applied. Writing
UTC rows into a local EPW misaligns radiation and weather schedules.

The two progressive scenarios are:

- `school_30yr_hydronic`: schedule alignment → premium fan/VFD →
  high-efficiency chiller → condensing boiler → glazing.
- `school_30yr_electrify`: schedule alignment → premium fan/VFD →
  high-efficiency chiller → AWHP surrogate → glazing.

Both are conceptual. The AWHP is modeled as an electric boiler at a screening
COP, glazing uses a simple-glazing envelope proxy, and fan/chiller/boiler
replacements directly edit efficiencies or equipment parameters. These do not
model heat-pump performance maps, plant redesign, controls integration,
detailed fenestration, equipment selection, or constructability.

```powershell
cd vibe_code_apps_20

# Focused unit suite; no network or Docker
python -m pytest tests/test_input_contracts.py tests/test_open_meteo_weather.py tests/test_deep_retrofit_patches.py tests/test_school_30yr_rehearsal.py -q

# Full suite
python -m pytest -q

# Opt-in live Open-Meteo + Docker integration
$env:RUN_SCHOOL_30YR_LIVE="1"
python -m pytest tests/test_school_30yr_rehearsal.py::test_live_school_30yr_rehearsal -q -s
Remove-Item Env:RUN_SCHOOL_30YR_LIVE

# Generate the canonical report directly
python scripts/school_30yr_rehearsal.py
```

The script's process exit describes execution only: simulation/runtime failure
is nonzero, while a completed `INVESTIGATE` rehearsal exits zero. The release
guard requires separate monthly electricity and natural-gas G14 passes.
Major-HVAC component costs use explicit shares that total one p50 package per
scenario; controls and glazing remain separate.

The 2026-07-18 live rehearsal produced 12/12 `COMPLETE` records. Simulation
completion is not publication approval: baseline electricity fails G14 at
52.21% NMBE / 52.61% CV(RMSE), natural gas fails at 78.03% / 93.74%, and
conceptual flags are present, so the fail-closed release guard returns
`INVESTIGATE` for each scenario and overall.

Canonical report: `.artifacts/school_30yr_rehearsal.json`. Its `comparison`
rollup reports:

- hydronic: 90,261.2 kWh and 4,864.5 therms saved/year; $17,986.53/year;
  $716,806.94 implementation cost; -$346,521.59 NPV; `INVESTIGATE`.
- electrify: 61,148.4 kWh and 8,085.7 therms saved/year; $17,133.43/year;
  $716,806.94 implementation cost; -$364,084.16 NPV; `INVESTIGATE`.
