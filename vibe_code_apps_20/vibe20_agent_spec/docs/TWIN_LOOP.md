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
