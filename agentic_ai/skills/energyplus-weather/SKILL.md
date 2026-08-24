---
name: energyplus-weather
description: Select, acquire, and document EnergyPlus weather files for calibration and scenario studies without silently mixing actual-year and typical weather.
---

# EnergyPlus weather

- For calibration, use actual-year weather aligned to the meter interval, timezone, and run period. Record source, station/location, coverage, transformations, and hash.
- Use TMY weather only for screening or design/scenario studies, clearly labeled as such.
- Do not silently replace one climate/station with another between baseline and candidate arms.
- When constructing an AMY EPW from a weather API, retain raw-response provenance, timezone conversion rules, missing-data treatment, and a validation report before use.

Weather quality and meter alignment are calibration inputs, not post-processing details.
