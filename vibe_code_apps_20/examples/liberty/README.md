# Liberty campus — shared-meter benchmark example

Two ~140,000 ft² buildings (50 and 100) sharing **one electric meter**, with
**building-specific gas meters**. This folder documents the campus JSON pattern
for the WattLab benchmark layer and the vibe19 → EnergyPlus twin loop.

## Checked-in vs local data

| Path | In git? | Purpose |
| --- | --- | --- |
| `campus.json` | yes | Buildings, areas, meter→building relationships |
| `Liberty_*.csv` | **no** (gitignored `*.csv`) | Optional local/private bill overlays |
| `tests/fixtures/shared_meter_campus/` | yes | Privacy-safe synthetic CSVs with the same golden anchors for CI + Studio |

Studio and `pytest` use the fixture campus by default. To run the CLI against
local Liberty CSVs (when present beside this README):

```bash
wattlab benchmark examples/liberty/campus.json
```

If the CSVs are missing you will get an actionable `FileNotFoundError` pointing
at the fixture. Never commit customer workbooks or raw Liberty CSVs.

## Import bills into a twin dump

Companion fuel workbooks (xlsx) are not an intake path. Export/normalize to CSV,
then:

```bash
wattlab seed import-bills \
  --electric path/to/electric.csv \
  --gas path/to/gas.csv \
  --gas-unit mcf \
  --window 2024-12:2025-11 \
  --electric-share 0.5 \
  --allocation area_weighted \
  --out /tmp/utility_bills.csv \
  --answers-fragment /tmp/bills_fragment.json
```

Shared-electric allocation is a **scenario**, not measured truth. Calibration
requires overlapping `YYYY-MM` periods with the dump/telemetry window — bill
years that do not overlap return `period_mismatch` instead of a false G14 pass.

## Headline numbers (fixture / published demo)

Latest common 12-month window Dec 2024 – Nov 2025 (1 kWh = 3,412 Btu,
1 Mcf ≈ 1.037 MMBtu): combined electric 2,928,898 kWh/yr; campus site EUI
71.6 kBtu/ft²-yr. Per-building EUI depends on allocation (50/50: 66.9 vs 76.3;
gas-share: 62.2 vs 81.0).
