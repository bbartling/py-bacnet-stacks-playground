# ECM Easy Buttons

Canonical ECM metadata lives in [`wattlab/measures/catalog.yaml`](../wattlab/measures/catalog.yaml).
Studio **ECM Easy Buttons** and `wattlab ecm` both read that registry.

## CLI

```powershell
wattlab ecm list
wattlab ecm describe ECM-AHU-SCHED-ALIGN
wattlab ecm packages
wattlab ecm package partial-g36
wattlab ecm audit
```

## Support statuses

| Status | Meaning |
| --- | --- |
| `PRODUCTION_PROXY_AND_ENERGYPLUS` | Proxy + IDF patch available |
| `PRODUCTION_PROXY_ONLY` | Proxy only |
| `CONCEPTUAL_ENERGYPLUS_PROXY` | Screening IDF surrogate |
| `RESEARCH` / `NEEDS_IMPLEMENTATION` | Visible card; Run EnergyPlus disabled |
| `NOT_APPLICABLE` | Hidden from recommended packages |

## Packages

`pneumatic-to-ddc`, `partial-g36`, `full-g36-conceptual`, `controls-only`, `low-cost`, `plant-optimization`, `no-capital-rcx`.

Incompatibilities are checked before stacking contradictory economizer types, overlapping G36 packages, or zero-OA with occupied DCV.

Coverage matrix: [`ecm_coverage_matrix.md`](ecm_coverage_matrix.md).

## Presentation order and agent defaults

Studio presents cards by `implementation_complexity` (`low` → `medium` →
`high`), then category and ECM id, and labels every card with its complexity.
This is a presentation order only: `ESCO_TOP15` remains in screening-rank
order. `ECM-OCC-STANDBY-DCV` is a medium-complexity `esco-top15`,
`controls-only`, and `no-capital-rcx` candidate adjacent to `ECM-DCV-CO2`.

`reports/ecm_scenario.json` is schema v2. Agents may provide
`sort_preference`, `package_hints`, `proxy_defaults`, and `roi_param_hints`;
v1 files with only selections remain loadable.
