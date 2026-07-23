# Benchmark governance — the rules that keep ROI honest

Why this layer exists: an agent can be technically sophisticated in EnergyPlus
and still be **economically untrustworthy**. The benchmark layer
(`wattlab.benchmarks`) is the governance that prevents sparse BAS evidence
from becoming a glossy ROI chart without guardrails.

## The three-layer stack

1. **Benchmark plausibility** (this layer) — whole-building sanity from bills
   and public peer data. Fast, no model needed.
2. **Bin-method / spreadsheet proxies** (`wattlab.bench`) — fast ESCO-style
   screening per measure.
3. **Calibrated simulation** (`wattlab.easy_button` + G14) — final scenario
   testing.

Skipping layer 1 or 2 to get to layer 3 faster is the canonical failure mode.

## EUI registry (`eui.py` + `benchmarks_public.json`)

- Metric: **site EUI, kBtu/ft²-year**. 1 kWh = 3,412 Btu; 1 Mcf = 1.037 MMBtu.
- Peer rows: EPA Portfolio Manager national medians by property type
  (office 52.9, courthouse 101.2, retail 51.4, …); fallback
  `commercial_all` = CBECS 2018 average 70.6.
- p20/p80 are screening bands for coloring, not published percentiles — say so
  when reporting.
- Property type drives everything: office vs courthouse flips "good" to "bad"
  at the same EUI. If type is uncertain, show both comparisons.

## Cost registry (`costs.py` + `retrofit_costs_public.json`)

Scope ladder with **explicit unit basis, currency year, confidence**:

| Scope | Band (USD/unit) | Basis | Vintage / confidence |
| --- | --- | --- | --- |
| `rcx_tuning` | 0.05–0.50, p50 0.26 | building_ft2 | 2020, high |
| `minor_hvac_controls` | 1.5–3.5, p50 2.35 | building_ft2 | 2017, high |
| `bas_overlay` | 2.5–7.5, p50 5.0 | building_ft2 | 2024, **low** (vendor ranges) |
| `major_hvac` | 3.8–7.0, p50 4.6 | building_ft2 | **2009$**, high |
| `non_energy_capital` | 6–15, p50 9.1 | building_ft2 | 2009$, medium |
| `windows_full_replacement` | 30–60, p50 39.7 | **glazing_ft2** | 2022, medium |
| `windows_secondary` | 25–45, p50 36.8 | glazing_ft2 | 2022, medium |
| `deep_retrofit` | 25–150, p50 45 | building_ft2 | 2022, medium |
| `controls_first` | 1–6, p50 3 | building_ft2 | **screening** (Lower-48 synthesis) |
| `major_hvac_renewal` | 10–26, p50 18 | building_ft2 | **screening** (current major renewal) |
| `deep_electrification` | 24–50, p50 32 | building_ft2 | **screening** (electrification / radical) |

Rules: historical medians are reference bands, never bids; windows math needs
glazing area (no glazing area → `no_reference`, not a guess);
`scope_for_measure` maps measure ids to scopes (SCHED/LOCKOUT/RESET →
rcx_tuning, GL36/DCV/ECON → minor_hvac_controls, BOILER/CHILLER-REPLACE →
major_hvac, …).

**Lower-48 screening synthesis + ROI takeaways:**
[`ESCO_RETROFIT_COST_ROI.md`](ESCO_RETROFIT_COST_ROI.md).

## Meter allocation (`meters.py`)

Shared meters are schema objects (`campus.json`), not spreadsheet hacks.
Modes: `area_weighted` (default), `equal`, `gas_share` (electric split by
building-specific gas shares; falls back to area when no gas signal),
`manual` (locked shares). All modes conserve totals. Present them
**side-by-side** until submetered or BAS-derived evidence picks one — none is
truth. Annualization uses the latest common complete 12-month window across
all meters; every building row records the allocation used.

## The gate (`guardrails.py::gate_capital_plan`)

Runs on every capital plan before publication. Checks:

| Check | Investigate when |
| --- | --- |
| `baseline_eui_band` | baseline below peer p20 (efficient buildings rarely support big claims) |
| `savings_fraction` | claimed site-energy savings above the scope ceiling (rcx 25% … deep 70%) |
| `post_retrofit_eui` | implied post-retrofit EUI below half the peer p20 (national-outlier claim) |
| `measure_cost_band` | cost/unit above the scope's hi band |
| `payback_plausibility` | payback under the scope floor (forgot install costs?) |

Missing context → `skipped` (never a false block). Verdict `INVESTIGATE` means:
show the deltas, require the human to override or tighten assumptions.
**Never suppress, soften, or summarize away a failed check.**

## Liberty as the regression anchor

`examples/liberty/` + `tests/test_benchmarks_liberty.py` pin the whole chain:
window Dec 2024→Nov 2025, campus 2,928,898 kWh / 9,688.6 Mcf, site EUI 71.6,
splits 66.9/76.3 (area) and 62.2/81.0 (gas-share). If a loader or conversion
change moves these, it's wrong until proven otherwise.

## Adding benchmarks

User/portfolio registries append via `load_registry(extra_paths=[...])` —
same row schema, later rows never silently override the public ones (lookup
returns first match; keep property types distinct). Every row must carry
`source`, `source_date`/`currency_year`, `confidence`.
