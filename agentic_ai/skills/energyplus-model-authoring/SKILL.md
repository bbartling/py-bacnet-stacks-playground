---
name: energyplus-model-authoring
description: Build or modify a defensible EnergyPlus seed model from building evidence, including geometry, schedules, HVAC mapping, and controlled IDF changes.
---

# EnergyPlus model authoring

Use this to create a seed/baseline IDF or a controlled model variant.

1. Map real HVAC functionally first; select the nearest EnergyPlus representation and list unmatched behavior. Preserve fuel, ventilation delivery, capacities, and control topology where material to the question.
2. Start geometry simple. Split shells/zones only for material differences in exposure, use, schedule, or HVAC; reconcile area and exterior exposure.
3. Map observed occupied, recovery, setup, after-hours, holiday, and exception schedules. Do not annualize a single week without qualification.
4. Establish the baseline and hash the IDF, weather, inputs, and EnergyPlus version. Autosizing is not evidence of installed capacity.
5. Apply small named patches with pre/post values, units, source evidence, and an output diff. Validate the IDF and retain artifacts before simulation.

Use `energyplus-calibration` for measured-data tuning, `energyplus-weather` for EPW selection, and `energyplus-mcp` only when that integration is available.
