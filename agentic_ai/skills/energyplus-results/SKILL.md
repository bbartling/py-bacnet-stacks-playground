---
name: energyplus-results
description: Extract, validate, and publish EnergyPlus results with hashes, quality flags, and defensible physical and economic claims.
---

# EnergyPlus results

Require successful EnergyPlus completion and preserve input/model/weather hashes, version, run period, artifacts, and exact meters/variables used.

Report fuel energy, facility kWh, demand kW, time of peak, comfort/unmet hours, equipment runtime, and relevant end uses separately. Confirm interval units and demand-window semantics before comparing to utility data.

Flag results for investigation when signs, schedules, deltas, physical behavior, or artifacts are inconsistent. A successful run alone is not a valid result. Derive figures/tables from immutable run artifacts; do not rewrite historical manifests or raw results to improve a narrative.
