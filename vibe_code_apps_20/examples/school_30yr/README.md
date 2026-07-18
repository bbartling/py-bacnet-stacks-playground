# school_30yr — fictional Detroit K-12 school (synthetic rehearsal bills)

**Provenance: `synthetic_rehearsal`.** Every number in this folder is
fictional. The building (a 100,000 ft2, two-story K-12 school in Detroit, MI)
does not exist, and the twelve 2025 monthly bills were authored for this
repository to rehearse the WattLab 30-year deep-retrofit workflow
(`scripts/school_30yr_rehearsal.py`). Nothing here is measured data from any
real property, school district, or utility account, and no proprietary data
was copied or transformed to produce it.

The values are shaped to be *plausible*, not real:

- `electricity.csv` — 12 consecutive months (2025-01..2025-12) of kWh, billed
  demand (kW), and charges. ~899,000 kWh/yr (~9.0 kWh/ft2) with a mild summer
  usage dip (school out of session) but higher summer demand (cooling).
- `gas.csv` — 12 consecutive months of therms and charges. ~28,400 therms/yr
  with winter heating dominating (Jan ≈ 24x Jul) and a small summer DHW base.
- Implied site EUI ≈ 59 kBtu/ft2-yr, inside the EPA Portfolio Manager K-12
  screening band (31–65).

`campus.json` carries the `provenance` field the rehearsal script requires;
bills are validated through `wattlab.contracts.UtilityDataset` (exactly 12
consecutive months, one fuel per dataset, positive usage) before any weather
download or simulation happens.
