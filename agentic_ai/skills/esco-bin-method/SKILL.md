---
name: esco-bin-method
description: Build transparent weather-bin engineering estimates for HVAC control and retrofit screening, with documented operating assumptions and spreadsheet/test oracles.
---

# ESCO bin method

Use when a weather-bin calculation is the requested screening method, not as a replacement for an EnergyPlus calibration.

Define weather bins, operating calendar, baseline/proposed controls, equipment performance, ventilation, fan-law assumptions, and units. Keep heating, cooling, fan, and demand effects separate; use enthalpy rather than dry-bulb alone where economizer logic needs it. Validate equations against a reviewed spreadsheet or deterministic fixture and label results as engineering estimates.
