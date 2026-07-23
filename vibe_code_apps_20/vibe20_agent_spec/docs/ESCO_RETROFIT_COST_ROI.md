# ESCO retrofit cost + ROI screening (Lower 48)

**Purpose:** give AI agents and energy engineers a **client-neutral screening
band** for early ECM capital tables — not a bid, not RSMeans localization, not
a guaranteed payback.

Pair with [`BENCHMARK_GOVERNANCE.md`](BENCHMARK_GOVERNANCE.md) and
`wattlab.benchmarks.guardrails.gate_capital_plan`. Never publish **calibrated**
ROI without G14 stamps + human confirmation.

## Framing

WattLab’s three-layer stack:

1. Benchmark plausibility (peers, cost bands)
2. ESCO bin-method proxies (`wattlab.bench`)
3. Calibrated EnergyPlus (+ G14)

Screening $/sf numbers are a **plausibility filter**. Historical ESCO database
medians and current electrification studies disagree in absolute dollars —
that is expected. Use the **scope column** (controls-first vs major renewal vs
deep electrification) before trusting any single $/sf.

Registry: `wattlab/data/benchmarks/retrofit_costs_public.json` (lo / p50 / hi,
`currency_year`, `confidence`, `unit_basis`).

## Historical LBNL / NAESCO Major HVAC (relative anchor)

Berkeley Lab / NAESCO ESCO project fact sheets (installations ~1996–2008)
report **turnkey** Major HVAC installation cost (design + construction + Cx +
construction-period financing; excluding long-term financing / incentives) and
median simple payback. Treat as **relative** segment anchors — not 2026 quotes.

| Market segment | Historical median Major HVAC install | Historical median simple payback |
| --- | --- | --- |
| Federal | ~$3.8/sf | ~7.0 yr |
| K-12 | ~$4.5/sf | ~10.4 yr |
| Postsecondary | ~$4.2/sf | ~8.1 yr |
| Healthcare | ~$5.4/sf | ~6.5 yr |
| State / local | ~$6.4/sf | ~8.2 yr |

Classic ESCO “major HVAC” bundles often mixed mechanical work with controls,
lighting, motors, and ops measures — so these medians sit **below** today’s
deep-retrofit / full electrification first costs.

## Current public anchors

| Source theme | Screening takeaway |
| --- | --- |
| NEEA / Red Car DOAS–VRF first-cost work | RTU heat-pump packages ~$19–20/sf; DOAS/VRF packages roughly ~$24–39/sf across analyzed types/climates |
| DOE large-building boiler / electrification guidance | Converting existing systems often ~$20–50/sf; panel upgrades, refrigerant/hydronic routing, and occupied-building constraints push high |
| PNNL controls / BAS case evidence | Controls-first can land near ~$1/sf on smaller offices when scope is overlay + sequencing (not wholesale plant replace) |
| FEMP Cx / recommissioning | New equipment Cx often ~$0.50–$3.00/sf; existing-building RCx often ~$0.05–$0.40/sf with short paybacks |

## Lower-48 screening table (synthesized)

**Confidence: screening.** Not bid numbers. Prefer mid-band for first ECM
summary; move low/high with building friction (see adders below).

| Building type | Controls-first upgrade | Major HVAC renewal | Deep electrification / radical retrofit |
| --- | --- | --- | --- |
| Office | $1–$4/sf | $12–$24/sf | $24–$32/sf |
| K-12 school | $2–$6/sf | $14–$26/sf | $30–$38/sf |
| Higher-ed admin / classroom | $2–$6/sf | $12–$24/sf | $24–$33/sf |
| State / federal office or civic | $2–$6/sf | $12–$25/sf | $20–$35/sf |
| Retail / branches | $1–$4/sf | $10–$20/sf | $25–$34/sf |
| Healthcare / hospital | $3–$7/sf | $18–$35/sf | $35–$50+/sf |

**Column definitions**

- **Controls-first** — BAS overlay / front-end, selective field devices,
  schedules, resets, trends/alarms, limited air-side work — not wholesale plant
  replace. Maps near registry scopes `rcx_tuning`, `bas_overlay`,
  `controls_first`, `minor_hvac_controls`.
- **Major HVAC renewal** — large equipment + distribution cleanup without fully
  reinventing the system concept. Maps near `major_hvac` /
  `major_hvac_renewal` (note historical LBNL `major_hvac` is 2009$ and lower).
- **Deep electrification / radical retrofit** — heat-pump conversion, DOAS,
  major redistribution, likely electrical work. Maps near
  `deep_electrification` / `deep_retrofit`.

**Short bottom line:** controls-led ~$1–$6/sf; major HVAC renewal ~$10–$26/sf;
radical / large electrification ~$24–$50+/sf — offices/retail lower end of deep
work, schools mid–high, hospitals top.

## What’s inside “turnkey”

Public ESCO turnkey usually includes design, construction, and commissioning.
Deep-retrofit studies still show most dollars in core HVAC package +
distribution + field install; soft costs matter:

- Engineering / design / permit premiums
- Contractor overhead / profit
- TAB (balancing is real money, not a throw-in)
- Occupied-building friction: demolition, night work, patch/paint, legacy BAS
  integration, hazmat, **electrical service upgrades**, shaft/chase reuse vs
  new routing

If old plant comes out cleanly and chases reuse → mid-band. If occupied 24/7,
new service, or system-concept change → high end.

## ROI / payback takeaways

| Scope | Screening economics |
| --- | --- |
| Controls / RCx | Often fast; RCx paybacks frequently under ~2 years; PNNL notes large % savings from properly implemented controls |
| Classic ESCO major HVAC bundles | Historical medians roughly ~6.5–10.4 years by segment — sanity check for public-sector PC-style bundles |
| Deep electrification | Do **not** expect a universal short payback from energy alone; stack renewal, comfort, IAQ, resilience, deferred maintenance, incentives (e.g. expanded 179D can be on the order of ~$0.50–$5/sf depending on compliance) |

**Hard WattLab rule:** screening ROI ≠ calibrated ROI. Calibrated capital plans
require G14 + `gate_capital_plan` → `PUBLISH` (or explicit human override of
`INVESTIGATE`).

## How agents should use this

1. Classify the ECM package into **controls-first / major renewal / deep**.
2. Pick building-type band from the screening table; stamp `currency_year` /
   `confidence` from the matching `retrofit_costs_public.json` row.
3. Run ESCO bin proxies (`wattlab bench`) then EnergyPlus crosscheck.
4. Localize with assembly databases / contractor input before any client quote.
5. Carry occupied-building adders explicitly when known.
6. Gate with `gate_capital_plan` before Studio capital deliverables.

See also: [`ESCO_CALCULATORS.md`](ESCO_CALCULATORS.md),
[`CALIBRATE_AND_DELIVERABLES.md`](CALIBRATE_AND_DELIVERABLES.md),
[`AGENT_TOOLS.md`](AGENT_TOOLS.md), skill `wattlab-benchmarking`.
